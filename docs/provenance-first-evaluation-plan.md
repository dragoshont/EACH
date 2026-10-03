# Provenance-first evaluation plan

Status: access and lineage assessment; **no qualified neural-model trial yet**.
User-directed reset: 2026-10-03. Access prerequisites come before model loading,
adapter work, repair trials or production qualification.

## Focused outcome: findings to independent implementation

The user's objective is a two-agent workflow, not a generic repair leaderboard:

```text
Frontier investigator
  -> public API evidence + recorded black-box observations
  -> origin review + approved behavioral packet
  -> separate Builder using an EACH-qualified local model
  -> private candidate + independent behavior/regression validation
  -> terminal attribution audit + signed retained evidence
```

**Models:** qualify access and inspectable base/post-training dataset lineage
once per exact model artifact, with a retained dossier. A new model, adapter,
fine-tune or materially changed lineage requires reassessment. The Builder
agent should consume the eligibility decision rather than making ad hoc
training-provenance judgments on every task. Missing evidence blocks use.

**Harness:** enforce the separation between investigator and Builder, exact
allowed materials, model eligibility, isolated execution, truthful validation,
terminal audit and complete receipts. Reuse existing components; change them
only for a concrete failure in this workflow. The catalog currently blocks
unqualified models; this is not yet a working qualified-model pipeline.

**Tasks:** independently implement one representative behavior from the user's
Xodus work, then expand to its remaining bounded behaviors. Unrelated humanize
trials remain history and do not answer whether this objective works.

This reduces repeated provenance uncertainty through reviewed evidence and
enforced policy. It cannot guarantee lawful training, originality, upstream
acceptability or legal clean-room status.

### Investigator-to-Builder contract

- A frontier model's unsupported finding is `MODEL_INFERENCE`, not a measured
  `BLACK_BOX_OBSERVATION`. Reproduce it or exclude it from a sensitive packet.
- Each observation records the tested artifact/version, platform, input,
  output/error, procedure, time and evidence hash. Distinguish measured behavior,
  public documentation, user assertions and unresolved hypotheses.
- The behavioral packet contains interface, requirements, edge cases,
  expected outcomes and source references. It excludes frontier-generated
  implementation, patches, pseudocode, source-derived algorithms and hidden
  investigator context. A paraphrased implementation is not a clean spec.
- Existing AI-derived fork patches are not Builder inputs. Preserve them
  separately for post-generation evaluation only. A pre-change source baseline
  must be permitted, pinned and checked for prior AI-derived modifications.
- A fresh Builder context receives only that packet and explicitly permitted
  baseline files. It never inherits the frontier conversation or unrestricted
  repository history. Sensitive approval is genuine and hash-bound.
- Preserve private validation evidence. Report only approved bounded feedback;
  no matching reference source or Auditor-derived implementation details return
  to Builder. A target that cannot be validated credibly remains unverified.

### First Xodus task: the user's private AI-work fork

The first metadata check examined the public fork, whose `main` matched
upstream. That was the wrong source for the user's AI-work changes. Prior
user-session history and live repository metadata now identify the private
AI-work repository and its companion private runtime repository. Their exact
references are retained in the private coordination packet, not published here.

The private work includes a 20-row gameplay-validation artifact with separate
fields for gameplay, save/reload, cloud, multiplayer, runtime/version, measured
performance and recording references. Only its schema and file identity were
inspected for this task map. Its contents remain investigator evidence, not an
approved Builder specification; private notes can contain implementation hints.
A row marked successful is not proof that every feature is implemented or that
the observation itself has acceptable origins.

Next, the investigator selects one bounded API behavior with a reproducible
input/output observation and an independently justified expected result.
Prefer a reversible, offline behavior that can be validated in a disposable
environment. Whole-game launch or broad store integration is not the first
task. Do not access personal saves, cloud data or launch games merely to create
this packet.

Retain the actual before/after range and observation-artifact hashes privately.
Prepare a new origin-reviewed behavioral packet from permitted evidence.
Treat unsupported notes as hypotheses; reproduce or exclude them. Select a
permitted pre-AI implementation baseline rather than copying the private fork
into the Builder context. The frontier patch remains sealed through generation
and terminal audit. No target implementation was read or generated during this
metadata and schema check.

### Immediate work, in dependency order

1. **Model access and lineage:** resolve the existing access checkpoint. No
   extra credits/token ceiling was added, but consent and unknown data lineage
   cannot be bypassed.
