#!/usr/bin/env python3
"""Build and optimize bootstrap.tar.gz from bootstrap-aarch64.zip.

Unpacks bootstrap-aarch64.zip, strips non-essential documentation/man pages,
updates SYMLINKS.txt, applies symlinks and packs a clean bootstrap.tar.gz.
"""

import argparse
import io
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile

TRIM_PREFIXES = (
    "share/man/",
    "share/doc/",
    "share/info/",
    "libexec/installed-tests/",
)


def read_ar_members(deb_path):
    members = {}
    with open(deb_path, "rb") as f:
        magic = f.read(8)
        if magic != b"!<arch>\n":
            raise ValueError(f"Not a valid deb (ar) archive: {deb_path}")
        while True:
            hdr = f.read(60)
            if len(hdr) < 60:
                break
            name = hdr[:16].decode("ascii").strip().rstrip("/")
            size = int(hdr[48:58].decode("ascii").strip())
            data = f.read(size)
            if size % 2 == 1:
                f.read(1)
            members[name] = data
    return members


def extract_deb_into_bootstrap(deb_path, dest, trim, new_sl_lines):
    if not os.path.isfile(deb_path):
        raise FileNotFoundError(f"Extra deb file not found: {deb_path}")

    print(f"[pack_bootstrap] Ingesting extra package: {deb_path}")
    members = read_ar_members(deb_path)
    control_key = next((k for k in members if k.startswith("control.tar")), None)
    if not control_key:
        raise ValueError(f"control.tar missing in {deb_path}")

    ctrl_fields = {}
    with tarfile.open(fileobj=io.BytesIO(members[control_key]), mode="r:*") as tar:
        cf = tar.extractfile("./control" if "./control" in tar.getnames() else "control")
        for line in cf.read().decode("utf-8", errors="replace").splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                ctrl_fields[k.strip()] = v.strip()

    pkg_name = ctrl_fields.get("Package")
    version = ctrl_fields.get("Version")
    arch = ctrl_fields.get("Architecture", "aarch64")
    if not pkg_name or not version:
        raise ValueError(f"Invalid control fields in {deb_path}: {ctrl_fields}")

    data_key = next((k for k in members if k.startswith("data.tar")), None)
    if not data_key:
        raise ValueError(f"data.tar missing in {deb_path}")

    installed_files = []
    added_files = 0
    added_links = 0
    pruned_files = 0

    with tarfile.open(fileobj=io.BytesIO(members[data_key]), mode="r:*") as tar:
        for m in tar.getmembers():
            parts = m.name.lstrip("./").split("/")
            if "usr" not in parts:
                continue
            idx = parts.index("usr")
            rel_name = "/".join(parts[idx + 1:])
            if not rel_name:
                continue

            if trim and rel_name.startswith(TRIM_PREFIXES):
                pruned_files += 1
                continue

            target_path = os.path.normpath(os.path.join(dest, rel_name))
            if not target_path.startswith(dest + os.sep):
                continue

            if m.isdir():
                os.makedirs(target_path, exist_ok=True)
            elif m.issym():
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                if os.path.lexists(target_path):
                    os.unlink(target_path)
                os.symlink(m.linkname, target_path)
                new_sl_lines.append(f"{m.linkname}←./{rel_name}")
                installed_files.append(rel_name)
                added_links += 1
            elif m.isfile():
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with tar.extractfile(m) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                mode = m.mode & 0o7777
                if mode:
                    os.chmod(target_path, mode)
                installed_files.append(rel_name)
                added_files += 1

    # Update var/lib/dpkg/status
    dpkg_status = os.path.join(dest, "var", "lib", "dpkg", "status")
    os.makedirs(os.path.dirname(dpkg_status), exist_ok=True)
    status_content = ""
    if os.path.isfile(dpkg_status):
        with open(dpkg_status, "r", encoding="utf-8", errors="replace") as f:
            status_content = f.read()

    if f"Package: {pkg_name}\n" not in status_content:
        stanza = (
            f"Package: {pkg_name}\n"
            f"Status: install ok installed\n"
            f"Priority: optional\n"
            f"Section: {ctrl_fields.get('Section', 'vcs')}\n"
            f"Installed-Size: {ctrl_fields.get('Installed-Size', '0')}\n"
            f"Maintainer: {ctrl_fields.get('Maintainer', 'Antigravity')}\n"
            f"Architecture: {arch}\n"
            f"Version: {version}\n"
            f"Depends: {ctrl_fields.get('Depends', '')}\n"
            f"Description: {ctrl_fields.get('Description', pkg_name)}\n\n"
        )
        with open(dpkg_status, "a", encoding="utf-8") as f:
            f.write(stanza)

    # Update var/lib/pkg/installed
    pkg_installed_dir = os.path.join(dest, "var", "lib", "pkg", "installed")
    os.makedirs(pkg_installed_dir, exist_ok=True)
    meta_path = os.path.join(pkg_installed_dir, f"{pkg_name}.meta")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"name={pkg_name}\nversion={version}\narch={arch}\n")

    files_path = os.path.join(pkg_installed_dir, f"{pkg_name}.files")
    with open(files_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(installed_files)) + "\n")

    print(f"[pack_bootstrap] Ingested {pkg_name} {version}: {added_files} files, {added_links} symlinks (pruned {pruned_files} doc files)")


