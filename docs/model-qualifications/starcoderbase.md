# StarCoderBase training-lineage assessment

Assessment date: 2026-10-03. **Independent dossier decision:
eligible for the bounded provenance-first research trial.** This is not a legal,
originality, corpus-membership or production-readiness certificate. The exact provisioned artifact must still be bound to this evidence before
loading; the decision does not qualify other models or complete a runtime test.

## Exact candidate and meaning of eligibility

- Model: `bigcode/starcoderbase`, revision
  `88ec5781ad071a9d9e925cd28f327dea22eb5188`.
- Architecture: GPT-BigCode, 15.5B parameters, 8,192-token context.
- Original publisher artifact: seven FP32 PyTorch weight shards. No
  third-party conversion is qualified by this assessment.
- Model license: BigCode OpenRAIL-M, distinct from training-source licenses.
- User completed Hugging Face authorization and access acceptance. Actual
  authenticated configuration and training-shard requests succeeded.

Eligibility here means that the publisher identifies the training stages and
datasets, releases the processed training mixture for inspection, documents
collection/filtering and source lineage, and we can actually access that
evidence. It does not mean we independently reconstructed training, proved
every item's copyright status, or checked every record in the corpus.

## Training stages

| Stage | Evidence | Assessment |
|---|---|---|
| Base pretraining | The original paper identifies StarCoderBase as trained on 1T tokens from The Stack v1.2-derived code in 80+ languages, GitHub issues/commits and Jupyter notebooks. The released `starcoderdata` card explicitly identifies it as the dataset for StarCoderBase and StarCoder. | Documented and inspectable. |
| Additional Python continuation | The paper distinguishes **StarCoder**, trained from StarCoderBase on another **35B Python tokens**, from the base checkpoint. | Not a stage of this selected StarCoderBase artifact. Required if assessing StarCoder/OctoCoder ancestry later. |
| Instruction, preference or RLHF training | The selected publisher artifact is the original base model; its card and the paper's stage distinction identify no such adaptation for it. Instruction-tuned variants are separate models, not silently included. | No applicable post-training stage in the documented selected base release. A later adapter/fine-tune requires a new assessment. |
| Format/runtime conversion | Original FP32 publisher shards were hash-verified, converted to FP16 safetensors and checked tensor-by-tensor. MLX loaded the result using its built-in `gpt_bigcode` classes and recorded explicit-head configuration. | Completed for the first wiring run below; precision conversion is not training or a new dataset stage. |

