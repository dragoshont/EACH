from __future__ import annotations

import json
from typing import Self

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


class _StubResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_cli_issue_show_without_import_exits_nonzero(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))
    exit_code = main(["issue", "show", "never-imported"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "issue show failed" in captured.out


def test_cli_issue_import_and_spec_build_approve_end_to_end(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))
    from each import issue_intake

    payload = {
        "title": "CLI test issue",
        "body": "a body",
        "html_url": "https://github.com/octocat/Hello-World/issues/1",
    }
    monkeypatch.setattr(issue_intake.urllib.request, "urlopen", lambda *a, **k: _StubResponse(payload))

    exit_code = main(["issue", "import", "https://github.com/octocat/Hello-World/issues/1"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "octocat-Hello-World-1" in captured.out

    exit_code = main(["issue", "show", "octocat-Hello-World-1"])
    assert exit_code == 0
    assert "UNTRUSTED" in capsys.readouterr().out

    exit_code = main(
        [
            "spec",
            "build",
            "octocat-Hello-World-1",
            "--target-repo",
            "https://github.com/octocat/Hello-World",
            "--target-ref",
            "master",
            "--allowed-path",
            "README",
            "--build-cmd",
            "true",
            "--acceptance-cmd",
            "true",
            "--forbidden-source",
            "no-gpl-sources",
        ]
    )
    assert exit_code == 0
    assert "draft spec written" in capsys.readouterr().out

    exit_code = main(["spec", "approve", "octocat-Hello-World-1", "--human", "tester"])
    assert exit_code == 0
    assert "spec approved" in capsys.readouterr().out

    # Re-approving must fail: approved specs are immutable.
    exit_code = main(["spec", "approve", "octocat-Hello-World-1", "--human", "tester"])
    assert exit_code == 2
    assert "already has an approved spec" in capsys.readouterr().out
