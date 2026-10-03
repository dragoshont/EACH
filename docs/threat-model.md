# Threat model

This document is created at M0 and updated at every milestone that changes
an isolation boundary or discovers a new mitigation gap. It is a working
engineering document, not a certification.

## Threats

### T1 — Network leakage

The Builder or its tools fetch implementation knowledge during generation
(web search, package registries, DNS lookups).

Mitigation: no network in the strong-isolation execution profile; **enforced
and tested** (not merely documented, see M1 adversarial evidence); network
policy recorded in the receipt.

### T2 — Hidden agent context

A framework silently injects repository history, global memories, prior
chats, or web results into the Builder's context.

Mitigation: explicit context constructor; the exact prompt/messages sent to
the model are logged; linear trajectory; no undeclared retrieval-augmented
generation.

### T3 — Training-data memorization

The model emits source code it memorized during pretraining, independent of
anything in the current spec.

Mitigation: model provenance metadata (exact weights/revision hash);
corpus-membership/search adapters where available; similarity scanning
(M4); an honest residual-risk statement. **Not fully solvable** — this is
why EACH never claims originality certification.

### T4 — Spec contamination

A Scout agent sees restricted material and silently folds it into a
"clean-looking" spec.

Mitigation: every spec fact carries an origin classification
(`PUBLIC_API_DOC`, `PUBLIC_ISSUE`, `MODEL_INFERENCE`, `RESTRICTED`, ...,
see M3); human approval gate for sensitive tasks; deterministic observation
collectors kept separate from the Scout.

### T5 — Audit feedback contamination

The Auditor discovers a forbidden source match and that match is fed back
into another Builder attempt, teaching the model the forbidden
implementation.

Mitigation: the Auditor is a **terminal boundary** (M4) — a flagged run is
rejected and archived; a retry starts fresh from the original approved
spec, never from audit findings.

### T6 — Existing target-source contamination

The sanitized worktree itself already contains AI-derived or
provenance-unknown code before EACH ever touches it.

Mitigation: target provenance classification is recorded; the receipt
records the exact target source SHA and its declared trust class.

### T7 — Tool escape

The Builder uses shell access to inspect network state, credentials, the
parent filesystem, Git history/remotes, or other forbidden locations.

Mitigation: sandboxed executor; explicit read/write scopes; a command
policy (allow/deny lists, enforced, not merely prompted); environment
variable scrubbing; no inherited secrets; no SSH agent; no Git
fetch/pull/clone/remote access (see M1 adversarial tests).

### T8 — Publication contaminates future clean-room work

An AI-authored shadow patch becomes public, and a future human
implementer of the same feature is unknowingly tainted by having seen it.

Mitigation: shadow artifacts are **private by default**; public
publication is always an explicit, separate, acknowledged step (see
`docs/EACH_BOOTSTRAP_MANDATE.md` §46, publication modes).

### T9 — False legal confidence

A user treats "no similarity match found" as proof of legal safety.

Mitigation: assurance levels are explicitly technical/engineering labels,
never "certified"; every receipt restates its limitations; see
`docs/claims-and-nonclaims.md`.

## Assurance levels

A receipt's assurance level is a property of *that specific run*, not a
fixed property of the tool.

| Level | Name | Minimum evidence |
|---|---|---|
| EACH-P0 | Untracked | Model/source unknown; unrestricted network; incomplete trajectory. Ordinary, unaudited AI code. |
| EACH-P1 | Recorded | Model/provider identified; prompt/trajectory recorded; target revision recorded; patch hash recorded. |
| EACH-P2 | Isolated | P1 **plus**: fixed model revision/hash; exact allowed inputs hashed; no-egress execution *verified* (not assumed); environment manifest; tool allowlist; no undeclared retrieval. |
| EACH-P3 | Dataset-auditable | P2 **plus**: model has documented/queryable training provenance; post-generation corpus/source checks executed; license/source evidence recorded; no disallowed match over policy thresholds. |
| EACH-P4 | Deterministic-generation | No neural model authors the promotable source (e.g. an approved declarative spec drives a deterministic generator); generator source/revision recorded; output reproducible byte-for-byte. |

P4 does not automatically mean legally clean-room. These labels represent
evidence properties only, and every receipt restates that explicitly:

```json
{
  "assurance": "EACH-P2",
  "legal_certification": false,
  "cleanroom_certification": false
}
```

### M1 status

M1 implements only the container executor profile (`--network none`, `--read-only`,
scrubbed environment, dropped capabilities, no host home or SSH-agent
mount, `docker --context colima-each` against a pinned base-image digest).
A configuration that cannot back that profile (network enabled, or an
unpinned/mutable image tag) is rejected at executor-construction time
rather than silently claimed as isolated.

