# Production readiness ledger and backward plan

Last updated: 2026-10-03.

**State: NOT PRODUCTION READY.** The M0-M8 research program is complete;
production qualification is a separate program. The user authorized
adversarial review, fixes and autonomous implementation on 2026-10-03.
That grant does not authorize target publication, changed sensitive specs,
gated-model terms or certification claims.

## 1. Target outcome

The first production release should be a **local, human-reviewed
authoring-provenance CLI for bounded repair tasks on supported Apple Silicon
Macs**. It must reliably preserve evidence, fail safely, and demonstrate useful
repair performance within a declared support envelope.

It is not an autonomous upstream contributor, hosted service, legal clean-room
certifier, or originality checker. Human review remains mandatory before a
candidate is adopted. No UI, daemon, database, RAG system, hosted backend or
custom cryptography is part of this plan.

Two outcomes must be measured separately:

| Outcome | Production requirement |
|---|---|
| Evidence integrity and operational reliability | Every supported run has an honest, verifiable outcome; failed generation or validation does not lose evidence or become a success. |
| Repair usefulness | Real local-model candidates solve a meaningful share of previously unseen tasks and pass independently held acceptance and regression tests. |

If usefulness fails, an explicitly narrower evidence-recording product may be
considered. It must not be silently substituted for a production repair tool.
That change needs an explicit product decision and a new claims statement.

## 2. Verified starting position

| Fact | Evidence / implication |
|---|---|
| Research release accepted | `each-release-mandate-aligned-v6`, revision 102: COMPLETED, 11 criteria PASS, no missing risk gates or outstanding tasks/checkpoints. |
| Reviewed implementation | `e3c0cf45b7091cb361f146b7338009bfa0fc7f53`; subsequent documentation publication is not a new implementation review. |
| Deterministic qualification | Configured base: 493 passed, 3 optional-extra skips. Explicit audit/models extras: 496 passed, zero skips. Ruff, doctor and packaging passed. |
| Independent review | Recorded GPT-family, Claude-family, security and policy PASS, with bounded review scope and disclosed limitations. |
| Historical repair usefulness | 25 tasks across Python, C, C++ and Rust; 75 selected recorded calls; **0 verified repairs**. This is a blocker for a useful repair-product claim, not an integrity failure. |
| Controlled M7 experiment | Fresh unseeded local model, complete receipt and terminal audit; **8 tests passed, 1 failed**. Not a working cache. |
| M8 result | One genuine private bounded C repair; protected replay reproduces baseline failure and candidate success. Not full Xodus/Wine/game compatibility. |
| Provenance audit availability | Production experiment comparisons were UNAVAILABLE. Invocation is not comparison coverage, originality proof or EACH-P3. |
| Retained inputs | Genuine recovered inputs verify against unchanged historical signed receipts. Original production revisions remain historical; legacy unknown producer metadata remains UNKNOWN. |

Source: [development status](development-status.md), especially the final
release and independent completion entries. Preserve the old failed Runs,
negative outcomes, signed receipts and recovery history.

## 3. Work backward from launch

| Backward step | Required predecessor | Evidence needed before proceeding |
|---|---|---|
| **P8: production launch** | P7 release approval | Published supported scope, exact release identity, install instructions, verified artifact, support owner and recovery instructions. |
| **P7: go/no-go** | P6 pilot and frozen candidate gates | All required criteria PASS at the candidate revision; independent semantic/security/policy verdicts; real runtime and recovery results; actual human go/no-go. |
| **P6: bounded pilot** | P5 reproducible release candidate | Representative real workflows complete safely, including interruptions and failed repairs; pilot evidence is private and verifiable. |
| **P5: release candidate** | P2-P4 integrated and verified | Fresh install, packaging, support matrix, upgrade/recovery and operator runbook demonstrated together. |
| **P4: operational safety** | P1 contract | Retention, permissions, signing-key lifecycle, interruption recovery and diagnostics verified without data loss or exposure. |
| **P3: audit qualification** | P1 audit claims and permitted corpus | A measured audit suite, licensed reference data, explicit availability states and fail-closed required-check policy. |
| **P2: useful repair slice** | P1 development envelope and credible validator | At least one meaningful real repair first, then blind holdout usefulness and independent regression evidence. |
| **P1: qualification contract** | P0 baseline | Executable development scope and budgets; qualification thresholds frozen separately before holdout use. |
| **P0: evidence baseline** | Existing research release | Confirm current artifacts and source identities; open a new production Run using supported runtime APIs. |

