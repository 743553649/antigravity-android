#define _GNU_SOURCE
#include <signal.h>
#include <ucontext.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <sys/auxv.h>
#include <dlfcn.h>

#ifndef HWCAP_ATOMICS
#define HWCAP_ATOMICS (1 << 8)
#endif

/* Linux kernel sigaction structure for AArch64 rt_sigaction syscall (134) */
struct kernel_sigaction {
    void (*k_handler)(int, siginfo_t *, void *);
    unsigned long sa_flags;
    void (*sa_restorer)(void);
    unsigned long sa_mask;
};

#ifndef FPSIMD_MAGIC
#define FPSIMD_MAGIC 0x46508001
#endif

struct _aarch64_ctx_local {
    uint32_t magic;
    uint32_t size;
};

struct fpsimd_ctx_local {
    struct _aarch64_ctx_local head;
    uint32_t fpsr;
    uint32_t fpcr;
    __uint128_t vregs[32];
};

static struct fpsimd_ctx_local *get_fpsimd_ctx(ucontext_t *uc) {
    uint8_t *p = (uint8_t *)uc->uc_mcontext.__reserved;
    while (p < (uint8_t *)uc->uc_mcontext.__reserved + sizeof(uc->uc_mcontext.__reserved) - sizeof(struct _aarch64_ctx_local)) {
        struct _aarch64_ctx_local *ctx = (struct _aarch64_ctx_local *)p;
        if (ctx->magic == FPSIMD_MAGIC) {
            return (struct fpsimd_ctx_local *)p;
        }
        if (ctx->size == 0) break;
        p += ctx->size;
    }
    return NULL;
}

static struct sigaction old_sigill_act;
static bool lse_handler_installed = false;

static void log_raw(const char *s) {
    const char *p = s;
    while (*p) p++;
    write(2, s, (size_t)(p - s));
}

static void log_hex(uint64_t val) {
    char buf[19];
    buf[0] = '0';
    buf[1] = 'x';
    for (int i = 15; i >= 0; i--) {
        int nib = (int)((val >> (i * 4)) & 0xF);
        buf[2 + (15 - i)] = (char)((nib < 10) ? ('0' + nib) : ('a' + nib - 10));
    }
    buf[18] = '\0';
    write(2, buf, 18);
}

static int raw_rt_sigaction(int sig, const struct kernel_sigaction *act, struct kernel_sigaction *oact) {
    register long x0 __asm__("x0") = sig;
    register long x1 __asm__("x1") = (long)act;
    register long x2 __asm__("x2") = (long)oact;
    register long x3 __asm__("x3") = 8; /* sizeof(kernel_sigset_t) on arm64 */
    register long x8 __asm__("x8") = 134; /* __NR_rt_sigaction */
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3), "r"(x8) : "memory");
    return (int)x0;
}

static inline uint64_t get_reg(const ucontext_t *uc, unsigned reg, bool is_sp) {
    if (reg == 31) {
        return is_sp ? uc->uc_mcontext.sp : 0ULL;
    }
    return uc->uc_mcontext.regs[reg];
}

static inline void set_reg(ucontext_t *uc, unsigned reg, uint64_t val, unsigned sz) {
    if (reg == 31) {
        return; // Writes to WZR/XZR are discarded
    }
    if (sz == 0) {
        uc->uc_mcontext.regs[reg] = (uint64_t)(uint8_t)val;
    } else if (sz == 1) {
        uc->uc_mcontext.regs[reg] = (uint64_t)(uint16_t)val;
    } else if (sz == 2) {
        uc->uc_mcontext.regs[reg] = (uint64_t)(uint32_t)val;
    } else {
        uc->uc_mcontext.regs[reg] = val;
    }
}

