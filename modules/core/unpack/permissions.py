#!/usr/bin/env python3
"""
permissions.py - Configures POSIX file permissions for binaries and libraries.
"""
import sys
import os
import stat

def make_executable(file_path: str) -> None:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Path does not exist: {file_path}")
    current = os.stat(file_path).st_mode
    os.chmod(file_path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

def make_readable(file_path: str) -> None:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Path does not exist: {file_path}")
    current = os.stat(file_path).st_mode
    os.chmod(file_path, current | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: permissions.py [--exec|--read] <path>")
        sys.exit(1)
    
    flag = "--exec"
    target = sys.argv[1]
    if len(sys.argv) >= 3:
        flag = sys.argv[1]
        target = sys.argv[2]
    
    try:
        if flag == "--exec":
            make_executable(target)
            print(f"[OK] Executable permissions set: {target}")
        else:
            make_readable(target)
            print(f"[OK] Readable permissions set: {target}")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed to set permissions: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
