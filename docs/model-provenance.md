# Model evidence, not licensing conclusions

## Governing eligibility correction (2026-10-03)

The user clarified that EACH works **only with models having clear training-data
provenance**. This is an eligibility requirement before new target generation,
not a preference traded away for repair performance.

The [finite qualification registry](model-qualifications/registry.json) records
the current exact-artifact decisions. StarCoderBase is **AUTHORIZED** and the
initial/reference Builder after retained original weights, conversion, runtime
identity and signed evidence verified. OctoCoder is separately **AUTHORIZED**
under its independently reviewed dataset-stage scope. StarCoder2 is **BLOCKED**
on synthetic ancestry; Comma is **DEFERRED** after one bounded document pass.
Model research is closed for this launch cycle under the
[dual-lane addendum](EACH_DUAL_LANE_ADDENDUM.md).

The catalog keys `starcoderbase-mlx` and `octocoder-mlx` require the exact
qualified artifacts; other entries fail closed before loading weights or
invoking an adapter. Historical
builders and receipts are retained for reproducibility and tests; their presence
does not authorize new generation. FixtureModel is a deterministic harness test.
Enforcement is at `catalog.load_model` and its official CLI callers. Low-level
Python adapters remain callable for development; using them to bypass
eligibility is prohibited, not claimed mechanically impossible.

Qualification must separately establish the exact base-model identity;
documented dataset identities/revisions and collection, filtering and license
processes; inspectable or queryable source lineage with coverage limits; and all
instruction-tuning, synthetic, preference/alignment and subsequent training
inputs. Distillation and synthetic-data ancestry cannot be assumed transparent.
Conversion and tokenizer/runtime identity remain necessary but are different
evidence. Missing stages or unavailable lineage cannot become PASS.

There is no authorized model-family list. OctoCoder's StarCoder continuation
and additional instruction data were assessed separately, not inherited from
StarCoderBase's decision. A model card's claim or a
permissive weight license alone does not establish clear training provenance.
This policy does not claim that documented datasets prove lawful individual
training items, originality of output, or legal clean-room status.

Qwen was a capability fallback outside this corrected qualification scope.
Its nine-call trial and other Qwen experiments remain signed historical records;
they are not evidence that provenance-qualified models failed. Do not rewrite
their identities or use them as a production provenance gate.

## Historical model experiments, not current authorization

The following M2/M6 notes predate the governing provenance-only correction.
They do not authorize a historical model or reopen a model search.

M2's initial supported Builder was Granite Code 3B Instruct through local MLX-LM.
Granite Base was also evaluated and did not produce a verified fixture repair.
This small comparison is not a broad leaderboard or evidence of originality.

M6's primary benchmark run uses `ibm-granite/granite-8b-code-instruct-128k`
(revision `bed93d8de15bb9bb55cb1da10ae860e2883f4254`, Apache-2.0, ungated).
Unlike the 3B catalog entries (which load pre-converted `mlx-community`
4-bit snapshots), this is the **original publisher's own bf16 safetensors
repository** loaded directly via `mlx_lm.load()` -- no third-party MLX
conversion step exists or is claimed. The manifest's `conversionChain` field
honestly records `"none"` for this entry rather than the community
conversion-chain phrasing used for the 3B entries below. This was verified,
not assumed: an `HfApi` model-info lookup, a direct `config.json` fetch, an
`mlx_lm.utils._get_classes(config)` resolution to the generic Llama MLX
implementation, an actual `snapshot_download`, and an actual `load_model()` +
`complete()` call (real generation, not a stub) were all performed before
this model was used in a benchmark run.

The manifest binds model weights, configuration, tokenizer assets, chat
templates, and other snapshot files by their actual SHA-256 content hashes.
Configuration or template changes change the artifact identity even if weights
are unchanged. Runtime versions come from the installed package, not a constant.
The adapter records its actual generation parameters and the rendered prompt
used by the backend, including the checkpoint's chat-template wrapping.

Community conversion-chain descriptions are **model-card publisher claims**.
They are recorded, not presented as independently reproduced conversion evidence.
The original source weight revision behind a community conversion can remain
unknown; an output artifact's exact hash does not resolve that limitation.

**License correction:** `bigcode/octocoder` at revision
`0f863c63e38ba80fc2c4010f34a7f46d537a9eee` declares `bigcode-openrail-m`
in its canonical Hugging Face metadata, not Apache-2.0 as mistakenly stated
in the original M2 commit summary. It is not gated at that revision.
Historical adapter diagnostics separately reported incomplete downloads
or an unimplemented adapter; these were not claims that MPS cannot support it.
The current catalog rejects unqualified training provenance before those
adapter diagnostics or any inference.

Model licenses do not automatically license generated target patches.
EACH records technical evidence and published claims, not legal conclusions.

## Historical primary-source candidate check (2026-10-03)

These early observations started qualification; none constituted an eligibility PASS.
They replace assumptions based on model families or generic search summaries.
Current decisions are in the registry and exact-model dossiers, including the
StarCoder2 correction that its 3B mixture excludes arXiv/Wikipedia/OpenWebMath.

