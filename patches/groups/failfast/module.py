"""ARMv8.0-A CPU capability fail-fast and preinit bypass patch.

Bypasses the preinit CPU feature check (0x71e8bc0) and preinit atomic flag
(0x724dd20) in language_server to allow startup on ARMv8.0-A processors
(Snapdragon 685, Cortex-A53/A73) lacking HWCAP_ATOMICS.
"""

import sys
from patch_lib import cli as _cli
from patch_lib import module_base as base
from patch_lib.report import hex_list
from groups.failfast import signatures as sig

GROUP_ID = "failfast"
GROUP = "failfast"
FILE = "failfast"
DESCRIPTION = "Bypass preinit CPU capability fail-fast check and preinit LSE atomic on ARMv8.0-A CPUs."
TAG = "patch_failfast"
EXPECTED_COUNTS = {"cpu_feature": 1, "preinit_atomic": 1}


def find_all(data, pattern):
    matches = []
    pos = 0
    while True:
        pos = data.find(pattern, pos)
        if pos == -1:
            break
        matches.append(pos)
        pos += len(pattern)
    return matches


def run(target_path, verify=False, dry_run=False, allow_missing=False, log=print):
    report = base.new_report(
        GROUP_ID, GROUP, FILE, DESCRIPTION,
        expected_counts=EXPECTED_COUNTS, offsets={})

    data = base.read_target(target_path, report)
    if data is None:
        return False, report

    raw_cpu = find_all(data, sig.TARGET_CPU)
    repl_cpu = find_all(data, sig.REPLACEMENT_CPU)
    raw_atomic = find_all(data, sig.TARGET_ATOMIC)
    repl_atomic = find_all(data, sig.REPLACEMENT_ATOMIC)

    report["observed_counts"] = {
        "cpu_feature": {"raw": len(raw_cpu), "replacement": len(repl_cpu)},
        "preinit_atomic": {"raw": len(raw_atomic), "replacement": len(repl_atomic)},
    }
    report["offsets"] = {
        "cpu_raw": hex_list(raw_cpu),
        "cpu_replacement": hex_list(repl_cpu),
        "atomic_raw": hex_list(raw_atomic),
        "atomic_replacement": hex_list(repl_atomic),
    }

    cpu_ok = (len(raw_cpu) == 0 and len(repl_cpu) == 1)
    atomic_ok = (len(raw_atomic) == 0 and len(repl_atomic) == 1)

    if verify:
        ok = cpu_ok and atomic_ok
        return base.run_verify(
            report, ok, TAG, log,
            detail=" (cpu: raw=%d repl=%d; atomic: raw=%d repl=%d)" % (
                len(raw_cpu), len(repl_cpu), len(raw_atomic), len(repl_atomic))), report

    if cpu_ok and atomic_ok:
        return base.run_already(
            report, TAG, log,
            detail=" (cpu repl=%d, atomic repl=%d)" % (len(repl_cpu), len(repl_atomic))), report

    if (len(raw_cpu) == 0 and len(repl_cpu) == 0) and (len(raw_atomic) == 0 and len(repl_atomic) == 0):
        if allow_missing:
            return base.run_missing(
                report, True, TAG, log, "no fail-fast signature found",
                state="skipped"), report

    # Fail closed on unexpected counts
    if len(raw_cpu) + len(repl_cpu) != 1:
        report["messages"].append("unexpected cpu feature count (raw=%d, repl=%d)" % (len(raw_cpu), len(repl_cpu)))
        log("[%s] ERROR: %s" % (TAG, report["messages"][-1]))
        return False, report

    if len(raw_atomic) + len(repl_atomic) != 1:
        report["messages"].append("unexpected preinit atomic count (raw=%d, repl=%d)" % (len(raw_atomic), len(repl_atomic)))
        log("[%s] ERROR: %s" % (TAG, report["messages"][-1]))
        return False, report

    changed = 0
    for pos in raw_cpu:
        data[pos:pos + len(sig.REPLACEMENT_CPU)] = sig.REPLACEMENT_CPU
        changed += 1

    for pos in raw_atomic:
        data[pos:pos + len(sig.REPLACEMENT_ATOMIC)] = sig.REPLACEMENT_ATOMIC
        changed += 1

    report["changed"] = changed
    report["state"] = "dry-run" if dry_run else "patched"
    if dry_run:
        log("[%s] dry-run: %d site(s) would be patched" % (TAG, changed))
        return True, report

    base.commit_write(target_path, data, log, TAG,
                      "patched %d occurrence(s)" % changed)
    return True, report


if __name__ == "__main__":
    sys.exit(_cli.main(run,
                       usage="Usage: python3 -m groups.failfast.module <binary> "
                             "[--verify|--dry-run|--allow-missing]"))
