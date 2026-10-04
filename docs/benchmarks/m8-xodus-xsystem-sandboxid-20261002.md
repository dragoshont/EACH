# M8: private shadow repair attempt — `xgameruntime#22` (`XSystemGetXboxLiveSandboxId`)

**Date:** 2026-10-02
**Run:** `each-m0-m8` (durable `architrave.run.v2`), task `M8`
**Spec:** `each-m8-xsystem-sandboxid-opt` (immutable, human-approved, R4/sensitive)
**Spec hash (approved):** `2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78`
**Human approval:** genuine, spec-specific external checkpoint
`m8-genuine-human-spec-approval`, resolved with actual user-message evidence
("I approve the exact private M8 spec.", 2026-10-02T19:59:44+03:00),
registered as external proof `m8-user-spec-approval-20261002`. This approval
covers **only** this exact spec draft (content hash above); it does not
extend to any future sensitive spec, and no prior approval (M3, M7) was
reused or impersonated for it.

## What this is, and what it is NOT

A single, bounded, **private, shadow-only** demonstration repair attempt
against the public issue
[xodus-gaming/xgameruntime#22](https://github.com/xodus-gaming/xgameruntime/issues/22):
`XSystemGetXboxLiveSandboxId` incorrectly returns `E_POINTER` when its
documented *optional* (`_Out_opt_`, per public Microsoft GDK docs) output
parameter `sandboxIdUsed` is NULL. Target pinned at
`xodus-gaming/xgameruntime@791710510d9ba0746bbd60754215eb321800e4f0`
(LGPL-2.1), edit scope restricted to exactly one file, `xsystem.c`.

**This candidate was never submitted anywhere and never will be from this
run.** Per `policies/xodus-shadow.yml` (re-fetched and pinned against
upstream's current contribution policy immediately before this run, see
`docs/m8-xodus-policy-pin-20261002.md`): `ai_source_upstream_promotion:
false`, `no_upstream_pr: true`. Upstream's own current policy independently
rejects LLM-assisted code for repositories that interact with Microsoft/XBOX
services, which further confirms this must stay private and shadow-only.
**No upstream PR was opened, and none will be.** The candidate patch text,
its prompt, and its raw model completion are **not reproduced in this
report** and were never read by this cloud conductor or any cloud-hosted
reviewer — only source-free evidence (hashes, outcomes, policy-compliance
booleans, sanitized errors) is published here, exactly as enforced for M7.

The only material sources used were the public issue text itself and the
user's own explicit assertions in the approved spec (allowed paths, build
command, acceptance command) — never decompiler output, disassembly,
unauthorized runtime traces, or any proprietary implementation. Every
declared material's recorded origin is `PUBLIC_ISSUE` or `USER_ASSERTION`,
mechanically enforced for a sensitive spec (`MODEL_INFERENCE`/`UNKNOWN`/
`RESTRICTED` origins are rejected at spec-approval time).

## Pipeline executed (real, not simulated)

1. **Builder**: the declared local model (never this cloud conductor)
   generated a unified-diff patch against the approved spec's single
   allowed path (`xsystem.c`), inside a bounded retry budget (max 3
   attempts), using only the approved public problem statement as its
   prompt — never the human-known fix location or any discovered match
   content.
2. **Validate**: each candidate patch was scope-checked (rejecting any path
   outside `xsystem.c`), applied in an isolated worktree, and the declared
   build + acceptance commands
   (`examples/xodus-m8-sandbox-id/build_check.py build/run`) were executed
   inside the pinned, read-only, no-network `each-m8-native-runtime`
   container (`docker --context colima-each`). The acceptance harness
   compiles and exercises **one isolated function** against an
   independently-authored stub header (`winstubs.h`, EACH's own test
   scaffold — not derived from any Microsoft/Wine header) and asserts three
   behavioral cases: optional-NULL now accepted, required-NULL still
   rejected, insufficient-buffer still rejected. This is explicitly **not**
   a full Wine/winelib build and does not link the real DLL or exercise a
   real GDK/Xbox service — an assurance limitation, not a claim of complete
   native-runtime proof.
3. **Audit**: runs only after a validated (patched + passing) candidate;
   **terminal** — a rejected candidate ends the run; no audit result or
   audit-rejection feedback is ever fed back into a later Builder attempt.
4. **Attestation**: the full receipt (spec/model/attempt/executor/assurance/
   legal-flag fields, plus diagnostic stage hashes) is Ed25519-signed,
   excluding only its own attestation block.

## Genuine outcome: `PATCH_REJECTED`

All 3 bounded Builder attempts were rejected at the **validate** stage
before any audit ran (`audit.result: "UNAVAILABLE"`, reason: "no validated
candidate exists; terminal audit has not run" — correctly *unavailable*,
not a fake PASS). No candidate ever reached a passing test run, so
`repairedResult: {}` and `touchedPaths: []`. The signed receipt's top-level
`outcome` honestly reads: `"PATCH_REJECTED: patch does not apply cleanly to
xsystem.c: stale or mismatched context/removed lines starting at line 23"`
— the real reason the final attempt was rejected.

