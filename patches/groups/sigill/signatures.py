"""Constants and signatures for ARMv8.0-A SIGILL preservation patch.

Intercepts runtime.rt_sigaction in Go runtime so it ignores SIGILL (signal 4),
leaving the LD_PRELOAD liblse_compat.so SIGILL handler active.
"""

TARGET = bytes.fromhex("e00740f9e10b40f9e20f40f9e31340f9c81080d2010000d4e02b00b9c0035fd6")
REPLACEMENT = bytes.fromhex("e08740a9e28f41a91f1000f1c81080d240000054010000d4ff2b00b9c0035fd6")
EXPECTED = 2

assert len(TARGET) == 32
assert len(REPLACEMENT) == 32