Primary stage evidence:
[original paper](https://arxiv.org/html/2305.06161v2),
[pinned model card](https://huggingface.co/bigcode/starcoderbase/blob/88ec5781ad071a9d9e925cd28f327dea22eb5188/README.md).
The inspected model-card SHA-256 is
`d3da47af55f61b85039733235b3697ac62da2f86f9e2e3d267268f282906d26a`.

## Dataset identity and direct inspection

Processed mixture: `bigcode/starcoderdata`, inspected revision
`9fc30b578cedaec69e47302df72cf00feed7c8c4`. The publisher history identifies
the data upload at `670883730e8f2076574206fa065ae75fef6f16b5` on
2023-03-31. We compared all **863 parquet file identities** at the inspected
revision with the model-release-day dataset revision
`771a4a11d98f975ff1a8d5f29206f4ef57fd25d3`: filename, Git blob, LFS hash and
size mappings match. The current README revision is not silently assumed to
be a new training mixture.

The comparison manifest SHA-256 is
`3636743c1f4356db564aa82f6379e0e9b59fed59f0e53faf9edac6c1fece7a34`.
This binds publisher file identities; it is not a download/hash of all dataset
content or independent proof that every file participated in training.

Authenticated bounded parquet inspection covered one shard and metadata-only
record from every distinct released component representation:

| Component | Observed schema / metadata |
|---|---|
| Python code | `id`, `content`, repository name/path and star count. |
| GitHub issues | `id`, `content`; no separate repository/license column in this processed representation. |
| Git commits | `id`, `content`; no separate repository/license column in this processed representation. |
| Jupyter scripts | Content hash, repository/path, repository licenses, ID and content. |
| Structured notebooks | Repository/path, license, ID, chain length and content. |

All inspected metadata columns were readable. About 3 MB of bounded range
reads were used; no bulk corpus copy or model weights were downloaded.
Training text and individual record metadata values were not exported to the
Builder or public report. An inspection sample does not establish uniform
record-level coverage throughout the entire dataset.

The processed issues/commit representations do not preserve separate
source-location columns. Their dataset/stage identity and processed content
are inspectable, but exact original-source attribution for every such record
is not independently established here. This limitation must remain explicit;
if the intended task policy requires that stronger per-record attribution,
the model is blocked for that task rather than granted a blanket PASS.

## Collection, filtering and limits

The Stack documentation describes GitHub/GHArchive collection, repository
license detection, exact/near deduplication and opt-out handling. The
StarCoder training-data card documents additional decontamination, filtering,
near-deduplication and PII removal for the selected mixture.

These are inspectable publisher processes, not proof of perfect filtering.
Detected licenses can be wrong; source attribution may be incomplete; removed
or unavailable upstream repositories can limit later reconstruction; training
code may itself contain generated material. No absence-of-memorization,
all-human-authorship or legal-safety claim follows.

Sources:
- [Processed training dataset](https://huggingface.co/datasets/bigcode/starcoderdata)
- [The Stack deduplicated collection and schema](https://huggingface.co/datasets/bigcode/the-stack-dedup)
- [StarCoder project](https://github.com/bigcode-project/starcoder)

## Retained evidence and next step

Private source-free component inspection:
`45e9fee3103c406069c0d2f752082c5d7b0fce102b904eae0a745c417a004cbd`.
Private release-identity comparison:
`764769847cd3b677b43c282153df61ef7fc4e19f7eef7ce62358e24d69a77ca7`.
Original model/dataset cards are retained with their hashes.

The original seven publisher shards have now been acquired, hash-verified and
converted locally to FP16 safetensors. Every converted tensor was read back and
compared with the intended rounded tensor; the original FP32 shards remain
retained. The conversion record binds source and output files and records that
no training or inference was performed by provisioning.

The first backend-load check exposed an MLX representation mismatch: the
checkpoint stores `lm_head.weight` explicitly while MLX's default tied-embedding
model omits that parameter. The actual stored input/output embedding tensors
were compared and are equal (both shapes 49152 by 6144). The adapter loads the
explicit output head with `tie_word_embeddings=False`, recording this runtime
configuration in identity. No weight is silently discarded or rewritten; the
failed load is retained separately, not counted as a successful generation.

## First actual EACH wiring result

The subsequent invocation used the official `starcoderbase-mlx` loader and
the existing `run_model_bakeoff` harness on the Mac at source
`9fc298bdd828ef64fb04184a6d6d70ed2f08759d`.

- Run: `starcoderbase-qualified-wiring-70e10a921950`.
- One actual nonempty model response; baseline test exit 1.
- Outcome: **PATCH_REJECTED**. No candidate validation ran and no repair
  success is claimed.
- Receipt SHA-256:
  `e4af7aa8eaffa5d441979a9b47bc0862a4baff4740a68c29b04ba58d6131bd10`.
- Signature and both original input files verified against a separately
  retained recovery root; the signed receipt remained unchanged.
- Measured total loader/harness time: 31.863 seconds. This is not pure token
  generation throughput or a benchmark against the other models.

This establishes actual local loading, inference, harness invocation and
retained evidence for the qualified artifact. It does not establish Xodus
capability. The legacy fixture prompt asks for a diff; a base completion/FIM
model must next be exercised with an appropriate declared prompt contract,
not judged as an instruction model or tuned against hidden expected patches.

An independent read-only Adversarial Judge reviewed this dossier and retained
inspection evidence and returned PASS/ELIGIBLE for the exact base checkpoint.
It explicitly accepted documented inspectable dataset/stage lineage, not
exhaustive per-record attribution. This is one independent research eligibility
assessment, not cross-family production or legal acceptance.
Bind only this exact model and evidence to the loader, retain
all original/conversion hashes, then run a real local wiring test before the
approved Xodus behavioral task. OctoCoder and StarCoder2 require separate
stage/dataset assessments; Qwen remains excluded.
