"""Harness self-test for the M8 real-source shadow-demonstration Builder
pipeline, using a deterministic ``FixtureModel`` canned response -- never
the real declared local model -- purely to validate the fetch/merge/
worktree/patch/validate/audit/sign wiring before spending real local-model
inference time. This is explicitly NOT the accepted M8 evidence; the
accepted receipt must come from a real ``RepairModel`` run against the
recorded local model (see docs/EACH_BOOTSTRAP_MANDATE.md M8 and
``each.xodus_shadow``'s own docstring).

The cached source fixture (``tests/unit/data/xsystem_selftest_source.c``)
is a byte-identical copy of the real, pinned, public
``xodus-gaming/xgameruntime`` file at the exact approved-spec commit --
fetched once, here cached for deterministic/offline tests, never altered.
``each.benchmark.fetch_file`` is monkeypatched to return it instead of
making a real network call during this self-test.

Requires the real, dedicated ``docker --context colima-each`` daemon AND
the locally pre-built ``each-m8-native-runtime`` image (see
``docker/m8-native-runtime/Dockerfile``); skipped, not silently passed,
when either is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

import each.xodus_shadow as xodus_shadow_module
from each.executor.base import ExecutionResult
from each.models.fixture import FixtureModel
from each.spec import ApprovedSpec, make_spec_packet
from each.spec_workflow import specs_dir
from each.xodus_shadow import run_xodus_shadow_build, summarize_receipt
from tests.adversarial._docker_guard import requires_colima_each

_CORRECT_PATCH = (Path(__file__).parent / "data" / "xodus_shadow_selftest_patch.txt").read_text()
_CACHED_SOURCE = (Path(__file__).parent / "data" / "xsystem_selftest_source.c").read_text()
# Applies cleanly and compiles (so the attempt is classifiable) but only
# fixes one of the two bugged lines, so the repaired acceptance run still
# fails -- used only to exercise the F6 trajectory-consistency fix below.
_APPLIES_BUT_LEAVES_BUG_PATCH = (
    Path(__file__).parent / "data" / "xodus_shadow_selftest_patch_applies_but_leaves_bug.txt"
).read_text()
_CORRECT_FIM_BODY = """    /* Always assume RETAIL environment for Wine */
    const char *Id = "RETAIL";

    TRACE( "iface %p, sandboxIdSize %d, sandboxId %p, sandboxIdUsed %p\\n", iface, sandboxIdSize, sandboxId, sandboxIdUsed );

    if (!sandboxId)
        return E_POINTER;

    if (sandboxIdSize < XSystemXboxLiveSandboxIdMaxBytes)
        return HRESULT_FROM_WIN32( ERROR_INSUFFICIENT_BUFFER );

    strcpy_s( sandboxId, sandboxIdSize, Id );
    if (sandboxIdUsed) *sandboxIdUsed = strlen( Id ) + 1;
    return S_OK;
"""
_CONSOLE_FIXED_SOURCE = _CACHED_SOURCE.replace(
    "if (!consoleId || !consoleIdUsed)", "if (!consoleId)"
).replace(
    "*consoleIdUsed = strlen( Id ) + 1;", "if (consoleIdUsed) *consoleIdUsed = strlen( Id ) + 1;"
)


def _native_image_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "--context", "colima-each", "image", "inspect", xodus_shadow_module.NATIVE_IMAGE_DIGEST],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


requires_m8_native_image = pytest.mark.skipif(
    not _native_image_available(),
    reason="each-m8-native-runtime image not built locally (see docker/m8-native-runtime/Dockerfile)",
)


def _approve_selftest_spec(task_id: str) -> ApprovedSpec:
    """Build and approve a self-test spec, durably recording its approval
    at the exact path :func:`each.xodus_policy.verify_xodus_shadow_binding`
    reads (``~/.each/specs/<task_id>/approved.json``) -- a plain in-memory
    ``ApprovedSpec.approve(...)`` is no longer sufficient to run the real
    pipeline, by design (F2): it must be a genuine, durably recorded
    approval, not a caller-constructed object nothing else ever sees.
    ``sensitive=True`` is required because this self-test's own
    ``target_repo`` is one of ``policies/xodus-shadow.yml``'s declared
    strict-run repositories.
    """
    packet = make_spec_packet(
        task_id=task_id,
        target_repo="https://github.com/xodus-gaming/xgameruntime",
        target_ref="791710510d9ba0746bbd60754215eb321800e4f0",
        problem_statement="Harness self-test stand-in for the real M8 spec problem statement.",
        allowed_paths=["xsystem.c"],
        build_commands=[["python3", "examples/xodus-m8-sandbox-id/build_check.py", "build", "xsystem.c"]],
        acceptance_commands=[["python3", "examples/xodus-m8-sandbox-id/build_check.py", "run"]],
        forbidden_sources=["proprietary-implementation", "decompiler-output", "disassembly", "unauthorized-runtime-trace"],
        approved_by="harness-selftest",
        sensitive=True,
    )
    approved = ApprovedSpec.approve(packet)
    task_dir = specs_dir() / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    approved_path = task_dir / "approved.json"
    approved_path.write_text(json.dumps(approved.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return approved


def test_fim_split_ignores_braces_inside_strings_comments_and_nested_blocks() -> None:
    source = """
