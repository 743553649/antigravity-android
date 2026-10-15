#!/usr/bin/env python3
"""
elf_header.py - Validates ELF header magic, 64-bit class, and Little-Endian format.
"""
import sys
import struct

def validate_elf_header(file_path: str) -> bool:
    with open(file_path, "rb") as f:
        header = f.read(16)
    
    if len(header) < 16:
        raise ValueError("File is smaller than 16 bytes (not an ELF)")
    
    # 0x00: Magic \x7fELF
    if header[:4] != b"\x7fELF":
        raise ValueError(f"Invalid ELF magic: {header[:4]}")
    
    # 0x04: EI_CLASS: 1 = 32-bit, 2 = 64-bit
    ei_class = header[4]
    if ei_class != 2:
        raise ValueError(f"Expected 64-bit ELF (class 2), got: {ei_class}")
    
    # 0x05: EI_DATA: 1 = 2's complement, little endian, 2 = big endian
    ei_data = header[5]
    if ei_data != 1:
        raise ValueError(f"Expected little-endian ELF (data 1), got: {ei_data}")
    
    return True

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: elf_header.py <binary_path>")
        sys.exit(1)
    
    try:
        if validate_elf_header(sys.argv[1]):
            print("[OK] Valid 64-bit Little-Endian ELF binary")
            sys.exit(0)
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
