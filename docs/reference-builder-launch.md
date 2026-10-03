# Reference Builder: first qualified Xodus experiment

**Status: COMPLETE — negative result (`PATCH_REJECTED`).**
This is a new experiment, not reuse of the historical M8 one-attempt approval.
The registry now authorizes the retained StarCoderBase artifact after
original-file, conversion and signed-runtime verification. Model qualification
is no longer the launch blocker. The user subsequently approved this exact
displayed Spec and asked execution to proceed. Approval does not extend to
future Specs.

## Exact proposed run

| Field | Value |
|---|---|
| Task | `each-launch-sandboxid-98510d3ac7c3` |
| Draft SHA-256 | `9fc83e8b91ff421ba05367781eb486ccb3e2abe68f57904b5f4e7b533f211606` |
| Approved Spec SHA-256 | `6e3f2736aa810ffa443c6a3ba139058d9d048f5644f719cd5f0afac024fd5d25` |
| Evidence SHA-256 | `e41d362603bb6b1a8aaf53b8c8af5c64d9f2d569ae5047e9bb644215e4eebf2a` |
| Initial Builder | `starcoderbase-mlx`, exact `bigcode/starcoderbase@88ec5781ad071a9d9e925cd28f327dea22eb5188`, retained qualified FP16 conversion only |
| Conversion record SHA-256 | `48bc14f9240345e8c81a5586e71a9f0ce7102fdc9ac80ded74199869653dbed7` |
| Target | `xodus-gaming/xgameruntime@791710510d9ba0746bbd60754215eb321800e4f0` |
| Permitted edit | `xsystem.c` only, bounded `XSystemGetXboxLiveSandboxId` behavior |
| Attempts | One local completion; at most 4,096 output tokens within the model's context limit |
| Proposal format | Existing `full_source` mode; EACH derives the scoped diff |
| Visibility | Private candidate, raw prompt/response and Auditor results |
| Prohibited | Cloud target authoring/review, dirty source or implementation advice, Auditor feedback, upstream submission |

## Actual result

Run `reference-base-sandboxid-98510d3ac7c3` invoked the authorized retained
StarCoderBase artifact exactly once. The response proposed no change from the
pinned public source, so the harness returned **`PATCH_REJECTED`** before
candidate compilation or tests. No retry, model substitution or hand-authored
target change occurred.

- Baseline acceptance exit: **1**, as required to exercise the documented bug.
- Candidate validation: **not run**; there was no candidate.
- Terminal Auditor: **not run**; there was no validated candidate subject.
- Network-denial probe: **verified**.
- Receipt assurance: **EACH-P1**. Although network isolation verified, the
  shared pipeline conservatively downgrades the overall label when no candidate
  reaches protected-material integrity verification.
- Signed receipt and all three declared retained materials: **PASS**.
- Receipt SHA-256:
  `28683ef83ac69c9954956391b0684035298f8fa8686fb1f68ae0b643f41a219b`.
- Trajectory SHA-256:
  `961c9b6b45563f478f2bb14927b518d2959f0c062d7670fba94a4a727e389c45`.
- Input/output token counts, completion-call seconds, decoder throughput and
  peak memory: **UNAVAILABLE** for this historical call; none is inferred.

This satisfies the launch-cycle requirement to perform a first real, bounded,
authorized provenance experiment. It does **not** establish repair capability,
full Xodus/Wine/game compatibility, production readiness, legal clean-room
status or upstream acceptability.

The existing full-source prompt is instruction-shaped, not native base-model
FIM. This known capability limitation will be recorded. Format rejection or a
failed repair is an acceptable observed result, not permission to substitute
another model or hand-edit its implementation. No new prompt adapter,
fine-tuning or infrastructure is a launch prerequisite.

## Builder-facing requirement

Implement the public `XSystemGetXboxLiveSandboxId` contract in the permitted
upstream source. `sandboxIdUsed` is optional (`_Out_opt_`): null must not reject
an otherwise valid call with a correctly sized `sandboxId` buffer.
`sandboxId` remains required. An undersized buffer retains the documented
insufficient-buffer error. Preserve behavior outside this bounded API issue.

These requirements come from the independently retrieved
[Microsoft GDK API documentation](https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xsystem/functions/xsystemgetxboxlivesandboxid?view=gdk-2604),
document revision `7d9199cfc63c9541bc65cc0b60c940b7e5baafe2`.
The Spec binds the evidence hash above and identifies this as private research,
not game compatibility or upstream-acceptance proof.

The open [xodus-gaming/xgameruntime#22](https://github.com/xodus-gaming/xgameruntime/issues/22)
identified the question. **Its raw body and implementation advice are excluded
from Builder input.** No dirty implementation or summarized fix is admitted.

## Existing independent validation

Build:
`python3 examples/xodus-m8-sandbox-id/build_check.py build xsystem.c`

Acceptance:
`python3 examples/xodus-m8-sandbox-id/build_check.py run`

The existing harness checks the optional-null output case and protects the
required-buffer and insufficient-buffer regressions. It compiles one extracted
public upstream C function with independently authored stubs; it is not a
native Wine/GDK DLL or full-game test.

Fresh preflight on the pinned public source: **build exit 0, acceptance exit 1,
EACH-P2 isolation**. No model ran during preparation. Raw preflight evidence,
public-document bytes and material hashes are retained privately.

Current upstream target and contribution-policy revisions were fetched again.
The policy remains at `ae13b61ce23f68e376e6f0562d5a690e41bd1587` and rejects
LLM-assisted code for this API-layer work. This experiment does not override it.

Approval applied only to the exact draft hash and the run envelope above.
No approval is inferred from program authorization, model-access consent,
historical M8 approval, or this document's existence.

## Executed entry point

After genuine approval was recorded through the existing Spec workflow, the Mac
used the APIs below. The fixed run ID now prevents silently repeating the call.

```python
from each.models.catalog import load_model
from each.spec_workflow import load_approved_spec
from each.xodus_shadow import run_xodus_shadow_build

approved = load_approved_spec("each-launch-sandboxid-98510d3ac7c3")
model = load_model("starcoderbase-mlx", max_tokens=4096)
result = run_xodus_shadow_build(
    model,
    approved,
    max_attempts=1,
    run_id="reference-base-sandboxid-98510d3ac7c3",
    proposal_format="full_source",
)
```

The project used its declared `models` and `audit` extras. Keep the resulting
receipt and target artifacts in the existing private store; expose only the
source-free outcome and verification summary.
