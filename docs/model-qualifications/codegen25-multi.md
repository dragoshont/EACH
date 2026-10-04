# CodeGen2.5-7B-multi qualification progress

Status on 2026-10-04: **AUTHORIZED for bounded private research; evaluated
with zero verified Xodus fixes**. Exact publisher weights, both conversion
stages, custom-tokenizer compatibility bytes and official loader verified.

Exact checkpoint:
`Salesforce/codegen25-7b-multi_P@3cfb2194ec55e4a229f2d2184623b747fa24ab94`.
This is the multilingual base checkpoint, not `mono` and not `instruct`.

The `mono` checkpoint is excluded because its model card declares a further
stage on “additional Python tokens” without identifying or releasing those
bytes. The `instruct` checkpoint adds separate instruction data and carries a
research-only license. Neither may inherit this decision.

## Training lineage

Publisher model card, repository documentation and release blog agree:

- the model is trained from scratch on public `bigcode/starcoderdata`;
- approximately 300B tokens form one epoch;
- training continues for 1.4T tokens, more than four epochs;
- repeated observations are transformed with the public CodeGen2 span-
  corruption/infill objective rather than replaced by opaque teacher
  completions;
- no inherited model weights, SFT, preference optimization or declared
  LLM-generated stage applies to the selected `multi` checkpoint.

This reuses EACH's existing StarCoderData stage assessment at
`bigcode/starcoderdata@9fc30b578cedaec69e47302df72cf00feed7c8c4`.
The release-day file-identity comparison and its source-rights limitations
remain unchanged. Public code may contain generated records at individual
record level; no intentional teacher-generated population was identified.

## Artifact and license

- Model revision:
  `3cfb2194ec55e4a229f2d2184623b747fa24ab94`.
- Publisher weights: three PyTorch shards, 27,582,926,880 bytes.
- Source tensor index: 323 entries.
- Publisher repository-manifest SHA-256:
  `09818758c2f96946748d0036cdc29bba299593ac81637333d36fad8dc546ef35`.
- Pinned model card SHA-256:
  `7b92fd553d709a37714f2b384dca19795a4957c9dc315a5c74b44639df35e787`.
- Config SHA-256:
  `60c43b45c09fe101bd3b412c7b00b0fd899d2d32455aebf08bdf3925b4bfb9df`.
- Private original-verification-record SHA-256:
  `f93fb3edfc99dd76f4e0c95372c0f849dfe8b327e99e5f68deb0840098cf954d`.
- Model license: Apache-2.0.
- Custom tokenizer file is pinned with the model revision and requires
  `tiktoken==0.4.0`; SHA-256
  `965c68328a5d2d810f585f0528ea80da2dc48fabc37bea9186168f072794b6cf`.
  It does not change the training corpus.
- StarCoderData package/source rights are heterogeneous and may require
  attribution. Apache-2.0 model distribution is not blanket source-code or
  output-license clearance.

The original FP32 PyTorch shards were converted tensor-by-tensor to FP16
safetensors and reopened for exact rounded-tensor equality. FP16 conversion
record SHA-256:
`371d9a9ce1089a16d6bdddfa94b194757001cc10e2e1b23b0b947b94588beec3`.
The FP16 artifact was then converted to MLX affine 8-bit, group size 64
(8.5 effective bits per weight reported). The final artifact contains two
weight shards and eight output files totaling 7,327,091,357 bytes.
Final conversion-record SHA-256:
`11ad1401525a01985c99746ce7fe56f758f9bb19bc98a21fc5c79b4a514eafe2`.

Transformers 5 required a deterministic compatibility patch to the exact
publisher tokenizer copy: stop forwarding the constructor's
`add_special_tokens` flag into a newly reserved base-class method name,
initialize the unchanged tiktoken encoder before the base constructor's new
`get_vocab` call, and use replacement decoding only for byte-token vocabulary
inspection. Encoding/decoding and the flag's control of the tiktoken special
tokens remain unchanged. Patched tokenizer SHA-256:
`8a6718384a609bcdda49504fb1fa38568940f27a2f96ac99badb945234f2171f`.
That exact Apache-2.0 implementation is vendored as reviewed EACH source and
loaded directly; the official Builder does **not** enable Hugging Face
`trust_remote_code`. Differential tests cover ordinary Unicode/byte-token
round trips, infill special tokens and both values of the special-token flag.
The expected token IDs and decodes were captured from the exact unmodified
publisher source (SHA-256
`965c68328a5d2d810f585f0528ea80da2dc48fabc37bea9186168f072794b6cf`)
under its declared Transformers 4.29.2 / tiktoken 0.4.0 runtime, not generated
from the patched implementation.
The loader also requires the exact qualified MLX, Transformers, tiktoken,
Torch and safetensors versions before opening the artifact.

Exact EACH artifact identity:
`Salesforce/codegen25-7b-multi_P@3cfb2194ec55e4a229f2d2184623b747fa24ab94#sha256:e164c1a2b77be037`.

## Runtime and fixed-task result

MLX-LM 0.32.0 loaded the exact artifact through the official
`codegen25-7b-multi-mlx` catalog path with the pinned custom tokenizer.
Official smoke record SHA-256:
`222726771b631d215aabbb0452cafcbe502d1d9deb070bfd157f2f0c666eb0d9`.

| Task | Best reached stage | Behavioral cases | Verified fix |
|---|---|---:|---:|
| Sandbox optional output | Candidate compiled | **1/6** | No |
| Console optional output | Structural rejection: signature repeated three times | NOT RUN | No |

The sandbox candidate passed only the valid-buffer/optional-size-NULL case and
failed the other five cases. Console never reached compilation. Both outputs
hit the 512-token limit. Signed private receipt SHA-256 values:

- sandbox:
  `4d693cfa2fb7392545ae549a148d462d17435a22258152342f981e4ac47524d2`;
- console:
  `f4c8ebed0f22d113ec5f3b378b27d83fed99cea4c7902c7cc7fc144dc24db485`.

CodeGen2.5-multi scores **0/2 verified fixes** and is weaker on this fixed
matrix than StarCoderBase, OctoCoder and K2 despite its competitive HumanEval
publisher result.

Primary sources:

- [Pinned model](https://huggingface.co/Salesforce/codegen25-7b-multi_P/tree/3cfb2194ec55e4a229f2d2184623b747fa24ab94)
- [Publisher CodeGen2.5 documentation](https://github.com/salesforce/CodeGen/tree/main/codegen25)
- [Publisher release analysis](https://www.salesforce.com/blog/codegen25/)
- [StarCoderData](https://huggingface.co/datasets/bigcode/starcoderdata)
