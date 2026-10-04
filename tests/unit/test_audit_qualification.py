"""Public synthetic qualification regressions; never target implementation."""

from each.audit.checks import exact_substring_check
from each.audit.corpus import InMemoryCorpusAdapter
from each.audit.run import reject_on_audit_flag, run_audit

REFERENCE = "def total(values):\n    return sum(values)\n"


def test_empty_candidate_is_not_an_exact_copy():
    assert exact_substring_check("", [REFERENCE]).status == "UNAVAILABLE"
    assert exact_substring_check(" \n\t", [REFERENCE]).status == "UNAVAILABLE"


def test_empty_candidate_is_not_a_declared_member():
    assert InMemoryCorpusAdapter([REFERENCE]).check("").status == "UNAVAILABLE"


def test_missing_required_check_rejects_without_implementation_feedback():
    audit = run_audit(REFERENCE)
    assert reject_on_audit_flag(audit, required_checks=("corpus-membership",))
    assert not reject_on_audit_flag(audit)  # Optional unavailability is not a rejection.


def test_omitted_required_result_is_also_unavailable():
    assert reject_on_audit_flag({"checks": {}}, required_checks=("exact-substring",))


def test_unknown_required_check_fails_closed():
    import pytest

    with pytest.raises(ValueError, match="unknown required"):
        run_audit(REFERENCE, required_checks=("typo",))


def test_policy_reports_available_scope_without_claiming_training_membership():
    audit = run_audit(
        "class Unrelated:\n    pass\n",
        corpus=[REFERENCE],
        corpus_revision="self-authored-synthetic-v1",
        required_checks=("exact-substring", "ngram-similarity"),
    )
    policy = audit["policy"]
    assert policy["missingRequiredChecks"] == []
    assert "corpus-membership" in policy["optionalUnavailableChecks"]
    assert policy["coverageCeiling"] == "declared-reference-only"
    assert policy["qualifiedForDeclaredChecks"] is True
    assert audit["checks"]["corpus-membership"]["status"] == "UNAVAILABLE"
    if audit["checks"]["ast-similarity"]["status"] == "UNAVAILABLE":
        assert audit["toolVersions"]["treeSitter"] is None
    else:
        assert audit["toolVersions"]["treeSitter"] not in ("unknown", None)


def test_required_external_membership_blocks_qualification():
    audit = run_audit(
        REFERENCE, corpus=[REFERENCE], required_checks=("corpus-membership",)
    )
    assert audit["policy"]["qualifiedForDeclaredChecks"] is False
    assert audit["policy"]["missingRequiredChecks"] == ["corpus-membership"]


def test_metadata_has_no_matched_source():
    import json

    audit = run_audit(REFERENCE, corpus=[REFERENCE])
    encoded = json.dumps(audit)
    assert REFERENCE not in encoded
    assert "return sum" not in encoded


def test_fixture_splits_have_disjoint_project_clusters():
    import json
    from pathlib import Path

    root = Path(__file__).parents[1] / "fixtures" / "audit-qualification"
    calibration = json.loads((root / "calibration.json").read_text())
    holdout = json.loads((root / "holdout.json").read_text())
    assert not {x["cluster"] for x in calibration["projects"]} & {
        x["cluster"] for x in holdout["projects"]
    }
    assert calibration["license"] == holdout["license"] == "Apache-2.0"
