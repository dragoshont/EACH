# OctoCoder lineage assessment progress

Status on 2026-10-03: **not yet eligible**. Access has been granted for the
model and the inspected post-training datasets, but this progress record is
not an eligibility decision or a performance result.

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

## Still to close

- Bind the full base/continuation artifact lineage to the selected checkpoint.
- Verify the CommitPackFT selected mixture and its relationship to the
  released records and training recipe, rather than assuming every dataset
  entry was used.
- Assess collection/license/filtering limits and the missing intermediate
  dataset with an independent dossier review.
- Only after eligibility: provision the exact weights, verify local runtime
  and evaluate the same approved Xodus behavioral packet.

No OctoCoder model weights were acquired or inference calls made in this
assessment step. Training-data access/inspection is not model evaluation.

Primary sources:
- [OctoCoder model card](https://huggingface.co/bigcode/octocoder/blob/0f863c63e38ba80fc2c4010f34a7f46d537a9eee/README.md)
- [OctoPack paper](https://arxiv.org/html/2308.07124v2)
- [Original StarCoder paper](https://arxiv.org/html/2305.06161v2)
- [Pinned OctoPack source](https://github.com/bigcode-project/octopack/tree/e17a8f6470264286bc6a52eb8263582083bf3bf6)
- [OpenAssistant original dataset](https://huggingface.co/datasets/OpenAssistant/oasst1)
