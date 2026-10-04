# K2-65B qualification progress

Status on 2026-10-04: **AUTHORIZED for bounded private research; evaluated
with zero verified Xodus fixes**. All original publisher hashes, local 8-bit
conversion, official loader and private runtime evidence verified. This is not
commercial-use clearance, legal certification or production qualification.

Exact base checkpoint:
`IFM/K2@400af6cd7de09fc9349cc6b5b24db20f778d5b72`.
This is the 65B base release, not `K2-Chat` and not a later aligned variant.

## Why this candidate

K2 is a capability-scale follow-up after three smaller/code-specialized models
produced no verified Xodus repair. It has 65.286B parameters, 8,192-token
context, a standard Llama architecture and approximately 13% explicitly
identified StarCoder-derived code in stage 1 plus 29.6% Python in stage 2.
The original FP16 artifact is 130,580,505,345 bytes. The Mac has 128 GiB unified
memory and 454 GiB free disk at provisioning start; local 8-bit MLX conversion
is planned to preserve more quality than the prior FP16-to-FP16 small-model
path while fitting safely in unified memory.

Granite Code 34B was considered first because of its code-fixing benchmarks,
but its pinned base card includes an IBM-filtered `FLAN_2022` variant and
additional incompletely enumerated phase-2 language sources. Those bytes and
the exact filtering result are not publicly inspectable, so Granite is not
eligible under the user's lineage rule despite Apache-2.0 model weights.

## Artifact identity

- Model repository revision:
  `IFM/K2@400af6cd7de09fc9349cc6b5b24db20f778d5b72`.
- Pinned model card SHA-256:
  `eac829f204f7f1e2f297339dd2f3124bc8e4e4fe89da5cb544f2a8a04d6f58a5`.
- 40 repository files, 29 LFS files, 130,580,505,345 repository bytes,
  including 130,572,453,976 bytes across the 27 weight shards.
- Publisher repository-manifest SHA-256:
  `5566356d8ea8989989ab1258d4324776bf36dde9fac82c66533a5b5a718b5f2d`.
- 27 original FP16 safetensors shards; each publisher LFS SHA-256 is retained
  from the pinned Hugging Face API and must match local bytes before conversion.
- Configuration declares `LlamaForCausalLM`, 80 layers, hidden size 8,192,
  64 attention heads, 8,192 positions and untied embeddings.
- MLX-LM 0.32.0 resolves the pinned configuration directly to
  `mlx_lm.models.llama.Model` / `ModelArgs`; no custom architecture code is
  required.

Original verification completed for all 27 shards and the 723-entry tensor
index. Private verification-record SHA-256:
`3a422e34687df44aeaad75063e50fa552d14e47e755aaaac0c369a99396e12f3`.

The exact publisher FP16 artifact was locally converted to MLX affine 8-bit,
group size 64 (8.5 effective bits per weight reported by MLX-LM). No training
occurred. The converted artifact contains 14 safetensors shards and 20 output
files totaling 69,371,802,420 bytes. Conversion record SHA-256:
`8b157bd5a49e8f0fa129c3e0278e0e823f8a4500eeb70adc4795d38bdb4d6d58`.
Exact EACH artifact identity:
`IFM/K2@400af6cd7de09fc9349cc6b5b24db20f778d5b72#sha256:8266ff62e09c6985`.

## Training lineage

K2 is documented as trained from scratch in two base-pretraining stages. The
complete preprocessed training sequence is published as 380 JSONL chunks:

- Dataset repository:
  `IFM/K2Datasets@17cd6d34bf7d2a5c68df74d3f5fc0b4d19c4bdf4`.
- Pinned dataset card SHA-256:
  `4db91b2b8e4debe6e2c561a0a460976677b816f3e882745a8e304533ffeaccae`.
- 382 repository files, 380 LFS files, 13,235,260,211,210 total bytes.
- Dataset repository-manifest SHA-256:
  `4a731053c01bdcde19a6c97e4341b507c0b698e75f40b5f0f8b2198362dfee84`.
