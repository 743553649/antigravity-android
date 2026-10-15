#!/usr/bin/env python3
"""
align.py - 4-byte APK ZipAlign utility.
Uses system zipalign if available; otherwise falls back to pure Python 4-byte ZIP alignment.
"""
import sys
import os
import shutil
import struct
import subprocess
import zipfile


def align_with_binary(in_apk, out_apk, alignment=4):
    if shutil.which("zipalign"):
        res = subprocess.run(["zipalign", "-f", "-p", str(alignment), in_apk, out_apk], capture_output=True)
        return res.returncode == 0
    return False


def dostime(dt):
    year, month, day, hour, minute, second = dt
    dosdate = max(0, min(65535, ((year - 1980) << 9) | (month << 5) | day))
    dostime_val = max(0, min(65535, (hour << 11) | (minute << 5) | (second // 2)))
    return dostime_val, dosdate


def align_with_python(in_apk, out_apk, alignment=4):
    """
    Pure Python 4-byte zip alignment according to Android ZIP alignment specification.
    Uncompressed entries (method == 0) are padded so their data starts on a multiple of alignment.
    """
    with zipfile.ZipFile(in_apk, "r") as zin:
        entries = []
        for info in zin.infolist():
            data = zin.read(info.filename)
            entries.append((info, data))

    with open(out_apk, "wb") as fout:
        central_dirs = []

        for info, data in entries:
            # Android SO alignment: 4096 bytes for .so, 4 bytes for others
            entry_align = 4096 if (info.filename.endswith(".so") and info.compress_type == 0) else alignment
            
            local_header_offset = fout.tell()
            filename_bytes = info.filename.encode("utf-8")
            extra = bytearray(info.extra or b"")

            if info.compress_type == 0:
                # Calculate where data would start: offset + fixed_header(30) + filename_len + extra_len
                current_data_pos = local_header_offset + 30 + len(filename_bytes) + len(extra)
                rem = current_data_pos % entry_align
                if rem != 0:
                    pad_len = entry_align - rem
                    if pad_len < 4:
                        pad_len += entry_align
                    # Android 0xd9d5 alignment header
                    pad_data = b"\xd5\xd9" + struct.pack("<H", pad_len - 4) + (b"\x00" * (pad_len - 4))
                    extra.extend(pad_data)

            mtime, mdate = dostime(info.date_time)

            # Write Local File Header
            header = struct.pack(
                "<IHHHHHIIIHH",
                0x04034b50,                 # Local header signature
                info.extract_version,        # Version needed
                info.flag_bits,              # General purpose bit flag
                info.compress_type,          # Compression method
                mtime,                       # Mod time
                mdate,                       # Mod date
                info.CRC,                    # CRC-32
                info.compress_size,          # Compressed size
                info.file_size,              # Uncompressed size
                len(filename_bytes),         # Filename length
                len(extra)                   # Extra field length
            )
            fout.write(header)
            fout.write(filename_bytes)
            fout.write(extra)
            fout.write(data)

            # Record central directory entry info
            central_dirs.append((info, filename_bytes, bytes(extra), local_header_offset))

        # Central Directory
        cd_start = fout.tell()
        for info, filename_bytes, extra, local_header_offset in central_dirs:
            mtime, mdate = dostime(info.date_time)
            cd_header = struct.pack(
                "<IHHHHHHIIIHHHHHII",
                0x02014b50,                 # Central header signature
                info.create_version,         # Version made by
                info.extract_version,        # Version needed
                info.flag_bits,              # Flags
                info.compress_type,          # Compression
                mtime,
                mdate,
                info.CRC,
                info.compress_size,
                info.file_size,
                len(filename_bytes),
                len(extra),
                len(info.comment or b""),
                0,                           # Disk number start
                info.internal_attr,
                info.external_attr,
                local_header_offset          # Relative offset of local header
            )
            fout.write(cd_header)
            fout.write(filename_bytes)
            fout.write(extra)
            if info.comment:
                fout.write(info.comment)

        cd_size = fout.tell() - cd_start
        # End of Central Directory
        eocd = struct.pack(
            "<IHHHHIIH",
            0x06054b50,
            0,
            0,
            len(central_dirs),
            len(central_dirs),
            cd_size,
            cd_start,
            0
        )
        fout.write(eocd)
    return True


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <in_apk> <out_apk> [alignment]", file=sys.stderr)
        sys.exit(1)

    in_apk = sys.argv[1]
    out_apk = sys.argv[2]
    alignment = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    if not os.path.isfile(in_apk):
        print(f"Error: input file {in_apk} not found", file=sys.stderr)
        sys.exit(1)

    if align_with_binary(in_apk, out_apk, alignment):
        print(f"[OK] ZipAligned using binary: {out_apk}")
    else:
        align_with_python(in_apk, out_apk, alignment)
        print(f"[OK] ZipAligned using Python 4-byte aligner: {out_apk}")


if __name__ == "__main__":
    main()
