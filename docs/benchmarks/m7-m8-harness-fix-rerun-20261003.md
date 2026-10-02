# M7/M8 harness-fix re-run — real local-model evidence (2026-10-03)

**Scope:** this report documents two brand-new, real, local-model-only
re-runs of the already-approved M7 and M8 specs, produced after a bounded
harness fix. It does **not** supersede, overwrite, or re-sign the original
`m7-clean-room-lru-cache-real` or `m8-xsystem-sandboxid-opt-20261002`
receipts, which remain the sole original, immutable evidence for their
respective dates. See `docs/development-status.md` for the authoritative
summary row for each milestone, which this report's findings have been
folded into honestly.

## Why this re-run exists

Source-free diagnosis of the original receipts' rejected patches (only
structural line-prefix-class counts, numeric hunk-header fields, and
regex-redacted exception messages were ever inspected -- never raw
prompt/completion/patch content) found two real, generic defects in the
shared patch-handling/retry harness, not anything target-specific:

1. **Blank-context-line stripping.** The declared local model
   (`ibm-granite/granite-8b-code-instruct-128k`, Apache-2.0, original
   publisher weights, no conversion, revision
   `bed93d8de15bb9bb55cb1da10ae860e2883f4254`) frequently emits a
   zero-length line for what should be a unified-diff blank *context*
   line (a single leading space), which desyncs `unidiff`'s internal
   hunk-line-count bookkeeping and causes a later, otherwise-valid hunk to
   be rejected as `"Unexpected hunk found"`.
2. **No real retry diversity.** All 3 bounded retry attempts used fixed
   greedy decoding (`temperature=0.0`, no seed). Despite the retry-feedback
   suffix materially growing the prompt between attempts, the completions
   were byte-for-byte identical across all 3 M7 attempts in the original
   run -- the retry budget was not actually exploring different
   completions.

## Fixes applied (generic, not target-specific)

- `each/patch.py`: new `_restore_blank_context_lines()`, wired into
  `extract_patch_text()`. Mechanically turns an already-empty line found
  strictly between an opened `@@` hunk header and the next file-header
  boundary into a single space. Never touches any other line, never adds
  or removes a line, never operates outside an opened hunk.
- `each/models/base.py`: new concrete, no-op-by-default
  `RepairModel.configure_sampling(*, temperature, seed)` on the abstract
  base, so a backend/test-double that does not override it is completely
  unaffected.
- `each/models/mlx_model.py`: `MLXRepairModel` now has real, stateful
  sampling configuration; `identity()`'s `generationParameters` reports the
  **actual** temperature/seed/sampling-mode used for that completion
  (never a static hardcoded claim).
- `each/clean_room.py` / `each/xodus_shadow.py`: each per-attempt retry
  loop now calls `model.configure_sampling(temperature=0.0 if attempt_num
  == 1 else 0.2, seed=None if attempt_num == 1 else attempt_num)` right
  before `model.complete(prompt)` -- attempt 1 stays fully deterministic
  and reproducible; later attempts get a small, fixed, fully-recorded,
  attempt-indexed diversity budget.
- Full `tests/unit` suite (280 tests, including new regression coverage
  for both fixes) passes; Ruff clean.

## Fresh M7 re-run: `m7-clean-room-lru-cache-fresh-20261003`

Same already-approved spec (`each-m7-clean-room-lru-cache`, approved hash
`8499cf22255d11c15f1f446c19d504bec21ac03dfbe524439b2af377c65e39b8`,
unchanged), same already-cached model, zero new approvals, zero new
model downloads.

- **Outcome: `PATCH_REJECTED`** (3/3 attempts).
- Blank-line-prefix defect class: **eliminated** -- 0 malformed-prefix body
  lines in any of the 3 attempts (the original run's attempt 1 alone had
  12 such lines).
- Retry diversity: **confirmed working** -- completions were 1036/1024/485
  characters (genuinely distinct), versus the original run's 3x
  byte-identical 1036-character completions.
- Remaining, now-isolated real cause: the model's own declared hunk-header
  line counts (`old_len`/`new_len`) do not match the actual number of body
  lines it produced for that hunk -- a genuine model-accuracy/capability
  limitation for this specific black-box, from-scratch reimplementation
  task, not a harness defect.

## Fresh M8 re-run: `m8-xsystem-sandboxid-opt-fresh-20261003`

Same already-approved spec (`each-m8-xsystem-sandboxid-opt`, approved hash
`2c5eca88fdccb0c1a0c94541e0b612d990b7d1dfd5ccfb0389ea61fb9e669c78`,
unchanged), same pinned target
(`xodus-gaming/xgameruntime@791710510d9ba0746bbd60754215eb321800e4f0`,
`xsystem.c` only), same already-cached model, zero new approvals, zero new
model downloads, zero spec changes.

- **Outcome: `PATCH_REJECTED`** (3/3 attempts).
- Blank-line-prefix defect class: **eliminated** -- 0 malformed-prefix body
  lines in any of the 3 attempts (the original run's attempt 1 failed
  exactly this way: `"Unexpected hunk found"` with in-hunk blank lines
  lacking a leading space).
- Retry diversity: **confirmed working** -- completions were 1391/723/681
  characters (genuinely distinct).
- Remaining, now-isolated real cause: all 3 attempts now fail with an
  internally-inconsistent hunk header (declared old/new line count does
  not match the attempt's own hunk body) -- a real model-accuracy
  limitation reproducing an exact patch against the real pinned source,
  not a harness defect, format bug, or spec-sufficiency problem.

## What this does and does not establish

- **Does establish:** the two identified harness defects were real, are
  now fixed, and are independently verified fixed via real local-model
  runs (not just unit-test assertion) -- the blank-line defect class is
  gone and retry diversity genuinely works.
- **Does not establish:** a verified M7 or M8 repair. Both fresh runs
  still end `PATCH_REJECTED` for a different, now more precisely
  identified reason (hunk-header line-count accuracy), which is a model
  capability limit for this declared checkpoint on these specific tasks,
  not something further harness changes alone can fix without either
  inventing structure the model did not produce (forbidden) or using a
  different/stronger model (out of scope for this bounded session: "no
  new models/downloads").
- Neither original receipt (`m7-clean-room-lru-cache-real`,
  `m8-xsystem-sandboxid-opt-20261002`) was read, mutated, re-signed, or
  regenerated by this work. Both fresh receipts are new, independently
  signed, immutable artifacts under their own new run ids.
- As with the original runs: `audit: UNAVAILABLE` on both fresh receipts
  (terminal audit never runs without a validated, applied, test-passing
  candidate), `legalCertification`/`cleanroomCertification: false`, no
  upstream PR opened, no shadow/strict candidate source published or
  reviewed in the cloud. Full project acceptance of M7/M8 remains pending
  further review.