- Dataset packaging license: ODC-By 1.0.
- Data-preparation source:
  `LLM360/k2-data-prep@f69878c898dce6bbb4d84c7982d1005132f8562f`
  (Git tree `1b80ceadde2b9e74c5984bd7091f9bd626e3e71f`;
  Apache-2.0 LICENSE SHA-256
  `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`).
- Training source:
  `LLM360/k2-train@869fbb9710bbe2c361f56c02a6d58ad83adbc755`
  (Git tree `83e848fa26cfcf31b3a3bfb361fab426bb37cb8e`;
  same Apache-2.0 LICENSE SHA-256).

Stage 1 (1.3T tokens) identifies exact source mixtures and multipliers:
DeepMind Mathematics, Pile PubMed abstracts/USPTO/PubMed Central,
SlimPajama ArXiv/StackExchange/books/Wikipedia, three StarCoderData
representations, Pile of Law, S2ORC and Falcon RefinedWeb.

| Stage 1 source | Starting tokens | Multiplier | Effective tokens | Mix |
|---|---:|---:|---:|---:|
| DeepMind Mathematics | 4.33B | 3x | 13.0B | 1.0% |
| Pile PubMed abstracts | 4.77B | 3x | 14.3B | 1.1% |
| Pile USPTO | 4.77B | 3x | 14.3B | 1.1% |
| Pile PubMed Central | 26.0B | 1x | 26.0B | 2.0% |
| SlimPajama ArXiv | 27.3B | 1x | 27.3B | 2.1% |
| StarCoderData SPM | 67.6B | 0.5x | 33.8B | 2.6% |
| StarCoderData deterministic FIM | 67.6B | 0.5x | 33.8B | 2.6% |
| SlimPajama StackExchange | 61.1B | 1x | 61.1B | 4.7% |
| StarCoderData ordinary sequence | 132.6B | 0.5x | 66.3B | 5.1% |
| Pile of Law | 76.7B | 1x | 76.7B | 5.9% |
| SlimPajama books | 80.6B | 1x | 80.6B | 6.2% |
| S2ORC | 107.9B | 1x | 107.9B | 8.3% |
| SlimPajama Wikipedia | 22.1B | 6x | 132.6B | 10.2% |
| Falcon RefinedWeb | 612.3B | 1x | 612.3B | 47.1% |

Stage 2 (69.4B tokens) identifies OpenWebMath, SlimPajama ArXiv/books/Wikipedia,
Dolma Simple Wikipedia, AlgebraicStack, Pile of Law, books, peS2o, Pile
PubMed Central, Python and S2ORC.

| Stage 2 source | Effective tokens | Mix |
|---|---:|---:|
| OpenWebMath | 14.6B | 21.0% |
| SlimPajama ArXiv | 2.0B | 2.9% |
| Dolma Simple Wikipedia | 4.3B | 6.2% |
| SlimPajama books | 2.0B | 2.9% |
| AlgebraicStack | 10.9B | 15.7% |
| Pile of Law | 2.0B | 2.9% |
| Books | 5.8B | 8.3% |
| peS2o | 1.2B | 1.8% |
| Pile PubMed Central | 2.0B | 2.9% |
| SlimPajama Wikipedia | 2.0B | 2.9% |
| Python | 20.5B | 29.6% |
| S2ORC | 2.0B | 2.9% |

The published sequence contains 360 stage-1 chunks of 2,048-token records and
20 stage-2 chunks of 8,192-token records. Bounded HTTP-range inspection of the
first record of all 380 chunks retained only source labels, schema and hashes:
source-map digest
`726bff67a872a87cc6b1e73924e3e3abf196e25b1a348c546f741c2b86af7878`.
Chunk 0 is tagged `pile-of-law`; chunk 360 begins stage 2 and is tagged
`python`; chunk 379 is tagged `pes2o`. Stage-1 records contain source,
subset/file/line provenance, token IDs and target mask; stage-2 records contain
source and token IDs. No corpus text was exported.

## Synthetic-material census

- DeepMind Mathematics is intentionally procedurally generated by a public,
  deterministic program, not authored by an opaque language-model teacher.
- StarCoder FIM is a deterministic transformation of released source records,
  not generated replacement text.