#define EMULATE_OP(ptr_type, s_type, ptr, s_val, opc, old_out) do { \
    ptr_type *p = (ptr_type *)(ptr); \
    ptr_type s = (ptr_type)(s_val); \
    ptr_type old; \
    switch (opc) { \
        case 0: /* LDADD / STADD */ \
            old = __atomic_fetch_add(p, s, __ATOMIC_SEQ_CST); \
            break; \
        case 1: /* LDCLR / STCLR */ \
            old = __atomic_fetch_and(p, ~s, __ATOMIC_SEQ_CST); \
            break; \
        case 2: /* LDEOR / STEOR */ \
            old = __atomic_fetch_xor(p, s, __ATOMIC_SEQ_CST); \
            break; \
        case 3: /* LDSET / STSET */ \
            old = __atomic_fetch_or(p, s, __ATOMIC_SEQ_CST); \
            break; \
        case 4: { /* LDSMAX / STSMAX (signed) */ \
            ptr_type cur = __atomic_load_n(p, __ATOMIC_SEQ_CST); \
            while (1) { \
                ptr_type des = ((s_type)cur > (s_type)s) ? cur : s; \
                if (__atomic_compare_exchange_n(p, &cur, des, true, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST)) { \
                    old = cur; \
                    break; \
                } \
            } \
            break; \
        } \
        case 5: { /* LDSMIN / STSMIN (signed) */ \
            ptr_type cur = __atomic_load_n(p, __ATOMIC_SEQ_CST); \
            while (1) { \
                ptr_type des = ((s_type)cur < (s_type)s) ? cur : s; \
                if (__atomic_compare_exchange_n(p, &cur, des, true, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST)) { \
                    old = cur; \
                    break; \
                } \
            } \
            break; \
        } \
        case 6: { /* LDUMAX / STUMAX (unsigned) */ \
            ptr_type cur = __atomic_load_n(p, __ATOMIC_SEQ_CST); \
            while (1) { \
                ptr_type des = (cur > s) ? cur : s; \
                if (__atomic_compare_exchange_n(p, &cur, des, true, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST)) { \
                    old = cur; \
                    break; \
                } \
            } \
            break; \
        } \
        case 7: { /* LDUMIN / STUMIN (unsigned) */ \
            ptr_type cur = __atomic_load_n(p, __ATOMIC_SEQ_CST); \
            while (1) { \
                ptr_type des = (cur < s) ? cur : s; \
                if (__atomic_compare_exchange_n(p, &cur, des, true, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST)) { \
                    old = cur; \
                    break; \
                } \
            } \
            break; \
        } \
        case 8: /* SWP */ \
            old = __atomic_exchange_n(p, s, __ATOMIC_SEQ_CST); \
            break; \
        default: \
            return false; \
    } \
    *(old_out) = (uint64_t)old; \
} while (0)

#define EMULATE_CAS(ptr_type, ptr, compare_val, new_val, old_out) do { \
    ptr_type *p = (ptr_type *)(ptr); \
    ptr_type expected = (ptr_type)(compare_val); \
    ptr_type desired = (ptr_type)(new_val); \
    __atomic_compare_exchange_n(p, &expected, desired, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST); \
    *(old_out) = (uint64_t)expected; \
} while (0)