The assurance level in each receipt is derived per-run, not hardcoded: it
is only **EACH-P2** when that run's own isolation probe (the same
`NETWORK_PROBE_SCRIPT` used by the adversarial tests, executed through the
run's actual executor configuration) genuinely observed a denied outbound
connection with Linux `ENETUNREACH` (numeric errno 101). Timeouts, remote
connection refusals, and unexpected results do not prove no-egress. The
probe uses Python isolated mode so target files cannot shadow its standard
library imports. If isolation is unverified, the strong-profile demo emits
an `ISOLATION_UNVERIFIED` receipt at **EACH-P1**, exits nonzero, and stops
before generation or target tests.
It does **not** claim EACH-P3, since no corpus/source similarity check or
documented model-training provenance exists yet (the M1 audit step is an
explicit `UNAVAILABLE` stub, never a fabricated PASS). The real,
historical outbound-network-denial probe recorded during bootstrap is
evidence for *that* probe only; it is never substituted for a given run's
own isolation evidence.

No native-macOS executor profile exists in M1; native host execution is
explicitly not implemented and not used as a substitute for container
isolation ("native host execution is not a strong-profile proxy").

## Known limitations as of M1

- No model has been integrated yet beyond `FixtureModel` (a deterministic,
  non-inferential canned response); T3 is not yet exercisable and will be
  revisited starting at M2.
- No Auditor exists yet; T4/T5/T9 mitigations are designed but not yet
  mechanically enforced — `each/audit/stub.py` returns an explicit
  `UNAVAILABLE` result rather than a fabricated PASS. Tracked for M3/M4.
- No attestation/signing exists yet; receipts are not yet tamper-evident.
  Tracked for M5.