// static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId(void) { ignored }
const char *ignored = "static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId {";
static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId(void)
/* comment with { before the real opening brace */
{
    const char *value = "}";
    /* } */
    char brace = '}';
    // }
    if (value) { value++; }
    return S_OK;
}
int after;
""".lstrip().replace("\n", "\r\n")
    prefix, suffix = xodus_shadow_module._split_sandbox_function_body(source)
    assert prefix.endswith("{\r\n")
    assert suffix.startswith("}\r\nint after;")
    assert prefix + '    return E_FAIL;\n' + suffix != source


@pytest.mark.parametrize(
    ("source", "valid"),
    [
        ("int unrelated;\n", False),
        ((
            "static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId(void);\n"
        ), False),
        ((
            "static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId(void) { return S_OK; }\n"
            "static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId(int x) { return E_FAIL; }\n"
        ), False),
        ((
            "// ignored continued comment \\\n"
            "static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId(void) { return E_FAIL; }\n"
            "static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId(void)\n"
            "{\n    return S_OK;\n}\n"
        ), True),
    ],
)
def test_fim_split_rejects_missing_declaration_duplicate_and_ignores_spliced_comment(
    source, valid,
) -> None:
    if valid:
        prefix, suffix = xodus_shadow_module._split_sandbox_function_body(source)
        assert prefix.endswith("{\n")
        assert suffix.startswith("}\n")
    else:
        with pytest.raises(xodus_shadow_module.PatchRejected):
            xodus_shadow_module._split_sandbox_function_body(source)


def test_fim_derives_a_scoped_diff_and_rejects_control_tokens() -> None:
    patch = xodus_shadow_module._extract_patch_text_for_mode(
        _CORRECT_FIM_BODY,
        "fim",
        path="xsystem.c",
        original_text=_CACHED_SOURCE,
    )
    assert "--- a/xsystem.c" in patch
    assert "+++ b/xsystem.c" in patch
    with pytest.raises(xodus_shadow_module.PatchRejected, match="control tokens"):
        xodus_shadow_module._extract_patch_text_for_mode(
            "<fim_prefix>unexpected",
            "fim",
            path="xsystem.c",
            original_text=_CACHED_SOURCE,
        )
    for invalid in ("", "   ", "<|endoftext|>"):
        with pytest.raises(xodus_shadow_module.PatchRejected):
            xodus_shadow_module._extract_patch_text_for_mode(
                invalid,
                "fim",
                path="xsystem.c",
                original_text=_CACHED_SOURCE,
            )


@pytest.mark.parametrize("attempts", [0, 2, 1.0, True])
def test_fim_requires_exactly_one_integer_attempt(monkeypatch, attempts) -> None:
    approved = _approve_selftest_spec("test-xodus-shadow-fim-one-attempt-policy")
    monkeypatch.setattr(
        xodus_shadow_module,
        "fetch_file",
        lambda *_a, **_k: pytest.fail("invalid FIM attempt policy must fail before fetching"),
    )
    with pytest.raises(ValueError, match="exactly one"):
        run_xodus_shadow_build(
            FixtureModel(_CORRECT_FIM_BODY),
            approved,
            max_attempts=attempts,
            proposal_format="fim",
            run_id=f"selftest-fim-policy-{uuid.uuid4().hex[:8]}",
        )


@pytest.mark.parametrize("profile", ["function", "body"])
@pytest.mark.parametrize(
    "signature",
    [
        xodus_shadow_module._SANDBOX_ID_FUNCTION_SIGNATURE,
        xodus_shadow_module._CONSOLE_ID_FUNCTION_SIGNATURE,
    ],
)
def test_function_profiles_derive_diff_without_custom_markers(profile, signature) -> None:
    _before, declaration, original_body, _suffix = xodus_shadow_module._function_profile_parts(
        _CACHED_SOURCE, signature,
    )
    name = "console" if "ConsoleId" in signature else "sandbox"
    body = original_body.replace(
        f"if (!{name}Id || !{name}IdUsed)", f"if (!{name}Id)"
    ).replace(
        f"*{name}IdUsed = strlen( Id ) + 1;",
        f"if ({name}IdUsed) *{name}IdUsed = strlen( Id ) + 1;",
    )
    completion = declaration + body + "}\n" if profile == "function" else body
    patch = xodus_shadow_module._function_profile_proposal(
        completion, _CACHED_SOURCE, "xsystem.c", signature, profile,
    )
    assert "--- a/xsystem.c" in patch
    assert "+++ b/xsystem.c" in patch
    assert "BEGIN_PATCH" not in completion
    assert "END_SOURCE" not in completion


def test_recommended_profiles_follow_observed_model_failures() -> None:
    assert xodus_shadow_module.recommended_xodus_task_profile(
        {
            "modelId": "bigcode/starcoderbase@88ec5781ad071a9d9e925cd28f327dea22eb5188#sha256:97c8813f705fc8c1",
            "modelManifest": {
                "repoId": "bigcode/starcoderbase",
                "revision": "88ec5781ad071a9d9e925cd28f327dea22eb5188",
            },
        }
    )["proposalFormat"] == "body"
    octo = xodus_shadow_module.recommended_xodus_task_profile(
        {
            "modelId": "bigcode/octocoder@0f863c63e38ba80fc2c4010f34a7f46d537a9eee#sha256:553d84a480a0c794",
            "modelManifest": {
                "repoId": "bigcode/octocoder",
                "revision": "0f863c63e38ba80fc2c4010f34a7f46d537a9eee",
            },
        }
    )
    assert octo["proposalFormat"] == "body"
    assert octo["promptStyle"] == "question-answer-tests"
    crystal = xodus_shadow_module.recommended_xodus_task_profile(
        {
            "modelId": (
                "LLM360/Crystal@34fc9cd58acd87002560379a95b432147cc9135a"
                "#sha256:af277cbad887d6d0"
            ),
            "modelManifest": {
                "repoId": "LLM360/Crystal",
                "revision": "34fc9cd58acd87002560379a95b432147cc9135a",
            },
        }
    )
    assert crystal["proposalFormat"] == "body"
    assert crystal["promptStyle"] == "code-continuation"
    k2 = xodus_shadow_module.recommended_xodus_task_profile(
        {
            "modelId": (
                "IFM/K2@400af6cd7de09fc9349cc6b5b24db20f778d5b72"
                "#sha256:8266ff62e09c6985"
            ),
            "modelManifest": {
                "repoId": "IFM/K2",
                "revision": "400af6cd7de09fc9349cc6b5b24db20f778d5b72",
            },
        }
    )
    assert k2["proposalFormat"] == "body"
    assert k2["promptStyle"] == "code-continuation"
    with pytest.raises(ValueError):
        xodus_shadow_module.recommended_xodus_task_profile(
            {"modelManifest": {"repoId": "unqualified/model"}}
        )
    with pytest.raises(ValueError, match="exact authorized"):
        xodus_shadow_module.recommended_xodus_task_profile(
            {
                "modelId": "bigcode/octocoder@wrong#sha256:0000",
                "modelManifest": {"repoId": "bigcode/octocoder", "revision": "wrong"},
            }
        )


def test_xodus_runner_rejects_spoofed_real_adapter_identity() -> None:
    class SpoofedFixture(FixtureModel):
        def identity(self):
            value = super().identity()
            value.update({
                "adapterType": "TransformersRepairModel",
                "adapterClassPath": "each.models.transformers_model.TransformersRepairModel",
            })
            return value

    with pytest.raises(ValueError, match="actual Builder adapter"):
        run_xodus_shadow_build(
            SpoofedFixture("unused"),
            None,
            max_attempts=1,
            proposal_format="body",
        )


def test_body_profile_does_not_apply_continued_unrelated_source(tmp_path) -> None:
    from each.patch import apply_patch, parse_patch

    patch = xodus_shadow_module._function_profile_proposal(
        _CORRECT_FIM_BODY + "}\nint unexpected_function(void) { return 0; }\n",
        _CACHED_SOURCE,
        "xsystem.c",
        xodus_shadow_module._SANDBOX_ID_FUNCTION_SIGNATURE,
        "body",
    )
    target = tmp_path / "xsystem.c"
    target.write_text(_CACHED_SOURCE)
    apply_patch(parse_patch(patch), tmp_path, {"xsystem.c"})
    assert "unexpected_function" not in target.read_text()


def test_function_profile_evaluates_the_function_not_response_wrappers(tmp_path) -> None:
    signature = xodus_shadow_module._SANDBOX_ID_FUNCTION_SIGNATURE
    _before, declaration, _body, _suffix = xodus_shadow_module._function_profile_parts(
        _CACHED_SOURCE, signature,
    )
    function = declaration + _CORRECT_FIM_BODY + "}\n"
    patch = xodus_shadow_module._function_profile_proposal(
        "Corrected function:\n```c\n" + function + "```\nDone.",
        _CACHED_SOURCE, "xsystem.c", signature, "function",
    )
    continued = xodus_shadow_module._function_profile_proposal(
        function + "\nUnapplied explanation of the answer.\n",
        _CACHED_SOURCE, "xsystem.c", signature, "function",
    )
    body = xodus_shadow_module._function_profile_proposal(
        _CORRECT_FIM_BODY + "}\n", _CACHED_SOURCE, "xsystem.c", signature, "body",
    )
    body_with_continuation = xodus_shadow_module._function_profile_proposal(
        _CORRECT_FIM_BODY + "}\nContinued explanation that must not be applied.\n",
        _CACHED_SOURCE, "xsystem.c", signature, "body",
    )
    from each.patch import apply_patch, parse_patch

    reconstructed = []
    for index, candidate_patch in enumerate((patch, continued, body, body_with_continuation)):
        root = tmp_path / str(index)
        root.mkdir()
        target = root / "xsystem.c"
        target.write_text(_CACHED_SOURCE)
        apply_patch(parse_patch(candidate_patch), root, {"xsystem.c"})
        reconstructed.append(target.read_text().split())
    assert reconstructed[0] == reconstructed[1] == reconstructed[2] == reconstructed[3]


@requires_colima_each
@requires_m8_native_image
def test_terminal_audit_receives_post_patch_source_not_diff(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_audit = xodus_shadow_module.run_audit
    observed = []

    def capture_source(source, **kwargs):
        observed.append(source)
        return original_audit(source, **kwargs)

    monkeypatch.setattr(xodus_shadow_module, "run_audit", capture_source)
    approved = _approve_selftest_spec("test-xodus-shadow-audit-source")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")
    result = run_xodus_shadow_build(
        model, approved, max_attempts=1,
        run_id=f"selftest-audit-source-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )
    assert result["outcome"] == "REPAIR_VERIFIED"
    assert len(observed) == 1
    assert not observed[0].startswith(("--- ", "diff --git "))
    assert "\n+++ b/" not in observed[0]
    assert "\n@@ " not in observed[0]
    assert observed[0].splitlines()[0] == _CACHED_SOURCE.splitlines()[0]
    assert "XSystemGetXboxLiveSandboxId" in observed[0]


@requires_colima_each
@requires_m8_native_image
def test_terminal_audit_uses_precaptured_candidate_bytes_even_if_the_worktree_file_is_mutated_after_execution(
    tmp_path, monkeypatch
) -> None:
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_run = container_module.ContainerExecutor.run
    observed: list[str] = []
    call_count = 0

    def _capturing_audit(source, **kwargs):
        observed.append(source)
        return {"checks": {}, "result": "PASS", "reason": "captured"}

    def _mutating_run(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        result = original_run(self, command, worktree, **kwargs)
        if call_count == 5:
            (worktree / "xsystem.c").write_text("MUTATED AFTER ACCEPTANCE\\n", encoding="utf-8")
        return result

    monkeypatch.setattr(xodus_shadow_module, "run_audit", _capturing_audit)
    monkeypatch.setattr(container_module.ContainerExecutor, "run", _mutating_run)
    approved = _approve_selftest_spec("test-xodus-shadow-precaptured-audit-bytes")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-precap-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert len(observed) == 1
    assert "MUTATED AFTER ACCEPTANCE" not in observed[0]
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["result"] == "PASS"


@requires_colima_each
@requires_m8_native_image
def test_fixture_model_candidate_is_verified_and_signed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-harness-selftest")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=1, run_id=f"selftest-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "REPAIR_VERIFIED"
    assert result["attempts"] == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["assuranceLevel"] == "EACH-P2"
    assert receipt["networkIsolationVerified"] is True
    assert receipt["attempts"][0]["outcome"] == "REPAIR_VERIFIED"
    assert receipt["baselineResult"]["exit_code"] == 1
    assert receipt["repairedResult"]["exit_code"] == 0
    output = receipt["repairedResult"]["stdout"]
    cases = json.loads(output.split("EACH_CASE_RESULTS:", 1)[1])
    assert len(cases) == 12
    assert all(case["status"] == "PASS" for case in cases)
    assert set(receipt["audit"]["checks"]) == {
        "exact-substring",
        "ngram-similarity",
        "ast-similarity",
        "license-scan",
        "corpus-membership",
    }
    # F5: the real materials/ files are actually retained and verifiable,
    # not just declared in the receipt's own JSON (and not a post-patch
    # candidate-mutated copy falsely declared under the pre-patch hash).
    from each.attestation import verify_materials_root

    materials_root = Path(result["receipt_json"]).parent / "materials"
    full_result = verify_materials_root(receipt, materials_root)
    assert full_result["status"] == "PASS"
    # F6: the top-level materials/baseline/repaired fields must come from
    # the one selected/classified attempt's own recorded dict.
    assert receipt["materials"] == receipt["attempts"][0]["materials"]
    assert receipt["baselineResult"] == receipt["attempts"][0]["baseline_result"]
    assert receipt["repairedResult"] == receipt["attempts"][0]["repaired_result"]

    summary = summarize_receipt(result["receipt_json"])
    assert summary["outcome"] == "REPAIR_VERIFIED"
    assert "prompt" not in summary
    assert "rawCompletion" not in summary
    assert "patchText" not in summary
    # F3: proposalFormat must be surfaced as a bounded enum, not an
    # arbitrary attempt-controlled string.
    assert summary["attemptProposalFormats"] == ["diff"]


@requires_colima_each
@requires_m8_native_image
def test_zero_exit_before_case_return_cannot_pass_behavioral_validation(tmp_path, monkeypatch) -> None:
    from each.raw_proposal import derive_unified_diff

    source = _CACHED_SOURCE.replace("if (!consoleId || !consoleIdUsed)", "if (!consoleId)").replace(
        "*consoleIdUsed = strlen( Id ) + 1;", "if (consoleIdUsed) *consoleIdUsed = strlen( Id ) + 1;"
    )
    prefix, suffix = xodus_shadow_module._split_sandbox_function_body(source)
    candidate = prefix + "    __builtin_exit(0);\n" + suffix
    patch = derive_unified_diff(path="xsystem.c", original_text=source, proposed_text=candidate)
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: source)
    approved = _approve_selftest_spec("test-xodus-no-premature-zero-success")
    result = run_xodus_shadow_build(
        FixtureModel("BEGIN_PATCH\n" + patch + "END_PATCH"),
        approved,
        max_attempts=1,
        run_id=f"selftest-no-premature-success-{uuid.uuid4().hex[:8]}",
    )
    assert result["outcome"] == "REPAIR_NOT_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    cases = json.loads(receipt["repairedResult"]["stdout"].split("EACH_CASE_RESULTS:", 1)[1])
    sandbox = [case for case in cases if case["api"] == "sandbox"]
    assert len(sandbox) == 6
    assert all(case["status"] == "FAIL" for case in sandbox)
    assert all(case["reason"] == "case_data_missing_or_invalid" for case in sandbox)


@requires_colima_each
@requires_m8_native_image
@pytest.mark.parametrize("api", ["sandbox", "console"])
def test_oracle_rejects_correct_characters_without_string_terminator(monkeypatch, api):
    from each.raw_proposal import derive_unified_diff

    candidate = _ALREADY_FIXED_SOURCE
    buffer_name = f"{api}Id"
    candidate = candidate.replace(
        f"strcpy_s( {buffer_name}, {buffer_name}Size, Id );",
        f"memcpy( {buffer_name}, Id, strlen( Id ) );",
    )
    patch = derive_unified_diff(path="xsystem.c", original_text=_CACHED_SOURCE, proposed_text=candidate)
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec(f"test-xodus-missing-terminator-{api}")
    result = run_xodus_shadow_build(
        FixtureModel("BEGIN_PATCH\n" + patch + "END_PATCH"),
        approved, max_attempts=1, run_id=f"missing-terminator-{uuid.uuid4().hex[:8]}",
    )
    assert result["outcome"] == "REPAIR_NOT_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    cases = json.loads(receipt["repairedResult"]["stdout"].split("EACH_CASE_RESULTS:", 1)[1])
    positive = [
        case for case in cases
        if case["api"] == api and case["case"] in {"optional_size_output_null", "value_and_size_output"}
    ]
    assert len(positive) == 2
    assert all(case["status"] == "FAIL" for case in positive)


@requires_colima_each
@requires_m8_native_image
def test_oracle_accepts_valid_function_with_braces_in_comments_and_literals(monkeypatch):
    from each.raw_proposal import derive_unified_diff

    candidate = _ALREADY_FIXED_SOURCE.replace(
        'const char *Id = "RETAIL";',
        '/* } ignored */\n    const char brace = \'}\';\n    const char *literal = "}";\n'
        '    (void)brace; (void)literal;\n    const char *Id = "RETAIL";',
    )
    patch = derive_unified_diff(path="xsystem.c", original_text=_CACHED_SOURCE, proposed_text=candidate)
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-oracle-lexical-braces")
    result = run_xodus_shadow_build(
        FixtureModel("BEGIN_PATCH\n" + patch + "END_PATCH"),
        approved, max_attempts=1, run_id=f"oracle-lexical-{uuid.uuid4().hex[:8]}",
    )
    assert result["outcome"] == "REPAIR_VERIFIED"


@requires_colima_each
@requires_m8_native_image
@pytest.mark.parametrize("api", ["sandbox", "console"])
@pytest.mark.parametrize("profile", ["function", "body"])
@pytest.mark.parametrize("model_repo", ["bigcode/starcoderbase", "bigcode/octocoder"])
def test_split_native_profiles_reach_six_independent_behavioral_cases(
    monkeypatch, api, profile, model_repo,
) -> None:
    with tempfile.TemporaryDirectory(prefix="each-split-profile-", dir=Path.home()) as private:
        monkeypatch.setenv("EACH_HOME", private)
        task_id = f"each-two-model-ledger-{api}-v1"
        packet = make_spec_packet(
            task_id=task_id,
            target_repo="https://github.com/xodus-gaming/xgameruntime",
            target_ref="791710510d9ba0746bbd60754215eb321800e4f0",
            problem_statement="Harness fixture: preserve the documented optional size output contract.",
            allowed_paths=["xsystem.c"],
            build_commands=[[
                "python3", "examples/xodus-m8-sandbox-id/build_check.py", "build", "xsystem.c", api,
            ]],
            acceptance_commands=[[
                "python3", "examples/xodus-m8-sandbox-id/build_check.py", "run", api,
            ]],
            forbidden_sources=["proprietary-implementation", "auditor-source-matches"],
            approved_by="harness-selftest",
            sensitive=True,
        )
        approved = ApprovedSpec.approve(packet)
        task_dir = specs_dir() / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "approved.json").write_text(json.dumps(approved.to_dict()))
        signature = (
            xodus_shadow_module._CONSOLE_ID_FUNCTION_SIGNATURE if api == "console"
            else xodus_shadow_module._SANDBOX_ID_FUNCTION_SIGNATURE
        )
        _before, declaration, body, _suffix = xodus_shadow_module._function_profile_parts(
            _CACHED_SOURCE, signature,
        )
        name = api
        corrected = body.replace(
            f"if (!{name}Id || !{name}IdUsed)", f"if (!{name}Id)"
        ).replace(
            f"*{name}IdUsed = strlen( Id ) + 1;",
            f"if ({name}IdUsed) *{name}IdUsed = strlen( Id ) + 1;",
        )
        response = declaration + corrected + "}\n" if profile == "function" else corrected

        class NativePromptFixture(FixtureModel):
            def identity(self):
                value = super().identity()
                value["modelManifest"] = {"repoId": model_repo}
                return value

            def complete(self, prompt):
                self.observed = prompt
                return super().complete(prompt)

        monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
        model = NativePromptFixture(response)
        result = run_xodus_shadow_build(
            model, approved, max_attempts=1, proposal_format=profile,
            run_id=f"split-native-{uuid.uuid4().hex[:8]}",
        )
        assert result["outcome"] == "REPAIR_VERIFIED"
        if model_repo == "bigcode/starcoderbase":
            assert model.observed.startswith("<fim_prefix>")
            assert model.observed.endswith("<fim_middle>")
            assert "Public behavioral cases:" in model.observed
        else:
            assert "Public behavioral cases:" in model.observed
            if profile == "body":
                assert model.observed.startswith("Question: Fix bugs in ")
                assert "\n\nAnswer:\nstatic HRESULT WINAPI " in model.observed
            else:
                assert model.observed.startswith(
                    "Question: The following public C function is buggy"
                )
                assert "Buggy function:" in model.observed
        receipt_path = Path(result["receipt_json"])
        receipt = json.loads(receipt_path.read_text())
        cases = json.loads(receipt["repairedResult"]["stdout"].split("EACH_CASE_RESULTS:", 1)[1])
        assert len(cases) == 6
        assert all(case["api"] == api and case["status"] == "PASS" for case in cases)
        from each.attestation import verify_materials_root, verify_receipt
        from each.signing import public_key_path

        assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
        assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"


@requires_colima_each
@requires_m8_native_image
def test_fixture_model_fim_candidate_is_verified_and_signed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CONSOLE_FIXED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-fim-selftest")

    class CapturingFixture(FixtureModel):
        def complete(self, prompt: str) -> str:
            self.observed_prompt = prompt
            return super().complete(prompt)

    model = CapturingFixture(_CORRECT_FIM_BODY, model_id="fixture/xodus-shadow-selftest-v1")
    result = run_xodus_shadow_build(
        model,
        approved,
        max_attempts=1,
        proposal_format="fim",
        run_id=f"selftest-fim-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )

    assert result["outcome"] == "REPAIR_VERIFIED"
    source_prefix, source_suffix = xodus_shadow_module._split_sandbox_function_body(_CONSOLE_FIXED_SOURCE)
    expected_prompt = (
        f"<fim_prefix>/* EACH approved requirement:\n{approved.packet.problem_statement}\n*/\n"
        f"{source_prefix}<fim_suffix>{source_suffix}<fim_middle>"
    )
    assert model.observed_prompt == expected_prompt
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    attempt = receipt["attempts"][0]
    assert attempt["proposal_format"] == "fim"
    assert attempt["infillPrefixSha256"] == xodus_shadow_module.sha256_bytes(source_prefix.encode())
    assert attempt["infillSuffixSha256"] == xodus_shadow_module.sha256_bytes(source_suffix.encode())
    assert receipt["baselineResult"]["exit_code"] == 1
    assert receipt["repairedResult"]["exit_code"] == 0
    from each.attestation import verify_materials_root, verify_receipt
    from each.signing import public_key_path

    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, Path(result["receipt_json"]).parent / "materials")["status"] == "PASS"
    assert summarize_receipt(result["receipt_json"])["attemptProposalFormats"] == ["fim"]


@requires_colima_each
@requires_m8_native_image
def test_fim_rejection_stops_after_one_call_and_retains_infill_hashes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-fim-rejection-single-call")

    class CountingFixture(FixtureModel):
        def complete(self, prompt: str) -> str:
            self.calls = getattr(self, "calls", 0) + 1
            return super().complete(prompt)

    model = CountingFixture("<fim_prefix>unexpected")
    result = run_xodus_shadow_build(
        model,
        approved,
        max_attempts=1,
        proposal_format="fim",
        run_id=f"selftest-fim-reject-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )
    assert model.calls == 1
    assert result["outcome"] == "PATCH_REJECTED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert len(receipt["attempts"]) == 1
    assert len(receipt["attempts"][0]["infillPrefixSha256"]) == 64
    assert len(receipt["attempts"][0]["infillSuffixSha256"]) == 64


@requires_colima_each
@requires_m8_native_image
def test_fim_generation_failure_retains_infill_hashes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-fim-generation-failure")
    model = FixtureModel("unused")

    def fail_generation(prompt: str) -> str:
        del prompt
        model.last_generation_attempted = True
        raise RuntimeError("private backend detail")

    monkeypatch.setattr(model, "complete", fail_generation)
    result = run_xodus_shadow_build(
        model,
        approved,
        max_attempts=1,
        proposal_format="fim",
        run_id=f"selftest-fim-generation-error-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )
    assert result["outcome"] == "EXECUTION_ERROR"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    attempt = receipt["attempts"][0]
    assert len(attempt["infillPrefixSha256"]) == 64
    assert len(attempt["infillSuffixSha256"]) == 64
    assert "private backend detail" not in json.dumps(summarize_receipt(result["receipt_json"]))


@requires_colima_each
@requires_m8_native_image
def test_terminal_audit_honestly_reports_invalid_utf8_candidate_source_as_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    monkeypatch.setattr(
        xodus_shadow_module,
        "_read_candidate_bytes_for_audit",
        lambda *_a, **_k: b"\xff\xfe",
    )
    approved = _approve_selftest_spec("test-xodus-shadow-invalid-utf8")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-invalid-utf8-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["result"] == "UNAVAILABLE"
    assert "valid UTF-8" in receipt["audit"]["reason"]


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_assurance_level_is_downgraded_to_p1_when_the_selected_attempts_materials_drift(
    tmp_path, monkeypatch
) -> None:
    """F4: the raw network-isolation probe genuinely passes, but the
    broader authoring-assurance claim must be conservatively downgraded
    when the selected attempt's own validation scaffold drifted during
    execution."""
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    monkeypatch.setattr(
        xodus_shadow_module,
        "verify_unchanged",
        lambda *_a, **_k: ["examples/xodus-m8-sandbox-id/build_check.py"],
    )
    approved = _approve_selftest_spec("test-xodus-shadow-assurance-downgrade")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-drift-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] == "EACH-P1"
    assert receipt["outcome"] == "REPAIR_NOT_VERIFIED"


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_fails_closed_when_isolation_cannot_be_verified(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    monkeypatch.setattr(xodus_shadow_module, "derive_assurance_level", lambda *_a, **_k: "EACH-P1")
    approved = _approve_selftest_spec("test-xodus-shadow-isolation-fail-closed")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=3, run_id=f"selftest-iso-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "ISOLATION_UNVERIFIED"
    assert result["attempts"] == 0
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["patchText"] == ""
    assert receipt["attempts"] == []


@pytest.mark.parametrize("error", [PermissionError("denied"), OSError("unavailable")])
def test_xodus_shadow_isolation_exception_retains_signed_originals_without_generation(
    tmp_path, monkeypatch, error,
) -> None:
    monkeypatch.setenv("EACH_HOME", str(tmp_path / "each-home"))
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    monkeypatch.setattr(
        xodus_shadow_module.ContainerExecutor,
        "verify_isolation",
        lambda *_a, **_k: (_ for _ in ()).throw(error),
    )
    calls = 0

    class NoGeneration(FixtureModel):
        def complete(self, prompt: str) -> str:
            nonlocal calls
            calls += 1
            pytest.fail("isolation failure must not invoke the Builder")

    approved = _approve_selftest_spec(f"test-xodus-isolation-exception-{type(error).__name__.lower()}")
    result = run_xodus_shadow_build(
        NoGeneration("unused"), approved, max_attempts=1,
        run_id=f"selftest-iso-exception-{tmp_path.name}-{type(error).__name__.lower()}",
    )

    assert calls == 0
    assert result["outcome"] == "ISOLATION_UNVERIFIED"
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert receipt["isolationEvidence"]["errorType"] == type(error).__name__
    assert len(receipt["materials"]) == 3
    from each.attestation import verify_materials_root, verify_receipt
    from each.signing import public_key_path

    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_audit_match_is_terminal_without_builder_feedback(tmp_path, monkeypatch) -> None:
    """Regression for the M4/994413b Auditor-is-terminal fix, replicated on
    this surface: a discovered audit match must end the run after exactly
    one Builder call, never triggering a second attempt or leaking the
    match hint back into a later prompt."""
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    forbidden_hint = "FORBIDDEN_POST_GENERATION_SOURCE_MATCH"

    calls: list[str] = []

    class CapturingModel(FixtureModel):
        def complete(self, prompt: str) -> str:
            calls.append(prompt)
            return super().complete(prompt)

    def discovered_match(source: str, *, corpus=None, corpus_revision="none"):
        assert len(calls) == 1
        assert source
        return {
            "checks": {"exact-substring": {"status": "FAIL", "sourceHint": forbidden_hint}},
            "result": "FAIL",
            "corpusRevision": corpus_revision,
        }

    monkeypatch.setattr(xodus_shadow_module, "run_audit", discovered_match)
    approved = _approve_selftest_spec("test-xodus-shadow-audit-terminal")
    model = CapturingModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=3, run_id=f"selftest-audit-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"] == "REPAIR_REJECTED_AUDIT"
    assert result["attempts"] == len(calls) == 1
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["audit"]["result"] == "FAIL"
    assert all(forbidden_hint not in prompt for prompt in calls)


_ALREADY_FIXED_SOURCE = _CACHED_SOURCE.replace(
    "if (!consoleId || !consoleIdUsed)", "if (!consoleId)"
).replace(
    "*consoleIdUsed = strlen( Id ) + 1;", "if (consoleIdUsed) *consoleIdUsed = strlen( Id ) + 1;"
).replace(
    "if (!sandboxId || !sandboxIdUsed)", "if (!sandboxId)"
).replace(
    "*sandboxIdUsed = strlen( Id ) + 1;", "if (sandboxIdUsed) *sandboxIdUsed = strlen( Id ) + 1;"
)


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_baseline_must_genuinely_reproduce_the_bug(tmp_path, monkeypatch) -> None:
    """An already-fixed baseline must finalize signed fail-closed evidence,
    never accept a vacuous regression check or discard the run history."""
    assert _ALREADY_FIXED_SOURCE != _CACHED_SOURCE
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _ALREADY_FIXED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-baseline-honesty")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1,
        run_id=f"selftest-baseline-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )
    assert result["outcome"] == "BASELINE_NOT_REPRODUCED"
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert receipt["baselineResult"]["exit_code"] == 0
    assert receipt["attempts"] == []
    from each.attestation import verify_materials_root

    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_baseline_classification_error_finalizes_signed_receipt_without_generation(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    real_interpret = xodus_shadow_module._interpret_native_run
    calls = 0

    def fail_baseline_classification(build_result, run_result):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise xodus_shadow_module.BenchmarkExecutionError("private launch classification detail")
        return real_interpret(build_result, run_result)

    class NoGeneration(FixtureModel):
        def complete(self, prompt: str) -> str:
            pytest.fail("unclassified baseline must not invoke the Builder")

    monkeypatch.setattr(xodus_shadow_module, "_interpret_native_run", fail_baseline_classification)
    approved = _approve_selftest_spec("test-xodus-shadow-baseline-classification-error")
    result = run_xodus_shadow_build(
        NoGeneration("unused"), approved, max_attempts=1,
        run_id=f"selftest-baseline-classification-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )

    assert result["outcome"] == "EXECUTION_ERROR"
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert receipt["attempts"] == []
    assert receipt["baselineResult"]["exit_code"] == 1
    from each.attestation import verify_materials_root, verify_receipt
    from each.signing import public_key_path

    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"
    assert "private launch classification detail" not in json.dumps(summarize_receipt(receipt_path))


@requires_colima_each
@requires_m8_native_image
@pytest.mark.parametrize(
    ("fail_call", "replacement", "expected_outcome", "expected_exit"),
    [
        (2, OSError("private baseline build OS detail"), "EXECUTION_ERROR", None),
        (3, OSError("private baseline acceptance OS detail"), "EXECUTION_ERROR", 0),
        (2, ExecutionResult(("docker",), 125, "", "launch failed"), "EXECUTION_ERROR", 125),
        (2, ExecutionResult(("cc",), 2, "", "compile failed"), "BASELINE_NOT_REPRODUCED", 2),
    ],
)
def test_xodus_shadow_baseline_stage_failures_finalize_decisive_signed_evidence(
    tmp_path, monkeypatch, fail_call, replacement, expected_outcome, expected_exit,
) -> None:
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_run = container_module.ContainerExecutor.run
    call_count = 0

    def fail_baseline_stage(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == fail_call:
            if isinstance(replacement, BaseException):
                raise replacement
            return replacement
        return original_run(self, command, worktree, **kwargs)

    class NoGeneration(FixtureModel):
        def complete(self, prompt: str) -> str:
            pytest.fail("failed baseline must not invoke the Builder")

    monkeypatch.setattr(container_module.ContainerExecutor, "run", fail_baseline_stage)
    approved = _approve_selftest_spec(
        f"test-xodus-shadow-baseline-stage-{fail_call}-{expected_outcome.lower()}"
    )
    result = run_xodus_shadow_build(
        NoGeneration("unused"), approved, max_attempts=1,
        run_id=f"selftest-baseline-stage-{fail_call}-{expected_outcome.lower()}-{uuid.uuid4().hex[:8]}",
    )

    assert result["outcome"] == expected_outcome
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert receipt["attempts"] == []
    assert receipt["baselineResult"].get("exit_code") == expected_exit
    summary = summarize_receipt(receipt_path)
    assert summary["outcome"] == expected_outcome
    assert "private baseline" not in json.dumps(summary)
    from each.attestation import verify_materials_root, verify_receipt
    from each.signing import public_key_path

    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"


@requires_colima_each
@requires_m8_native_image
@pytest.mark.parametrize("fail_call", [4, 5])
def test_xodus_shadow_candidate_os_error_preserves_partial_stage_evidence(
    tmp_path, monkeypatch, fail_call,
) -> None:
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_run = container_module.ContainerExecutor.run
    call_count = 0

    def fail_candidate_stage(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == fail_call:
            raise OSError("private candidate OS detail")
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(container_module.ContainerExecutor, "run", fail_candidate_stage)
    approved = _approve_selftest_spec(f"test-xodus-shadow-candidate-os-error-{fail_call}")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")
    result = run_xodus_shadow_build(
        model, approved, max_attempts=1,
        run_id=f"selftest-candidate-os-{fail_call}-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )

    assert result["outcome"] == "EXECUTION_ERROR"
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    attempt = receipt["attempts"][0]
    assert attempt["patch_text"]
    assert attempt["touched_paths"]
    if fail_call == 4:
        assert attempt["build_result"] is None
    else:
        assert attempt["build_result"]["exit_code"] == 0
    assert attempt["run_result"] is None
    assert "private candidate OS detail" not in json.dumps(summarize_receipt(receipt_path))
    from each.attestation import verify_materials_root, verify_receipt
    from each.signing import public_key_path

    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_candidate_build_failure_is_decisive_and_skips_acceptance(
    tmp_path, monkeypatch,
) -> None:
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_run = container_module.ContainerExecutor.run
    call_count = 0

    def fail_candidate_build(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 4:
            return ExecutionResult(tuple(command), 2, "", "private compiler detail")
        if call_count > 4:
            pytest.fail("candidate acceptance must not run after a decisive build failure")
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(container_module.ContainerExecutor, "run", fail_candidate_build)
    approved = _approve_selftest_spec("test-xodus-shadow-candidate-build-decisive")
    result = run_xodus_shadow_build(
        FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1"),
        approved,
        max_attempts=1,
        run_id=f"selftest-candidate-build-decisive-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )

    assert call_count == 4
    assert result["outcome"] == "BUILD_FAILED"
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    attempt = receipt["attempts"][0]
    assert attempt["build_result"]["exit_code"] == 2
    assert attempt["run_result"] is None
    assert receipt["repairedResult"]["exit_code"] == 2
    summary = summarize_receipt(receipt_path)
    assert summary["outcome"] == "BUILD_FAILED"
    assert "private compiler detail" not in json.dumps(summary)


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_later_candidate_run_launch_failure_replaces_prior_selected_attempt(
    tmp_path, monkeypatch,
) -> None:
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_run = container_module.ContainerExecutor.run
    call_count = 0

    def fail_second_candidate_run(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 7:
            return ExecutionResult(tuple(command), 125, "", "private launch detail")
        return original_run(self, command, worktree, **kwargs)

    class SequenceModel(FixtureModel):
        def __init__(self) -> None:
            super().__init__(_APPLIES_BUT_LEAVES_BUG_PATCH, model_id="fixture/xodus-shadow-selftest-v1")
            self.responses = [_APPLIES_BUT_LEAVES_BUG_PATCH, _CORRECT_PATCH]
            self.calls = 0

        def complete(self, prompt: str) -> str:
            response = self.responses[self.calls]
            self.calls += 1
            return response

    monkeypatch.setattr(container_module.ContainerExecutor, "run", fail_second_candidate_run)
    approved = _approve_selftest_spec("test-xodus-shadow-later-run-launch-failure")
    model = SequenceModel()
    result = run_xodus_shadow_build(
        model,
        approved,
        max_attempts=2,
        run_id=f"selftest-later-run-launch-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )

    assert call_count == 7
    assert model.calls == 2
    assert result["outcome"] == "EXECUTION_ERROR"
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert len(receipt["attempts"]) == 2
    assert receipt["attempts"][0]["outcome"] == "REPAIR_NOT_VERIFIED"
    assert receipt["attempts"][1]["outcome"].startswith("EXECUTION_ERROR")
    assert receipt["selectedAttempt"] == 2
    assert receipt["outcome"].startswith("EXECUTION_ERROR")
    assert receipt["repairedResult"]["exit_code"] == 125
    summary = summarize_receipt(receipt_path)
    assert summary["outcome"] == "EXECUTION_ERROR"
    assert summary["selectedAttempt"] == 2
    assert "private launch detail" not in json.dumps(summary)


@requires_colima_each
@requires_m8_native_image
def test_exhausting_all_attempts_on_a_rejected_patch_reports_that_real_outcome_not_a_false_repair_not_verified(
    tmp_path,
) -> None:
    """Regression for the same mislabeling bug each.benchmark/each.clean_room
    already fix: if every attempt is exhausted on a malformed/rejected
    completion (never reaching a classified build/run), the receipt's final
    outcome must be the real last attempt's own outcome (e.g.
    "PATCH_REJECTED: ..."), not a sentinel "REPAIR_NOT_VERIFIED" that
    falsely implies a patch was applied, built, run, and simply failed."""
    approved = _approve_selftest_spec("test-xodus-shadow-all-attempts-rejected")
    model = FixtureModel("this completion has no patch markers at all", model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(model, approved, max_attempts=2, run_id=f"selftest-rejected-{tmp_path.name}-{uuid.uuid4().hex[:8]}")

    assert result["outcome"].startswith("PATCH_REJECTED")
    assert result["outcome"] != "REPAIR_NOT_VERIFIED"
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("PATCH_REJECTED")
    assert len(receipt["attempts"]) == 2
    assert all(a["outcome"].startswith("PATCH_REJECTED") for a in receipt["attempts"])
    assert all(a["completion_call_seconds"] >= 0 for a in receipt["attempts"])
    summary = summarize_receipt(result["receipt_json"])
    assert len(summary["attemptMetrics"]) == 2
    assert all(metric["completionCallSeconds"] >= 0 for metric in summary["attemptMetrics"])
    # F4: no attempt ever reached the point the materials-integrity check
    # runs at all (every attempt was rejected before any candidate
    # build/run) -- an UNPERFORMED required check must never be silently
    # treated as PASS, so the receipt must never claim the strongest
    # EACH-P2 authoring-assurance label here even though the raw network
    # probe genuinely passed.
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] != "EACH-P2"


@requires_colima_each
@requires_m8_native_image
def test_xodus_shadow_backend_failure_retains_signed_partial_receipt_and_metrics(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    approved = _approve_selftest_spec("test-xodus-shadow-backend-failure")
    model = FixtureModel("unused", model_id="fixture/xodus-shadow-selftest-v1")

    def fail_generation(prompt: str) -> str:
        model.last_generation_attempted = True
        raise RuntimeError("private backend detail")

    monkeypatch.setattr(model, "complete", fail_generation)
    result = run_xodus_shadow_build(
        model, approved, max_attempts=1,
        run_id=f"selftest-backend-failure-{tmp_path.name}-{uuid.uuid4().hex[:8]}",
    )

    assert result["outcome"] == "EXECUTION_ERROR"
    receipt_path = Path(result["receipt_json"])
    receipt = json.loads(receipt_path.read_text())
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    assert attempt["outcome"].startswith("EXECUTION_ERROR")
    assert attempt["completion_call_seconds"] >= 0
    assert attempt["generation_attempted"] is True
    from each.attestation import verify_materials_root, verify_receipt
    from each.signing import public_key_path

    assert verify_receipt(receipt, public_key_path().read_bytes())["status"] == "PASS"
    assert verify_materials_root(receipt, receipt_path.parent / "materials")["status"] == "PASS"
    summary = summarize_receipt(receipt_path)
    assert summary["outcome"] == "EXECUTION_ERROR"
    assert summary["attemptMetrics"][0]["generationAttempted"] is True
    assert "private backend detail" not in json.dumps(summary)


@requires_colima_each
@requires_m8_native_image
def test_an_execution_error_still_preserves_the_applied_patch_and_real_build_run_results(tmp_path, monkeypatch) -> None:
    """F6 regression: a patch that genuinely applies, builds, and runs, but
    whose (build, run) pair ``_interpret_native_run`` cannot classify, must
    never lose that real applied patch / real build / real run evidence --
    both must be recorded on the attempt BEFORE classification runs, so
    they survive a classification-time raise rather than being left at
    their initial empty defaults."""
    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    real_interpret = xodus_shadow_module._interpret_native_run
    call_count = 0

    def _flaky_interpret(build_result, run_result):
        nonlocal call_count
        call_count += 1
        # Call 1 is the pre-loop BASELINE classification (must stay real);
        # call 2 is the per-attempt candidate classification this test
        # exercises.
        if call_count == 2:
            raise xodus_shadow_module.BenchmarkExecutionError("simulated ambiguous native build/run output")
        return real_interpret(build_result, run_result)

    monkeypatch.setattr(xodus_shadow_module, "_interpret_native_run", _flaky_interpret)
    approved = _approve_selftest_spec("test-xodus-shadow-execution-error-preserves-evidence")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-execerr-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert receipt["outcome"].startswith("EXECUTION_ERROR")
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    assert attempt["patch_text"]
    assert attempt["touched_paths"]
    assert attempt["repaired_result"]
    assert attempt["repaired_result"]["exit_code"] is not None
    assert real_interpret is not None  # the genuine function, unused here, confirms monkeypatch replaced it


@requires_colima_each
@requires_m8_native_image
def test_a_real_container_timeout_during_the_acceptance_run_preserves_the_build_result_and_finalizes_a_partial_receipt(
    tmp_path, monkeypatch
) -> None:
    """F6 regression: a patch that genuinely applies and builds, but whose
    acceptance-run ``executor.run`` call itself raises ``ContainerExecutorError``
    (a real container-launch/timeout failure, not merely an ambiguous
    classification), must never propagate uncaught out of the whole
    function -- it must finalize a truthful, signed, partial receipt with
    the real build result preserved, the run result explicitly absent (no
    fabricated exit code), a conservative EACH-P1 assurance level, and the
    private diagnostic text kept out of the source-free summary view.

    Calls 1-4 (the isolation probe, the real baseline build, the real
    baseline run, and this attempt's real candidate build) are allowed to
    execute for real against the dedicated colima-each executor; only call
    5 (this attempt's acceptance run) is forced to raise."""
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    original_run = container_module.ContainerExecutor.run
    call_count = 0

    def _flaky_run(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 5:
            raise container_module.ContainerExecutorError("simulated fixture container timeout")
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(container_module.ContainerExecutor, "run", _flaky_run)
    approved = _approve_selftest_spec("test-xodus-shadow-real-container-timeout")
    model = FixtureModel(_CORRECT_PATCH, model_id="fixture/xodus-shadow-selftest-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=1, run_id=f"selftest-timeout-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert call_count == 5
    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt_path = Path(result["receipt_json"])
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["outcome"].startswith("EXECUTION_ERROR")
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    assert attempt["patch_text"]
    assert attempt["touched_paths"]
    assert attempt["build_result"] is not None
    assert attempt["build_result"]["exit_code"] == 0
    assert attempt["run_result"] is None
    assert attempt["materials_integrity"] == "UNAVAILABLE"
    assert result["outcome"] == "EXECUTION_ERROR"
    assert "simulated fixture container timeout" not in json.dumps(result)
    assert receipt["repairedResult"] == {}
    # A genuine network-isolation PROBE pass stays recorded as a plain fact,
    # but the broader authoring-assurance claim must still be conservatively
    # downgraded: an unperformed materials-integrity check is never "PASS".
    assert receipt["networkIsolationVerified"] is True
    assert receipt["assuranceLevel"] == "EACH-P1"

    # Signature-only verification must still PASS for this honest, signed
    # partial receipt.
    from each.cli import main as each_cli_main

    assert each_cli_main(["verify", str(receipt_path)]) == 0

    # The private diagnostic text ("simulated fixture container timeout")
    # must never cross into the source-free summary view.
    summary = summarize_receipt(result["receipt_json"])
    summary_text = json.dumps(summary)
    assert "simulated fixture container timeout" not in summary_text
    assert summary["outcome"] == "EXECUTION_ERROR"
    assert summary["repairedExitCode"] is None


@requires_colima_each
@requires_m8_native_image
def test_an_earlier_completed_attempt_is_preserved_when_a_later_attempt_hits_a_real_container_error(
    tmp_path, monkeypatch
) -> None:
    """F6 regression: attempt 1 applies cleanly but does not fix the bug
    (REPAIR_NOT_VERIFIED, a real classified attempt); attempt 2's
    acceptance run hits a real ``ContainerExecutorError``. The receipt must
    retain BOTH attempts (never silently drop attempt 1's real evidence),
    and the top-level/selected-attempt fields must consistently describe
    whichever attempt is actually reported as final -- never a mix of the
    two."""
    import each.executor.container as container_module

    monkeypatch.setattr(xodus_shadow_module, "fetch_file", lambda *_a, **_k: _CACHED_SOURCE)
    # A patch that applies and compiles cleanly but only fixes one of the
    # two bugged lines, so case1 of the real acceptance driver still fails
    # (hr stays E_POINTER) -- a genuine, cleanly classified REPAIR_NOT_VERIFIED,
    # not a PatchRejected/crash/ambiguous outcome -- before attempt 2 starts.
    wrong_patch = _APPLIES_BUT_LEAVES_BUG_PATCH

    original_run = container_module.ContainerExecutor.run
    call_count = 0
    # Calls: 1 probe, 2 baseline build, 3 baseline run, 4 attempt-1 build,
    # 5 attempt-1 run (real, classified REPAIR_NOT_VERIFIED), 6 attempt-2
    # build (real), 7 attempt-2 run -> forced ContainerExecutorError.
    FAIL_ON_CALL = 7

    def _flaky_run(self, command, worktree, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == FAIL_ON_CALL:
            raise container_module.ContainerExecutorError("simulated fixture container timeout (attempt 2)")
        return original_run(self, command, worktree, **kwargs)

    monkeypatch.setattr(container_module.ContainerExecutor, "run", _flaky_run)
    approved = _approve_selftest_spec("test-xodus-shadow-later-attempt-container-error")

    class SequenceModel(FixtureModel):
        def __init__(self, responses: list[str], model_id: str) -> None:
            super().__init__(responses[0], model_id=model_id)
            self._responses = responses
            self._call_count = 0

        def complete(self, prompt: str) -> str:
            response = self._responses[self._call_count]
            self._call_count += 1
            self.last_prompt = prompt
            return response

    model = SequenceModel([wrong_patch, _CORRECT_PATCH], model_id="fixture/xodus-shadow-selftest-sequence-v1")

    result = run_xodus_shadow_build(
        model, approved, max_attempts=2, run_id=f"selftest-later-timeout-{tmp_path.name}-{uuid.uuid4().hex[:8]}"
    )

    assert call_count == FAIL_ON_CALL
    assert result["outcome"].startswith("EXECUTION_ERROR")
    receipt = json.loads(Path(result["receipt_json"]).read_text())
    assert len(receipt["attempts"]) == 2
    assert receipt["attempts"][0]["outcome"] == "REPAIR_NOT_VERIFIED"
    assert receipt["attempts"][0]["build_result"] is not None
    assert receipt["attempts"][0]["run_result"] is not None
    assert receipt["attempts"][1]["outcome"].startswith("EXECUTION_ERROR")
    assert receipt["attempts"][1]["build_result"] is not None
    assert receipt["attempts"][1]["run_result"] is None
    # The reported top-level/selected fields must describe attempt 2 (the
    # real final attempt), never a stale mix with attempt 1's.
    assert receipt["selectedAttempt"] == 2
    assert receipt["outcome"] == receipt["attempts"][1]["outcome"]