2. **Investigator packet, independently ready:** use the identified private
   observation inventory to propose one bounded behavior. Record exact API,
   permitted baseline, observation procedure, inputs/outputs, negative controls,
   source origins and uncertainties; keep implementation advice out.
3. **Harness boundary:** validate that packet's declared materials, fresh
   Builder context and credible tests with the existing harness. Do not
   redesign unrelated machinery or count FixtureModel as qualified inference.
4. **Real trial:** only after model eligibility and sensitive-spec approval,
   run the separate local Builder; retain all performance and provenance data.
   Neither access nor observation inventory alone completes this step.

## Ordered steps

| Step | Action | Exit condition |
|---|---|---|
| 1. Access | Check model and dataset permissions separately, using only previously granted access. The user reviews/accepts any gated terms in their own account. | We can lawfully inspect the candidate's actual training-data evidence and obtain its exact model artifact. Otherwise record BLOCKED. |
| 2. Training lineage | Identify the exact checkpoint, base-training mixture, dataset versions, source identifiers, filtering and every continued/instruction/preference/synthetic/distillation stage. Review accessible records and coverage limits. | A short independently assessed dossier is ELIGIBLE, with no required UNKNOWN stage. No family name, hash or license alone grants eligibility. |
| 3. Local runtime | Only for an eligible model, acquire/hash the approved weights and verify one existing supported backend on the Mac. Record any format conversion and actual sampling/context behavior. | Real local completion with recorded artifact/runtime identity; no cloud target generation or silent model substitution. |
| 4. Wiring test | Exercise one real-model fixture through the existing scoped patch, isolated validation, terminal audit and signed-retained-file pipeline. Use completion/FIM for base models and the documented instruction format for instruct models. | Actual stages and failures are inspectable. A fixture repair is a wiring result, not a usefulness benchmark. |
| 5. Xodus pilot | Resolve the user's actual change range; freeze one representative permitted Xodus behavior, approved investigator packet and pre-change baseline. Keep the frontier implementation hidden. Use the same packet and documented attempt policy for each eligible candidate. | A real local-model implementation passes independently observed behavior and regression checks; full evidence is retained. Negative/inconclusive outcomes remain explicit. |
| 6. Selection | Compare provenance eligibility and utility as separate dimensions, using the recorded results. | Choose an eligible candidate with demonstrated useful repair or preserve an honest negative result. No provenance relaxation to improve the score. |

This supersedes the earlier generic three-task exploration as the next task
priority. It is not the later production holdout or a claim of full-fork
compatibility. No extra infrastructure or qualification framework is needed.

## Candidates and access priority

| Priority | Exact candidate | Data that must be assessed | Current prerequisite |
|---|---|---|---|
| 1 | `bigcode/starcoderbase` | Actual StarCoder training mix: The Stack v1.2-derived code, notebooks, issues and commits; exact checkpoint-stage mapping. | Model configuration returned HTTP 401 on the Mac; no existing Hugging Face credential. The dataset README is reachable, but record access is not established. |
| 2 | `bigcode/octocoder` | StarCoder ancestry plus CommitPackFT and OASST OctoPack fine-tuning data and processing. | Weights are ungated; base ancestry and every post-training stage still need qualification. Existing incomplete-download/adapter diagnostics are not provenance approval. |
| 3 | `bigcode/starcoder2-3b` base | Exact The Stack v2 training subset and all additional sources, including the documented natural-language data. | Model weights are ungated; dataset terms and record access are separate. The Stack v2 bulk access requires additional agreement. |
| Alternative | `allenai/OLMo-1B-hf` original base | Dolma v1_5, original training recipe, component source lineage and publisher HF-format conversion. Not OLMo2 or an instruct checkpoint. | Manifest/recipe are accessible; sample shards returned HTTP 403 for every component on the Mac. It remains BLOCKED. |

Granite remains a candidate only if its required source-level training lineage
can be established. Qwen is excluded from provenance-first qualification.
No row above is an approved model.