- The container executor currently runs as the image's default user
  (root inside the container's own user namespace, not the host); a
  non-root `--user` mapping was attempted but deferred because Colima's
  default bind-mount UID mapping made it unreliable in this environment.
  This does not weaken network/secret isolation (verified in
  `tests/adversarial/test_container_isolation.py`) but is a residual
  defense-in-depth gap, tracked for a later milestone.
- The patch applier (`each/patch.py`) supports only textual unified-diff
  hunks (via `unidiff`); it does not yet handle binary diffs, renames, or
  mode changes. Out of scope for hello-repair; revisit if a later
  milestone's real-world fixtures require it.

## Known limitations as of M6

- The pinned `granite-3b-code-instruct-mlx` checkpoint's real
  `max_position_embeddings=2048` is small relative to real-world
  historical bug files. A pre-generation check now rejects any rendered
  prompt plus reserved output that exceeds this declared limit, recording
  the exact token counts (`BUILDER_CONTEXT_BUDGET_EXCEEDED`) instead of
  silently truncating, mutating, or degrading the prompt. This is a
  genuine, measured model-capability constraint, not a harness defect: in
  the real 22-task historical benchmark only 4/22 tasks' excerpted
  prompts ever reached a real generation call even after diff-blind
  AST-based narrowing (`select_prompt_excerpt` in `each/benchmark.py`);
  of those 4, 0 ever produced an applicable patch (truncated before a
  complete BEGIN_PATCH/END_PATCH pair given the checkpoint's 512-token
  output reservation, or a malformed diff) -- see
  `docs/benchmarks/m6-granite-3b-code-instruct-mlx-20261002.md`. A larger
  (128K-context) checkpoint (`granite-8b-code-instruct-128k-mlx`) reached
  real generation on 22/22 tasks under the identical policy; see
  `docs/benchmarks/m6-granite-8b-code-instruct-128k-20261002.md`.
- A separate harness bug (fixed in commit `898f2d7`) mislabeled a task
  whose every attempt was rejected (never reaching a classified
  repaired-test run) as `REPAIR_NOT_VERIFIED` instead of its real
  `PATCH_REJECTED` outcome. Both benchmark reports above have been
  corrected to the real per-attempt outcomes; a regression test
  (`tests/adversarial/test_benchmark_task.py`) now covers this case.

- The excerpter narrows large files to the specific functions/methods a
  task's pre-fix test references (plus local call-graph expansion) and
  caps oversized leading docstrings; it never reads the fix commit, diff,
  or known-solution content (T2 continues to hold). It is a pragmatic,
  stdlib/AST-only input-construction aid, not a retrieval or ranking
  system, and it does not guarantee every real-world file will fit a
  small context window.
- A third defect, found by an independent dual-family (GPT-family and
  Claude-family) adversarial review before M6 was accepted: the benchmark
  source cache (`materialize_task_sources` in `each/benchmark.py`) was
  keyed only by `task.task_id`, with no check that the cached directory's
  content actually matched `task.pre_fix_sha`. A stale cache entry
  extracted under an earlier, different sha could therefore silently be
  served as the pre-fix source forever; this was confirmed for real for
  one task (a cached file held the fix-only line instead of the actual
  buggy line). Fixed by keying the cache path on both `task.task_id` and
  `task.pre_fix_sha` (so a different sha can never resolve to the same
  cache directory), purging the entire contaminated cache, and adding a
  regression test (`tests/unit/test_benchmark_source_cache.py`). Both
  benchmark reports above were regenerated from a clean re-run produced
  entirely after this fix, with every task's baseline pytest run
  independently confirmed to genuinely fail beforehand.
- The model's generation attempts are of highly variable quality across
  tasks: some plausibly target the right function with a coherent edit,
  some target unrelated code, and some are degenerate (a literal
  unified-diff template with placeholder text, or a no-op edit). All
  share the same universal failure to produce the exact required
  `BEGIN_PATCH`/`END_PATCH` markers. This variability is itself genuine
  signal about the checkpoint's current repair capability on this task
  distribution, not evidence of a harness defect (the same diff-blind
  excerpter supplies consistent context regardless of outcome).
  **Note (added after M7):** this describes the M6 extractor's behavior at
  the time of that specific benchmark run only. `each.patch.extract_patch_text`
  was later extended with a fenced-unified-diff fallback (a completion
  using a plain ```` ``` ```` code fence instead of explicit
  `BEGIN_PATCH`/`END_PATCH` markers is now also accepted) -- the M6 reports
  above are not re-run against this capability and should not be read as
  current evidence of the harness's present extraction behavior.

## Known limitations as of M7

- `RunStore.wait_external()` (in the third-party Architrave kit,
  `harness/architrave_runtime.py`) deliberately persists only a one-time
  resolution challenge's SHA-256 hash in canonical Run state; the plaintext
  challenge is returned once to the caller and is never written to durable
  evidence. During this project's real M7 checkpoint, that one-time return
  value was captured only in an ephemeral shell-output temp file, which did
  not survive a host/session transition -- leaving a genuinely human-approved
  spec with a checkpoint that could never be resolved under the original
  design, short of fabricating a challenge or hand-editing canonical Run
  state (both explicitly out of bounds). Fixed with a narrow, documented
  addition to the kit: `RunStore.reissue_challenge()` (plus an
  `external-reissue-challenge` CLI subcommand) lets a trusted
  coordinator/human actor obtain a fresh challenge, but only by presenting an
  ALREADY-REGISTERED, unconsumed `external-proof` artifact that genuinely
  matches the checkpoint's id/principal/provider -- the identical binding
  `resolve_external()` itself enforces -- so it can never manufacture
  approval, only re-open the door for evidence that already genuinely
  exists; the prior challenge hash is invalidated and a new
  `external.challenge_reissued` event is recorded. Covered by seven focused
  regression tests
  (`tests/unit/test_runtime_external_checkpoint_recovery.py`): matching-proof
  happy path, wrong-principal rejection, untrusted-producer rejection, an
  already-resolved checkpoint, stale-token invalidation after reissue,
  untrusted-actor rejection, and event-log/hash-chain integrity.

## Corrections from an independent adversarial review (post-M7/M8 real-receipt stage)

An independent GPT-family adversarial review of the real M7/M8
`REPAIR_NOT_VERIFIED`/`PATCH_REJECTED` receipt evidence found and this
consolidated commit fixed:

- **Source-free export leakage.** `each.xodus_shadow.run_xodus_shadow_build`'s
  per-attempt `BUILD_FAILED` handling previously embedded the raw compiler
  stdout/stderr diagnostic (which can echo candidate-source fragments)
  directly into the attempt's `outcome` string, and
  `summarize_receipt`/the function's own top-level return value derived
  `outcome` fields from that same unbounded string. Fixed by introducing a
  shared `each.outcome.sanitize_outcome_class` whitelist: every
  outcome/attempt-outcome value crossing a documented source-free boundary
  (the function's own return value, `summarize_receipt`'s export) is now
  reduced to one of a fixed, reviewed label set; the raw diagnostic is kept
  only in a dedicated private `attempt_record["build_failure_result"]`
  field inside the receipt. Mirrored into `each.clean_room`.
- **Unenforced strict-run policy.** `policies/xodus-shadow.yml` previously
  existed only as documentation -- nothing loaded or checked it, and
  nothing bound a caller-supplied `ApprovedSpec` to the genuine, durably
  recorded human approval in `~/.each/specs/<task_id>/approved.json`,
  meaning a caller could in principle construct and self-approve a spoofed
  spec. Fixed with `each.xodus_policy.verify_xodus_shadow_binding`, called
  immediately after `approved.verify()` and before any network fetch,
  container execution, or disk write: it re-reads the real durable approval
  via the existing M3 `load_approved_spec` workflow function (never a new
  approval mechanism) and, for a declared `strict_run_repositories` target,
  requires `sensitive=True` plus the policy YAML's own required clauses
  (`ai_source_upstream_promotion: false`, `cloud_llm_candidate_review:
  false`, `no_upstream_pr: true`, `default_visibility: private`).
- **Write-path containment.** `each.xodus_shadow._assemble_source_root` now
  independently validates `allowed_path` (traversal/absolute-path/symlink,
  resolved-containment against its destination) before any host write, even
  though that path already comes from a hash-bound approved spec --
  defense in depth, not trust-by-provenance alone. `run_id` is validated
  with the existing `each.paths.validate_task_id` in both
  `run_xodus_shadow_build` and `run_clean_room_build` before it becomes a
  directory name. `Receipt.write()` now refuses to write inside this
  repository's own working tree and refuses to overwrite an
  already-written receipt (a receipt is immutable; a retried run gets a new
  `run_id`, never an in-place rewrite).
- **Assurance derived from network isolation alone.** The shared
  `EACH-P2` assurance level was derived only from the container's
  pinned-image/no-network/root-probe evidence, with no check that the
  validation harness scaffold itself (the files a candidate's own build/run
  step executes alongside, which that step has read-write access to) was
  left unmodified. `each.worktree.verify_unchanged` re-hashes the
  harness-owned paths in a worktree against the original `build_worktree`
  manifest after each candidate build/run; `each.xodus_shadow` and
  `each.clean_room` now both conservatively downgrade an otherwise-passing
  attempt to `REPAIR_NOT_VERIFIED` (never `REPAIR_VERIFIED`) if that
  check detects drift, and record the check's own pass/fail status per
  attempt. This is a narrow, scoped materials-integrity check, not a
  redefinition of `derive_assurance_level`'s own broader isolation
  evidence.
- **Declaration-only artifact integrity.** `each.attestation`'s signature
  previously only hashed a receipt's own *declared* JSON fields (e.g. the
  `materials` path-to-hash mapping itself), never the real files those
  hashes claim to describe -- deleting or mutating a referenced file left
  the signature verification passing. `Receipt.write()` can now also copy
  the exact files the selected attempt's worktree declared under
  `materials` into a `materials/` subdirectory next to the receipt (with
  the same traversal/escape containment as every other write path here);
  this is additive, source-free declaration-signature verification
  remains valid for every receipt that predates this change.
- **Trajectory-attempt mixing.** Both `each.xodus_shadow` and
  `each.clean_room` previously updated the receipt's top-level
  `prompt`/`raw_completion`/`model_identity` fields unconditionally from
  whichever attempt merely ran *last*, independent of which attempt's own
  `patch_text`/`baseline_result`/`repaired_result` were actually reported
  (a later retry rejected before classification could silently pair its
  own prompt/completion with an earlier attempt's real, if failing,
  result). Both pipelines now track the one classified
  `selected_attempt_record` explicitly and resolve every top-level
  trajectory field from it consistently; `Receipt` gained a
  `selected_attempt` field recording which attempt number is reported.
- **Gate staleness across a source-changing `resume`.** A deterministic/
  semantic/reality gate recorded in `harness/architrave_runtime.py`
  (third-party Architrave kit) had no binding to the exact source commit
  its evidence was produced against; `resume(accept_commit=True)` could
  change the canonical baseline commit while leaving earlier-commit gate
  PASS results readable as still-current proof. `record_gate` now stamps
  each gate with `sourceCommit` (the baseline commit at record time), and
  `missing_gate_requirements` only counts a PASS gate toward a
  requirement when its `sourceCommit` matches the Run's current baseline
  commit -- a gate recorded against a superseded commit becomes a missing
  requirement again, by design, rather than quietly staying trusted.
  `grant_task_attempt`'s `actor` parameter remains a plain string check
  (`"coordinator"` or a `"human:"` prefix) with no cryptographic/external
  proof binding; this is now explicitly documented as relying on the same
  "the local caller is already the single trusted operator" boundary every
  other `actor=` parameter in that module relies on, not a claim of
  real authentication.
- **Qualified-model filesystem concurrency.** Qualified converted artifacts are
  pinned in trusted source by conversion-record and complete output-file hashes.
  The lazy MLX loader verifies the complete snapshot immediately before and
  after backend load while holding a cooperative sibling file lock. This
  serializes cooperating loaders and rejects a persistent backend-open writer
  mutation. The provisioner and arbitrary filesystem writers do not acquire
  this loader lock.
  It is not atomic hardware-backed measurement: a malicious process running as
  the same trusted local operator can ignore the cooperative lock and attempt
  precisely timed file substitution. EACH does not claim protection from that
  same-user adversary, TEE attestation or remote proof of loaded weights.
