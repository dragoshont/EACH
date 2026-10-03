# Provenance-first evaluation plan

Status: access and lineage assessment; **no qualified neural-model trial yet**.
User-directed reset: 2026-10-03. Access prerequisites come before model loading,
adapter work, repair trials or production qualification.

## Ordered steps

| Step | Action | Exit condition |
|---|---|---|
| 1. Access | Check model and dataset permissions separately, using only previously granted access. The user reviews/accepts any gated terms in their own account. | We can lawfully inspect the candidate's actual training-data evidence and obtain its exact model artifact. Otherwise record BLOCKED. |
| 2. Training lineage | Identify the exact checkpoint, base-training mixture, dataset versions, source identifiers, filtering and every continued/instruction/preference/synthetic/distillation stage. Review accessible records and coverage limits. | A short independently assessed dossier is ELIGIBLE, with no required UNKNOWN stage. No family name, hash or license alone grants eligibility. |
| 3. Local runtime | Only for an eligible model, acquire/hash the approved weights and verify one existing supported backend on the Mac. Record any format conversion and actual sampling/context behavior. | Real local completion with recorded artifact/runtime identity; no cloud target generation or silent model substitution. |
| 4. Wiring test | Exercise one real-model fixture through the existing scoped patch, isolated validation, terminal audit and signed-retained-file pipeline. Use completion/FIM for base models and the documented instruction format for instruct models. | Actual stages and failures are inspectable. A fixture repair is a wiring result, not a usefulness benchmark. |
| 5. Small repair trial | Freeze three fresh permissive historical tasks, hidden human fixes, identical input policy and three attempts per task for each eligible candidate. Keep the consumed Qwen development cluster out of this comparison. | Report all attempts: response validity, scoped application, build, acceptance/regression, isolation, time and evidence completeness. Unsupported validation stays inconclusive, never verified. |
| 6. Selection | Compare provenance eligibility and utility as separate dimensions, using the recorded results. | Choose an eligible candidate with demonstrated useful repair or preserve an honest negative result. No provenance relaxation to improve the score. |

This is the initial small comparison, not the later production holdout or
pilot. No extra infrastructure or qualification framework is needed.

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
