# OctoCoder lineage assessment progress

Status on 2026-10-03: **independently assessed ELIGIBLE for bounded research
dataset lineage**, at the same scope as the original StarCoderBase dossier.
Access has been granted for the model and inspected post-training datasets.
The lineage decision alone does not qualify performance or certify exact
sample membership/licensing. Subsequent original-weight provisioning and one
actual qualified EACH wiring result are recorded below.

Candidate: `bigcode/octocoder` at
`0f863c63e38ba80fc2c4010f34a7f46d537a9eee`.

## Resolved stage distinction

The original OctoPack paper identifies the selected final model as **StarCoder
fine-tuned on CommitPackFT plus filtered OASST**, not simply StarCoderBase with
an unspecified instruction layer. The original StarCoder paper identifies
StarCoder's additional **35B Python-token** continuation after StarCoderBase.
That continuation must remain in OctoCoder's lineage.

The OctoPack paper describes selecting 5,000 CommitPackFT samples across its
six evaluated languages and using 8,587 filtered OASST conversations. Its
Self-Instruct and other data ablations are separate experiments, not
automatically part of the selected final model.

## Actual OASST record check

Inspected filtered dataset:
`bigcode/oasst-octopack@1f5db3451c66a64e37158fcdf8c1951db8e90b33`,
file SHA-256
`de45760df5da837d265615a17f23fddefb13c18569481e75a522d2bbb5732ada`.

Following the project's documented first-question/first-answer rule, all
**17,174 distinct selected messages from 8,587 conversations** were joined by
message ID to `OpenAssistant/oasst1`'s original release messages. Every
selected message was found and its text hash matched. All selected originals
have an explicit false synthetic flag; none had an unknown flag. This verifies
the released records' metadata, not a guarantee that contributors never used
external assistance.

Original dataset revision:
`fdf72ae0827c1cda404aff25b6603abec9e3399b`; inspected compressed file
SHA-256 `2ff4aa8999c911ffec7972ddf70359f220b3da184b731f3649f68b1391e19341`.
Raw conversation text was not exported or passed to a Builder.

The preprocessing script's intermediate `HuggingFaceH4/oasst1_guanaco`
repository currently returned 404. The direct final-to-original ID/text match
is real evidence; it does not by itself reproduce every intermediate filter.

## Independent assessment and remaining runtime work

- The published paper
  describes 5,000 CommitPackFT samples, not training on the entire released
  dataset. The repository's example `finetuning/starcoder/finetune.sh` points
  to `ArmelR/guanaco-commits`; it is not sufficient by itself to identify the
  final model's complete training run. The small committed manual mixtures
  must not be silently substituted for the paper's selected mixture.
- Independent review accepted the identified dataset-stage ancestry and direct
  OASST record join, preserving the exact-subset and intermediate-reconstruction
  limitations. No required unidentified datasource stage was found in the
  supplied evidence. This is not proof of the historical training job or a
  universal source-license guarantee.
- Original-weight provisioning and one actual local fixture wiring call have
  subsequently completed. The approved Xodus behavioral packet remains a
  separate task; this fixture result is not Xodus capability evidence.

The assessment distinguishes **known dataset-stage lineage**
from **exact training-sample membership**. The paper identifies all selected
dataset stages and the sampling population/rule; the released source records
are inspectable. This inspection has not recovered the exact 5,000 CommitPackFT
row IDs or reconstructed the training job. Whether that is a blocking gap
depends on the same documented-dataset-lineage scope used for StarCoderBase;
it must not silently become an exact-membership or lawful-training claim.
The independent verdict was PASS/ELIGIBLE for the exact checkpoint and this
bounded dataset-stage scope, not for loader implementation or full release.