**Forward execution order:** P0 -> P1 -> smallest P2 slice -> P3/P4 ->
integrated P2 holdout -> P5 -> P6 -> P7 -> P8.
P3 and P4 can proceed independently after P1. P5 depends on all three workstreams.
Do not spend more than two consecutive tasks on support machinery without
returning to a demonstrable repair slice, unless a named blocker requires it.

## 4. Actionable work ledger

Statuses: READY means dependency-ready, not done; PENDING means its dependencies
are open; BLOCKED means an evidenced obstruction. Development task gates do not
replace criterion risk floors or release approval. P0 was reconciled; P1 has a
verified development candidate awaiting independent acceptance; P2a exhausted
its authorized exploration without a verified repair.

| ID | Work packet / accountable role | Prerequisites | Acceptance evidence | Status |
|---|---|---|---|---|
| P0 | Reconcile baseline and create production Run / coordinator | None | Verify actual research state; register user implementation authority, production outcome, criterion matrix and dependency graph through supported APIs. Default-deny policy permits only named in-scope operations. Never rewrite completed research acceptance. | PASS (baseline reconciled) |
| P1 | Freeze production development contract / coordinator | P0 | One tested support row and budgets; genuinely authenticate API return before API repair acceptance. Matching untrusted process JSON is insufficient. Qualification targets freeze before holdout use; no invented approval or narrower outcome substitution. | BLOCKED: actual independent adversarial/security REVISE; API-return authentication unavailable |
| P2a | Deliver one useful vertical slice / harness implementer | P1 | Dedicated `colima-each`, pinned image, actual per-run no-egress proof, declared input/trajectory hashes and protected validators. Genuine pre-fix failure and independently observed acceptance/negative/regression cases pass; immutable subject is audited; signed retained files verify. Outer agent writes harness/tests, never target repair code or known-fix hints. | BLOCKED: 0/3 repairs, 9 calls; bounded exploration stopped |
| P2b | Diagnose utility failures and qualify a blind holdout / evaluation owner | P2a, P3, P4 | Account for context, response format, patch application, compile, validation, infrastructure and audit failures separately. Freeze the candidate policy, run the holdout, report every outcome and budget overrun. Do not tune against holdout answers. | PENDING |
| P3 | Qualify audit availability and policy / audit owner | P1 | Exact-copy, renamed-copy, boilerplate and semantic-equivalent fixtures; permitted reference corpus identity/license recorded; measured false-positive/negative behavior; required missing check cannot produce an audit-qualified acceptance. No Auditor-to-Builder information flow. | MEASURED: synthetic holdout fails 5% false-flag bar; required external membership remains unavailable |
| P4 | Harden supported operations and evidence lifecycle / harness implementer + security reviewer | P1 | Real cancellation, crash, disk-full, corrupt/missing materials, key loss/recovery, permission and concurrent-run exercises. No forged repair PASS, silent lost trajectory, private export or old-key overwrite. Document the local trusted-key boundary. | DEVELOPMENT DRILLS PASS; independent R4 acceptance and broader crash durability remain open |
| P5 | Package and qualify the release candidate / release owner | P2b, P3, P4 | Fresh supported Mac installation and uninstall of the package only; locked dependencies and immutable executor images; offline sealed workflow; upgrade preserves prior receipts; backup restore and signature verification succeed. Exact source/build provenance retained. | PENDING |
| P6 | Run a consented private pilot / operator + evaluation owner | P5 | Proposed pilot targets below satisfied; independent human assessment of usefulness; actual failures/interventions recorded; support and recovery runbooks exercised. No public target patches or automatic upstream submissions. | PENDING |
| P7 | Freeze and approve the release / independent reviewers + product owner | P6 | Configured build/tests, real product tests, security/policy, independent GPT/Claude assessment and canonical full Run.verify pass at the frozen revision. All risk floors covered per criterion. Human go/no-go recorded genuinely. | PENDING |
| P8 | Publish production CLI release / release owner | P7 | Versioned release/package, accurate claims, supported scope, changelog and runbook links published; hashes checked; private evidence remains private; post-release checks reproduce installation and representative workflow. | PENDING |

