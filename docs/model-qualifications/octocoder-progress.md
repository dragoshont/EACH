# OctoCoder lineage assessment progress

Status on 2026-10-03: **independently assessed ELIGIBLE for bounded research
dataset lineage**, at the same scope as the original StarCoderBase dossier.
Access has been granted for the model and inspected post-training datasets.
This decision does not provision the weights, enable the loader, qualify
performance, or certify exact sample membership/licensing.

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
- Next: provision and hash the exact original weights, verify local runtime
  and evaluate the same approved Xodus behavioral packet.

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

Primary sources:
- [OctoCoder model card](https://huggingface.co/bigcode/octocoder/blob/0f863c63e38ba80fc2c4010f34a7f46d537a9eee/README.md)
- [OctoPack paper](https://arxiv.org/html/2308.07124v2)
- [Original StarCoder paper](https://arxiv.org/html/2305.06161v2)
- [Pinned OctoPack source](https://github.com/bigcode-project/octopack/tree/e17a8f6470264286bc6a52eb8263582083bf3bf6)
- [OpenAssistant original dataset](https://huggingface.co/datasets/OpenAssistant/oasst1)
