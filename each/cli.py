"""EACH command-line interface.

v0.1 implements only ``each doctor``. Later milestones add ``each issue``,
``each spec``, ``each run``, ``each audit``, ``each attest``, and
``each verify`` (see docs/EACH_MILESTONE_PROMPTS.md). The CLI intentionally
has no daemon: every command is a single, auditable invocation.
"""

from __future__ import annotations

import argparse
import sys

from each import __version__
from each.doctor import doctor_passed, run_checks


def _cmd_doctor(_args: argparse.Namespace) -> int:
    checks = run_checks()
    width = max(len(check.name) for check in checks)
    for check in checks:
        marker = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[check.status]
        required = "required" if check.required else "optional"
        print(f"{marker} {check.name.ljust(width)}  [{check.status:4s} {required:8s}]  {check.detail}")
    ok = doctor_passed(checks)
    if ok:
        print("\neach doctor: PASS (all required checks satisfied)")
    else:
        print("\neach doctor: FAIL (a required check failed)")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="each", description="Evidence-Audited Cleanroom Harness")
    parser.add_argument("--version", action="version", version=f"each {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="report environment health")
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