These roles are accountability assignments, not claims that workers or
approvals already exist. Implementation occurs on the dedicated Mac feature
checkout. The Windows checkout remains a coordination surface.

## 5. Proposed measurable acceptance contract

**These are engineering planning defaults, not separately user-approved
numbers or measured results.** The implementation grant permits the coordinator
to adopt or revise them, with rationale, before evaluating the holdout. Record
that as an engineering decision, not fabricated human consent. Human production
go/no-go remains separate. Never lower a target after seeing results merely to
obtain PASS.

| Area | Proposed target | How to measure |
|---|---|---|
| Useful repairs | At least **10 verified repairs out of 30 new blind holdout tasks** within the declared task envelope and fixed budgets. | One supported local model/policy evaluated consistently; all 30 tasks included in the denominator. Unapplied, infrastructure, context and audit failures remain visible. Report results per supported language. This is an initial utility bar, not a correctness guarantee. |
| Validator credibility | Zero false REPAIR_VERIFIED outcomes in the qualification adversarial suite; at least 100 deliberately invalid/spoofing cases. | Exercise compiler failures, early process exit, test/validator mutation, skipped tests, wrong subjects, forged summaries, stale evidence, path/symlink escapes and incomplete replay. Tests must check the observed contract, not composed flags alone. |
| Audit qualification | Detect all exact-copy fixtures and at least 90% of the seeded renamed-copy fixtures; at most 5% false flags on a labelled benign/common-code set. | Publish dataset sizes, corpus revision, policy thresholds and classification errors. No general originality claim. Keep held-out audit evaluation separate from threshold tuning. |
| Audit availability | Every check designated required by the task policy is available and executed before an audit-qualified acceptance; otherwise block that classification. | Optional unavailable checks stay UNAVAILABLE with an explicit coverage ceiling. If corpus-membership cannot be supported, exclude that claim and EACH-P3 rather than invent evidence. |
| Evidence durability | Every pilot run has a signed final or honest partial receipt; all declared retained files verify. Zero silent evidence loss, private export or forged success. | Verify actual files independently after both normal completion and injected interruptions; enforce retention/quota limits without deleting evidence silently. |
| Pilot stability | At least 30 runs across 3 consented private workflows over at least 7 days, on the declared support envelope. | Include real useful repairs, negative outcomes and recovery exercises; separately count fixture tests and real local-model attempts. User approval of usefulness is genuine, not inferred from AI review. |
| Recovery | All documented recovery drills succeed without overwriting original receipts or rotating an existing key unexpectedly. | Restore retained evidence from backup and verify with the original public key; recover an interrupted run without duplicating uncertain side effects. |
| Performance and cost | No accepted run silently exceeds P1's declared wall-time, memory or attempt budget. | Measure actual model loading and execution; report timeout/limit failures. Set numerical budgets from the supported Mac and representative task measurements, not guessed universal latency. |

Thirty tasks are not a claim of statistical production-grade correctness.
Broader claims require broader evidence. Keep exploratory development tasks,
the existing 25 historical tasks and the new holdout distinct. A failed holdout
requires a new candidate and a genuinely fresh holdout, not repeated tuning
against the same hidden fixes.

### Measurement and custody rules

