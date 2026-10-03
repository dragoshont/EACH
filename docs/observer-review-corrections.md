# Mandatory observer review correction — 2026-10-03

**P1 API-return acceptance: BLOCKED. Original production repair goal: unmet.**
Actual independent adversarial and security reviews of the frozen firstslice
returned REVISE. This correction does not authorize or adopt a narrower
process-response production product, provide R4 PASS, or extend the exhausted
three-task/nine-call utility budget.

## Actual reproduced mechanism and bounded correction

On predecessor `7d2400fa61a549bb76b7108c8d8bc2b14821a9cd`, public self-authored
synthetic controls were executed through the actual no-egress `colima-each`
executor and benchmark API:

| Control | Before correction | Corrected behavior |
|---|---|---|
| Print matching JSON and exit zero before requested function return | Observer response match; benchmark `REPAIR_VERIFIED` | Process response can match, but API classification is `REPAIRED_RUN_INCONCLUSIVE` |
| Monkeypatch `json.dumps`, substitute matching response while function returns the wrong value | Observer response match; benchmark `REPAIR_VERIFIED` | Same explicit process-response ceiling; never API repair verification |
| Emit JSON nested 20,000 levels (observed host recursion limit 1,000) | Actual `RecursionError` escaped observer and benchmark, no final receipt | Candidate JSON parse/compare recursion is incomplete; signed negative receipt retains fixture trajectory/patch/inputs |
| Ordinary matching return fixture | Matching response, previously counted as repair | Also inconclusive for the stronger API contract; not a loophole for apparently honest code |

Candidate code and serialization run in the same interpreter. Host expected
values and read-only/fresh containers do not authenticate a requested Python
function's execution/return. No token, captured JSON-function reference or
sentinel-only proxy is introduced. The original API contract remains unmet.

The observer's scope is now `sandboxed-process-response`, with
`apiReturnAuthenticated: false`. Complete-case counts denote complete process
responses, not proof of API invocation completion. The benchmark stops retries
on a matching response-only candidate without accepting a repair or running an
acceptance audit. `RecursionError` is caught only at the candidate JSON
parse/compare boundary, not broadly throughout the harness.

`python -m each.production_development` now returns exit **2** and bounded
`BLOCKED`/`API_RETURN_AUTHENTICATION_UNAVAILABLE` JSON for each historical task.
It has no exposed generation path and reports zero actual model calls.
This is enforcement of the existing exhausted/unqualified lane, not a new
product spec or silent change to a sensitive approved specification.

## F3: existing exact-firstslice gate evidence, not a rerun

The original development proof
`.architrave/evidence/8b43fe055d7f-526d336260fa-frozen-development-evidence.json`
did **not** contain the claimed 534/537 gate outputs. That proof and its hash
remain unchanged. The actual separate original gate artifacts were located,
verified against registered hashes and their exact execution SHA
`8b43fe055d7fe198bc90a5d1525260f920444153`:

| Existing artifact | Actual recovered result |
|---|---|
| `8b43fe055d7f-25b07ca07c8f-frozen-integrated-1.json` | Configured `bash gates/checks.sh`, exit 0, **534 passed, 3 skipped** |
| `8b43fe055d7f-35f87a7550c7-frozen-integrated-2.json` | Explicit audit/models pytest, exit 0, **537 passed, zero skips** |

Original artifact SHA-256, respectively:

```text
2c5518c09d8342e98454cac2d22b1b7b8ee489ce50557f9d887227d096bf5f26
c33639b3ae412f2c9b7dabc76b5dffcb490c38f17d683eb157e2a40cdfe86b3d
```

The source-free supplement contains exact commands, counts, execution SHA,
original artifact digests and stdout/stderr hashes, **not raw logs**:

```text
.architrave/evidence/8b43fe055d7f-8b5ef2c066d9-sourcefree-existing-8b-gate-supplement.json
SHA-256 143f6f02d24b24aeec96b4c42d1064fa31e6f5c61fa82353bdb320cc1aa392d9
```

Both unchanged old test commands were **not rerun**. The supplement is a
historical evidence projection, not new independent acceptance. Zero configured
invariant rules remain zero assurance of comprehensive invariants.

## Unchanged P3/P4 results and history

The [P3/P4 snapshot](production-p3p4-evidence.md) remains historical at its exact
frozen implementation. Both synthetic audit splits detected 8/8 exact and 4/4
renamed copies but falsely flagged 1/14 benign units (7.14% > 5%): P3 FAIL.
External membership and license scanning remain UNAVAILABLE.

P4 actual interruption, timeout, quota, permissions, artifact corruption,
concurrency and temporary-key restore measurements remain bounded operational
evidence. They do not repair the API-return trust boundary, imply zero
power-loss durability risk, or provide independent R4 acceptance.

Firstslice FAILED revision 69, P3/P4 FAILED revision 36, research COMPLETED
revision 102, all original negative signed receipts/retained inputs and the
user's signing key remain unchanged. Only public synthetic harness tests and
source-free correction evidence are new. No real inference, model loading or
weight download, private target publication, production tag or P5-P8 advancement.

## Frozen corrective implementation and gates

