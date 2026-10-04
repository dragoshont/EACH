# CrystalCoder qualification and Xodus evaluation

Status on 2026-10-04: **AUTHORIZED for bounded local research under EACH's
documented, inspectable dataset-stage lineage standard; evaluated with zero
verified Xodus fixes**. This is authoring-provenance evidence, not legal
certification, exact training-sample reconstruction, or production approval.
This follow-up used the user's later explicit direction to evaluate additional
clean models after the original two-model cycle produced no useful fix; it does
not retroactively change the older launch evidence.

Exact checkpoint:
`LLM360/Crystal@34fc9cd58acd87002560379a95b432147cc9135a`.
EACH artifact identity:
`LLM360/Crystal@34fc9cd58acd87002560379a95b432147cc9135a#sha256:af277cbad887d6d0`.

## Lineage decision

CrystalCoder is a 7B base model trained from scratch. The publisher describes
three stages:

1. the first half of SlimPajama;
2. the second half of SlimPajama plus two epochs of StarCoderData, with
   deterministic fill-in-the-middle transformation;
3. selected Python and web-related StarCoderData plus SlimPajama.

The released training-data repository is pinned at
`LLM360/CrystalCoderDatasets@e42bace8739ade3b2d73025746bdac8a38345427`;
the data-preparation source is public in `LLM360/crystalcoder-data-prep`.
No inherited model checkpoint or separate post-training stage is identified
for this base release. The decision is limited to identifiable, inspectable
dataset stages. It does not prove exact row membership, historical job
reconstruction, exhaustive source licensing, all-human authorship,
non-memorization, originality, or lawful use.

Primary sources:

- [Pinned model card](https://huggingface.co/LLM360/Crystal/blob/34fc9cd58acd87002560379a95b432147cc9135a/README.md)
- [CrystalCoder paper](https://arxiv.org/abs/2312.14847)
- [Pinned training-data release](https://huggingface.co/datasets/LLM360/CrystalCoderDatasets/tree/e42bace8739ade3b2d73025746bdac8a38345427)
- [Data-preparation repository](https://github.com/LLM360/crystalcoder-data-prep)

## Exact retained artifact

The original publisher BF16 PyTorch shards were downloaded without weight
conversion. All three bytes-on-disk hashes matched the pinned publisher
metadata:

| File | Bytes | SHA-256 |
|---|---:|---|
| `pytorch_model-00001-of-00003.bin` | 4,916,534,793 | `45d3ddd1d30058d55c8ccc250139aeeef318f14c39c53bbfa830fb669ac79ebe` |
| `pytorch_model-00002-of-00003.bin` | 4,922,601,368 | `c1c03da74d41317a7e2c5a799e09a8ee5ce4a94ba19976befa9f1135c48cf93a` |
| `pytorch_model-00003-of-00003.bin` | 3,311,569,314 | `c33c1d1ace28b1ac3a7afa7e82b18322446bacf76f12fd07401879dafd4d6cfe` |

The catalog also pins the index, configuration, tokenizer and publisher custom
Python files. Its pinned custom architecture is incompatible with Transformers
5.18 because an imported 4.x API was removed. EACH therefore imports those
exact publisher modules directly in a separate locked local runtime:
Transformers 4.44.2 and Torch 2.14.1. The main MLX environment remains
unchanged.

The runtime project, lock and helper hashes are authorization pins, not merely
receipt metadata. Execution uses a scrubbed environment, private temporary
working directory, no dependency resolution, isolated Python startup, process
timeout, bounded output, macOS sandbox network denial, global write denial
outside the private work directory, and read denial for EACH
run/shadow/oracle evidence, repository evidence/docs/tests, common credential
locations and private probe files. The helper verifies network, multiple
private-file and outside-work write denial before importing publisher code,
then reports the actual Python, Torch and Transformers versions for exact
comparison with the catalog pins. A real MPS load and nonempty completion
succeeded with all probes true through the official catalog entry.

## Xodus results

The same approved public sandbox-ID and console-ID tasks, protected six-case
oracle, pinned source and no-network container were used. No candidate text is
published.

The inherited whole-file FIM packet exceeded the declared 2,048-token context
window (2,349 and 2,314 input tokens) and failed before generation. EACH then
reduced the packet to the selected function. Both 512-token and 1,024-token FIM
outputs saturated their exact output budgets; sandbox remained structurally
incomplete and console failed compilation. A final selected-function
code-continuation profile also saturated 512 output tokens; sandbox failed
compilation and console repeated the function signature five times and was
rejected.

| Task | Best reached stage | Behavioral cases | Verified fix |
|---|---|---:|---:|
| Sandbox optional output | Build attempted and failed | NOT RUN | No |
| Console optional output | Structural rejection | NOT RUN | No |

CrystalCoder therefore scores **0/2 verified fixes**. Task shaping improved the
failure from pre-generation context rejection to real candidate delivery, but
did not produce compilable, behaviorally testable repairs. More output budget
is not justified by the observed repetitive saturation. This capability result
does not revoke the checkpoint's bounded lineage authorization.

Final secured continuation receipts:

- sandbox `crystalcoder-sandbox-secured-v2-20261004`,
  SHA-256 `6e03d88280a48644d683a0c367ec11bda3f9b7098ff572942d9500b1a950e141`;
- console `crystalcoder-console-secured-v2-20261004`,
  SHA-256 `d635c463030f99fb26e8a5a51809932ef5aca94c14ed66a1c150a58fdb0f3da6`.

Both record `networkDenied=true`, both private-file probes denied, outside-work writes
denied, and the exact pinned
runtime project, lock and helper hashes. Raw prompts, completions, candidates
and compiler diagnostics remain private.