P1 separates development tasks, audit calibration fixtures and qualification
holdouts. Freeze sampling frame, eligibility, exclusions, project/fix clusters,
identifiers and custody before execution. Related fixes or variants cannot
straddle splits. Holdout answers, human fixes and hidden tests remain outside
Builder input and tuning feedback. Reveal qualification outcomes only after
model/policy/validator identity is frozen. A change informed by those outcomes
consumes the holdout; new qualification requires fresh tasks.

Report validated repair count and audit-qualified repair count separately.
All eligible tasks remain in the denominator, including required-audit
unavailability, infrastructure failures and budget overruns. Confidence means
sampling uncertainty, not an AI score or signature-derived assurance. Report
raw counts and intervals with their assumptions; correlated project tasks
do not establish independent-binomial population rates. Ten repairs out of
thirty does not establish a universal one-third success rate.

Audit calibration records dataset sizes, independent labelled units,
transformation rules, label rationale, corpus/tool identities and thresholds.
Evaluate a disjoint set without tuning to its labels. Distinguish a correct
common-code match from inappropriate policy escalation. Handcrafted spoof
cases provide regression coverage, not a population estimate of zero risk.

## 6. First useful slice and failure diagnosis

Start with a small, permissively licensed repair in the task envelope most
likely to be supportable; constrain source size and supply a complete approved
behavioral contract. Do not start with another large model acquisition or
assume fixing the M7 cache is a production prerequisite.

P1 records one observed support row: architecture, macOS, RAM, Python,
model backend and exact weights/config/tokenizer identities; executor context,
image/toolchain digests; supported language, source/context/output limits,
patch forms, timeout, memory, attempts and disk reserve. Measure cold loading
and representative validation on calibration tasks before assigning hard caps.
Unknown support rows remain unsupported. Imported target code never executes
on the Mac host.

First exploration is bounded to **three eligible tasks and three model
attempts per task**, under measured caps. One coherent harness fix batch may
address an evidenced root cause. If no useful repair emerges, preserve the
failure taxonomy and escalate the capability limitation once; do not acquire
models or tune tasks indefinitely. Adoption remains human-reviewed.

Before counting P2a success, observe expected validation cases/results through
a candidate-independent boundary, with immutable validator identity and
matching candidate hashes. A zero exit or candidate-emitted completion marker
alone is insufficient. Demonstrate genuine baseline failure, normal success
and early-exit/forged-output/mutation rejection through the actual executor.
Reuse the existing scoped validation pipeline, not a new framework.

Before changing model choice, quantify where failures occur:

1. Does the actual context fit the declared model budget?
2. Does the response satisfy the proposal contract?
3. Does the candidate apply to the recorded preimage and permitted paths?
4. Did compilation succeed and did the independent validator actually run?
5. Does the candidate pass meaningful positive, negative and regression cases?
6. Are subject hashes, input provenance, audit states and retained files truthful?

Fix the earliest evidenced harness defect. If the local model remains incapable
on a valid packet, preserve the negative result. Any model comparison uses
identical packets and budgets, existing authorized local artifacts first.
New gated-model terms are never accepted on the user's behalf.

## 7. Release-blocking triage and known limitations

| Item | Required disposition before launch |
|---|---|
| Zero verified repairs in the existing benchmark | P2 must establish real utility; more AI approvals do not close this. |
| In-process native validators can be fooled by candidate early exit or degenerate behavior | Add independent positive/negative controls and completion/result checks; demonstrate spoof rejection. Never call a passing exit alone proof of comprehensive correctness. |
| Provenance comparisons unavailable in actual experiments | P3 must provide real supported comparisons or exclude their claims. Missing corpus evidence is never PASS or a legal guarantee. |
| Historical missing producer/subject metadata | Preserve UNKNOWN; require explicit current source identity and immutable subject for new qualification evidence. Revalidation is not new authorship. |
| Legacy fixture/error handling and optional source-edit restrictions | Reproduce and triage against the support envelope. Fix supported-path failures; explicitly exclude unsupported paths. Do not treat fixture behavior as real-model utility evidence. |
| Patch encoding, deletion and unsupported diff forms | Document and enforce supported forms; unsupported input must fail explicitly, not appear successfully applied. |
| Private key storage, backup and receipt retention | Demonstrate permissions, recovery, cleanup boundaries and key identity preservation. No invented hardware/TEE protection. |
| Stale M0/M1 prose in onboarding/security documents | Reconcile present-tense status and supported commands while preserving historical sections as dated history. |

