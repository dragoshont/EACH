"""One bounded development repair, not a release qualification or holdout.

Run on the measured Mac only: ``uv run python -m each.production_development``.
Target code executes solely through the existing colima-each executor.
Only sanitized hashes/counts/status cross this command's output boundary.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import platform
import shutil
import signal
import time

from each.attestation import verify_materials_root, verify_receipt
from each.benchmark import BenchmarkTask, run_benchmark_task
from each.executor.python_observer import PythonCase
from each.hashing import sha256_file
from each.models.base import ContextBudgetExceeded
from each.models.catalog import load_model
from each.paths import each_home
from each.signing import public_key_path

# Behavioral origin: public historical commit title "Show more than bytes for
# negative file sizes", plus the public naturalsize API/documented SI/IEC/GNU
# formatting contract. No historical implementation or fix tests supplied.
# This entire project/fix cluster is development-only, excluded from holdouts.
TASK = BenchmarkTask(
    task_id="production-dev-humanize-negative-size",
    repo="python-humanize/humanize",
    license="MIT",
    pre_fix_sha="aaca29f35306c48c9965047ac5d39807a33652a7",
    fix_sha="db9678288054dba85f5ce8959c20cc2436f7a1fa",
    bug_path="src/humanize/filesize.py",
    source_paths=("LICENCE",),
    test_paths=(),
    test_command=("trusted-host-json-v1",),
    problem_statement=(
        "Public naturalsize(value, binary=False, gnu=False, format='%.1f') "
        "must render negative file sizes using the same size-unit conventions "
        "as positive magnitudes, preserving the negative sign. SI units use "
        "1000; binary IEC and GNU units use 1024. Preserve zero, one-byte and "
        "positive-size formatting and custom decimal format behavior."
    ),
    observation_cases=(
        PythonCase("negative-si", "naturalsize", (-3000,), "-3.0 kB"),
        PythonCase("negative-iec", "naturalsize", (-3000, True), "-2.9 KiB"),
        PythonCase("negative-gnu", "naturalsize", (-3000, False, True), "-2.9K"),
        PythonCase("positive-si", "naturalsize", (3000,), "3.0 kB"),
        PythonCase("positive-iec", "naturalsize", (3000, True), "2.9 KiB"),
        PythonCase("positive-gnu", "naturalsize", (3000, False, True), "2.9K"),
        PythonCase("zero", "naturalsize", (0,), "0 Bytes"),
        PythonCase("one-byte", "naturalsize", (1,), "1 Byte"),
        PythonCase("negative-one-byte", "naturalsize", (-1,), "-1 Byte"),
        PythonCase("custom-format", "naturalsize", (-3000, False, False, "%.2f"), "-3.00 kB"),
        PythonCase("bad-input", "naturalsize", ("not-a-number",), error="ValueError"),
    ),
    expected_tests=11,
    proposal_format="full_source",
)

ONE_BYTE_TASK = dataclasses.replace(
    TASK, task_id="production-dev-humanize-one-byte-float",
    pre_fix_sha="8059ebe1732c89177709476165f6e87cc76fe1b7",
    fix_sha="a79fb3a6c8bbe52afe71cd278bbea3bda5241a41",
    problem_statement=(
        "Public naturalsize must format a value of one byte as '1 Byte', "
        "including floating-point and numeric-string inputs representing one. "
        "Preserve SI, IEC, GNU, negative-size and custom decimal-format behavior."
    ),
    observation_cases=(
        PythonCase("float-one", "naturalsize", (1.0,), "1 Byte"),
        PythonCase("string-one", "naturalsize", ("1.0",), "1 Byte"),
        PythonCase("integer-one", "naturalsize", (1,), "1 Byte"),
        PythonCase("zero", "naturalsize", (0,), "0 Bytes"),
        PythonCase("si", "naturalsize", (3000,), "3.0 kB"),
        PythonCase("iec", "naturalsize", (3000, True), "2.9 KiB"),
        PythonCase("gnu", "naturalsize", (3000, False, True), "2.9K"),
        PythonCase("negative", "naturalsize", (-3000,), "-3.0 kB"),
        PythonCase("format", "naturalsize", (3000, False, False, "%.2f"), "3.00 kB"),
        PythonCase("bad-input", "naturalsize", ("not-a-number",), error="ValueError"),
    ), expected_tests=10,
)

ROLLOVER_TASK = dataclasses.replace(
    TASK, task_id="production-dev-humanize-yotta-rollover",
    pre_fix_sha="f8a74b4c1342a3987d3aaa409111bcd9f3a740f7",
    fix_sha="33119c0a88a2cd1b204e660c1d2b09c5a5b8791e",
    problem_statement=(
        "Public naturalsize must roll over from zettabytes to yottabytes at "
        "the SI boundary: 10**24 bytes represents '1.0 YB'. Preserve lower "
        "units, negative sizes, zero, singular bytes, binary and GNU formatting."
    ),
    observation_cases=(
        PythonCase("yotta", "naturalsize", (10**24,), "1.0 YB"),
        PythonCase("zetta", "naturalsize", (10**21,), "1.0 ZB"),
        PythonCase("negative-yotta", "naturalsize", (-10**24,), "-1.0 YB"),
        PythonCase("si", "naturalsize", (3000,), "3.0 kB"),
        PythonCase("iec", "naturalsize", (3000, True), "2.9 KiB"),
        PythonCase("gnu", "naturalsize", (3000, False, True), "2.9K"),
        PythonCase("zero", "naturalsize", (0,), "0 Bytes"),
        PythonCase("one", "naturalsize", (1,), "1 Byte"),
        PythonCase("bad-input", "naturalsize", ("not-a-number",), error="ValueError"),
    ), expected_tests=9,
)


class BudgetExceeded(RuntimeError):
    pass


def _timeout(_signum, _frame):
    raise BudgetExceeded("declared development wall-time exceeded")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=["negative-size", "one-byte-float", "yotta-rollover"],
                        default="negative-size")
    args = parser.parse_args()
    task = {"negative-size": TASK, "one-byte-float": ONE_BYTE_TASK, "yotta-rollover": ROLLOVER_TASK}[args.task]
    # This deliberately does not claim support for additional machines.
    if platform.machine() != "arm64" or platform.mac_ver()[0] != "27.0.1":
        raise RuntimeError("unmeasured host: development support contract does not apply")
    if shutil.disk_usage(each_home()).free < 20 * 1024**3:
        raise RuntimeError("development disk reserve insufficient")
    import mlx.core as mx

    mx.set_memory_limit(64 * 1024**3)
    model = load_model("qwen2.5-coder-14b-instruct-mlx", max_tokens=2048)
    original_check = model.check_context_budget
    original_complete = model.complete

    def check(prompt):
        rendered, count = original_check(prompt)
        if count + 2048 > 8192:
            raise ContextBudgetExceeded("declared 8192-token context cap exceeded")
        return rendered, count

    def complete(prompt):
        check(prompt)
        signal.alarm(300)
        try:
            return original_complete(prompt)
        finally:
            signal.alarm(0)

    model.check_context_budget = check
    model.complete = complete
    signal.signal(signal.SIGALRM, _timeout)
    started = time.monotonic()
    result = run_benchmark_task(task, model, max_attempts=3)
    elapsed = time.monotonic() - started
    # Read locally only; never emit source, prompts, completions or target patch.
    from pathlib import Path

    path = Path(result["receipt_json"])
    receipt = json.loads(path.read_text())
    signature = verify_receipt(receipt, public_key_path().read_bytes())
    retained = verify_materials_root(receipt, path.parent / "materials")
    summary = {
        "taskId": task.task_id,
        "outcome": result["outcome"],
        "receiptSha256": sha256_file(path),
        "receiptPath": str(path),
        "attempts": result["attempts"],
        "actualModelCalls": sum(a.get("generation_attempted", False) for a in receipt["attempts"]),
        "wallSeconds": elapsed,
        "withinTaskBudget": elapsed <= 1200,
        "mlxPeakBytes": mx.get_peak_memory(),
        "signature": signature,
        "retainedMaterials": retained,
        "baseline": [a.get("baseline_classification", {}) for a in receipt["attempts"]],
        "candidate": [a.get("repaired_classification", {}) for a in receipt["attempts"]],
        "auditStates": {k: v["status"] for k, v in receipt["audit"].get("checks", {}).items()},
        "auditSubjectSha256": receipt["auditSubjectSha256"],
        "inputTokenCount": model.identity()["contextPolicy"]["lastInputTokenCount"],
        "holdout": False,
        "approval": "engineering authorization; not human adoption or release approval",
    }
    summary_path = path.parent / "development-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    summary_path.chmod(0o600)
    print(json.dumps(summary))
    return 0 if signature.get("status") == "PASS" and retained.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