def pack_bootstrap(zip_path, out_tar_gz, trim=True, extra_debs=None):
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Input zip not found: {zip_path}")

    tmp = tempfile.mkdtemp(prefix="bootstrap_build_")
    try:
        dest = os.path.abspath(tmp)
        total_files = 0
        pruned_files = 0
        pruned_bytes = 0

        with zipfile.ZipFile(zip_path, "r") as z:
            sl_raw = z.read("SYMLINKS.txt").decode("utf-8", errors="replace")

            for info in z.infolist():
                name = info.filename.lstrip("./")
                if not name or name.endswith("/"):
                    continue
                if name == "SYMLINKS.txt":
                    continue

                total_files += 1
                if trim and name.startswith(TRIM_PREFIXES):
                    pruned_files += 1
                    pruned_bytes += info.file_size
                    continue

                target_file = os.path.normpath(os.path.join(dest, name))
                if not target_file.startswith(dest + os.sep):
                    continue

                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                with z.open(info) as src, open(target_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                mode = (info.external_attr >> 16) & 0o7777
                if mode:
                    os.chmod(target_file, mode)

        # Process symlinks
        new_sl_lines = []
        total_links = 0
        pruned_links = 0

        for line in sl_raw.splitlines():
            if "←" not in line:
                continue
            target, link_name = line.split("←", 1)
            rel_name = link_name.lstrip("./")
            total_links += 1

            if trim and rel_name.startswith(TRIM_PREFIXES):
                pruned_links += 1
                continue

            link_path = os.path.normpath(os.path.join(dest, rel_name))
            if not link_path.startswith(dest + os.sep):
                continue

            os.makedirs(os.path.dirname(link_path), exist_ok=True)
            if os.path.lexists(link_path):
                os.unlink(link_path)
            os.symlink(target, link_path)
            new_sl_lines.append(f"{target}←{link_name}")

        # Ingest extra deb packages if provided
        if extra_debs:
            for deb in extra_debs:
                extract_deb_into_bootstrap(deb, dest, trim, new_sl_lines)

        # Write clean SYMLINKS.txt
        sl_out_path = os.path.join(dest, "SYMLINKS.txt")
        with open(sl_out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_sl_lines) + "\n")

        print(f"[pack_bootstrap] Extracted: {total_files - pruned_files} base files "
              f"(pruned {pruned_files} doc/man files, ~{pruned_bytes / (1024 * 1024):.2f} MB)")
        print(f"[pack_bootstrap] Symlinks: {len(new_sl_lines)} total preserved")

        # Create tar.gz archive
        os.makedirs(os.path.dirname(os.path.abspath(out_tar_gz)), exist_ok=True)
        tmp_tar = out_tar_gz + ".tmp"
        if os.path.exists(tmp_tar):
            os.unlink(tmp_tar)

        with tarfile.open(tmp_tar, "w:gz", compresslevel=9) as tar:
            tar.add(dest, arcname=".")

        os.replace(tmp_tar, out_tar_gz)
        out_size_mb = os.path.getsize(out_tar_gz) / (1024 * 1024)
        print(f"[pack_bootstrap] Successfully wrote: {out_tar_gz} ({out_size_mb:.2f} MB)")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Pack & trim bootstrap archive")
    parser.add_argument("--zip", required=True, help="Path to bootstrap-aarch64.zip")
    parser.add_argument("--out", required=True, help="Path to output bootstrap.tar.gz")
    parser.add_argument("--no-trim", action="store_true", help="Do not prune doc/man files")
    parser.add_argument("--extra-deb", action="append", default=[], help="Extra deb packages to bundle into bootstrap")
    args = parser.parse_args()

    pack_bootstrap(args.zip, args.out, trim=not args.no_trim, extra_debs=args.extra_deb)


if __name__ == "__main__":
    main()