## 8. Evidence, change control and stop rules

The production ledger is a tracked summary; a new canonical Run holds execution
state under ignored `.architrave/runs/`. Use `harness/architrave_runtime.py`,
never manually edit canonical state. Register immutable execution evidence with
its actual producing revision and bind gates to each applicable criterion.

For every accepted packet, record: criterion IDs, dependencies, source SHA,
actual commands and results, private artifact hashes, risk, reviewer scope,
limitations, and disposition. Public reports contain sanitized metadata only.
Private prompts, completions, target source/patches, model weights and keys are
never published automatically or supplied to external candidate reviewers.

Sensitive spec changes require real approval. Publishing target lineage is a
separate user decision. The existing private Xodus shadow policy stays in force.
AI reviewers contribute independent analysis; they do not provide human consent
or legal certification.

Stop advancement when a required criterion fails, required evidence is unavailable,
validation was spoofed, privacy/isolation drifts, or a signing/recovery action is
uncertain. Fix within the current packet or record an actual blocker; continue
only independent dependency-ready work. Never turn an unavailable check into
PASS, rewrite old results, or reduce a gate after a failure.

Declared optional UNAVAILABLE checks do not stop unrelated work; they cap the
supported classification and claims. A required missing check blocks only its
dependent acceptance and tasks. Auditor results remain terminal; retries
receive the original permitted packet, never matching source or audit-derived
implementation details.

At P7, freeze implementation, complete configured and product gates, obtain
independent GPT/Claude and specialized security/policy verdicts at that revision,
then execute canonical `RunStore.verify()`. Publish final documentation
separately from reviewed implementation identity.

## 9. Scheduling and next action

There is no defensible production ETA yet: utility and audit availability are
unproven. P1 records an initial work estimate; P2a and P3 produce the evidence
needed to forecast P5-P8. The proposed pilot imposes a minimum seven-day
observation window, not a total project estimate.

**Next action: independent review of the frozen development candidates and
disposition of measured P3/P4 qualification gaps.** P3/P4 prerequisite work
has executed as recorded in section 11; no production acceptance is inferred.
P2a's current exploration is stopped, not silently extended.
The later mandatory review correction in section 12 blocks P1 API acceptance;
P3/P4 measurements remain independent diagnostic/operational evidence.
The original intake direction was to load the accepted research evidence,
open the production qualification Run, and freeze a small supported envelope and the
development contract under the user's autonomous implementation authority.
This document does not publish a release or claim human approval of its
engineering thresholds.

## 10. Adversarial review and execution policy

The first independent ledger review returned REVISE: validator credibility
was not a P2a prerequisite; development and release decisions were conflated;
measurement splits, support limits and optional-unavailability rules needed
definition. Those findings are incorporated above. Review is not production
acceptance, and historical gates do not qualify new implementation.

The implementation choice is to reuse the existing CLI, durable Run, model
adapters, executor, receipts and audit helpers. Narrow the initial task envelope
before replacing machinery; introduce a new dependency/model only after an
observed unsupported capability or missing-tool error and applicable consent.
No replacement control plane or speculative infrastructure is justified.

P0 bookkeeping is low-risk and mechanically checked. P1's validator boundary,
P2/P3 trust-sensitive changes and P4 recovery/key work require independent
verification; security/policy or high-blast-radius changes require the
configured cross-family and specialized review floor. Record actual provider
provenance and scope, not reviewer self-labels. Existing risk gates remain
authoritative per criterion.

Run targeted checks during each small slice and full configured gates at
integration or mandatory high-risk boundaries. A ledger-only change requires
document/link consistency, not a claim of fresh runtime acceptance. Preserve
the real intake, decisions, gates, private artifacts and phase events through
supported APIs; do not reconstruct nonexistent execution history.

