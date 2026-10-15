#!/usr/bin/env python3
"""
elf_arch.py - Validates that the ELF binary targets the ARM64 / AArch64 architecture.
"""
import sys
import struct

EM_AARCH64 = 183  # 0x00B7

def validate_aarch64(file_path: str) -> bool:
    with open(file_path, "rb") as f:
        # Read first 20 bytes to reach e_machine at offset 18
        data = f.read(20)
    
    if len(data) < 20:
        raise ValueError("File too short for ELF64 header")
    
    if data[:4] != b"\x7fELF":
        raise ValueError("Not an ELF binary")
    
    # e_machine is 2 bytes at offset 18 (0x12) in little-endian
    e_machine = struct.unpack("<H", data[18:20])[0]
    if e_machine != EM_AARCH64:
        raise ValueError(f"Architecture mismatch: expected AArch64 ({EM_AARCH64}), found {e_machine}")
    
    return True

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: elf_arch.py <binary_path>")
        sys.exit(1)
    
    try:
        if validate_aarch64(sys.argv[1]):
            print("[OK] Architecture is AArch64 (ARM64)")
            sys.exit(0)
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
