from __future__ import annotations

from each.cli import build_parser, main
from each.doctor import doctor_passed, run_checks


def test_doctor_checks_run_without_crashing() -> None:
    checks = run_checks()
    names = {check.name for check in checks}
    assert "python" in names
    assert "each-home" in names


def test_doctor_required_checks_satisfied_in_dev_environment() -> None:
    checks = run_checks()
    assert doctor_passed(checks), [c for c in checks if c.required and c.status == "FAIL"]


def test_cli_doctor_exits_zero_when_passing(capsys) -> None:
    exit_code = main(["doctor"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "each doctor: PASS" in captured.out


def test_cli_parser_has_version() -> None:
    parser = build_parser()
    assert parser.prog == "each"


def test_cli_model_bakeoff_unavailable_model_exits_nonzero(capsys) -> None:
    exit_code = main(["model", "bakeoff", "not-a-real-model"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "model unavailable" in captured.out