Related sources: [claims and non-claims](claims-and-nonclaims.md),
[threat model](threat-model.md), [research release evidence](development-status.md),
[authoritative mandate](EACH_BOOTSTRAP_MANDATE.md).

## 10. Executed first development slice (2026-10-03)

Canonical Run: `each-production-first-slice-20261003`. The completed research
Run remains revision 102, with original acceptance/evidence untouched. The new
Run represents P0-P8, with default-deny development grants and confirmation
requirements for target publication, gated terms, sensitive specs and release.
Engineering authorization is not fabricated human consent.

P0 reconciled source, research state and absent owned worker PIDs. P1 measured
the support row and separate arithmetic calibration in
[the development contract](production-development-contract.md). Qualification
defaults were retained as an engineering decision before any holdout use.

The observer reuses the executor and standard library. It was then described
as candidate-independent; actual independent review disproved API-return
authentication, as corrected in section 12.
Actual controls and the benchmark API exercise early exit, forged summaries,
skipped cases, immutable test/source mounts, real failure and real success.
Forty-one additional harness regressions cover this slice, partial source-cache
provisioning, authenticated resource ownership/resume recovery and source-fence
decoding. This is regression coverage, not the later 100-case qualification.
Independent GPT/Claude, security/policy and criterion reality acceptance remain
outstanding; a development task gate is not R4 acceptance.

| Development task | Actual calls | Original signed outcome | Receipt SHA-256 |
|---|---:|---|---|
| humanize negative-size | 3 | REPAIRED_RUN_INCONCLUSIVE | `de8bdeea965c19a029585b80ccd7ef7d17768d7712d8280782b23edf23da2498` |
| humanize one-byte-float | 3 | PATCH_REJECTED | `a84459107ffc6fc764f04e131a0050d49c6f7026374ce7307fd99abd8c29c461` |
| humanize yotta-rollover | 3 | PATCH_REJECTED | `021cf3c6dff8ed51049e4e101d0281bcdd70e86ee3d94f6403f5993da8d535eb` |

**Utility: zero verified repairs out of three new development tasks; nine real
local-model calls.** No holdout was selected/consumed. All tasks belong to the
humanize development cluster, excluded from future holdouts; they do not supply
independent population-rate evidence. Each task reproduced genuine baseline
failure with every expected case observed. Each signed receipt and all three
declared retained paths verify. Task times were 101.30, 140.67 and 131.59 seconds,
all below the reported 1,200-second ceiling.
Generation source is `e635eebf7c211e25846b3a7cf07c7529b306ce9e` for the first
task and `47cf12df2313e3ae44c71360b4e85825dfaebb50` for the latter two;
later diagnostics do not restamp original producer SHAs.

Diagnosis identified a real source-presentation defect: a closed code fence
was passed through as Python, then a conservative fence count rejected literal
Markdown in valid Python docstrings. The consolidated correction removes only
the outer presentation wrapper, preserves valid Python literals and rejects
ambiguous separate blocks. Original receipts/outcomes remain immutable.
Source-free diagnosis of recorded responses, with **zero new model calls**,
showed unchanged one-byte candidates and rollover candidates failing meaningful
lower-unit regressions. This is an evidenced format/no-op/behavioral ceiling
under this packet policy, not proof that every local model is incapable.

No candidate qualified for terminal provenance comparison; audit stayed
UNAVAILABLE/not-run for that explicit reason. There is no audit-qualified
repair, EACH-P3, production-launch, human-adoption or legal-certification claim.
This utility lane stops at its authorized cap. P3/P4 are the next independent
dependency-ready engineering workstreams after frozen-candidate review.

## 11. Independent P3/P4 continuation (2026-10-03)

Run `each-production-p3p4-20261003-v2` executes independent prerequisites using
P1's measured development contract; P1 R4 acceptance remained pending at that
snapshot and is now BLOCKED by the later review correction. The original
failed firstslice Run (revision 69), nine real calls/negative receipts and
completed research Run (revision 102) remain unchanged. A policy-intake-only
predecessor was denied before implementation; no utility budget was extended.

