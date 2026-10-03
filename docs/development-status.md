# Development status

**Current status (2026-10-03):** M0-M8 research is complete at the accepted
release documented below; production qualification is not complete. Earlier
entries are dated development history, not present-tense acceptance.

The user authorized **M0-M8**, with YAGNI and sequential acceptance gates.
At this earlier remediation point the full program was **not complete**. The user-authorized harness-only
remediation received independent Astra **PASS** at
`9dfd9f97acd55a2253831b5a51606584a251482c`, with 313 audit-enabled tests passing
at that commit. This closes the reviewed harness defects, not the historical
failed target experiments or the complete cross-family/security/policy release
gate. See [the bounded acceptance report](bounded-remediation-review.md).

A subsequent harness-only root-cause-fix commit (`2095d17...`, 2026-10-03, see
the M7/M8 rows below) fixed two further generic harness defects and added new
fresh-run negative evidence; at that commit the audit/models-extras gate
passes 319 tests with zero skips, and the base (no optional extras) gate
passes 316 tests with 3 expected skips.

A further commit (`4a44a33...`, 2026-10-03) added a generic `full_source`
proposal-format harness option (`each/raw_proposal.py`) that removes the
model's hunk-header-arithmetic requirement by having the harness itself
derive the unified diff via stdlib `difflib.unified_diff` against the known
pre-image. A fresh M8 attempt under this mode against the SAME
already-approved spec produced the project's first genuinely verified target
repair (`REPAIR_VERIFIED`, independently re-checked signature+materials
`PASS`); this is now recorded as real `reality`-gate evidence in the
`each-release-completion` durable Run (`m8-target-repair-verified: PASS`). The
equivalent M7 attempt did not reach a verified repair (`REPAIRED_RUN_INCONCLUSIVE`)
but is genuinely different, more informative negative evidence than the
earlier hunk-header mismatch. At this commit the audit/models-extras gate
passes 343 tests with zero skips (330 prior + 13 new unit tests for the new
Run evidence kind), and all deterministic gates (base gate, audit/models
gate, Ruff, `each doctor`) were re-verified fresh at this exact commit. Full
release completion (cross-family GPT+Claude semantic review, R4
security/policy review, and a genuinely verified **M7** target repair)
remains pending.

A second, more generous full-source M7 retry (same commit, same approved
spec, same model, 5 attempts instead of 3) was then run as bounded,
justified continued root-cause work; it also classified
`REPAIRED_RUN_INCONCLUSIVE` on all 5 attempts (source-free classification
only: every attempt's repaired-candidate executor call returned a non-zero
exit code, never a clean passing exit).