| Attempt | Outcome class                                                                 |
|---------|--------------------------------------------------------------------------------|
| 1       | `PATCH_REJECTED: malformed unified diff: Unexpected hunk found: @@ -24,7 +24,7 @@` |
| 2       | `PATCH_REJECTED: patch does not apply cleanly...starting at line 24`          |
| 3       | `PATCH_REJECTED: patch does not apply cleanly...starting at line 23`         |

**Correction note:** this run was initially (incorrectly) produced and
labeled by code that mislabeled every all-rejected run as the generic
sentinel `REPAIR_NOT_VERIFIED`, a bug class found by independent adversarial
review (GPT-family, confirmed by independent GPT- and Claude-family
re-reviews) in the shared M7/M8 pipeline code. The fix
(`each/xodus_shadow.py`: `final_outcome` initialized to `None` with a
post-loop fallback to the real last attempt's outcome, matching
`each/benchmark.py`'s established pattern) was applied, a regression test
was added (`tests/unit/test_xodus_shadow_selftest.py`), and this run was
**re-executed from the original approved spec** (never from any discovered
match content) to produce this freshly signed, honestly-labeled receipt:
run id `m8-xsystem-sandboxid-opt-20261002-corrected`. The original
mislabeled receipt at `~/.each/runs/m8-xsystem-sandboxid-opt-20261002/` is
preserved, unmodified.

A second, independent Claude-family reviewer additionally corrected the
*characterization* of the underlying public bug: it is an **over-strict
NULL-validation defect** (the code rejects a valid, documented-optional NULL
argument), not a "null-pointer dereference/crash" as an earlier internal
description loosely stated. This report uses the corrected characterization
throughout.

This is an **honest, mandate-compliant failure record** — the model did not
produce a passing, cleanly-applying patch within the bounded attempt budget
on this task. `REPAIR_NOT_VERIFIED` elsewhere in this project's receipts
(e.g. M7's own original attempt) specifically means "no patch validated,"
and must never be read as compatibility success; this corrected report goes
further and states the actual rejection reason per attempt, which is more
honest still.

## Model identity (real, local-only)

- `ibm-granite/granite-8b-code-instruct-128k@bed93d8de15bb9bb55cb1da10ae860e2883f4254#sha256:79fa25cb92f7851a`,
  Apache-2.0
- Runtime: `each.models.mlx_model` (`mlx-lm`), loaded directly from the
  original publisher bf16 safetensors (no conversion)
- Config/tokenizer/template/weights files all individually SHA-256 hashed
  in the receipt's `modelManifest`
- Generation: greedy, `temperature=0.0`, `maxTokens=1536`,
  `maxPositionEmbeddings=128000` (well within declared context budget)
- Zero cloud inference; the candidate was authored only by this declared
  local model, never by the outer Copilot/Architrave conductor

## Isolation and integrity evidence

- Executor: `each-m8-native-runtime@sha256:5e3fd3be8e066385dfa7eaf5bf7ef2a14a5e2090a6a8ba3227de5e9aeffb6baf`,
  `docker --context colima-each`, `network: none`, read-only root
  filesystem, `cpuLimit: 2`, `memoryLimit: 512m`
- Real outbound-connection denial probed from inside the executor:
  `connect(('1.1.1.1', 443))` → `errno 101` (`ENETUNREACH`), exit code 1
- Independent security review of the harness and policy-reuse code found
  no vulnerabilities (one already-disclosed, bounded residual gap: the
  container runs as its default/root user, mitigated by
  `cap-drop ALL`/`no-new-privileges`/read-only root/`network: none`,
  tracked in `docs/threat-model.md`)
- Independent policy-compliance check against `policies/xodus-shadow.yml`'s
  enforced clauses: PASS (no upstream PR, private-only, forbidden-sources
  enforcement, material-origin enforcement all verified against the real
  spec and receipt)
- Two independent semantic reviews of the harness (GPT-family, Claude-family)
  both returned PASS, including a fresh skeptical re-check specifically of
  the outcome-labeling fix described above
- Assurance level: `EACH-P2`

## Non-certification statement

`cleanroomCertification: false` and `legalCertification: false` are recorded
explicitly in the signed receipt. EACH produces authoring-provenance
evidence, not a legal clean-room or compatibility-certification opinion.
This report does not claim the underlying bug is fixed in any shippable
sense — no candidate ever passed validation. Any real-world determination
of patch correctness, legal provenance, or upstream acceptability requires
qualified human (and, for upstream contribution, maintainer) review this
harness does not and cannot provide.

## Conclusion

M8's acceptance criterion is the genuine shadow-only/no-upstream-promotion/
sensitive-spec-approval property, not "the model must produce a passing
patch." That property holds: a real, spec-specific human approval was
obtained and verified before any Builder call; build, validation, and
terminal audit ran for real inside a verified no-network, read-only
executor; the candidate was authored only by the declared local model;
no candidate, prompt, or completion was exposed to this cloud conductor or
any cloud review; policy explicitly forbids and this run did not attempt
any upstream submission. The honest, corrected outcome is `PATCH_REJECTED`
— the model did not produce a cleanly-applying patch within the bounded
attempt budget on this specific task.