Actual [audit measurements](audit-qualification.md): self-authored Apache-2.0
reference corpus, four disjoint project clusters and 26 units per split.
Exact 8/8 and renamed 4/4 detections in both; benign false flags 1/14 (7.14%) in
both, above the frozen engineering 5% target. Three common-code matches per
split are correct attribution but also expose inappropriate default escalation.
No label-based suppression or holdout tuning. External training membership and
mature license scanning remain UNAVAILABLE. P3 qualification is not PASS;
the consumed synthetic holdout is regression-only on replay.

Actual [operational drills](operator-runbook.md): SIGINT to owned PIDs,
SIGKILL to owned container CIDs, timeout, real 1 MiB tmpfs ENOSPC, permission
denial, missing/corrupt/symlink artifacts, concurrent key initialization/runs,
temporary-key/evidence backup restore and full verification. Existing
Receipt/signing/path/executor/observer helpers are reused; no crypto/framework
or target implementation is added. No user's original key is rotated/deleted.

The drill found and fixed an additional real source-fidelity mechanism: Colima
read stale lengths after an in-place overwrite of a baseline-read file.
Candidate observation now uses a fresh sanitized worktree with identical
preimage manifest; actual container/host byte-hash and cancellation-receipt
regressions pass. Original firstslice acceptance must still be independently
reviewed; this new candidate does not retroactively qualify its runtime.

The [frozen integration evidence](production-p3p4-evidence.md) records
implementation `0ce8302260c70e3a5d882b95c9a3a84db6e56206`: configured base
573 passed/3 optional skips, explicit audit/models 576 passed/zero skips,
39 new targeted controls, and the source-free artifact hash. The continuation
Run is FAILED revision 36 (P3 FAIL, P4 UNTESTED); engineering tasks completed
do not turn that outcome into production acceptance.

P4 implementation/testing is not R4 production acceptance. Missing host
SIGKILL/power-loss and MLX-interruption guarantees are explicit ceilings, not
invented PASS. No audit-qualified repair, production release, pilot, legal
certification or new local-model repair is claimed. P2 utility remains blocked,
so P2b/P5 are not dependency-ready.

## 12. Mandatory independent observer correction (2026-10-03)

Actual independent adversarial/security reviews at frozen `8b43fe055d7f`
returned REVISE. The previously unconditional "early exit incomplete, never
PASS" claim was false: arbitrary candidate code shared the worker interpreter
and serializer. Actual public synthetic controls reproduced matching valid JSON
plus early exit and serializer substitution, both previously yielding
`REPAIR_VERIFIED` without authenticating the requested API return.

The [corrected development contract](production-development-contract.md)
declares **sandboxed PROCESS-RESPONSE observation only**. Matching response
observations cannot produce API `REPAIR_VERIFIED`; they produce signed
`REPAIRED_RUN_INCONCLUSIVE` evidence and stop retries. P1 remains BLOCKED pending
a genuine stronger boundary or an explicitly authorized changed qualified
contract. No narrower production outcome has been substituted or approved.
The exhausted development entry point stops before loading a model.

Deep candidate stdout JSON was also actually reproduced raising
`RecursionError` through observer/benchmark before receipt finalization.
The narrow candidate JSON parse/compare boundary now marks it incomplete;
actual regressions retain signed negative fixture trajectory, patch and inputs.
This is not a broad exception swallow or a new framework.

The original source-free development proof did **not** embed the claimed
534/537 gate outputs. Existing exact-8b configured/extras artifacts were
independently located and hash-checked, and source-free summaries recovered
without rerunning unchanged tests. Original failed Runs, the nine local-model
calls/negative receipts and research revision 102 remain immutable.

See [the correction evidence](observer-review-corrections.md). P3 remains failed
at 1/14 benign false flags per split; external membership/scanning remain
UNAVAILABLE. P4 operational measurements do not authenticate API returns or
confer R4 acceptance. Original production usefulness and P5-P8 remain unmet.
