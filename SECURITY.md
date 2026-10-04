# Security policy

## Supported version

`v0.1.0-alpha.1` is an experimental preview. Security fixes are applied to the
latest code on `main`; no long-term support window is promised.

## Report a vulnerability privately

Use GitHub's **Security → Report a vulnerability** form for
[`dragoshont/EACH`](https://github.com/dragoshont/EACH/security/advisories/new).
Do not open a public issue for a vulnerability that includes credentials,
private target material, exploit details or sensitive receipts.

Include the affected revision, command or component, reproduction conditions,
observed impact and whether any credential or private artifact may have been
exposed. Do not attach model weights, private target patches or live secrets.

## Execution boundary

EACH executes generated candidates only through declared validation surfaces.
The exercised strong profile uses a pinned container image, no network,
read-only root filesystem, scrubbed environment and scoped mounts. Optional
local-model inference may run on the Mac host; that is not the candidate-code
sandbox. See [`docs/threat-model.md`](docs/threat-model.md).

No scanner, sandbox or receipt proves legal clean-room status, originality,
non-infringement or absence of every vulnerability.
