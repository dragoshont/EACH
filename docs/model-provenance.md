# Model evidence, not licensing conclusions

M2's initial supported Builder is Granite Code 3B Instruct through local MLX-LM.
Granite Base was also evaluated and did not produce a verified fixture repair.
This small comparison is not a broad leaderboard or evidence of originality.

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