- AlgebraicStack is mathematical source/proof code selected with public,
  hand-crafted language-specific heuristics.
- RefinedWeb, SlimPajama, S2ORC/peS2o, Pile sources, Wikipedia,
  StackExchange, books and public code are collected source material rather
  than a declared LLM-generated training stage.
- No selected K2 base stage declares teacher-generated completions, knowledge
  distillation, inherited weights, SFT, preference optimization or safety
  tuning.
- Individual public web/code records may themselves contain generated content;
  this cannot be exhaustively excluded and remains an explicit record-level
  limitation. No intentionally LLM-generated population or opaque generator
  ancestry was identified in the declared two-stage recipe.

The selected base checkpoint has no SFT, preference optimization or inherited
model-weight stage. K2-Chat and the later safety-tuning material described in
the expanded technical report are separate checkpoints and are excluded.

## License findings

- Model weights/code declaration: Apache-2.0.
- Published K2 preprocessed sequence: ODC-By 1.0.
- Falcon RefinedWeb: ODC-By 1.0 plus Common Crawl terms; underlying web
  copyrights remain heterogeneous.
- peS2o/S2ORC: ODC-By 1.0, derived from open-access scholarly material.
- Pile of Law: CC-BY-NC-SA-4.0 at the pinned public dataset; this is a
  material non-commercial/share-alike source-stage constraint.
- Proof-Pile-2: preserves the licenses of its ArXiv, OpenWebMath and
  AlgebraicStack source records rather than assigning one blanket license.
- StarCoderData and SlimPajama preserve heterogeneous upstream/source rights;
  their dataset/package licenses do not provide blanket legal clearance for
  every record.

The Apache-2.0 model license and ODC-By dataset wrapper are not substitutes for
the source-stage terms above. Qualification, if completed, will be for private
bounded research evidence only and will not assert commercial-use clearance,
lawful training, originality, non-memorization or output licensing.

## Runtime and fixed-task result

MLX-LM 0.32.0 loaded the exact 8-bit artifact through the official
`k2-65b-mlx` catalog path. Ordinary code continuation produced a nonempty
completion; K2 FIM tokens produced whitespace-only output in the bounded smoke,
so the fixed tasks used selected-function code continuation. Official smoke
record SHA-256:
`8241c7af544633e3c4256c3313852e07190f86d6d25f1ec379f6105945d1b284`.

| Task | Build | Behavioral cases | Verified fix |
|---|---|---:|---:|
| Sandbox optional output | PASS | **4/6** | No |
| Console optional output | PASS | **3/6** | No |

Sandbox passed value-and-size, required-buffer NULL and both short-buffer
cases. It failed optional-size-output NULL and both-outputs NULL. Console
passed required-buffer NULL and both short-buffer cases; it failed both
positive-output cases and both-outputs NULL. Both candidates compiled and ran,
so these are logic failures rather than proposal-delivery failures.

Private signed receipt SHA-256 values:

- sandbox:
  `48455a8ac3236aeb4a7852c21294cc2dca25e63cce93b7300d3233cb4fdd8507`;
- console:
  `be6d4f51352b40c8eb5907d54c9b930f55bd10f6df80fd44c80e7266894c0a7a`.

K2 scores **0/2 verified fixes**. The 65B scale increase did not outperform the
15.5B StarCoderBase/OctoCoder body-profile result on this fixed matrix.

Primary sources:

- [Pinned K2 model](https://huggingface.co/IFM/K2/tree/400af6cd7de09fc9349cc6b5b24db20f778d5b72)
- [Pinned K2 dataset sequence](https://huggingface.co/datasets/IFM/K2Datasets/tree/17cd6d34bf7d2a5c68df74d3f5fc0b4d19c4bdf4)
- [K2 technical report](https://arxiv.org/abs/2501.07124)
- [Falcon RefinedWeb](https://huggingface.co/datasets/tiiuae/falcon-refinedweb)
- [Proof-Pile-2](https://huggingface.co/datasets/EleutherAI/proof-pile-2)
- [Pile of Law](https://huggingface.co/datasets/pile-of-law/pile-of-law)
- [peS2o](https://huggingface.co/datasets/allenai/peS2o)