Implementation: `5505301b6e41adf26e799efc95ebcefba645666d`.
Corrective Run: `each-production-observer-review-fix-20261003`, revision **33**,
**FAILED**, `accepted: false`. Engineering tasks are development-gated complete;
F1/F2 independent R4 acceptance is UNTESTED. F3 recovered-evidence verification
is PASS from exact digest/count checks. The original API acceptance criterion
is canonical FAIL (unmet), publicly described as **P1 BLOCKED**—not a
fabricated waiting-for-human approval.

The changed-source integration cycle ran once: configured base **585 passed,
3 optional skips**; explicit audit/models **588 passed, zero skips**.
Ruff, doctor, wheel/sdist and Run schema/projection validation passed.
Targeted correction checks: **44 passed, zero skips**, including 12 new
regression cases. These are engineering facts, not API-return authentication,
fresh-install qualification or semantic/security/policy PASS.
The unchanged 8b gate commands were not rerun.

New ignored source-free evidence:

```text
.architrave/evidence/5505301b6e41-af1ae1f913dc-frozen-observer-correction-sourcefree-evidence.json
SHA-256 ad7a4c046320f4eaf3ca0c388b7bc939d71f392ce18f1c3a75835115e4b02aae
```

It includes the existing 8b supplement's source-free gate metadata as well as
new exact-SHA engineering results, observed attack/error mechanisms and
explicit acceptance ceilings. No raw logs, private target source, trajectory,
patch, model weights, signing key or canonical signed Run are published.

## Same-task final reader proof and permissions correction

This is a documentation/evidence closure, **not another implementation**.
`5505301b6e41adf26e799efc95ebcefba645666d` remains the tested code.
The [runbook](operator-runbook.md) now limits its 0700/0600 materials claim to
the explicit `Receipt.write(materials_source=...)` copy path. Observation
benchmark retention does not universally set those leaf modes; private
root/ancestor permissions provide the boundary. No new permissions framework
or code change is justified by the reported wording defect.

### Actual reader payload

```text
.architrave/evidence/5505301b6e41-893c37352e86-same-task-550-reader-closure-evidence.json
SHA-256 271191892c35a262021ff8f415d04317aa05bbf00094e5d5293fa17d0e31b86c
```

Unlike a hash-only summary, this file supplies all captured stdout/stderr from
the existing exact-550 configured/extras/Ruff/doctor/package commands. Private
store/home/checkout paths are redacted; original log and stdout/stderr hashes
remain separately available. The base includes actual progress, 585 passed/
3 skipped and doctor/CHECKS completion; extras includes 588 passed with no
skips; package includes actual wheel/sdist completion. The existing audit
calibration/holdout counts and original file hashes are also included—neither
dataset was reexecuted or retuned.

**44-targeted evidence ceiling:** the registered separate 8.85-second targeted
run was pre-freeze at a dirty `7d2400fa61a5` working tree. Its original captured
completion section and stdout hash are supplied. Its full raw stdout was not
retained; no complete log was fabricated from that hash or relabelled as clean
550 execution. The named controls are included in the existing clean-550
588-passed, zero-skip suite. A new `pytest --collect-only` query provides all
44 node identities without executing tests; unsafe candidate-code parameter
IDs are hash-redacted with private collection-path/hash references. Source
identity is checked against 550, including one checkout CRLF/LF-only difference.

The base's three skips are mapped from existing progress positions to unchanged
collection order and the optional `tree_sitter` import-or-skip definitions:

- `tests/adversarial/test_audit.py::test_renamed_copy_is_caught_by_ast_similarity`
- `tests/adversarial/test_audit.py::test_common_boilerplate_is_not_flagged`
- `tests/adversarial/test_audit.py::test_independently_written_semantic_equivalent_is_not_flagged`

### Actual new schema-only invocation

```text
.venv/bin/python harness/validate_run_v2.py \
  .architrave/runs/each-production-observer-review-fix-20261003

.architrave/evidence/5505301b6e41-a36fbd451e7c-same-task-closure-schema-invocation.json
SHA-256 9479ae2799186bf87d1040c793579beb6f281798c61d79c2f4d1f03d81d523da
```

Exit **0**, schema/projection **PASS**: actual Run **FAILED revision 33**,
34 events, two tasks, four criteria. The receipt includes actual schema stdout/
stderr, command, invocation commit and canonical Run digest. This is a new
schema check, not fresh product-test execution or production acceptance.

### Stale intake and protected history

The initial `each-production-p3p4-20261003` was still RUNNING revision 3,
with no worker, lease, attempt or uncertain side effect. Through supported
resume/fail-task/criterion/verify operations it is now **FAILED revision 9**,
with zero workers/leases/attempts and unchanged policy grants. No denied
task was launched; no artificial lease expiry or retrospective rewrite occurred.
Its READY task labels are nonlaunchable in a terminal Run.

```text
.architrave/evidence/86023c74bf8c-ce87d4d65375-stale-intake-supported-closure.json
SHA-256 f0fd495d50a5ccee4499bb9cb5466255ca9cb598e9dbba36299bc9979792df45
```

Reader proof checks unchanged canonical/event digests for firstslice **69**,
research **102**, P3/P4 **36** and corrective **33**; all three original
negative signed receipts and nine declared paths verify. User key bytes were
unchanged during closure. No unchanged code tests, model calls/downloads,
holdout reuse, default-branch publication, private release or production tag.
P1's original API-return acceptance remains BLOCKED and the production goal unmet.