| Stage | Declared/inspected source | Scope |
|---|---|---|
| Multilingual base | Original StarCoderBase lineage dossier: The Stack v1.2-derived code, issues, commits and notebooks; released `starcoderdata` files unchanged from the model-release revision. | Reused dataset-stage evidence, not a new base qualification by model name. |
| Python continuation | Original StarCoder paper explicitly identifies 35B additional Python tokens from the same training dataset for StarCoder. | A real additional stage in OctoCoder ancestry; not part of StarCoderBase itself. |
| Instruction tuning | Original OctoPack paper/model card identify CommitPackFT plus filtered OASST as the final model mixture. | Self-Instruct and xP3x are described as separate ablations, not assumed final-model ingredients. |
| OASST ancestry | Released first-two-message selections all match original OASST IDs/text hashes, with explicit false synthetic flags. | Metadata is evidence of recorded ancestry, not proof that every contributor independently authored every word. |
| CommitPackFT ancestry | Released records expose repository, commit, paths and license metadata in all six sampled language components; public collection/filtering scripts are pinned. | Exact random subset membership and comprehensive per-record licensing are not established. |

Inspected CommitPackFT release:
`fc56fe33c030c6daa414c2b112c932b8eed085e6`.
Pinned collection/filtering source:
`bigcode-project/octopack@e17a8f6470264286bc6a52eb8263582083bf3bf6`.
Its model license is OpenRAIL-M, not Apache-2.0; neither that license nor the
dataset's collection license replaces individual source licenses.

Bounded direct inspection of the first released CommitPackFT record in each
of Python, JavaScript, Java, Go, C++ and Rust confirmed readable repository,
commit, old/new path, language and license metadata. This is six records,
not the exact 5,000 selected examples or an exhaustive license audit. The
sampled Rust record is labelled **AGPL-3.0**; calling the entire released
collection permissive would be incorrect. Known license metadata and clear
dataset identity are not legal clearance for outputs.

No OctoCoder model weights were acquired or inference calls made in this
assessment step. Training-data access/inspection is not model evaluation.

## Subsequent qualified provisioning and actual EACH wiring

Implementation: `867957cb670efdc19946170b8a38267c263cdbd8`.
The new `octocoder-mlx` catalog entry reuses the existing qualified loader
and provisioner. Provision explicitly with:
`python -m each.models.provision_starcoderbase --model octocoder`.
It does not qualify any other checkpoint, family or historical conversion.

All seven original FP32 safetensors hashes were rechecked against the pinned
HF API metadata and downloaded bytes before tensor loading. Only safetensors
and metadata/tokenizer files were requested, not duplicate PyTorch `.bin`
weights. Original files remain in the private HF cache. The 120 GiB free-space
floor and exclusive destination checks apply; existing/partial conversions
are never overwritten.

### Publisher index discrepancy and runtime resolution

The first attempt failed closed before writing a converted shard: the original
index declares **485** tensors but the actual seven files store **484**.
The sole absent index entry is `lm_head.weight`. The stored input embedding
`transformer.wte.weight` is present. This is not the explicit stored-head case
seen in StarCoderBase.

The original configuration has no explicit tie flag; the installed original
GPTBigCode configuration class resolves `tie_word_embeddings=True`, as does
MLX's built-in GPTBigCode configuration. The provisioner admits only this
exact missing-head alias, only with a tied original GPTBigCode configuration,
and records the original index count and omitted alias. All other missing,
extra, duplicate or wrongly mapped tensors still fail closed. No actual
weight is discarded or synthesized. The output index describes all **484**
stored tensors; every FP16 tensor was reopened and compared with its intended
FP32-to-FP16 rounding. This precision conversion is not training.

The failed attempt's empty destination was inspected and renamed to a retained
`.partial-index-mismatch-cdc2097dada0` sibling before retrying. Its private
diagnostic and preservation receipt remain intact. Initial acquisition/check
time was 342.740 seconds; the subsequent cached recheck/conversion was 64.571
seconds. These are provisioning times, not generation throughput.

