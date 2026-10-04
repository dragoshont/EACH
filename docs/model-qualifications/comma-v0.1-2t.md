# Comma v0.1-2T: finite document assessment

**Decision: DEFERRED -- insufficient reviewed synthetic-ancestry evidence.**
This one-pass assessment is complete for the launch cycle. No weights were
downloaded, no local runtime was evaluated, and no additional research is a
StarCoderBase launch dependency.

Exact candidate: `common-pile/comma-v0.1-2t` at
`3fba8938462ae9303c6e88770fc2d098370f0eaa`.

| Gate | Evidence and remaining limit |
|---|---|
| Artifact identity | Publisher API identifies the revision and 7,002,656,768 BF16 parameters. Apache-2.0 model distribution. Local weight/tokenizer/config hashes remain UNKNOWN: no download. |
| Pretraining | Published `common-pile/comma_v0.1_training_dataset`, derived from the Common Pile v0.1 filtered collection; source mixture/effective token accounting is published. |
| Starting point | Publisher training configuration has `checkpoint.init_ckpt_path: null` and `continue_training_from_init: false`, with top-level seed 777 and data/model seeds 42. This supports the documented from-scratch recipe. `LlamaForCausalLM` is architecture metadata, not inherited Llama weights. |
| Training stages | Reported 1.93T-token main stage and 75.5B-token cooldown; final artifact averages ten cooldown checkpoints. These are pretraining/weight-processing stages, not instruction tuning. The base model card states no alignment stage. |
| Synthetic ancestry | Stack-v2 educational code uses classifiers to select existing code; that is not evidence that a teacher generated the code. The one-pass review did not establish full 30-source synthetic ancestry or classifier training-label ancestry. Required uncertainty remains UNKNOWN, not PASS. |
| Rights/source evidence | Source mixture and license accounting are published. The publisher explicitly warns that license laundering and inaccurate metadata prevent a guarantee that all training text was openly licensed. Retain this as residual risk, not automatic failure or legal clearance. |
| EACH suitability | Runtime, trajectory capture and repair capability UNEVALUATED. No authorization to load follows from this desk assessment. |

The reported training table distinguishes approximately 463.6B raw source
tokens from 1,034.4B effective main-stage tokens for the 1T recipe, with the 2T
recipe repeating sources. These are publisher training-mixture quantities, not
EACH performance measurements.

No opaque weight ancestor was identified in the inspected recipe. That is not
proof that all synthetic ancestry is absent. The unresolved full-corpus G4
assessment makes the terminal launch-cycle decision **DEFERRED**, rather than
silently treating the only remaining prerequisite as local inference.

The user's assertion that Comma was raised in a 2026 Wine discussion remains
`USER_ASSERTION / UNVERIFIED`: the bounded search did not locate that specific
primary posting. Absence from the search does not prove no discussion occurred.
Neither a proposal nor this assessment establishes Wine or Xodus acceptance.

Primary sources inspected by the bounded research worker:
- [Publisher model API](https://huggingface.co/api/models/common-pile/comma-v0.1-2t)
- [Pinned model card](https://huggingface.co/common-pile/comma-v0.1-2t/blob/3fba8938462ae9303c6e88770fc2d098370f0eaa/README.md)
- [Pinned model configuration](https://huggingface.co/common-pile/comma-v0.1-2t/blob/3fba8938462ae9303c6e88770fc2d098370f0eaa/config.json)
- [Published training dataset](https://huggingface.co/datasets/common-pile/comma_v0.1_training_dataset)
- [Publisher training configuration](https://huggingface.co/common-pile/comma-v0.1-2t-checkpoints/blob/main/config.yaml)
- [Common Pile paper](https://arxiv.org/abs/2506.05209)

The training-configuration/dataset revisions were not frozen by this bounded
pass. A later separately authorized assessment would need that binding;
do not represent these moving references as a completed artifact lineage proof.