Access links:
- [StarCoderBase model](https://huggingface.co/bigcode/starcoderbase)
- [StarCoder training data](https://huggingface.co/datasets/bigcode/starcoderdata)
- [The Stack v2 training identifiers](https://huggingface.co/datasets/bigcode/the-stack-v2-train-smol-ids)

Never paste tokens into chat or commit credentials. Existing access can be
checked without accepting new terms. The assistant must not accept click-through
terms or represent user consent that did not occur.

## What counts as a result

- **Eligibility:** documented, inspectable base and post-training dataset lineage.
- **Usefulness:** actual local-model repairs against credible independent tests.
- **Evidence integrity:** signed declarations plus real retained bytes verify.
- **Audit coverage:** only the comparisons that actually executed with permitted
  reference material; missing required evidence blocks its classification.

These are not interchangeable. A signature does not prove repair correctness.
Matching output from an arbitrary Python process does not authenticate an API
return; the known observer ceiling remains in force. Available training data
does not certify lawful training, originality or legal clean-room status.
No terminal audit result or matching reference implementation is fed to Builder.
Private target source, prompts, completions, weights and signing keys stay private.

There is no added agent-credit/token-budget ceiling. Model context windows,
output bounds and memory/time safety limits remain technical execution facts,
not permission to truncate secretly or expand inference indefinitely.

## Current execution state

The official catalog/CLI rejects all currently unqualified entries before
builder invocation. Low-level adapters are development APIs, not an approved
eligibility bypass. FixtureModel remains available solely as a deterministic
harness test.

The canonical Mac Run `each-provenance-first-20261003`, revision 7, records:
- Catalog provenance prerequisite: PASS.
- Eligible training lineage: BLOCKED_EXTERNAL.
- Qualified local evaluation: BLOCKED_EXTERNAL.
- Status: WAITING_EXTERNAL; zero generation calls, weights acquired or terms
  accepted by this qualification step.

The catalog correction at `149ad3caae0aa18f76fdba05fbcc5144d9062400` passed
configured gates (594 tests, three optional skips), explicit audit/models
checks (597 tests, zero skips) and Ruff. Independent bounded correction review
accepted the fail-closed behavior and documentation; it did **not** qualify
a model or complete a repair trial.

**Next work is step 1, not another repair experiment.** Once permitted access
is established, finish one candidate's dossier before enabling it.
See [model provenance](model-provenance.md) for primary sources and
[the production ledger](production-readiness-ledger.md) for later release gates.

## Performance publication and retention

User direction, 2026-10-03: retain all evaluation data so performance results
can be published. This is not permission to publish private target artifacts.

Keep original specifications, permitted input files, model/dataset eligibility
evidence, exact model manifests, backend/environment identity, rendered prompts,
raw responses, every attempt, patches, validation and audit outputs, errors,
sampling parameters and signed receipts privately. Do not prune failures,
replace an old run, or delete retained weights/evidence as cleanup. Backups and
signing-key storage follow the operator runbook; private keys never enter the
public result package.

Use a fresh report identifier for every experiment. Reports cannot overwrite
an existing report, including an interrupted report's private diagnostic journal.
The journal retains materialization errors separately from public summaries.
Each completed task summary records its original receipt digest.
New benchmark tasks archive their original input files and prompt excerpt
before execution/generation. Expected backend failures retain a signed partial
attempt with its measured call duration and private diagnostic. Unexpected
task errors are journalled and re-raised; an incomplete suite is not published
as a completed comparison or invented zero-call result.

New task reports record end-to-end task seconds and measured completion-call
seconds retained in attempt receipts. Completion-call timing includes adapter
work; it is not pure decoder throughput. Cold loading, tokenizer counts,
peak memory and tokens/second must be separately measured by a backend that
exposes them before those numbers are published. Missing historical metrics
remain unavailable, never zero or retrospectively guessed.

Publish sanitized task outcomes and numeric metrics, cohort size, actual calls,
both all-task and context-reached denominators, required-audit availability,
hardware/runtime/source revisions and fixed evaluation conditions. Include
failed repairs, errors, rejected proposals and budget/context exclusions.
Use the sanitized report renderer, not a raw private receipt or diagnostic
journal. Historical unqualified Qwen/Granite capability runs are a separate
cohort, not measurements of eligible provenance-first models.

Nothing in this retention instruction reopens inference before the access
and training-lineage prerequisites are satisfied.

A read-only retention inventory on 2026-10-03 found **14 existing benchmark
reports and 175 distinct referenced receipt files**, with no missing receipt
files. Its private inventory digest is
`5bf86162cd3dea18311c7a19e3e3b3a200acb6972f98714168ab925f07715b35`.
No original files were changed or deleted and no generation calls were made.
This inventories receipt identity, not a new model comparison or full-material
qualification of every historical run.