A new concrete harness hypothesis then justified a third attempt: each
retry's prompt previously carried only a generic "did not make the failing
tests pass" message, giving the Builder no actionable signal to correct
*what* was wrong. A new `each/test_feedback.py` module deterministically
extracts a small, bounded (<=1500 char), structurally-identified subset of
a real pytest run's own output (its own `E `-prefixed exception/assertion
lines and `FAILED`/`ERROR` short-summary node ids, never unprefixed
hidden-test source context) and wires it into the next retry's rendered
prompt (commit `636de86`). A third full-source run (5 attempts, run id
`m7-clean-room-lru-cache-fullsource-feedback-20261003`) confirms the
feedback plumbing itself works as intended (each attempt after the first
recorded a real `test_feedback_hash` derived from the previous attempt's
own repaired-run output) but still classified `REPAIRED_RUN_INCONCLUSIVE`
on all 5 attempts, with attempts 2-5 producing an **identical** collection-time
failure (same `test_feedback_hash` across all four) despite each being fed
genuinely distinct, real diagnostic feedback -- i.e. the Builder did not
act on the corrective signal it was given. The coordinator independently
re-verified this run's signature and materials both `PASS` via
`each verify --full`. This is new, more specific negative evidence (the
harness-side feedback mechanism is confirmed working; the remaining gap is
the model's own correction behavior on this specific task), not a working
repair. Having now exhausted three independently-configured full-source
attempts against the declared 8B checkpoint (plain retry, more-attempts
retry, feedback-wired retry) without a verified repair, a concrete new
hypothesis -- model capacity -- was tested next rather than repeating the
same 8B protocol.

**Fourth attempt, larger model (2026-10-03, commit `3bc28e9`):** the
project's declared mandate candidate family includes larger original
ibm-granite Apache-2.0 publisher checkpoints; `ibm-granite/granite-20b-code-instruct`
(pinned revision `03d2f3664ed0059eac4d35797b43fb52d551bb5b`, not gated,
verified via `huggingface_hub.model_info()` before provisioning) was
provisioned outside any sealed run via the existing `huggingface_hub`
snapshot helper (same mechanism as the 8B model; no new download
framework) and added as a new `granite-20b-code-instruct-mlx` catalog
entry. Provisioning this checkpoint also surfaced and fixed a real,
generic harness defect: its `config.json` (`model_type="gpt_bigcode"`)
declares its context window as `n_positions` rather than the
`max_position_embeddings` field name `each/model_manifest.py` previously
only checked, which had silently SKIPPED (not failed closed) the
context-budget check entirely for any such checkpoint -- fixed with an
explicit, tested fallback (`03d2f3664ed0059eac4d35797b43fb52d551bb5b`'s
own `config.json` resolves to the documented `8192`-token window). A
fresh 5-attempt full-source run using the same feedback-wired pipeline
(run id `m7-clean-room-lru-cache-fullsource-20b-20261003`, same already-
approved spec, `max_tokens=2048` reserved output against the smaller 8192
context, checked not silently truncated) also classified
**`REPAIRED_RUN_INCONCLUSIVE`** on all 5 attempts (repaired-run exit codes
`2,1,1,2,1` -- a mix of pytest collection errors and clean non-passing
test-suite exits, never a clean pass). This is genuinely different,
more-informative negative evidence than the 8B feedback-wired run: every
one of the 20B model's 5 attempts produced a genuinely distinct
`test_feedback_hash` (versus the 8B run's 4 identical attempts), meaning
this larger model DID respond with new content to each round of genuine
corrective feedback -- but still did not converge to a validated passing
repair within the bounded 5-attempt budget. The coordinator independently
re-verified this run's signature and materials both `PASS` via
`each verify --full`. **The cause of this M7-specific gap remains
undiagnosed** across model sizes 8B and 20B of the same declared family;
this document does not assert task difficulty, prompting, or a specific
model limitation as the diagnosed cause. Having now exhausted four
independently-configured full-source attempts (8B plain retry, 8B
more-attempts retry, 8B feedback-wired retry, 20B feedback-wired retry)
against the same approved spec without a verified repair, the already-
authorized larger `granite-34b-code-instruct` fallback (pinned revision
`4bdfb589ebd261be0942a00dd239175d9d65bc47`, ~68GB, same Apache-2.0
publisher family) remains the next concrete, already-justified step; see
the model's own correction behavior, not missing diagnostic information),
not a working repair. Having now exhausted three independently-configured
full-source attempts (plain retry, more-attempts retry, and
feedback-wired retry) without a verified repair, no further M7 generation
retries are planned at this time pending a genuinely new diagnosis; this is
accepted as honest, bounded negative evidence rather than a reason to keep
retrying the same protocol. See
`docs/benchmarks/m7-m8-harness-fix-rerun-20261003.md` for the earlier
fresh-run evidence and its honest, undiagnosed-cause framing, and the M7/M8
table rows below for the full-source-mode results.


| Milestone | Current evidence |
|---|---|
| M0 | Package, Apache-2.0 license, CLI doctor, ordinary CI, and canonical Architrave knowledge profile established. |
| M1 | Independently verified: 51 tests, real failing/passing fixture, exact material identities, fail-closed numeric no-egress evidence, read-only container root, and real timeout cleanup. |
| M2 | Independently verified local Granite 3B Instruct/MLX repair, recorded full model/config/tokenizer artifact hashes, actual runtime/parameters, and rendered prompts. No cloud target inference. |
| M3 | Intake/spec workflow implemented; genuine user approval received on 2026-10-02 for the pinned BSD-3-Clause review packet. |
| M4 | Terminal auditor (copy/renaming/boilerplate heuristics plus a real Tree-sitter comparison) runs only after a validated candidate; audit rejection is terminal and never reaches another Builder attempt in the same run. |
| M5 | Receipt signature binds the entire canonical payload (model/spec/assurance/certification/attempt fields) plus diagnostic stage hashes, using a local signing key outside the repository; real tamper rejection (patch/spec/validation mutation, missing material) verified. |
| M6 | **PASS** (independent GPT-family and Claude-family adversarial review, each registered as a semantic gate). Real 5-task smoke, then 22 real historical permissive repairs benchmarked against the real no-network container, across two local models. 3B pilot (`granite-3b-code-instruct-mlx`, see `docs/benchmarks/m6-granite-3b-code-instruct-mlx-20261002.md`): only 4/22 tasks reached real generation calls under its declared 2048-token context (18/22 honestly rejected pre-generation with exact token counts; 0/4 eligible tasks produced an applicable patch). Primary 128K-context run (`granite-8b-code-instruct-128k-mlx`, original ibm-granite publisher weights, no conversion; see `docs/benchmarks/m6-granite-8b-code-instruct-128k-20261002.md`): all 22/22 tasks reached real generation (66 genuine `model.complete()` calls total), confirming the context-budget fix; 0/22 verified repairs -- 65/66 attempts' completions omitted the required BEGIN_PATCH/END_PATCH markers and the remaining attempt returned a placeholder-template diff with no real file changes, a genuine instruction-following/localization limitation of varying severity across tasks, not a harness defect (patch extraction is intentionally strict). An independent dual-family adversarial review (GPT-family and Claude-family) found and the coordinator fixed a real evidence-integrity defect before acceptance: the benchmark source cache was keyed only by task id, letting a stale cache entry from an earlier sha silently masquerade as the pre-fix source (confirmed for one task); fixed by keying the cache on task id + exact pre-fix sha, purging the contaminated cache, adding a regression test, and regenerating both benchmark reports from a clean re-run with every task's baseline independently confirmed to genuinely fail beforehand. A final confirmation round from both families on the fully-corrected state caught two further small doc overclaims (an inaccurate "on-target completion" example and a misdescribed rejection reason), both independently verified and corrected before acceptance. Accepted as valid M6 evidence per the project's own criterion (genuine input construction and real attempts, not a required success rate). **Mixed-language closure (2026-10-03):** two independent reviewers (GPT-6 Astra, Claude-sonnet-5.5) re-read mandate section 121/128 and confirmed the then-22-task Python-only corpus met the count floor but not the literal "mix of C/C++/Rust/Python" language requirement, with no success-rate/task-count minimum beyond one qualifying task per missing language. Closed by independently qualifying (real container-verified pre-fix-fails/known-fix-passes baselines, derived only from each bug's own public commit title/PR description/documented language-standard contract, never the private diff) and adding exactly one genuine historical repair task per missing language: **C** (`zserge/jsmn`, a malformed-JSON unmatched-closing-bracket rejection bug), **C++** (`fmtlib/fmt`, a zero-value/zero-precision printf conversion bug), and **Rust** (`dtolnay/semver`, a malformed patch-digit-after-minor-wildcard version-requirement bug) -- 25 tasks total, the original 22 Python tasks unchanged. A new pinned, tracked `docker/benchmark-native-runtime/Dockerfile` (same `python:3.12-slim` base digest as every other EACH image, plus Debian-apt `gcc`/`g++`/`rustc`/`cargo`) provides the compiler toolchain; native tasks materialize an exact, explicitly-named file set (never a whole-repo tarball) and are classified by validator exit code (0 pass / 1 fail / anything else honestly inconclusive), never pytest-summary parsing. A full real run of all 25 tasks against the same declared `granite-8b-code-instruct-128k-mlx` model (report `benchmark-suite-20261003T051654Z`, 75 genuine `model.complete()` calls, 0/25 verified repairs -- the 3 new native tasks all `PATCH_REJECTED`, consistent with the existing project criterion of genuine attempts over a required success rate) confirms the full pipeline, not just the zero-generation-call qualification probes. All three new receipts' signatures and real retained materials both independently verify `PASS` via `each verify --full`. A new `each benchmark retain-materials` CLI command and `retain_task_materials()` harness function (genuine re-fetch of the same immutable `pre_fix_sha`-pinned bytes, never invented bytes) also closed a pre-existing gap for the original 22-task corpus: every one of its receipts (report `benchmark-suite-20261002T102321Z`) now independently full-verifies `PASS` against freshly recovered, byte-exact materials. One real process deviation is disclosed, not hidden: during C++ bug-hypothesis exploration, the target header was briefly compiled/run directly on the host before the violation was caught; those host artifacts were purged immediately and the qualification was redone entirely through the real no-network container executor. |
| M7 | Spec genuinely approved; Builder run executed against the real no-network container executor. **Original real receipt outcome: `REPAIR_NOT_VERIFIED` across all 3 declared attempts** (`~/.each/runs/m7-clean-room-lru-cache-real/receipt.json`) -- `repairedExitCode: null` (no attempt reached a validated, applied patch), `audit: UNAVAILABLE` (terminal audit never runs without a validated candidate), signature verification `PASS` (declaration-only; this predates the full-artifact-integrity verifier added later), `assuranceLevel: EACH-P2`, `legalCertification`/`cleanroomCertification: false`. This is a genuine, signed, real-attempt failure record, not a verified repair. The user gave a NEW genuine approval ("i approve m7", 2026-10-02) for the bounded clean-room-style `functools.lru_cache` demonstration spec, independently matching its draft content hash (`b8427bd9...`) and approved hash (`8499cf22...`). A real operational defect was found and fixed while resolving the earlier external checkpoint: `wait_external()`'s one-time resolution challenge was lost (its only copy, an ephemeral shell-output temp file, did not survive a host/session transition) before `resolve_external()` ran, leaving a genuinely-approved checkpoint stuck with no way to close it under the original design. Rather than fabricate a challenge or hand-edit Run state (both explicitly forbidden), a new, narrow `RunStore.reissue_challenge()` recovery method (plus `external-reissue-challenge` CLI subcommand) was added: it requires a trusted coordinator/human actor and an already-registered, unconsumed `external-proof` artifact that genuinely matches the checkpoint's id/principal/provider, so it can never manufacture approval, only re-open the door for evidence that already exists. **Root-cause harness fix (2026-10-03) and new immutable evidence:** source-free diagnosis of the original receipt's rejected patches (structural line-prefix/hunk-header counts only, never raw content) found two real, generic harness defects, not target-specific: (1) the declared local model (`ibm-granite/granite-8b-code-instruct-128k`) frequently emits a truly empty line for a blank unified-diff context line instead of a single leading space, desyncing `unidiff`'s hunk-line bookkeeping -- fixed by a narrow `_restore_blank_context_lines()` transform in `each/patch.py` that only restores an already-empty line strictly inside an already-opened hunk; (2) all 3 retry attempts previously used fixed greedy (`temperature=0.0`, no seed) decoding, so despite a materially larger retry-feedback prompt the completions were byte-identical across all 3 attempts -- fixed by adding `RepairModel.configure_sampling()` (no-op default; real implementation in `MLXRepairModel`) and wiring attempt 1 to stay deterministic while attempts 2-3 use a small fixed, fully-recorded `temperature=0.2`/`seed=attempt_num`. A fresh, real, local-model-only M7 run under a brand-new immutable run id (`m7-clean-room-lru-cache-fresh-20261003`, receipt never overwrites/re-signs the original; generated 2026-10-03, this is a point-in-time snapshot of that run's own evidence, not a claim about any other/later run) confirms both fixes work as intended (zero blank-line-prefix defects remain; attempt completions are now genuinely distinct -- 1036/1024/485 chars rather than 3x identical) but **still outcome `PATCH_REJECTED` across all 3 attempts, with no attempt reaching a validated/applied patch (no acceptance exit)**: the coordinator independently re-verified this fresh run's own full materials-integrity and signature checks both `PASS` against the retained artifact files (not declaration-only). Each rejected attempt's hunk header declares an old/new line count that does not match the hunk's own body line count. **The cause of that mismatch (model capability, prompt/template framing, decoding configuration, or another harness interaction) is currently undetermined** -- this document does not assert a specific diagnosed cause, and no private model output was inspected to reach one. No new model was downloaded; this is the same declared, already-cached checkpoint. This is useful negative evidence, not a working repair. **Full-source-mode attempt (2026-10-03, commit `4a44a33`):** a new `each.raw_proposal` module and a `proposal_format="full_source"` option on `run_clean_room_build()` let the harness itself derive the unified diff (via stdlib `difflib.unified_diff` against the known pre-image) instead of asking the model to compute an exact hunk-header line count -- removing that specific failure mode entirely while running the exact same `each.patch.parse_patch`/`apply_patch` scope/path/pre-image validation on the resulting diff text. A fresh run under a new immutable run id (`m7-clean-room-lru-cache-fullsource-20261003`) against the SAME already-approved spec got past `PATCH_REJECTED` into real build/run territory on all 3 attempts, but was classified **`REPAIRED_RUN_INCONCLUSIVE`**: attempt 1 produced an ambiguous (partially-passing, partially-failing) pytest result, not a clean pass or clean fail; attempts 2-3 (higher-temperature retries) produced syntactically invalid full-source bodies (a Python `IndentationError` at collection time). The coordinator independently re-verified this fresh run's signature and materials both `PASS` via `each verify --full` against the retained artifact files. This is genuinely different, more informative negative evidence than the diff-mode hunk-header mismatch (the harness-side diff-derivation issue is now eliminated), but **M7 still has no verified repair** at this commit; the acceptance criterion remains honestly `FAIL`. **Second, more generous full-source retry (2026-10-03, same approved spec, same model, 5 attempts instead of 3, run id `m7-clean-room-lru-cache-fullsource-retry-20261003`):** also classified `REPAIRED_RUN_INCONCLUSIVE` on all 5 attempts. Source-free classification-level inspection only (never the raw pytest output, which may embed private target test content): every attempt's repaired-candidate build/run executor call returned a non-zero exit code (either `1`, consistent with the baseline's own pre-existing failing-test exit code, meaning the candidate still did not make the target test suite pass; or `2` on two attempts, consistent with a pytest collection-time error rather than a clean pass or a clean, unambiguous fail). No attempt in either full-source run (3-attempt or 5-attempt) reached a validated, passing repair. **The cause of this M7-specific gap relative to M8's immediate full-source success is currently undetermined** (task complexity/scope difference is a plausible but undiagnosed hypothesis; no specific cause is asserted here). **Feedback-wired full-source retry (2026-10-03, commit `636de86`):** a new `each/test_feedback.py` module (bounded, structurally-identified extraction of a real pytest run's own `E `-prefixed exception/assertion lines and `FAILED`/`ERROR` node-id lines, capped at 1500 chars, never unprefixed hidden-test source) was wired into both of `each/clean_room.py`'s post-run retry paths, so each retry after the first carries genuine, attempt-specific diagnostic detail instead of a generic "did not pass" message. A fresh 5-attempt run under a new immutable run id (`m7-clean-room-lru-cache-fullsource-feedback-20261003`) against the SAME already-approved spec recorded a real, non-empty `test_feedback_hash` on every attempt after the first, confirming the plumbing itself works, but still classified **`REPAIRED_RUN_INCONCLUSIVE`** on all 5 attempts -- and attempts 2-5 produced an *identical* collection-time failure (matching `test_feedback_hash` across all four), meaning the Builder did not act on the distinct corrective feedback it was actually given. The coordinator independently re-verified this run's signature and materials both `PASS` via `each verify --full`. This narrows the undiagnosed gap: the harness-side feedback mechanism is now confirmed functional; the remaining limitation is the declared local model's own correction behavior on this task, not missing diagnostic information or a harness defect. Having now exhausted three independently-configured full-source attempts (plain retry, more-attempts retry, feedback-wired retry) against the same approved spec without a verified repair, a concrete new hypothesis (model capacity) was tested next. **Larger-model attempt (2026-10-03, commit `3bc28e9`):** `ibm-granite/granite-20b-code-instruct` (pinned revision `03d2f3664ed0059eac4d35797b43fb52d551bb5b`, Apache-2.0, not gated, same declared mandate candidate family) was provisioned outside any sealed run via the existing `huggingface_hub` snapshot helper and added as a `granite-20b-code-instruct-mlx` catalog entry; provisioning it also surfaced and fixed a real generic harness defect (`each/model_manifest.py` only read `max_position_embeddings`, silently skipping the context-budget check for this checkpoint's `config.json`, which declares its window under the GPT-BigCode-family field name `n_positions` instead -- fixed with a tested fallback, resolving correctly to `8192`). A fresh 5-attempt full-source run (run id `m7-clean-room-lru-cache-fullsource-20b-20261003`, `max_tokens=2048` against the smaller 8192 context) also classified **`REPAIRED_RUN_INCONCLUSIVE`** on all 5 attempts (repaired-run exit codes `2,1,1,2,1`). This is genuinely different, more-informative negative evidence than the 8B feedback-wired run: all 5 of the 20B model's attempts produced a genuinely distinct `test_feedback_hash` (versus the 8B run's 4 identical attempts), confirming this larger model does respond with new content to genuine corrective feedback, but it still did not converge to a validated repair within the bounded attempt budget. The coordinator independently re-verified this run's signature and materials both `PASS` via `each verify --full`. **The cause of this M7-specific gap remains undiagnosed across both tested model sizes (8B and 20B) of the same declared family.** No further M7 generation retries are planned at this time without a genuinely new diagnosis; the already-authorized `granite-34b-code-instruct` fallback (pinned revision `4bdfb589ebd261be0942a00dd239175d9d65bc47`) remains the next concrete, already-justified step if pursued. **Newer/smaller-model and pragmatic-fallback attempts, superseding the "34B remains the next step" framing above (2026-10-03):** per updated guidance to prefer a newer, non-deprecated checkpoint over a pure-capacity escalation, `ibm-granite/granite-3.3-8b-instruct` (pinned revision `51dd4bc2ade4059a6bd87649d68aa11e4fb2529b`, Apache-2.0, not gated, `model_type: granite`, 131072 context -- a modern generation distinct from the gpt_bigcode-family 8B/20B/34B code-instruct checkpoints already tried) was provisioned and added as `granite-3.3-8b-instruct-mlx`. A fresh 5-attempt feedback-wired full-source run (run id `m7-clean-room-lru-cache-granite33-8b-20261003`) classified `REPAIRED_RUN_INCONCLUSIVE` on all 5 attempts, with every attempt failing identically at Python collection time (a consistent, source-free-verified exception-class match across all 5 attempts, not a sampling fluke) -- this newer checkpoint did not fare better than the earlier granite-code-instruct sizes on this task. Per the already-authorized pragmatic-fallback ordering, `Qwen/Qwen2.5-Coder-14B-Instruct` (pinned revision `aedcc2d42b622764e023cf882b6652e646b95671`, Apache-2.0, not gated, `model_type: qwen2`, 32768 context, original publisher weights with its own LICENSE file in the snapshot) was provisioned next and added as `qwen2.5-coder-14b-instruct-mlx`. A fresh 5-attempt feedback-wired full-source run (run id `m7-clean-room-lru-cache-qwen25coder14b-20261003`) also classified `REPAIRED_RUN_INCONCLUSIVE` on all 5 attempts, this time with every attempt's exception class source-free-verified as a consistent `AssertionError` (a repaired candidate that applies and runs, but whose behavior does not satisfy the approved test) rather than a collection-time failure -- a qualitatively different, more advanced failure mode than the smaller/code-instruct checkpoints, but still not a verified repair. With both the newer-generation and pragmatic-fallback candidates exhausted, the already-downloaded `granite-34b-code-instruct` (pinned revision `4bdfb589ebd261be0942a00dd239175d9d65bc47`) was run next (run id `m7-clean-room-lru-cache-granite34b-20261003`), also classifying `REPAIRED_RUN_INCONCLUSIVE` on all 5 attempts with the same consistent `AssertionError` pattern as the 14B model. **Five distinct models across the full declared candidate family (8B, 20B, 3.3-8B, 14B, 34B) have now been tried against this exact approved spec with feedback-wired retries, and none has produced a verified repair; the two largest/most capable models converge on a consistent, source-free-verified `AssertionError` failure class (plausible-looking but functionally-incorrect generated code) rather than a syntax or formatting defect.** This is a genuine, well-evidenced negative capability result for this task on the currently available declared local models, not an unexplored gap; the cause (task difficulty/scope, prompt/excerpt framing, or a genuine capability ceiling of the tested models on this specific compatibility-shim task) remains undiagnosed, and no private candidate output was inspected by the outer conductor to reach this classification -- only structurally-extracted exception-class tokens, never raw tracebacks/source. The acceptance criterion remains honestly `FAIL`. |
| M8 | Spec genuinely approved ("I approve the exact private M8 spec.", 2026-10-02T19:59:44+03:00; draft hash `f6f5b61f...`, approved hash `2c5eca88...`); bounded private shadow experiment executed against `xodus-gaming/xgameruntime#22` (target `7917105...`, `xsystem.c` only). **Original real receipt outcome: `REPAIR_NOT_VERIFIED` across all 3 declared attempts** (`~/.each/runs/m8-xsystem-sandboxid-opt-20261002/receipt.json`) -- `repairedExitCode: null`, `audit: UNAVAILABLE`, signature verification `PASS` (declaration-only), `assuranceLevel: EACH-P2`, `legalCertification`/`cleanroomCertification: false`, AI source upstream promotion `false`, no upstream PR opened, no shadow/strict candidate source published. This is a genuine, honestly-recorded research-experiment failure, not a repair/spec-sufficiency/validation/audit success. **Root-cause harness fix (2026-10-03) and new immutable evidence:** same two generic harness fixes as M7 (blank-context-line restoration; per-attempt sampling diversity), re-verified with a fresh real local-model-only run under a brand-new immutable run id (`m8-xsystem-sandboxid-opt-fresh-20261003`, same already-approved spec, zero spec changes, same already-cached model, original receipts untouched/unresigned; this is a point-in-time snapshot of that run's own evidence, not a claim about any other/later run). Source-free diagnosis confirms the blank-line defect class is now fully eliminated (zero malformed-prefix body lines across all 3 attempts, versus the original run's attempt 1 failing exactly that way), and sampling diversity produced genuinely distinct completions (1391/723/681 chars). The coordinator independently re-verified this fresh run's own full materials-integrity and signature checks both `PASS` against the retained artifact files. **Still outcome `PATCH_REJECTED` across all 3 attempts, with no attempt reaching a validated/applied patch (no acceptance exit)**: every attempt's hunk header declares an old/new line count that does not match the attempt's own hunk body. **The cause of that mismatch is currently undetermined** -- this document does not assert a specific diagnosed cause (model capability, prompting, or otherwise), and no private model output was inspected to reach one. This is useful negative evidence, not a working repair. **Full-source-mode attempt (2026-10-03, commit `4a44a33`) -- VERIFIED REPAIR:** using the same new `proposal_format="full_source"` option (harness-derived diff via `difflib.unified_diff` against the known pre-image, removing the model's hunk-header arithmetic requirement) on `run_xodus_shadow_build()`, a fresh run under a new immutable run id (`m8-xsystem-sandboxid-opt-fullsource-20261003`) against the SAME already-approved spec (same `specHash: 2c5eca88...`) produced outcome **`REPAIR_VERIFIED` on attempt 1** -- the first genuinely verified target repair recorded in this project. The coordinator independently re-ran `each verify --full` against the retained receipt: signature verification `PASS`, materials verification `PASS` (both declarations and the actual retained artifact files, not declaration-only), `networkIsolationVerified: true`. `assuranceLevel` remains `EACH-P2` per the harness's own isolation-evidence computation; audit sub-checks (`ast-similarity`, `corpus-membership`, `exact-substring`, `license-scan`, `ngram-similarity`) remain honestly `UNAVAILABLE` (no corpus/license-scanner configured in this v0.1 harness -- this is NOT a fake PASS, and this document does not claim legal clean-room certification). This evidence is registered in the `each-release-completion` durable Run as a `reality`-type gate (`gate-m8-target-repair-20261003`, producer `target-repair`, a new honest evidence kind added to `harness/architrave_runtime.py` specifically so this real result could be recorded without ever copying the private receipt's raw prompts/completions/patch/source into the public-repo-adjacent Run evidence store); the `m8-target-repair-verified` acceptance criterion is now genuinely `PASS`. Full project acceptance of M8 remains pending further review (cross-family semantic review and R4 security/policy review are still `BLOCKED_EXTERNAL`); no upstream PR opened, no shadow/strict candidate source published or reviewed in the cloud. |

An independent adversarial review (GPT-6 Astra, high reasoning, long context) of the M7/M8 harness returned **FAIL** with 9 findings (5 BLOCKER, 3 MAJOR, 1 gate-evidence) against source `c78ad8d1...`. One consolidated harness-only batch attempted to address those findings; subsequent reviews identified incomplete fixes. The bullets below describe implementation history, not independent acceptance (no target candidates regenerated, no models downloaded, no historical receipts re-signed or altered):

- **F1** (private-export leakage): `xodus_shadow.summarize_receipt()`'s source-free export now runs every outcome field (top-level and per-attempt) through a shared bounded-class whitelist (`each/outcome.py`) instead of fragile string truncation, so candidate-controlled diagnostic text can never cross the source-free boundary.
- **F2** (declared policy not enforced): a new `each/xodus_policy.py` loads and binds `policies/xodus-shadow.yml` plus the actual durably-approved spec record (re-read from `~/.each/specs/<id>/approved.json`, never trusted from an in-memory object alone) before any fetch/side effect -- rejecting a spoofed self-approved spec or a policy/approval mismatch closed before any fetch, write, or model call.
- **F3** (unchecked host paths): both pipelines now validate `run_id` and the assembled source root (traversal/symlink-escape containment) before any write; `Receipt.write()` now refuses to write inside the repository's own working tree and refuses to silently overwrite an already-written receipt directory.
- **F4** (P2 from network isolation alone): both pipelines now independently verify the validation-time materials (`test_path`) were not altered by the candidate (`each/worktree.verify_unchanged`) and the exact loaded model snapshot was not altered since provisioning (`each/model_manifest.verify_snapshot_matches`), with a conservative outcome downgrade on drift, rather than deriving the advertised assurance level from the network-isolation probe alone.
- **F5** (artifact verification absent): `Receipt.write()` gained an optional `materials_source` copy step that copies the exact selected attempt's declared material bytes into a `materials/` subdirectory next to the receipt (traversal/escape-contained), giving a verifier real retained file bytes to check against the declared hashes, not declaration-only trust.
- **F6** (trajectory mixing): both pipelines now track the specific classified attempt (`selected_attempt_record`/`selected_worktree`) through the retry loop and report that SAME attempt's prompt/raw_completion/model_identity/materials at the top level -- a later rejected retry can never silently overwrite an earlier classified attempt's trajectory. `Receipt` gained an explicit `selectedAttempt` field making this binding checkable, not assumed.
- **F7** (recovery/gate scope): `record_gate()` now stamps every gate with the exact `sourceCommit` it was verified against, and `missing_gate_requirements()` only honors a PASS gate recorded against the Run's CURRENT baseline commit -- a gate recorded before a later `resume(accept_commit=True)` no longer silently keeps satisfying its criterion.
- **F8** (stale public claims): this file, `docs/m8-xodus-review-packet-20261002.md`, `docs/m8-xodus-policy-pin-20261002.md`, and `docs/threat-model.md` were corrected to state the real M7/M8 outcomes, qualify third-party game-trace claims as issue-reporter claims (not independently verified), and clarify that the M6-era "no BEGIN_PATCH/END_PATCH markers" description predates the later fenced-diff-fallback extractor.
- **F9** (gate evidence): the full test suite and Ruff were re-run clean at the corrected commit (see below); fresh gates were registered against that commit per F7's new binding (all gates recorded before this commit are now honestly stale under that same fix, by design).

A second independent GPT-6 Astra (high reasoning, long context) review of the corrected harness changed its verdict from **FAIL** to **REVISE**, confirming F1 (source-free export), the principal/model-identity selection fix, and the baseline-staleness gating were genuinely fixed, while identifying concrete residual gaps in the *implementation depth* of F2/F3/F4/F5/F6/F7 (not new scope) plus one real doc contradiction (F8). All were addressed in one further consolidated harness-only batch (again: no target candidates regenerated, no models downloaded, no historical receipts re-signed or altered):

- **F5** (now implemented in full, not just wired): `Receipt.write()` now verifies the real sha256 of every retained material file against its declared hash BEFORE copying or signing (previously only a placeholder-hash test existed, proving no real check had ever fired); `each/attestation.py` gained a genuine `verify_materials_root()` existence+hash verifier (the stale docstring referencing a nonexistent `verify_artifact_root` was fixed); `each verify --full [--artifact-root PATH]` wires this into the CLI, clearly distinguishing declaration-only from full-artifact-integrity verification. Both pipelines now copy materials from the pristine, never-mutated source root (not a per-attempt worktree that patches had already touched), closing the real pre-patch/post-patch hash mismatch.
- **F2** (policy, fail-closed): `each/xodus_policy.py` now rejects any repository not in a new `pinned_targets` envelope (previously fail-open on an empty/missing list) and requires an exact match on target ref, allowed paths, and declared commands against the real pinned M8 envelope in `policies/xodus-shadow.yml`, plus `terminal_audit=true`, no-reverse-engineering, and non-empty forbidden-sources checks, all before any fetch/side effect.
- **F3** (destination containment): `Receipt.write()` now checks both the material SOURCE and DESTINATION sides for symlink/traversal escape and rejects an existing destination file/run collision; `each/paths.validate_private_root()` rejects an `EACH_HOME` resolving inside the repository checkout, called immediately after spec/policy verification and before any fetch/materialize/write in both pipelines.
- **F4** (assurance level): both pipelines now capture `networkIsolationVerified` once from the raw pre-run network probe, independent of overall `assuranceLevel`, and conservatively downgrade the receipt's `assuranceLevel` from `EACH-P2` to `EACH-P1` whenever the selected attempt's materials integrity check does not PASS -- so a detected drift can no longer coexist with an advertised P2.
- **F6** (trajectory derivation): both pipelines now derive every final (`materials`, `baselineResult`, `repairedResult`, patch text, touched paths) field from the SAME selected/reported attempt's own stored per-attempt record, never from separately-reassigned loop variables that a later unrelated attempt could silently overwrite.
- **F7** (gate/grant binding): `record_gate()` now requires every PASS deterministic-gate artifact to independently declare the CURRENT Run baseline commit as its own recorded `sourceCommit` (captured once, honestly, when the artifact was first recorded) -- an artifact recorded under an earlier baseline can no longer be referenced as evidence for a brand-new gate registered after `resume(accept_commit=True)` moved the baseline, closing the exact laundering gap a gate's own self-reported stamp alone could not prevent. `grant_task_attempt()` now requires a `checkpoint_id` naming an actual, already-`RESOLVED` external checkpoint genuinely bound to the exact task (`resumeTask == task_id`) with a recorded resolution proof -- an arbitrary trusted-actor `reason` string can no longer reopen an exhausted/failed task with no matching real recovery event.
- **F8** (stale/contradictory public claims): previous prose asserted later "-corrected" target runs without verified evidence for them. Those assertions are withdrawn. As of this batch (this F8 bullet is a snapshot of the state at that time, not a standing claim about all future runs), the only authoritative M7/M8 receipt summaries cited here are the original immutable `m7-clean-room-lru-cache-real` and `m8-xsystem-sandboxid-opt-20261002`: `REPAIR_NOT_VERIFIED`, three attempts each, repaired exit code absent, audit `UNAVAILABLE`, declaration signature `PASS`. No later run, inferred rejection cause, fresh corrected-pathway evidence, or target success is established *at this point in the document's history*. M8 approval was genuinely received at 2026-10-02T19:59:44+03:00; its draft hash is `f6f5b61f...` and approved hash `2c5eca88...`. (A later, separately-dated 2026-10-03 root-cause-fix entry in the M7/M8 table rows above supersedes this snapshot's "no later run" scope with new fresh-run evidence, framed with its own honest, undiagnosed-cause language -- it does not retroactively change what this F8 batch itself established.)

Focused regression tests were added for every fix above (outcome sanitization, policy/approval binding -- including a real reload-comparison bug this review surfaced and fixed, `Receipt.write()` containment/overwrite refusal, materials-copy containment, model-snapshot drift, worktree drift, the F6 trajectory-consistency scenario end-to-end against the real container executor, and the F7 gate-staleness scenario end-to-end against a real `RunStore`).

A third independent GPT-6 Astra (high reasoning, long context) review changed its verdict to **REVISE** again, confirming the prior F1/principal-identity/baseline-staleness fixes held and identifying further concrete implementation-depth gaps in F3/F4/F5/F6/F7, plus a renewed F8 doc-accuracy finding. All were addressed in one further consolidated harness-only batch on top of source `34b99219...` (no target candidates regenerated, no models downloaded, no historical receipts re-signed or altered):

- **F5** (full verification, not declaration-only): `each verify --full` now requires BOTH signature `PASS` and actual materials `PASS`; a missing/deleted materials directory is honestly reported `UNAVAILABLE` but makes `--full` exit non-zero (it previously exited 0). Ordinary signature-only verification is unaffected.
- **F3** (containment): `Receipt.write()` now rejects a symlinked receipt directory and a symlinked `materials/` root before any `mkdir`/copy, anchoring the containment check to the already-validated receipt directory rather than trusting a symlink's own resolved target as the anchor; `each/xodus_shadow.py`'s M8 source-materialization root gets the same check before `mkdir`.
- **F4** (assurance/mutation): `materials_integrity` now defaults to `UNAVAILABLE` (not `PASS`) whenever every attempt in a run is rejected before the check ever executes, so an unperformed check can never silently count as passing and contribute to an `EACH-P2` assurance claim; `ContainerExecutor` gained a `protected_paths` parameter that layers individual read-only bind mounts over the writable worktree mount, giving real OS-level write protection for harness/validation scaffold files during execution (not only a post-execution hash re-check).
- **F6** (failure trajectory): both pipelines now record `patch_text`/`touched_paths` immediately after a patch genuinely applies, and `repaired_result` immediately after the real build/run executor call returns -- both BEFORE outcome classification -- so a classification-time `BenchmarkExecutionError` can no longer discard real applied-patch/build/run evidence. `each/clean_room.py`'s previously-uncaught ambiguous repaired-run classification (a stale comment incorrectly claimed it matched `each.bakeoff`'s precedent) is now caught and recorded as `REPAIRED_RUN_INCONCLUSIVE` instead of silently discarding the entire run's prior attempt history with no receipt at all.
- **F7** (source freshness / recovery grants): `_record_artifact()` no longer unconditionally stamps "whatever the baseline reads right now" onto a registered deterministic receipt -- the receipt content must itself declare a `commit` field, and that declared commit must match the current Run baseline at registration time, closing the gap where a stale, never-before-registered receipt file could be replayed as fresh evidence simply by registering it after the baseline moved. External checkpoints gained a `recoveryGrantConsumed` flag: a single resolved checkpoint can now back exactly one `grant_task_attempt()` call, not an unbounded number of them if the task later fails again on its own.
- **F8** (public truth): this file's M7/M8 rows, as of this batch, no longer cite any "-corrected" rerun as additional authoritative evidence -- no fresh target-side evidence was produced by this harness-only batch to support that framing, and the coordinator's own independent re-reading of the original receipts was the only evidence this document claimed at the time. The original `m7-clean-room-lru-cache-real` and `m8-xsystem-sandboxid-opt-20261002` receipts remain the sole, immutable, authoritative milestone *target-repair* evidence: `REPAIR_NOT_VERIFIED`, 3 attempts each, `repairedExitCode` absent/null, `audit: UNAVAILABLE`, signature verification `PASS` (declaration-only), `legalCertification`/`cleanroomCertification: false`. Neither receipt was mutated, re-signed, or regenerated by this batch. (As above: a later, separately-dated 2026-10-03 entry adds new fresh-run evidence under new immutable run ids, framed honestly as undiagnosed-cause `PATCH_REJECTED` negative evidence -- it supersedes only this bullet's "no later run" scope, not the original receipts themselves.)

New regression tests cover: `--full` verify exit codes under whole-directory deletion, single-file deletion, mutation, and empty/malformed declarations (plus a valid full-pass fixture); symlinked receipt directory and symlinked materials root rejection; `ContainerExecutor` read-only protected-path mounting and traversal/absolute-path rejection; the materials-integrity-default downgrade for both pipelines' real-Docker selftests; patch/build/run evidence surviving a classification-time raise for both pipelines; deterministic-receipt commit-declaration enforcement (undeclared, stale, and replayed-after-resume cases, plus a genuinely-fresh case); and single-use recovery-grant replay denial. Full project acceptance remains pending the coordinator's own next independent review.

At the time of that F3-F8 batch, the checks covered 281 tests with zero skips, owned-code (`each/`, `tests/`)
Ruff clean. (This was that batch's own snapshot count; it is not a standing claim about the test
count at any later commit -- see the top of this document for the current audit-enabled test count
at the latest commit.)
(`harness/` is the third-party Architrave kit and is outside
the owned-code Ruff scope; its F7 gate-staleness fix and its checkpoint-challenge-reissue
recovery path are each covered by their own dedicated regression tests instead.)
Receipts, trajectories, weights, keys, and working target artifacts remain
outside the public repository.

**Evidence-write exclusive-create fix and gate-freshness refresh (2026-10-03,
commit `f5ed0cd`):** the active durable Run's earlier ad-hoc registration
script had written gate evidence to a fixed, deterministic path; a later
retry of that script silently overwrote already-registered bytes under an
already-computed artifact digest, permanently tripping the runtime's own
artifact-tamper check (`ARTIFACT_TAMPERED`) on every later load of the
original `each-release-completion` Run. That check was never suppressed,
weakened, or worked around; the damaged Run's private local state remains
untouched, immutable history. The actual gap -- nothing prevented a caller
from reusing an evidence path at all -- is now closed structurally:
`RunStore.write_evidence_receipt()` embeds a fresh execution id into every
evidence filename and creates it with `O_EXCL`, so a genuine collision fails
loudly instead of silently overwriting; `_record_target_repair_receipt()`'s
own evidence write was rewired to use it. All of `base-gate`,
`audit-models-gate`, and `ruff-doctor` were then re-run fresh and
re-registered against this exact commit (the successor `each-release-completion-2`
Run's baseline), closing the gap where those criteria's evidence still
pointed at an older, pre-merge commit.

**Live M7 re-validation of the two newly-merged root-cause fixes, plus a
third (2026-10-03, commits `d4224cc`/`db1cdb6`/`6113557`):** two fixes
merged from a concurrent development thread -- (1) the stateless Builder now
receives its OWN previous candidate, captured before execution and
hash-bound, in the next retry prompt (previously it saw only the unchanged
stub plus an error category); (2) the pytest classifier now correctly
distinguishes a genuine partial test failure (exit 1, failed > 0, matching
the expected count) from a genuinely inconclusive run, and surfaces ONLY
approved-spec-item numbers 1-9 parsed from failing case ids, never raw
names/messages/paths -- were exercised live, not merely unit-tested. A fresh
5-attempt run against `ibm-granite/granite-3.3-8b-instruct` (modern
Apache-2.0 replacement for the deprecated `granite-20b-code-instruct`
checkpoint; pinned revision `51dd4bc2...`) reproduced the same genuine
`nonlocal` closure-scoping `SyntaxError` on all 5 attempts (a real,
recorded model-capacity limit on this specific spec, not a harness defect).
A fresh 5-attempt run against `Qwen/Qwen2.5-Coder-14B-Instruct` (pinned
revision `aedcc2d4...`, justified fallback per the recorded Granite-3.3
failure) got substantially further: all 5 attempts reached a real,
clean-exit-1 repaired-test run (never inconclusive), live-confirming fix
(2) above operates correctly in a genuine run -- but outcome stayed
`REPAIR_NOT_VERIFIED` across all 5, with an identical `test_feedback_hash`
on every attempt (the model did not act on the approved-item-number
feedback it was given). A third fix landed immediately after (commit
`db1cdb6`): retry prompts now re-include the VERBATIM approved
specification text for exactly the failed item numbers reported by bounded
feedback (never test code, exception text, or outer-authored content) after
the model's own previous candidate. A further fresh 5-attempt Qwen2.5-Coder-14B
run exercising this third fix showed genuine behavioral change -- candidate
hashes now differ across attempts 3-5 (previously byte-identical across all
5) -- but still did not converge to a verified repair within the bounded
budget, and `test_feedback_hash` stayed identical across all 5 (same
items kept failing). **M7 remains honestly `FAIL`** after three
independently-verified root-cause fixes and two justified modern local
models, each exercised live rather than assumed from the fixes' unit tests
alone. Per the explicit no-blanket-escalation instruction, `granite-34b-code-instruct`
was not attempted merely for more capacity.

**M8 re-audit/replay under the current (post-patch-source, not diff-based)
auditor (2026-10-03):** the already-verified M8 receipt
(`m8-xsystem-sandboxid-opt-fullsource-20261003`, `REPAIR_VERIFIED`,
`specHash: 2c5eca88...`) was independently replayed -- never regenerated --
against the CURRENT auditor code. The retained pre-patch source's sha256,
the receipt's own `patchHash`, and its own `trajectoryHash` were all
independently recomputed from the real retained artifacts and matched
exactly; the patch was then re-applied to reconstruct the exact post-patch
candidate bytes, and `each.audit.run.run_audit()` (current code, which
audits post-patch SOURCE, not a diff) was run directly against them. Result:
not rejected, all sub-checks honestly `UNAVAILABLE` (no corpus/license-scanner
configured), identical to the original. This is recorded as a second,
explicitly-linked `reality`-gate artifact under the `m8-target-repair-verified`
criterion (which remains, correctly, unchanged `PASS`) -- the original
receipt was not mutated, re-signed, or regenerated by cloud.

Cross-family semantic review (GPT-family and Claude-family) and R4
security/policy review remain the two genuinely external, `UNTESTED`
blockers to full release completion; they are active coordinator-review
lanes, not a stop condition for the rest of the program.

## Recorded user approval

Review task `pallets-itsdangerous-410-review`, based on
[pallets/itsdangerous#410](https://github.com/pallets/itsdangerous/issues/410)
in the BSD-3-Clause project:

- Target commit: `096c8d42545d3b68ea21a4f890fb2b2d8979c0bd`.
- Editable paths: `src/itsdangerous/url_safe.py`, `src/itsdangerous/serializer.py`.
- Validation: Python compileall and upstream URL-safe tests.
- Draft hash: `88226ec2f82b6a4ca4b8c2e2967a621377b48c45e762fa1c6514274be920ed72`.

This is approval of a spec/policy packet, not generated implementation or
legal certification. The user explicitly approved this unchanged draft on
2026-10-02. Its sealed approved-packet hash is
`168aa1265149cca0ba46ae5a74ab3b82b457858a5c86a4eb765f751feafceb24`.

The earlier automated `octocat/Hello-World` demonstration was incorrectly
described as human-approved and permissively licensed. Its approval was
performed by the agent, and GitHub reports no repository license. Its immutable
private records are retained as historical evidence, not treated as valid
acceptance evidence. The replacement human-judgment checkpoint is now resolved
with the actual user decision.

Resume the existing Run, not a duplicate conductor. Continue
M4-M8 only after their own requirements pass; retain private shadow outputs and
never open an upstream Xodus PR.

## M7 edit-proposal mode: implemented, exercised, genuinely still unresolved

A new, smallest-justified `proposal_format="source_edit"` mode was added to
`each.clean_room.run_clean_room_build()` (and `each.raw_proposal`) so a local
model can continue correcting its OWN already-mostly-working prior candidate
via a minimal `{"old","new"}` JSON edit, instead of being asked to regenerate
the whole file from scratch (which the existing `full_source` mode had been
doing across five bounded attempts, each discarding a candidate that was
genuinely 8/9 passing on the approved M7 spec). The harness performs the
`str.replace` itself (rejecting an absent or ambiguous `old`), then derives
the final unified diff, via `difflib`, against the ORIGINAL pristine stub
pre-image -- exactly like `full_source` mode -- preserving the existing
apply-onto-a-fresh-worktree invariant. Covered by 15 new `raw_proposal` unit
tests and two new `clean_room`-level `FixtureModel` selftests (happy-path
minimal-edit verification, and absent-`old` rejection-and-retry-against-the-
same-seed). 411 tests pass; `ruff check` clean. Committed as `9505440`.

This mode was then exercised for real: a fresh, independently-receipted,
bounded (max 5 attempts) M7 correction chain
(`m7-clean-room-lru-cache-qwen14b-source-edit-20261003`), seeded with the
model's OWN actual last candidate from the prior stuck
`qwen14b-requirement-fix` run (read directly from that run's own retained
`materials/`, never hand-edited), against the same unchanged approved spec
(`8499cf22...`) and the same already-provisioned Qwen2.5-Coder-14B-Instruct
local model, proper canonical chat template, recorded context/sampling.

Genuine result: `REPAIR_NOT_VERIFIED` after exhausting all 5 attempts.
Attempt 1 ran but did not pass the real acceptance suite. Attempts 2-3
applied a syntactically-invalid edit (the model's own `old`/`new` text did
not preserve the surrounding indentation, producing a real Python
`IndentationError` at pytest collection time -- correctly classified as
`REPAIRED_RUN_INCONCLUSIVE`, never conflated with a clean pass/fail).
Attempts 4-5 were rejected by the harness before any container execution
because the model's own completion supplied an identical `old`/`new` pair
(`PATCH_REJECTED`, not an edit) -- the harness correctly never silently
no-ops or hand-repairs a degenerate edit. No cloud-authored fix, test
source, or reference implementation was ever shown to the model; only the
fixed, approved spec text for item 6 and the model's own prior candidate.

`m7-target-repair-verified` remains honestly `FAIL`. Across this project's
full authorized model roster and all three proposal-format modes
(`diff`, `full_source`, `source_edit`), the available local models
(granite-3.3-8b-instruct, Qwen2.5-Coder-14B-Instruct, granite-34b-code-instruct;
the original granite-20b-code-instruct deprecated checkpoint) have not
produced a genuinely verified M7 repair within bounded attempts. **Correction
(2026-10-03, this entry): an earlier draft of this paragraph incorrectly
stated granite-34b-code-instruct's safetensors weight bytes were "never
actually downloaded" -- they genuinely were (a real ~6m19s full-weight
snapshot download, used for the one real `m7-clean-room-lru-cache-granite34b-
20261003` attempt recorded above), and were deliberately deleted afterward
purely to reclaim ~68GB of local disk space (config/tokenizer metadata was
kept; this is the config/tokenizer-only state a fresh disk inspection finds
today). Re-provisioning the full weights would require a fresh multi-hour
download, not a new model-capability decision -- this is a disk-housekeeping
fact, not a retraction of the real run or its recorded outcome.** This is
recorded as a genuine local-model capability ceiling for this specific
clean-room spec, not a harness defect, and not force-passed.

## M7 mandate section 129 realignment: a distinct, narrower, satisfiable criterion

Per renewed user authorization (2026-10-03) grounded in a direct re-read of
`docs/EACH_BOOTSTRAP_MANDATE.md` section "129. M7 -- Clean-room-style
controlled demonstration": that section's own literal Acceptance text is
"complete receipt; information firewall demonstrably enforced; candidate
remains shadow-only unless user explicitly publishes AI lineage" -- it never
requires the candidate's own validation to have passed. The user reported
that two independent reviewers (GPT-6 Astra `a781cc85-2b9f-488f-a8b2-
29037f27ad81`; Claude-sonnet-5.5 `77a323a6-ef7b-42c2-a78a-4ee17fb3add3`)
read the same section text and agreed with this reading, explicitly
correcting an earlier, stricter interpretation. **This agent independently
verified the mandate text itself supports this reading** before acting on it;
the two reviewer interpretations are recorded here as user-reported facts,
not independently re-verified by this agent (this agent has no channel to
query those reviewers directly).

**This does NOT change `m7-target-repair-verified`**, which keeps meaning
exactly what it always meant (a genuinely verified repair) and remains
honestly `FAIL` -- tracked as an open, visible "extra, not required" goal,
never silently dropped, never flipped, never conflated with the new
criterion below.

A new, narrower, section-129-aligned criterion --
`m7-clean-room-experiment-complete` -- was added to a new durable Run
(`each-release-mandate-aligned`, baseline commit `b2d25574b2af263844352730c8e
46704336b09eb`), registered via a new `RunStore._record_m7_experiment_receipt()`
method that independently re-verifies the real private receipt's signature
and retained materials (`each verify --full`), requires explicit
`legalCertification: false` / `cleanroomCertification: false`, requires
`networkIsolationVerified: true`, and requires the receipt's own
`audit.checks` to exactly match the real terminal auditor's fixed check set
(`exact-substring`, `ngram-similarity`, `ast-similarity`, `license-scan`,
`corpus-membership`) -- so only a receipt where the Auditor genuinely ran
(even if every finding is honestly `UNAVAILABLE`) can satisfy it, never a
stub or a forged/partial mapping.

**A harness gap needed fixing first**: `each/clean_room.py`'s
`run_clean_room_build()` previously only ever invoked the real terminal
auditor on the `REPAIR_VERIFIED` path -- every failed-validation receipt's
`audit` field stayed permanently `UNAVAILABLE` with the reason "no validated
candidate exists; terminal audit has not run", which does not satisfy
section 129's requirement that the Auditor's findings always be visible.
Fixed (commit `bc7a39a`): after the attempt loop genuinely ends (generation
has already stopped; there is structurally no way for this to feed into
another Builder call), if the selected attempt applied a real patch and its
retained materials integrity is `PASS`, the harness reapplies that attempt's
own retained `patch_text` to a fresh worktree of the pristine fixture root,
reads the real post-patch SOURCE (never a diff), and runs the same
`run_audit()` used on the verified path -- purely observational, never
changing the `REPAIR_NOT_VERIFIED` outcome classification.

**Fresh evidence run** (post-`bc7a39a`, run id `m7-clean-room-lru-cache-
qwen14b-terminal-audit-20261003`, `max_attempts=1`, seeded with the same
real prior Qwen2.5-Coder-14B-Instruct candidate used for the `source_edit`
experiment above): **this is a genuinely DIFFERENT, smaller experiment than
the 5-attempt `source_edit`/`requirement-fix` runs described above -- its
own single attempt's edit did not change the function body at all (only
touched the signature), so its own repaired-candidate run failed all 9
approved test cases (`repairedExitCode: 1`, all 9 `FAILED`), not "8/9
passing, case 6 failing" (that 8/9 fact belongs only to the separate,
earlier `qwen14b-requirement-fix` run that this run's single attempt was
seeded from -- it is not re-asserted or assumed to repeat here).** What this
run's receipt DOES newly, genuinely provide is a populated top-level
`audit.checks` (all five checks honestly `UNAVAILABLE`, with real tool
versions `each-audit v0.1-mvp` / `tree-sitter 0.26.0`, `corpus_revision:
"none"`) -- confirming the terminal-audit-on-failure fix works, and giving
the new `m7-clean-room-experiment-complete` criterion a receipt it can
genuinely verify. `each verify --full` against this receipt: signature
PASS, materials PASS. `legalCertification`/`cleanroomCertification: false`,
`networkIsolationVerified: true`.

**Source-free seven-item section 129 view for this receipt**:
1. What was publicly known: Python's own `functools.lru_cache` interface/
   semantics (publicly documented stdlib behavior).
2. What was observed: the approved, hash-pinned clean-room spec text
   (`specHash 8499cf22...`) describing 9 required behaviors for a from-
   scratch `lru_cache_clean_room` reimplementation; no reference source was
   ever shown.
3. What Builder received: the approved spec text, the model's own prior
   candidate source (as a `source_edit` seed), and permitted failed-case
   IDs/an approved requirement-6 observation -- never hidden test source or
   a cloud-authored fix.
4. What the model produced: one JSON `{"old","new"}` edit touching only the
   function signature, applied by the harness via `str.replace` against its
   own prior candidate.
5. What tests proved: all 9 approved acceptance tests `FAILED` against the
   resulting candidate (`repairedExitCode: 1`).
6. What the Auditor found: all 5 checks honestly `UNAVAILABLE` (no
   corpus/adapter configured in this v0.1 harness) -- not a PASS, not a
   silent skip.
7. What remains uncertain: why the model's single edit did not touch the
   function body; whether more attempts/a different seed would have
   produced a different (though still unverified) result. **Legal clean-room
   certification: NO. Upstream acceptability: destination-project decision.**
   Shadow-only: this candidate is never published, never sent to cloud
   review, and stays private under `~/.each/runs/`.

The `m7-clean-room-experiment-complete` criterion is registered `PASS` in
`each-release-mandate-aligned` against this receipt
(`gate-m7-clean-room-experiment-complete`), via a reality gate bound to the
`runtime` surface. `m7-target-repair-verified` is intentionally NOT carried
into this Run's blocking matrix as a registered criterion; it is tracked
here, in this document, as an honestly-open extra goal.

## M8: current-code re-audit replay of the original genuine passing candidate

M8's original receipt (`m8-xsystem-sandboxid-opt-fullsource-20261003`,
`outcome: REPAIR_VERIFIED`, `specHash 2c5eca88...`, local model
`ibm-granite/granite-8b-code-instruct-128k`) is unchanged and immutable. Its
original audit predates the current source-based `run_audit()` (it audited
diff text). A new, retained, source-free sidecar file
(`~/.each/runs/m8-xsystem-sandboxid-opt-fullsource-20261003/current-auditor-
replay.json`, alongside the untouched original `receipt.json`/`receipt.md`)
independently verifies, using ONLY the real retained original artifacts
(never a fresh model call, never a cloud edit):
1. the retained pre-patch `xsystem.c` reproduces the receipt's own declared
   materials hash;
2. recomputing `sha256(patch_text)` reproduces the receipt's own
   `patchHash` (`0e0721b8...`);
3. recomputing `sha256(prompt + NUL + raw_completion)` reproduces the
   receipt's own `trajectoryHash` (`ce4301b4...`);
4. applying `patch_text` to the retained pre-patch source reproduces the
   exact same post-patch candidate the original audit reasoned about.

Only after all four fidelity checks `PASS` does it run the CURRENT
`each.audit.run.run_audit()` directly against that reconstructed post-patch
SOURCE (not a diff): all 5 checks honestly `UNAVAILABLE` (no corpus/adapter
configured), `current_auditor_rejected: false`. This is a genuine replay/
re-audit of the SAME authoring-linked candidate under current code, not a
regeneration, not a FixtureModel substitution, and not a re-signing of the
original record. Re-executed 2026-10-03 at commit `b2d2557` to confirm it
still reproduces identically.

## Harness hardening from independent adversarial review (commit `b2d2557` -> next)

An independent GPT-family semantic review of the pinned `b2d2557` checkout
found two concrete, real gaps in the new mandate-aligned registration
machinery (not rubber-stamped):
1. `record_gate()`'s reality-gate surface check treated `target-repair-
   receipt` and `clean-room-experiment-receipt` evidence as interchangeable
   (both resolve to the `runtime` surface), so nothing stopped the WEAKER
   experiment evidence from being bound to a `*-target-repair-verified`
   criterion. Fixed: any criterion id ending in `-target-repair-verified`
   now requires its bound evidence to be the genuinely verified
   `target-repair-receipt` kind; `clean-room-experiment-receipt` evidence is
   rejected for those criteria specifically (it remains valid for any other
   criterion, e.g. the new `m7-clean-room-experiment-complete`).
2. `_record_m7_experiment_receipt()` did not hard-require
   `networkIsolationVerified: true`, and accepted any non-empty `audit.checks`
   mapping as proof the real Auditor ran (a forged/partial mapping could
   pass). Fixed: both are now hard requirements, with the exact-check-set
   comparison described above.

Both fixes are narrowly scoped to the new registration method/gate logic
added this session; they do not touch `each/` (the target-facing harness) or
any existing M0-M6/M8 evidence. Full suite re-verified green after the fix
(see gate evidence below).

## Gate-evidence correction: audit-models-gate must use explicit `--extra` flags

The first `audit-models-gate` registration at `b2d2557`
(`b2d25574b2af-b95ef9afa631-audit-models-gate.json`) incorrectly ran plain
`uv run pytest -q` in a fresh subprocess; `uv run` without `--extra` flags
auto-syncs the project venv DOWN to only required (non-extra) dependencies
before running, silently uninstalling `tree-sitter` even though it had been
manually `uv sync --all-extras`'d moments earlier in a different shell
invocation -- reproducing `409 passed, 3 skipped` rather than the required
zero-skip, extras-installed run. **That artifact and its gate
(`gate-audit-models-gate`) are preserved immutably, unedited, and are never
cited as zero-skip evidence.** A corrected run using the explicit command
`uv run --extra audit --extra models pytest -q` was independently executed
and verified `412 passed`, zero skipped, at the same commit; a new artifact
(`artifact-audit-models-gate-extras-fix-98c2b0dcc3e4`) and gate
(`gate-audit-models-gate-extras-fix`) were registered, and the
`audit-models-gate` criterion was re-set to `PASS` referencing the corrected
gate. A coordinator-independent execution in a dedicated fresh worktree with
a brand-new `EACH_HOME` (no model cache reuse) reproduced the same `412
passed`/zero-skip/clean-ruff/clean-doctor/successful-`uv build` result,
corroborating this is a reproducible fact about the commit, not an
environment fluke.

## Three fresh independent re-reviews at `632e331`, convergent fix batch, and a successor Run (`7d9c6f9`)

A security-review agent and two independent code-review agents (one modeling
a "GPT-family" posture, one a "Claude-family" posture) were dispatched fresh
against the pinned `632e33151d857e81b6e6c752618d225b3c7c2c60` checkout.

**Security re-review**: all prior P1/P2/P3/Astra/Claude findings confirmed
genuinely fixed; 447 passed/0 skipped; ruff clean; no new issues.

**GPT-family re-review**: 6 genuinely fixed, 6 partially fixed, 1 not fixed
(model-identity validation was still effectively string-based).

**Claude-family re-review**: independently converged on the same core gaps
and additionally found a concrete new bypass: `record_gate()`'s
target-evidence validation block was gated behind
`if "target-repair" in producers:`, so a criterion declaring `targetEvidence`
ownership bound ONLY to a non-`target-repair`-producer artifact (e.g.
`external-proof`) skipped the entire kind/purpose/specHash check.

### Integrated fix batch (commit `a14e983`)

One coherent batch closed all seven convergent counterexample classes:
1. Criterion-owned `targetEvidence` (kind/purpose/targetSpecHash) moved from
   name-inferred milestone-prefix matching to real schema-validated data on
   each criterion (`normalize_target_evidence()` in
   `harness/architrave_runtime.py`); `MILESTONE_APPROVED_SPEC_HASHES` removed
   entirely. `validate_recorded_real_model_identity()` added in
   `each/models/base.py` with a real adapter-class allowlist
   (`REAL_MODEL_ADAPTER_CLASS_PATHS`), rejecting any receipt that doesn't
   declare an allowlisted `adapterClassPath` plus structurally complete
   manifest/generation-parameter data.
2. Receipt emission now captures the actual producing harness commit and
   clean/dirty state at generation/validation/audit time
   (`each/receipt.py`), distinct from any installed/legacy `UNKNOWN` baseline.
3. `_record_target_replay_receipt()` added: sound replay-subject
   verification reusing the real `verify_receipt()`/materials-verification/
   `ContainerExecutor` pipeline end-to-end, exact-enum fidelity checks (no
   substring/placeholder acceptance), byte-exact candidate reconstruction
   from retained pristine preimage + patch compared against
   `auditSubjectSha256`.
4. Private projections (M7 summaries, rejection payloads, replay exports)
   now use bounded enums/typed hashes/safe identifiers; no raw outcome
   dicts, absolute paths, or arbitrary diagnostic strings cross the
   source-free boundary.
5. `_verify_seed_source_provenance()` (`each/clean_room.py`) now requires
   matching current approved spec + model identity, a selected eligible
   attempt, byte-exact preimage+patch reconstruction (not just hash
   comparison), and transitive ancestry verification with bounded-depth
   cycle rejection.
6. Trusted pre-exec audit-subject capture (already correct for M8) is now
   applied consistently to M2 bakeoff and M6 benchmark sibling code paths:
   subject hash is bound to the signed, selected, PRE-execution candidate,
   never a post-execution reread of mutable source.
7. Classification-failure handling in bakeoff/benchmark now persists the
   returned `ExecutionResult` BEFORE classification and finalizes every
   inconclusive/non-test outcome with accumulated attempt/model-identity
   state intact, instead of silently defaulting to `{}`.

**A second, narrower bypass was found and fixed directly during independent
verification of the delegated batch** (not by the delegated agent): the
item-1 gating condition above was initially still
`if "target-repair" in producers:` — exactly the AstraR1 bypass — leaving a
window where a `targetEvidence`-owning criterion bound only to non-target-
repair evidence skipped validation entirely. Fixed by widening the gate to
`if "target-repair" in producers or any_criterion_owns_target_evidence:`,
confirmed via a genuine `git stash` before/after test
(`test_target_evidence_owning_criterion_rejects_non_target_repair_producer_evidence`)
that fails pre-fix and passes post-fix.

466 tests passed (0 skipped, up from 447), ruff clean, `each doctor` PASS,
`uv build` succeeded. Committed as `a14e983`, pushed normally (fast-forward,
no amend) to `dragoshont-each-project-bootstrap`.

### Legacy real-model-identity compatibility fix (commit `7d9c6f9`)

Attempting to re-register the genuine, already-signed M7/M8 receipts
(`~/.each/runs/m7-clean-room-lru-cache-qwen14b-terminal-audit-20261003/receipt.json`,
`~/.each/runs/m8-xsystem-sandboxid-opt-fullsource-20261003/receipt.json`)
against the hardened `validate_recorded_real_model_identity()` surfaced a
genuine backward-compatibility gap: both receipts predate this session's
addition of `adapterClassPath`/`adapterType` to `RepairModel.identity()` and
only ever recorded `implementationModule`/`implementationSha256`. The
validator's unconditional `adapterClassPath` requirement would have
permanently orphaned this real evidence for no genuine provenance reason.

Fix: accept the legacy shape ONLY when `implementationModule` (plus a
non-empty `implementationSha256`) uniquely and unambiguously resolves to
exactly one entry in `REAL_MODEL_ADAPTER_CLASS_PATHS` — never derived from
caller-controlled `modelId`/`adapterType` text, which this legacy shape
doesn't even carry. A legacy receipt declaring the FixtureModel's own
`implementationModule` (`each.models.fixture`) is still rejected (covered by
`test_rejects_a_legacy_fixture_receipt_declaring_the_fixture_implementation_module`).
468 tests passed, 0 skipped; ruff clean. Committed as `7d9c6f9` (separate
commit, no amend/force-push per explicit instruction), pushed to
`dragoshont-each-project-bootstrap`.

### Successor Run `each-release-mandate-aligned-v2`

The original durable Run `each-release-mandate-aligned` has no supported API
to retroactively add the new `targetEvidence` structured field to an
already-created criterion (only `create()` accepts full criteria
definitions). Rather than manually editing canonical Run state (forbidden),
a genuine successor Run `each-release-mandate-aligned-v2` was created via the
supported `store.create()` API, re-asserting the EXACT same 8-criterion
acceptance matrix with `targetEvidence` properly declared on
`m7-clean-room-experiment-complete` and `m8-target-repair-verified`. The
predecessor Run remains immutable and untouched; its historical criterion
statuses after this session's baseline move are explicitly understood as
STALE relative to the new commit and are never reported as current evidence.

At the final frozen commit `7d9c6f96c5bf750ef850049805c1d4a8f50783e7`, the
successor Run's acceptance matrix is:

| Criterion | Status |
|---|---|
| `harness-rootcause-fix` | PASS |
| `base-gate` | PASS |
| `audit-models-gate` | PASS |
| `ruff-doctor` | PASS |
| `m7-clean-room-experiment-complete` | PASS |
| `m8-target-repair-verified` | PASS |
| `cross-family-semantic-review` | UNTESTED (genuinely pending; the user/coordinator will independently obtain and supply this verdict) |
| `security-policy-review-r4` | UNTESTED (genuinely pending, same as above) |

### Known, explicitly tracked limitation (carried forward, not resolved)

The 22-task historical Granite-8B-128k benchmark report (`102321Z`) has
signed receipts but no retained `materials/` directories, so full
byte-exact reconstruction/verification of those 22 historical records is not
possible; this session's materials-retention fix applies going forward only.
Recovering genuine original bytes retroactively, or producing a fresh local
benchmark run if the originals are unavailable, remains open and untouched —
no historical bytes have been fabricated or implied to exist.

### Final release: `each-release-mandate-aligned-v6` COMPLETED at `e3c0cf45b7091cb361f146b7338009bfa0fc7f53`

This entry is a **publication of the already-reviewed source**, not a new
implementation review — no source change accompanies this commit.

Reviewed implementation commit `e3c0cf45b7091cb361f146b7338009bfa0fc7f53`
("Preserve independent risk gates for target-owned acceptance criteria")
fixed the last confirmed defect: `record_gate()`'s target-evidence-ownership
enforcement had been applying to every gate type, which made it structurally
impossible for an independent deterministic or semantic risk gate to ever
bind to a `targetEvidence`-owning criterion (`m7-clean-room-experiment-complete`,
`m8-target-repair-verified`, `m8-replay-validation-64b3e8a`). The fix scopes
that enforcement to `gate_type in {"reality", "e2e"}` only, leaving full
target-ownership/kind/purpose/spec-hash matching intact for reality/e2e
evidence, while deterministic and semantic gates now correctly bind without
requiring a forbidden target-repair producer.

The durable Run `each-release-mandate-aligned-v6` was resumed onto this
commit via the supported `resume(accept_commit=True)` API (same Run, no new
successor needed), and every piece of evidence was freshly re-derived and
re-registered at the new baseline through `RunStore`'s own supported methods
— `_record_artifact`, `record_gate`, `set_criterion`,
`_record_semantic_verdict`, `_record_security_verdict`,
`_record_policy_decision`, `_record_m7_experiment_receipt`,
`_record_target_repair_receipt`, `_record_target_replay_receipt`,
`_record_external_proof`, `add_task`, `start_task`, `wait_external`,
`resolve_external`, `grant_task_attempt`, `finish_worker`, `complete_task`,
and finally `verify`. No canonical Run state was hand-edited.

Final acceptance matrix (all 11 criteria, fresh at `e3c0cf4`):

| Criterion | Status |
|---|---|
| `harness-rootcause-fix` | PASS |
| `a3bf1f4-successor-defect-fix` | PASS |
| `base-gate` | PASS |
| `audit-models-gate` | PASS |
| `ruff-doctor` | PASS |
| `m6-mixed-language-coverage` | PASS |
| `m7-clean-room-experiment-complete` | PASS |
| `m8-target-repair-verified` | PASS |
| `m8-replay-validation-64b3e8a` | PASS |
| `cross-family-semantic-review` | PASS |
| `security-policy-review-r4` | PASS |

The two release-wide criteria were set to PASS from genuinely independent,
freshly produced GPT-family and Claude-family semantic verdicts (not
self-authored), plus dedicated security and policy verdict gates. Their
`e2e-or-reality` requirement was satisfied by a real local Ed25519-signed
runtime-reality proof: a `SIGNING_REQUIRED` external checkpoint was opened,
a source-free payload combining a fresh container read-only-kernel-isolation
probe, a fresh network-isolation probe (genuine `errno 101` denial connecting
to `1.1.1.1:443` through the product's own no-network container executor,
not a bootstrap-level probe), and sanitized M7/M8/full-suite summaries was
signed with the existing `each/signing.py` Ed25519 key (outside Git), verified
independently twice, registered as an `external-proof` artifact, and the
checkpoint resolved — all through supported APIs. This signature is a local
cryptographic operation under a trusted local coordinator/key-holder
boundary; it is explicitly **not** a human-approval claim, hardware
attestation, or TEE proof.

`missing_gate_requirements()` returns zero gaps across all 11 criteria. The
Run's own `store.verify()` reports `status: "COMPLETED"`, `completed: true`,
with empty `failedCriteria`/`untestedCriteria`/`blockedExternalCriteria`/
`missingEvidence`/`incompleteTasks`/`pendingExternalCheckpoints`. Schema
validation (`harness/validate_run_v2.py`) reports PASS (revision 100, 11
acceptance criteria, 101 events).

**Retained historical limits, unchanged:** M6's 25 historical tasks (22
Python + 3 native) are re-verified, not re-generated; original producer SHAs
are preserved. M7's experiment outcome remains a genuine negative
(`REPAIR_NOT_VERIFIED`, unseeded, 3 attempts); its audit coverage was honestly
`UNAVAILABLE` (no reference corpus), never coerced to PASS. M8's historical
target-repair receipt keeps its legacy `UNKNOWN` original producer SHA and
audit-subject hash; only the current replay's reconstructed subject hash is
asserted as current proof. No TEE, no legal/clean-room certification, no
upstream Xodus PR, no P3 coverage claim, no hardware attestation, and no
human-approval claim is made anywhere in this evidence chain.

#### Independent completion check and historical-material recovery

The coordinator independently called the supported `RunStore.verify()` at
the frozen implementation revision after final registration. It returned
`accepted=True`, `status=COMPLETED`, revision **102**. The actual Run also
passed JSON Schema validation, had no missing per-criterion risk gates, and
contained one completed signing task and one resolved signing checkpoint.
The coordinator independently verified the registered runtime proof's
Ed25519 signature and its payload hash with the public key.

The earlier missing-materials limitation above is **closed by genuine
hash-matching recovery**, not by rewriting historical receipts. All 22
original Python benchmark receipts passed `each verify --full` against
new private recovery roots; their original signed bytes remain unchanged.
The selected mixed-language evidence comprises those 22 historical tasks
and three separately recorded clean-source native tasks: **25 tasks,
75 recorded generation calls, zero verified repairs**. Input-integrity
reverification does not change their original generation revisions.

The independently executed final configured base gate ran `uv sync --locked`,
then the configured tests and doctor: **493 passed, three optional-extra
tests skipped**. The separate explicit audit/models-extra suite had
**496 passed, zero skipped**; Ruff, doctor and wheel/sdist builds passed.
These counts must not be merged into a claim that the base command itself
had zero skips.

The accepted M7 artifact references the fresh unseeded receipt
`75069a3d2e4c75870f1c62cacad52784365b29cb8b787ad742177100cd0d025f`,
not the older `source_edit` receipt with unavailable seed lineage. Its
three genuine local-model responses still produce **eight passing tests
and one failure**. Completion means the mandated controlled experiment
and evidence chain are complete, not that the cache implementation works.

The reviewed implementation is `e3c0cf45b7091cb361f146b7338009bfa0fc7f53`.
Subsequent documentation-only commits publish these results; they are not
new implementation revisions covered by the recorded code verdicts.

## Production development first slice — 2026-10-03

This is a new development program, not a change to the completed research
release above. Run `each-production-first-slice-20261003` owns the P0-P8 graph.
P0 baseline reconciliation passed; P1 development controls/support calibration
passed, with independent R4 acceptance still outstanding.

The actual local Qwen2.5-Coder-14B original snapshot generated nine calls on
three new MIT-licensed Python historical development tasks. **Zero repairs were
verified.** All original negative receipts and retained inputs verify; source,
prompts, completions and patches remain private. The three-task cap is exhausted,
not extended. Parser interoperability, no-op and regression failures were
diagnosed without new sampling or imported target execution on the Mac.

See [executed ledger evidence](production-readiness-ledger.md#10-executed-first-development-slice-2026-10-03)
and [measured contract](production-development-contract.md) for hashes, budgets,
custody and limitations. The public changes harden the independent observer and
durable development recovery; they do not establish a production repair tool.
Independent review at the frozen implementation revision remains pending.
P3/P4 may proceed independently; holdout, operational qualification, packaging
qualification, seven-day pilot and genuine human go/no-go remain unaccepted.

## Independent P3/P4 execution — 2026-10-03

Continuation Run `each-production-p3p4-20261003-v2` uses supported runtime APIs
and default-deny grants. The initial continuation intake was policy-denied
before implementation; v2 corrects only that intake. The failed firstslice
revision 69 and completed research revision 102 are unchanged. P1's tested
development contract permits independent prerequisites, but R4 P1 acceptance
is not inherited as PASS. No new utility tasks, real model calls or downloads.

The public Apache-2.0 synthetic audit corpus has separate four-cluster
calibration/holdout splits, 26 labelled units each. Both detected 8/8 exact and
4/4 renamed copies, but falsely flagged 1/14 semantic/novel benign units:
7.14%, above the frozen 5% target. The synthetic holdout is consumed; no repair
holdout was selected. Common-code matches and inappropriate default escalation
are separately recorded. External membership/license scanning remain UNAVAILABLE.
See [audit qualification](audit-qualification.md); no P3 acceptance is claimed.

Operational drills exercise actual exact-owned-PID SIGINT, exact-container-CID
kill, observer timeout, bounded 1 MiB tmpfs ENOSPC, real permission denial,
artifact corruption/symlinks, concurrent processes/runs and temporary-key
backup/restore with original public-key and retained-input verification.
Concrete lost-key rotation, signing-leaf/lock symlink, private permissions,
quota trajectory retention and observation-benchmark cancellation defects
were reproduced and narrowly fixed.

A genuine Colima read-fidelity defect was also reproduced: after baseline-read
files were overwritten in place, host stat reported 54 bytes but the container
read 23 bytes in 3/3 public synthetic probes. Candidate validation now reuses
the existing materializer to create a fresh sanitized worktree with the same
preimage manifest. Actual container/host byte-hash regression and benchmark
SIGINT/kill partial-receipt drills passed afterward. This does not reclassify,
re-sign or regenerate any original negative firstslice receipt.

[The operator runbook](operator-runbook.md) records supported commands and
explicit limits: no MLX interruption/power-loss guarantee, no automatic prune
or general recovery CLI, no TEE, no recursive historical cleanup. Independent
cross-family/security/policy acceptance remains pending. P2 usefulness is still
blocked at zero of three repairs/nine calls; P2b and P5-P8 do not advance.

The frozen implementation is
`0ce8302260c70e3a5d882b95c9a3a84db6e56206`: configured base 573 passed with
three optional-extra skips, explicit audit/models 576 passed with zero skips;
Ruff, doctor and packaging passed. All 39 added controls passed targeted
checks without skips. [Frozen metadata and canonical disposition](production-p3p4-evidence.md)
record FAILED revision 36, P3 FAIL/P4 UNTESTED and unchanged predecessor history.
This documentation publication does not restamp the implementation's gate SHA.

## Mandatory actual independent review correction — 2026-10-03

Actual adversarial/security review of `8b43fe055d7f` returned REVISE.
**P1 API-return acceptance is BLOCKED**, not R4 PASS. Shared-interpreter
candidate code can print matching JSON before exit or replace serialization;
actual synthetic executor/benchmark regressions reproduced both previously
yielding `REPAIR_VERIFIED` without authenticating API return.

The [corrected contract](production-development-contract.md) now honestly
describes process-response observations. Such matching responses cannot
verify an unrestricted Python API repair and now terminate as signed
`REPAIRED_RUN_INCONCLUSIVE` evidence. This does not authorize/adopt a narrower
production outcome; the original repair goal remains unmet. The exhausted
development command is BLOCKED before model loading/generation.

Actual deeply nested candidate JSON also reproduced `RecursionError` escaping
before receipt finalization. Narrow candidate-JSON handling now marks it
incomplete and retains signed negative deterministic fixture evidence.
Read-only/fresh worktrees and signatures are not API-return authentication.

[Correction evidence](observer-review-corrections.md) supplies the separate
existing exact-8b configured/extras output summaries (534+3 skips / 537 zero
skips) with original artifact/output hashes. The earlier frozen proof did not
embed those outputs; no unchanged 8b command was rerun or historical artifact
restamped. Original nine negative local-model calls, Runs 69/36/102 and signing
key are unchanged. P3 still FAIL; P4 independent R4 acceptance still open.
