# M8 sensitive-spec review packet: each-m8-xsystem-sandboxid-opt

**Status: APPROVED.** The user genuinely approved this exact, unchanged
draft ("I approve the exact private M8 spec.", 2026-10-02T19:59:44+03:00).
The coordinator independently re-verified the draft content hash was
unchanged before sealing the approval record
(`~/.each/specs/each-m8-xsystem-sandboxid-opt/approved.json`, approved hash
`2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78`). The
real external proof is registered as `m8-user-spec-approval-20261002`; the
`m8-genuine-human-spec-approval` checkpoint was resolved through the
existing resolve API (no fabricated or reused approval). This packet is
retained as the historical record of what was reviewed and approved, not a
live pending decision.

This packet exists so a human (`dragoshont`) could decide whether to approve
or reject the exact immutable spec draft below. This was a **new, separate**
decision from the M3 (`pallets-itsdangerous-410-review`) and M7
(`each-m7-clean-room-lru-cache`) approvals already on record; neither of
those approvals was extended to this spec, and no prior approval was reused
or impersonated here.

- **Task id:** `each-m8-xsystem-sandboxid-opt`
- **Draft content hash:** `f6f5b61f6eb082eb608fedd9d00854e9aec72e401f5c17c826eb3c7cff25b33f`
- **Approved hash:** `2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78`
- **Draft location (private):** `~/.each/specs/each-m8-xsystem-sandboxid-opt/draft.json`
- **Risk:** R4 (sensitive — governed by `policies/xodus-shadow.yml`)
- **External checkpoint:** `m8-genuine-human-spec-approval` (RESOLVED, Run `each-m0-m8`)

## What this spec authorizes

A single, bounded EACH repair run against a public open-source target:

- **Target:** `xodus-gaming/xgameruntime` (LGPL-2.1), pinned at commit
  `791710510d9ba0746bbd60754215eb321800e4f0`.
- **Public issue:** [xgameruntime#22](https://github.com/xodus-gaming/xgameruntime/issues/22)
  — `XSystemGetXboxLiveSandboxId` returns `E_POINTER` when its documented
  *optional* `sandboxIdUsed` output parameter is NULL, breaking real,
  commercially shipped Game Pass titles (the issue reporter's own traced
  game list and failure claims -- "9 of 10 titles calling it with
  `sandboxIdUsed = NULL` during startup; Balatro and DREDGE both fail to
  proceed" -- are third-party reports from the public issue text, not
  independently reproduced or verified by EACH).
- **Independently confirmed against public Microsoft GDK docs** (fetched
  live, see `docs/m8-xodus-policy-pin-20261002.md`): `sandboxIdUsed` is
  documented `_Out_opt_` (optional); `sandboxId` is documented
  `_Out_writes_bytes_to_(...)` (**not** optional — must remain required).
- **Allowed edit scope:** exactly one file, `xsystem.c` — no other file.
- **Build command:** `python3 examples/xodus-m8-sandbox-id/build_check.py build xsystem.c`
  — mechanically extracts the one function this issue concerns (by
  signature text, never by the human-known fix location), compiles it in
  an isolated, independently-authored stub harness (`winstubs.h`, EACH's
  own test scaffold, not derived from any Microsoft/Wine header file).
- **Acceptance command:** `python3 examples/xodus-m8-sandbox-id/build_check.py run`
  — asserts 3 behavioral cases: (1) `sandboxIdUsed=NULL` with a valid
  buffer now succeeds instead of `E_POINTER` (the actual bug fix); (2)
  `sandboxId=NULL` still correctly returns `E_POINTER` (it remains
  required, not accidentally relaxed); (3) a too-small buffer still
  correctly returns the existing insufficient-buffer error (no regression).
  *Validated by hand against both the real unmodified buggy source and a
  hand-written fix during spec preparation — both behave as expected.*
- **Forbidden sources (enforced):** `proprietary-implementation`,
  `decompiler-output`, `disassembly`, `unauthorized-runtime-trace`.
- **Sensitive-origin enforcement:** every declared material field's origin
  is `PUBLIC_ISSUE` or `USER_ASSERTION` — none is `MODEL_INFERENCE`,
  `UNKNOWN`, or `RESTRICTED` (mechanically rejected for a sensitive spec).

## What this spec explicitly does NOT authorize

- **No upstream PR, ever**, for this or any xgameruntime/xodus candidate
  (`policies/xodus-shadow.yml`: `ai_source_upstream_promotion: false`,
  `no_upstream_pr: true`). Upstream's own current contribution policy
  (pinned, re-fetched fresh — see the policy pin doc) independently
  confirms LLM-assisted code is rejected outright for repositories like
  `xgameruntime` that interact with Microsoft/XBOX services.
- **No cloud review of the generated candidate.** The candidate patch, its
  prompt, and its raw model completion are never printed into this
  conversation or reviewed by any cloud-hosted model — only source-free
  evidence (hashes, pass/fail outcomes, policy-compliance booleans) ever
  surfaces here, exactly as enforced for M7.
- **No claim of full native compile/runtime proof.** The build/acceptance
  harness compiles and runs *one isolated function* against an
  independently-authored stub header — it does **not** perform a full
  Wine/winelib build, does not link against the real DLL, and does not
  exercise a real Xbox/GDK service. The receipt records this plainly as an
  explicit assurance limitation (mandate section 63: native Xodus
  validation is not yet proven and must not be misreported as P2).

## What approval means

This approval authorized exactly this one bounded repair attempt against
exactly this pinned source, through EACH's existing sealed, no-network
Builder/validate/audit/attestation pipeline (the same machinery already
proven for M1–M7) — nothing broader, and nothing that bypasses
`policies/xodus-shadow.yml`. The real executed outcome is recorded in
`docs/development-status.md`'s M8 row and in the private receipt at
`~/.each/runs/m8-xsystem-sandboxid-opt-20261002/receipt.json`
(`REPAIR_NOT_VERIFIED`; no verified repair).

## How this was approved

The approval was recorded via:
`uv run python3 -m each.cli spec approve each-m8-xsystem-sandboxid-opt --human dragoshont`
then resolved through the existing Run API with genuine message evidence
(the real external proof `m8-user-spec-approval-20261002`, never
fabricated).