| Candidate | Verified publisher evidence | Remaining qualification boundary |
|---|---|---|
| `bigcode/starcoderbase` | API reports revision `88ec5781ad071a9d9e925cd28f327dea22eb5188`, OpenRAIL-M, The Stack dedup, and gated access. Anonymous card retrieval returned HTTP 401. | Authorized access and exact full training-mixture lineage review; no terms accepted on the user's behalf. |
| `bigcode/starcoder2-3b` base | API reports revision `733247c55e3f73af49ce8e9c7949bf14af205928` and **ungated model weights**. Card identifies The Stack v2, additional Arxiv/Wikipedia data, a pretraining search index and no instruction-model claim. | Review every additional data source and the exact training subset. The Stack v2 metadata/data are separately gated; weight availability does not imply corpus access or full qualification. |
| `bigcode/octocoder` | Actual card identifies StarCoder fine-tuning on CommitPackFT and OASST; API reports revision `0f863c63e38ba80fc2c4010f34a7f46d537a9eee`, ungated weights and OpenRAIL-M. CommitPackFT exposes repository/commit/path/license fields. | Verify base lineage plus both exact post-training datasets. Its metadata includes unknown and copyleft repository-license categories; dataset metadata is not a blanket permissive-license guarantee. |
| Granite Code base | The original publisher card exists, identifies two training phases and multiple code/natural-language sources, Apache-2.0, and a deprecation notice. | Dataset names and filtering claims do not establish inspectable complete sample lineage; review the additional repositories and second-phase mixture. Do not infer qualification from Apache-2.0. |

The Stack v2 public API exposes blob/content IDs, repository, revision, path
and detected-license fields. Its terms require genuine user acknowledgment;
bulk access additionally requires an agreement with Software Heritage/INRIA.
No gated dataset was downloaded, no weights acquired and no new target
generation performed during this check. Missing access and lineage coverage
remain explicit blockers.

Primary sources:
- [StarCoderBase metadata](https://huggingface.co/api/models/bigcode/starcoderbase)
- [StarCoder2-3B card](https://huggingface.co/bigcode/starcoder2-3b/blob/733247c55e3f73af49ce8e9c7949bf14af205928/README.md)
- [StarCoder2 source project](https://github.com/bigcode-project/starcoder2)
- [The Stack v2 metadata and terms](https://huggingface.co/api/datasets/bigcode/the-stack-v2)
- [Training-subset metadata](https://huggingface.co/api/datasets/bigcode/the-stack-v2-train-full-ids)
- [OctoCoder card](https://huggingface.co/bigcode/octocoder/blob/0f863c63e38ba80fc2c4010f34a7f46d537a9eee/README.md)
- [CommitPackFT](https://huggingface.co/datasets/bigcode/commitpackft)
- [OASST OctoPack](https://huggingface.co/datasets/bigcode/oasst-octopack)
- [Original Granite Code base card](https://huggingface.co/ibm-granite/granite-3b-code-base-2k)

### Original OLMo-1B base: additional ungated candidate, not yet eligible

The original `allenai/OLMo-1B-hf` is a documented publisher conversion of
`allenai/OLMo-1B`, not an OLMo2 or instruction checkpoint. Its public revision
is `aee7752d9c08ee4775e9b0091426d8410e8f6a89`. The publisher's dataset card
maps OLMo-1B to **Dolma v1_5**, not the different v1_7 mixture.

The original frozen training recipe was located at OLMo source commit
`15af6688f1a56609fef2f56eb66052b0baa0ec47`,
`configs/official/OLMo-1B.yaml`. It describes from-scratch initialization,
a 3.1T-token pretraining run and the v1_5 tokenized-data paths. The original
paper describes instruction/RLHF adaptation as future work; that supports
the original base checkpoint's scope, not a claim about later instruct
variants. The HF card explicitly documents the format conversion.

The pinned Dolma repository is
`7f48140530a023e9ea4c5cfb141160922727d4d3`. Its `urls/v1_5.txt` manifest
hash is `0b660ad1cd93a840d759a4efa82f800a0580fd693de6da64dba484aa55d21efc`.
It names the original books, C4, Common Crawl, PeS2o, Reddit, Stack and
Wiki components. Dataset licensing remains mixed; its collection license
does not replace source licenses or prove lawful training.

**Status: BLOCKED, not ELIGIBLE.** A bounded direct inspection on the actual
Mac reached the manifest but received HTTP **403 for every component's
sample shard**. No component-record inspection can therefore be marked
successful in that execution. A separate research report saw some public
records from another execution context; that does not replace missing local
inspection or resolve every lineage stage. Required unknowns remain blockers,
even when a model is described as fully open.

The local existing-access check found no Hugging Face credential. StarCoderBase
configuration access returned 401; the StarCoder dataset README metadata was
reachable, but that does not prove access to its training records. No access
terms were accepted, no weights were acquired and no inference ran.

Next qualification work is to obtain permitted inspectable corpus access,
verify component-level source lineage and exact checkpoint/stage mapping,
then independently assess the dossier before enabling a model. The catalog
continues to reject unqualified entries rather than treating missing evidence
as a capability fallback. The separate StarCoderBase dossier documents the
subsequent access approval and exact-checkpoint eligibility decision.

Sources:
- [Pinned OLMo-1B HF conversion card](https://huggingface.co/allenai/OLMo-1B-hf/blob/aee7752d9c08ee4775e9b0091426d8410e8f6a89/README.md)
- [Original frozen training recipe](https://github.com/allenai/OLMo/blob/15af6688f1a56609fef2f56eb66052b0baa0ec47/configs/official/OLMo-1B.yaml)
- [Pinned Dolma v1_5 manifest](https://huggingface.co/datasets/allenai/dolma/blob/7f48140530a023e9ea4c5cfb141160922727d4d3/urls/v1_5.txt)
- [Original OLMo paper](https://arxiv.org/html/2402.00838v3)
