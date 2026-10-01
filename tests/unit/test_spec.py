from __future__ import annotations

import pytest

from each.spec import ApprovedSpec, SpecIntegrityError, SpecPacket, make_spec_packet


def _packet(allowed_paths: list[str] | None = None) -> SpecPacket:
    return make_spec_packet(
        task_id="t1",
        target_repo="examples/hello-repair",
        target_ref="local-fixture",
        problem_statement="bug",
        allowed_paths=allowed_paths or ["src/greet.py"],
        build_commands=[],
        acceptance_commands=[["python", "-m", "unittest"]],
        forbidden_sources=["network"],
        approved_by="tester",
    )


def test_approve_and_verify_round_trips() -> None:
    approved = ApprovedSpec.approve(_packet())
    approved.verify()  # must not raise


def test_verify_rejects_hash_mismatch_from_widened_scope() -> None:
    approved = ApprovedSpec.approve(_packet())
    widened_packet = _packet(allowed_paths=["src/greet.py", "src/extra.py"])
    tampered = ApprovedSpec(packet=widened_packet, approved_hash=approved.approved_hash)
    with pytest.raises(SpecIntegrityError, match="hash mismatch"):
        tampered.verify()


def test_different_content_yields_different_hash() -> None:
    hash_a = _packet(allowed_paths=["src/greet.py"]).sha256()
    hash_b = _packet(allowed_paths=["src/other.py"]).sha256()
    assert hash_a != hash_b