Private conversion record SHA-256:
`6432ad00b631f340dee0665b8b9e29be678ed765c95a42f434184341ef3e0aca`.
The record contains all original and output file hashes, dtype/versions,
round-trip verification and the exact index exception.

Converted shards (original pins are in `each/models/catalog.py`):

| Shard | FP16 safetensors SHA-256 |
|---|---|
| 1 | `b7a16a596bea36e9d7bcef51c39606511f7b71a9937765a9f1d31d2c3dac9f54` |
| 2 | `3fd47345858ece602413108baef3d378acba6d605637a0239216432dcb5ae4ab` |
| 3 | `b8e8f1ffa9650464fbb35463efed64c1cce204f0c249f847b6f7c70211837b15` |
| 4 | `c0361b47d87edd118bc3c8988771b12e98d16b228320fd4d7651fa1dfdf5ef91` |
| 5 | `385f422c14238b7823d8f69cc55507dc561164140e2325fdf708b60898d97ac2` |
| 6 | `6ea998c7c0699315afca94b9e403505faa688f9ba3d6f450b927f3c93cb75e21` |
| 7 | `84f561e0893eed749437a8f609c9cf5909a6a3c9a9bc0225321a61c533cf2dbc` |

### One real local response

- Run: `octocoder-qualified-wiring-256c03641b83`.
- Official `load_model("octocoder-mlx", max_tokens=512)`, followed by
  `run_model_bakeoff(..., max_attempts=1, proposal_format="diff")`.
- Documented rendering: `Question: {harness instruction}\n\nAnswer:`.
  The exact rendered input is retained in the signed receipt; no expected fix
  or outer-agent completion was substituted.
- MLX actually loaded `mlx_lm.models.gpt_bigcode.Model`, with recorded and
  post-load-verified `tie_word_embeddings=True`.
- One actual nonempty response, baseline exit **1**, candidate exit **0**:
  **REPAIR_VERIFIED** on the hello-repair wiring fixture.
- Strong `colima-each` executor, **EACH-P2**; baseline and candidate tests are
  protected, the candidate uses a fresh worktree, and original inputs are
  retained. Diff mode now has the same protections as FIM.
- Receipt signature and both retained input files: **PASS**.
- Receipt SHA-256:
  `3cac16bc725501f93066d93e3307c8c3d4cead2bf369df3a29ed66c5d8d1f8df`.
- Manifest/loading: 23.193 s; harness: 5.109 s; total: 28.302 s;
  completion-call: 4.436 s. Actual encoded input: **195 tokens**.
  Output token count and decoder tokens/second were not measured.
- Runtime: MLX 0.32.3, MLX-LM 0.32.0, Torch 2.14.1, Transformers 5.18.0,
  safetensors 0.8.0. Original FP32 and converted FP16 artifacts are retained.

Private evidence lives under `~/.each/runs/` and the existing parent Run
`each-provenance-first-20261003`. The scoped execution child is
`each-octocoder-wiring-20261003`: the research parent's empty mutation policy
was preserved rather than manually rewritten. Source-bound integrated gate
stdout and exact receipts are retained for independent review. No
implementation judge-family PASS is asserted by this dossier.

This is one successful fixture wiring check, not a repair benchmark, Xodus
trial, full program completion, production/P3 qualification or legal clearance.
No further Base utility attempts or other model evaluations ran in this slice.
Private prompts, responses, candidate source, keys, data records and weights
were not exported.

Primary sources:
- [OctoCoder model card](https://huggingface.co/bigcode/octocoder/blob/0f863c63e38ba80fc2c4010f34a7f46d537a9eee/README.md)
- [OctoPack paper](https://arxiv.org/html/2308.07124v2)
- [Original StarCoder paper](https://arxiv.org/html/2305.06161v2)
- [Pinned OctoPack source](https://github.com/bigcode-project/octopack/tree/e17a8f6470264286bc6a52eb8263582083bf3bf6)
- [OpenAssistant original dataset](https://huggingface.co/datasets/OpenAssistant/oasst1)
