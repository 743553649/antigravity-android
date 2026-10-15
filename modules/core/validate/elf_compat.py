#!/usr/bin/env python3
"""
elf_compat.py - Validates ELF executable type (EXEC/DYN) for Android/Bionic execution.
"""
import sys
import struct

ET_EXEC = 2  # Executable file
ET_DYN = 3   # Shared object / Position-Independent Executable (PIE)

def validate_executable_type(file_path: str) -> str:
    with open(file_path, "rb") as f:
        data = f.read(18)
    
    if len(data) < 18 or data[:4] != b"\x7fELF":
        raise ValueError("Invalid ELF file")
    
    e_type = struct.unpack("<H", data[16:18])[0]
    if e_type == ET_EXEC:
        return "ET_EXEC"
    elif e_type == ET_DYN:
        return "ET_DYN"
    else:
        raise ValueError(f"Unexpected ELF type: {e_type} (expected ET_EXEC or ET_DYN)")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: elf_compat.py <binary_path>")
        sys.exit(1)
    
    try:
        t = validate_executable_type(sys.argv[1])
        print(f"[OK] Binary type: {t}")
        sys.exit(0)
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
