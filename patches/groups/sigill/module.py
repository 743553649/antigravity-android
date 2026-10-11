"""ARMv8.0-A SIGILL preservation patch.

Prevents Go runtime from registering its own SIGILL handler, ensuring that
the LD_PRELOAD liblse_compat.so handler remains active across the entire process lifetime.
"""

import sys
from patch_lib import cli as _cli
from patch_lib import module_base as base
from patch_lib.report import hex_list
from groups.sigill import signatures as sig

GROUP_ID = "sigill"
GROUP = "sigill"
FILE = "sigill"
DESCRIPTION = "Preserve LD_PRELOAD SIGILL handler by skipping Go rt_sigaction for SIGILL (4)."
TAG = "patch_sigill"
EXPECTED = sig.EXPECTED


def run(target_path, verify=False, dry_run=False, allow_missing=False, log=print):
    report = base.new_report(
        GROUP_ID, GROUP, FILE, DESCRIPTION,
        expected_counts={"raw": EXPECTED}, offsets={})

    data = base.read_target(target_path, report)
    if data is None:
        return False, report

    raw_matches = []
    repl_matches = []
    pos = 0
    while True:
        pos = data.find(sig.TARGET, pos)
        if pos == -1:
            break
        raw_matches.append(pos)
        pos += len(sig.TARGET)

    pos = 0
    while True:
        pos = data.find(sig.REPLACEMENT, pos)
        if pos == -1:
            break
        repl_matches.append(pos)
        pos += len(sig.REPLACEMENT)

    report["observed_counts"] = {
        "raw": len(raw_matches), "replacement": len(repl_matches)}
    report["offsets"] = {
        "raw": hex_list(raw_matches),
        "replacement": hex_list(repl_matches),
    }

    if verify:
        ok = len(raw_matches) == 0 and len(repl_matches) == EXPECTED
        return base.run_verify(
            report, ok, TAG, log,
            detail=" (raw=%d replacement=%d)" % (len(raw_matches), len(repl_matches))), report

    if len(raw_matches) == 0 and len(repl_matches) == EXPECTED:
        return base.run_already(
            report, TAG, log,
            detail=" (replacement=%d)" % len(repl_matches)), report

    if len(raw_matches) == 0 and len(repl_matches) == 0:
        if allow_missing:
            return base.run_missing(
                report, True, TAG, log, "no rt_sigaction signature",
                state="skipped"), report

    if len(raw_matches) != EXPECTED:
        report["messages"].append(
            "unexpected raw count %d (expected %d)" % (len(raw_matches), EXPECTED))
        log("[%s] ERROR: %s" % (TAG, report["messages"][-1]))
        return False, report

    for pos in raw_matches:
        data[pos:pos + len(sig.REPLACEMENT)] = sig.REPLACEMENT

    report["changed"] = len(raw_matches)
    report["state"] = "dry-run" if dry_run else "patched"
    if dry_run:
        log("[%s] dry-run: %d site(s) would be patched" % (TAG, len(raw_matches)))
        return True, report

    base.commit_write(target_path, data, log, TAG,
                      "patched %d occurrence(s)" % len(raw_matches))
    return True, report


if __name__ == "__main__":
    sys.exit(_cli.main(run,
                       usage="Usage: python3 -m groups.sigill.module <binary> "
                             "[--verify|--dry-run|--allow-missing]"))
