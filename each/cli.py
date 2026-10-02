"""EACH command-line interface.

v0.1 implements only ``each doctor``. Later milestones add ``each issue``,
``each spec``, ``each run``, ``each audit``, ``each attest``, and
``each verify`` (see docs/EACH_MILESTONE_PROMPTS.md). The CLI intentionally
has no daemon: every command is a single, auditable invocation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from each import __version__
from each.doctor import doctor_passed, run_checks


def _cmd_demo_hello_repair(_args: argparse.Namespace) -> int:
    from each.demo import run_hello_repair

    result = run_hello_repair()
    print(f"outcome: {result['outcome']}")
    print(f"receipt (json): {result['receipt_json']}")
    print(f"receipt (md):   {result['receipt_md']}")
    return 0 if result["outcome"] == "REPAIR_VERIFIED" else 1


def _cmd_model_bakeoff(args: argparse.Namespace) -> int:
    from each.bakeoff import run_model_bakeoff
    from each.models.catalog import UnavailableModelError, load_model

    try:
        model = load_model(args.model)
    except UnavailableModelError as exc:
        print(f"model unavailable: {exc}")
        return 2

    try:
        result = run_model_bakeoff(model, max_attempts=args.max_attempts)
    except ValueError as exc:
        print(f"invalid bake-off arguments: {exc}")
        return 2
    print(f"model:   {model.model_id}")
    print(f"outcome: {result['outcome']}")
    print(f"attempts: {result['attempts']}")
    print(f"receipt (json): {result['receipt_json']}")
    print(f"receipt (md):   {result['receipt_md']}")
    return 0 if result["outcome"] == "REPAIR_VERIFIED" else 1


def _cmd_issue_import(args: argparse.Namespace) -> int:
    from each.issue_intake import IssueIntakeError, fetch_issue

    try:
        cached = fetch_issue(args.url, task_id=args.task_id)
    except IssueIntakeError as exc:
        print(f"issue import failed: {exc}")
        return 2
    print(f"task id: {Path(cached.cache_path).stem}")
    print(f"title:   {cached.title}")
    print(f"hash:    {cached.content_sha256}")
    print(f"cache:   {cached.cache_path}")
    return 0


def _cmd_issue_show(args: argparse.Namespace) -> int:
    from each.issue_intake import IssueIntakeError, load_cached_issue

    try:
        cached = load_cached_issue(args.task_id)
    except IssueIntakeError as exc:
        print(f"issue show failed: {exc}")
        return 2
    print("UNTRUSTED issue text (origin=PUBLIC_ISSUE); not automatically a Builder input.")
    print(f"source:       {cached.html_url}")
    print(f"retrieved at: {cached.retrieved_at}")
    print(f"hash:         {cached.content_sha256}")
    print(f"title:        {cached.title}")
    print("body:")
    print(cached.body)
    return 0


def _cmd_spec_build(args: argparse.Namespace) -> int:
    from each.spec_workflow import SpecBuildRequest, SpecWorkflowError, build_spec_draft

    request = SpecBuildRequest(
        task_id=args.task_id,
        target_repo=args.target_repo,
        target_ref=args.target_ref,
        allowed_paths=tuple(args.allowed_path),
        build_commands=tuple(tuple(cmd.split()) for cmd in args.build_cmd),
        acceptance_commands=tuple(tuple(cmd.split()) for cmd in args.acceptance_cmd),
        forbidden_sources=tuple(args.forbidden_source),
        sensitive=args.sensitive,
    )
    try:
        packet = build_spec_draft(request)
    except SpecWorkflowError as exc:
        print(f"spec build failed: {exc}")
        return 2
    print(f"draft spec written for task {args.task_id!r}")
    print(f"draft hash: {packet.sha256()}")
    print(f"sensitive:  {packet.sensitive}")
    return 0


def _cmd_spec_approve(args: argparse.Namespace) -> int:
    from each.spec_workflow import SpecWorkflowError, approve_spec

    try:
        approved = approve_spec(args.task_id, approved_by=args.human)
    except SpecWorkflowError as exc:
        print(f"spec approve failed: {exc}")
        return 2
    print(f"spec approved for task {args.task_id!r}")
    print(f"approved by:   {approved.packet.approved_by}")
    print(f"approved hash: {approved.approved_hash}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    import json

    from each.attestation import verify_receipt
    from each.signing import public_key_path

    receipt_path = Path(args.receipt_json)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read receipt: {exc}")
        return 2

    key_path = Path(args.public_key) if args.public_key else public_key_path()
    try:
        public_key_pem = key_path.read_bytes()
    except OSError as exc:
        print(f"cannot read public key: {exc}")
        return 2

    result = verify_receipt(receipt, public_key_pem)
    print(f"verification: {result['status']}")
    print(f"reason: {result['reason']}")
    print("note: integrity/provenance verification is NOT legal clean-room certification.")
    return 0 if result["status"] == "PASS" else 1


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

    demo = subparsers.add_parser("demo", help="deterministic demonstration pipelines")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)
    hello_repair = demo_sub.add_parser(
        "hello-repair", help="run the M1 deterministic hello-repair vertical slice"
    )
    hello_repair.set_defaults(func=_cmd_demo_hello_repair)

    model = subparsers.add_parser("model", help="local-model operations (M2)")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    bakeoff = model_sub.add_parser("bakeoff", help="run the hello-repair fixture against a real local model")
    bakeoff.add_argument("model", help="model catalog key, e.g. granite-3b-code-base-mlx")
    bakeoff.add_argument("--max-attempts", type=int, default=3)
    bakeoff.set_defaults(func=_cmd_model_bakeoff)

    issue = subparsers.add_parser("issue", help="GitHub issue intake (M3)")
    issue_sub = issue.add_subparsers(dest="issue_command", required=True)
    issue_import = issue_sub.add_parser("import", help="fetch and content-hash-cache a public GitHub issue")
    issue_import.add_argument("url", help="https://github.com/<owner>/<repo>/issues/<number>")
    issue_import.add_argument("--task-id", default=None, help="override the derived task id")
    issue_import.set_defaults(func=_cmd_issue_import)
    issue_show = issue_sub.add_parser("show", help="print a previously imported issue (marked untrusted)")
    issue_show.add_argument("task_id")
    issue_show.set_defaults(func=_cmd_issue_show)

    spec = subparsers.add_parser("spec", help="immutable spec construction and human approval (M3)")
    spec_sub = spec.add_subparsers(dest="spec_command", required=True)
    spec_build = spec_sub.add_parser(
        "build", help="build an unapproved spec draft; policy fields come only from these flags, never issue text"
    )
    spec_build.add_argument("task_id")
    spec_build.add_argument("--target-repo", required=True)
    spec_build.add_argument("--target-ref", required=True)
    spec_build.add_argument("--allowed-path", action="append", default=[], dest="allowed_path")
    spec_build.add_argument("--build-cmd", action="append", default=[], dest="build_cmd")
    spec_build.add_argument("--acceptance-cmd", action="append", default=[], dest="acceptance_cmd")
    spec_build.add_argument("--forbidden-source", action="append", default=[], dest="forbidden_source")
    spec_build.add_argument("--sensitive", action="store_true")
    spec_build.set_defaults(func=_cmd_spec_build)
    spec_approve = spec_sub.add_parser("approve", help="explicit human approval; binds the draft to its content hash")
    spec_approve.add_argument("task_id")
    spec_approve.add_argument("--human", required=True, help="approver identity (never read from issue/Scout text)")
    spec_approve.set_defaults(func=_cmd_spec_approve)

    verify = subparsers.add_parser("verify", help="verify a receipt's integrity attestation (M5)")
    verify.add_argument("receipt_json", help="path to a receipt.json file")
    verify.add_argument(
        "--public-key",
        default=None,
        help="path to the EACH signing public key PEM (default: ~/.each/keys/each-signing-ed25519-public.pem)",
    )
    verify.set_defaults(func=_cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
