# Contributing to EACH

EACH is an experimental authoring-provenance harness. Contributions must
preserve evidence truth, private-by-default artifacts and fail-closed behavior.

## Set up

```bash
git clone https://github.com/dragoshont/EACH.git
cd EACH
uv python install 3.12
uv sync --locked
uv run each doctor
```

Apple Silicon macOS is the exercised platform for local-model and Colima
integration. Ordinary unit tests may run elsewhere, but that does not qualify
another platform for the strong execution profile.

## Meaningful checks

```bash
uv run ruff check each tests
uv run pytest -q
uv run each doctor
uv build
```

On a Mac with the dedicated `colima-each` context and pinned fixture image:

```bash
bash gates/checks.sh
uv run each demo hello-repair
```

Model weights and expensive model evaluations are never required for an
ordinary contribution or pull request.

## Fixtures and sources

- New fixtures must be original EACH material or identify their exact source,
  revision and redistribution license.
- Preserve third-party copyright and license notices.
- Never commit model weights, caches, private target patches, proprietary
  material, credentials, signing keys, raw model responses or private receipts.
- Tests that use a public upstream source must pin its revision and distinguish
  copied source from independently written scaffolding.
- A successful compile is not a successful repair. Tests and documentation must
  report complete behavioral outcomes and preserve failures.

## Pull requests

Describe the behavior changed, the smallest relevant checks run, optional skips
and any evidence/assurance claim affected. Do not broaden model eligibility,
execution permissions, allowed paths or publication scope without explicit
evidence and review.

By contributing, you agree that your contribution is licensed under the
repository's Apache-2.0 license unless a file clearly retains a compatible
third-party license and notice.