static bool emulate_lse(ucontext_t *uc, uint32_t insn) {
    unsigned sz = (insn >> 30) & 3;

    // Pattern 0: Load-Acquire RCpc (LDAPR, LDAPRB, LDAPRH) [ARMv8.3-A / FEAT_LRCPC]
    // Mask: 0x3FFFFC00 == 0x38BFC000 (e.g. ldaprb w8, [x8] -> 0x38bfc108)
    if ((insn & 0x3FFFFC00) == 0x38BFC000) {
        unsigned rn = (insn >> 5) & 0x1F;
        unsigned rt = insn & 0x1F;
        uintptr_t addr = (uintptr_t)get_reg(uc, rn, true);
        uint64_t val = 0;

        switch (sz) {
            case 0: val = *(const volatile uint8_t *)addr; break;
            case 1: val = *(const volatile uint16_t *)addr; break;
            case 2: val = *(const volatile uint32_t *)addr; break;
            case 3: val = *(const volatile uint64_t *)addr; break;
        }

        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if (rt != 31) {
            set_reg(uc, rt, val, sz);
        }
        return true;
    }

    // Pattern 1: Atomic memory operations (LDADD, LDCLR, LDEOR, LDSET, SWP, LDSMAX, LDSMIN, LDUMAX, LDUMIN)
    // Bits 29..24 = 111000 (0x38), Bit 21 = 1, Bits 11..10 = 00
    if (((insn >> 24) & 0x3F) == 0x38 && ((insn >> 21) & 1) == 1 && ((insn >> 10) & 3) == 0) {
        unsigned rs = (insn >> 16) & 0x1F;
        unsigned rn = (insn >> 5) & 0x1F;
        unsigned rt = insn & 0x1F;
        unsigned op_bits = (insn >> 12) & 0xF;

        uintptr_t addr = (uintptr_t)get_reg(uc, rn, true);
        uint64_t s_val = get_reg(uc, rs, false);
        uint64_t old_val = 0;

        switch (sz) {
            case 0:
                EMULATE_OP(uint8_t, int8_t, addr, s_val, op_bits, &old_val);
                break;
            case 1:
                EMULATE_OP(uint16_t, int16_t, addr, s_val, op_bits, &old_val);
                break;
            case 2:
                EMULATE_OP(uint32_t, int32_t, addr, s_val, op_bits, &old_val);
                break;
            case 3:
                EMULATE_OP(uint64_t, int64_t, addr, s_val, op_bits, &old_val);
                break;
            default:
                return false;
        }

        if (rt != 31) {
            set_reg(uc, rt, old_val, sz);
        }
        return true;
    }

    // Pattern 2: Compare and Swap (CAS, CASA, CASL, CASAL)
    // Bits 29..24 = 001000 (0x08), Bit 23 = 1, Bit 21 = 1, Bits 14..10 = 11111 (0x1F)
    if (((insn >> 24) & 0x3F) == 0x08 && ((insn >> 23) & 1) == 1 && ((insn >> 21) & 1) == 1 && ((insn >> 10) & 0x1F) == 0x1F) {
        unsigned rs = (insn >> 16) & 0x1F; // compare value & destination for old value
        unsigned rn = (insn >> 5) & 0x1F;  // memory address
        unsigned rt = insn & 0x1F;         // new value to store

        uintptr_t addr = (uintptr_t)get_reg(uc, rn, true);
        uint64_t compare_val = get_reg(uc, rs, false);
        uint64_t new_val = get_reg(uc, rt, false);
        uint64_t old_val = 0;

        switch (sz) {
            case 0:
                EMULATE_CAS(uint8_t, addr, compare_val, new_val, &old_val);
                break;
            case 1:
                EMULATE_CAS(uint16_t, addr, compare_val, new_val, &old_val);
                break;
            case 2:
                EMULATE_CAS(uint32_t, addr, compare_val, new_val, &old_val);
                break;
            case 3:
                EMULATE_CAS(uint64_t, addr, compare_val, new_val, &old_val);
                break;
            default:
                return false;
        }

        if (rs != 31) {
            set_reg(uc, rs, old_val, sz);
        }
        return true;
    }

    // Pattern 3: Compare and Swap Pair (CASP, CASPA, CASPL, CASPAL)
    // Bits 29..24 = 001000 (0x08), Bit 23 = 0, Bit 21 = 1, Bits 14..10 = 11111 (0x1F)
    if (((insn >> 24) & 0x3F) == 0x08 && ((insn >> 23) & 1) == 0 && ((insn >> 21) & 1) == 1 && ((insn >> 10) & 0x1F) == 0x1F) {
        unsigned rs = ((insn >> 16) & 0x1F) & ~1U; // even register
        unsigned rn = (insn >> 5) & 0x1F;
        unsigned rt = (insn & 0x1F) & ~1U;         // even register

        uintptr_t addr = (uintptr_t)get_reg(uc, rn, true);
        unsigned bit30 = (insn >> 30) & 1;

        if (bit30 == 0) {
            uint64_t compare_val = (get_reg(uc, rs + 1, false) << 32) | (get_reg(uc, rs, false) & 0xFFFFFFFFULL);
            uint64_t new_val = (get_reg(uc, rt + 1, false) << 32) | (get_reg(uc, rt, false) & 0xFFFFFFFFULL);
            uint64_t old_val = 0;
            EMULATE_CAS(uint64_t, addr, compare_val, new_val, &old_val);
            set_reg(uc, rs, old_val & 0xFFFFFFFFULL, 2);
            set_reg(uc, rs + 1, (old_val >> 32) & 0xFFFFFFFFULL, 2);
            return true;
        } else {
            unsigned __int128 *p = (unsigned __int128 *)addr;
            unsigned __int128 compare_val = (((unsigned __int128)get_reg(uc, rs + 1, false)) << 64) | get_reg(uc, rs, false);
            unsigned __int128 new_val = (((unsigned __int128)get_reg(uc, rt + 1, false)) << 64) | get_reg(uc, rt, false);
            __atomic_compare_exchange_n(p, &compare_val, new_val, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
            set_reg(uc, rs, (uint64_t)compare_val, 3);
            set_reg(uc, rs + 1, (uint64_t)(compare_val >> 64), 3);
            return true;
        }
    }

    // Pattern 4: RCpc2 unscaled loads and stores (LDAPUR, LDAPURB, LDAPURH, LDAPURSB, LDAPURSH, LDAPURSW, STLUR, STLURB, STLURH) [ARMv8.4-A / FEAT_LRCPC2]
    // Bits 29..24 = 011001 (0x19), Bit 21 = 0, Bits 11..10 = 00
    if (((insn >> 24) & 0x3F) == 0x19 && ((insn >> 21) & 1) == 0 && ((insn >> 10) & 3) == 0) {
        unsigned opc = (insn >> 22) & 3;
        int32_t simm9 = (int32_t)((insn >> 12) & 0x1FF);
        if (simm9 & 0x100) {
            simm9 |= ~0x1FF; // sign-extend 9-bit immediate
        }
        unsigned rn = (insn >> 5) & 0x1F;
        unsigned rt = insn & 0x1F;
        uintptr_t addr = (uintptr_t)(get_reg(uc, rn, true) + (int64_t)simm9);

        if (opc == 0) {
            // STLUR (Store-Release)
            uint64_t s_val = get_reg(uc, rt, false);
            __atomic_thread_fence(__ATOMIC_RELEASE);
            switch (sz) {
                case 0: *(volatile uint8_t *)addr = (uint8_t)s_val; break;
                case 1: *(volatile uint16_t *)addr = (uint16_t)s_val; break;
                case 2: *(volatile uint32_t *)addr = (uint32_t)s_val; break;
                case 3: *(volatile uint64_t *)addr = (uint64_t)s_val; break;
            }
            return true;
        } else if (opc == 1) {
            // LDAPUR (Load-Acquire unsigned)
            uint64_t val = 0;
            switch (sz) {
                case 0: val = *(const volatile uint8_t *)addr; break;
                case 1: val = *(const volatile uint16_t *)addr; break;
                case 2: val = *(const volatile uint32_t *)addr; break;
                case 3: val = *(const volatile uint64_t *)addr; break;
            }
            __atomic_thread_fence(__ATOMIC_ACQUIRE);
            if (rt != 31) {
                set_reg(uc, rt, val, sz);
            }
            return true;
        } else if (opc == 2) {
            // LDAPURSB / LDAPURSH / LDAPURSW (signed 64-bit into Xt)
            uint64_t val = 0;
            switch (sz) {
                case 0: val = (uint64_t)(int64_t)(*(const volatile int8_t *)addr); break;
                case 1: val = (uint64_t)(int64_t)(*(const volatile int16_t *)addr); break;
                case 2: val = (uint64_t)(int64_t)(*(const volatile int32_t *)addr); break;
                default: return false;
            }
            __atomic_thread_fence(__ATOMIC_ACQUIRE);
            if (rt != 31) {
                set_reg(uc, rt, val, 3);
            }
            return true;
        } else if (opc == 3) {
            // LDAPURSB / LDAPURSH (signed 32-bit into Wt)
            uint64_t val = 0;
            switch (sz) {
                case 0: val = (uint64_t)(uint32_t)(int32_t)(*(const volatile int8_t *)addr); break;
                case 1: val = (uint64_t)(uint32_t)(int32_t)(*(const volatile int16_t *)addr); break;
                default: return false;
            }
            __atomic_thread_fence(__ATOMIC_ACQUIRE);
            if (rt != 31) {
                set_reg(uc, rt, val, 2);
            }
            return true;
        }
    }

    return false;
}

static bool emulate_dotprod(ucontext_t *uc, uint32_t insn) {
    bool is_vec = ((insn & 0x9fe0fc00) == 0x0e809400);
    bool is_elem = ((insn & 0x9fc0f400) == 0x0f80e000);
    if (!is_vec && !is_elem) {
        return false;
    }

    struct fpsimd_ctx_local *fpsimd = get_fpsimd_ctx(uc);
    if (!fpsimd) {
        return false;
    }

    unsigned q = (insn >> 30) & 1;
    unsigned u = (insn >> 29) & 1;
    unsigned rm = (insn >> 16) & 0x1F;
    unsigned rn = (insn >> 5) & 0x1F;
    unsigned rd = insn & 0x1F;

    uint8_t vd_copy[16];
    uint8_t vn_copy[16];
    uint8_t vm_copy[16];
    memcpy(vd_copy, (const void *)&fpsimd->vregs[rd], 16);
    memcpy(vn_copy, (const void *)&fpsimd->vregs[rn], 16);
    memcpy(vm_copy, (const void *)&fpsimd->vregs[rm], 16);

    uint32_t *vd32 = (uint32_t *)vd_copy;
    int num_lanes = q ? 4 : 2;

    if (is_vec) {
        for (int i = 0; i < num_lanes; i++) {
            if (u) {
                uint32_t sum = 0;
                for (int k = 0; k < 4; k++) {
                    sum += (uint32_t)vn_copy[4 * i + k] * (uint32_t)vm_copy[4 * i + k];
                }
                vd32[i] += sum;
            } else {
                int32_t sum = 0;
                const int8_t *vn_s = (const int8_t *)vn_copy;
                const int8_t *vm_s = (const int8_t *)vm_copy;
                for (int k = 0; k < 4; k++) {
                    sum += (int32_t)vn_s[4 * i + k] * (int32_t)vm_s[4 * i + k];
                }
                ((int32_t *)vd32)[i] += sum;
            }
        }
    } else {
        unsigned h = (insn >> 11) & 1;
        unsigned l = (insn >> 21) & 1;
        unsigned index = (h << 1) | l;
        int m_offset = (int)(index * 4);

        for (int i = 0; i < num_lanes; i++) {
            if (u) {
                uint32_t sum = 0;
                for (int k = 0; k < 4; k++) {
                    sum += (uint32_t)vn_copy[4 * i + k] * (uint32_t)vm_copy[m_offset + k];
                }
                vd32[i] += sum;
            } else {
                int32_t sum = 0;
                const int8_t *vn_s = (const int8_t *)vn_copy;
                const int8_t *vm_s = (const int8_t *)vm_copy;
                for (int k = 0; k < 4; k++) {
                    sum += (int32_t)vn_s[4 * i + k] * (int32_t)vm_s[m_offset + k];
                }
                ((int32_t *)vd32)[i] += sum;
            }
        }
    }

    if (!q) {
        memset(vd_copy + 8, 0, 8);
    }
    memcpy((void *)&fpsimd->vregs[rd], vd_copy, 16);

    return true;
}

static void sigill_handler(int sig, siginfo_t *info, void *ucontext) {
    ucontext_t *uc = (ucontext_t *)ucontext;
    uintptr_t pc = uc->uc_mcontext.pc;
    uint32_t insn = *(uint32_t *)pc;

    if (emulate_lse(uc, insn) || emulate_dotprod(uc, insn)) {
        uc->uc_mcontext.pc += 4;
        return;
    }

    log_raw("[lse_compat] FATAL: unhandled SIGILL at PC=");
    log_hex((uint64_t)pc);
    log_raw(" INSN=");
    log_hex((uint64_t)insn);
    log_raw("\n");

    // Pass-through to original handler if not an LSE instruction
    if (old_sigill_act.sa_flags & SA_SIGINFO) {
        if (old_sigill_act.sa_sigaction) {
            old_sigill_act.sa_sigaction(sig, info, ucontext);
            return;
        }
    } else if (old_sigill_act.sa_handler) {
        if (old_sigill_act.sa_handler == SIG_DFL || old_sigill_act.sa_handler == SIG_IGN) {
            signal(SIGILL, old_sigill_act.sa_handler);
            raise(SIGILL);
            return;
        }
        old_sigill_act.sa_handler(sig);
        return;
    }

    signal(SIGILL, SIG_DFL);
    raise(SIGILL);
}

int sigaction(int signum, const struct sigaction *act, struct sigaction *oldact) {
    if (signum == SIGILL) {
        if (oldact) {
            *oldact = old_sigill_act;
        }
        if (act) {
            old_sigill_act = *act;
        }
        return 0; // Keep kernel handler point to sigill_handler
    }

    typedef int (*sigaction_fn)(int, const struct sigaction *, struct sigaction *);
    static sigaction_fn real_sigaction = NULL;
    if (!real_sigaction) {
        real_sigaction = (sigaction_fn)dlsym(RTLD_NEXT, "sigaction");
    }
    if (real_sigaction) {
        return real_sigaction(signum, act, oldact);
    }
    return 0;
}

__attribute__((constructor(101))) static void init_lse_compat(void) {
    log_raw("[lse_compat] INIT: installing kernel SIGILL handler\n");
    lse_handler_installed = true;

    struct kernel_sigaction ksa;
    memset(&ksa, 0, sizeof(ksa));
    ksa.k_handler = sigill_handler;
    ksa.sa_flags = SA_SIGINFO | SA_NODEFER;
    ksa.sa_restorer = NULL;
    ksa.sa_mask = 0;

    struct kernel_sigaction old_ksa;
    memset(&old_ksa, 0, sizeof(old_ksa));

    int ret = raw_rt_sigaction(SIGILL, &ksa, &old_ksa);
    if (ret != 0) {
        log_raw("[lse_compat] ERROR: raw_rt_sigaction failed with code: ");
        log_hex((uint64_t)(int64_t)ret);
        log_raw("\n");
    } else {
        log_raw("[lse_compat] SUCCESS: SIGILL handler active in Linux kernel\n");
    }
}
