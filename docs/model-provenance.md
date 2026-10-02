# Model evidence, not licensing conclusions

M2's initial supported Builder is Granite Code 3B Instruct through local MLX-LM.
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
Its current catalog unavailability separately reports incomplete downloads
or an unimplemented adapter; it is not a claim that MPS cannot support it.

Model licenses do not automatically license generated target patches.
EACH records technical evidence and published claims, not legal conclusions.

