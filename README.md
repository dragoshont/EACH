# EACH

### Evidence for AI-authored repairs. Not a certificate.

**EACH** (Evidence-Audited Cleanroom Harness) is a local CLI that records
what a coding model received, what it generated, how the candidate was
validated, and which source-attribution checks actually ran.

```text
Issue / observations -> approved spec -> declared local model
                     -> scoped candidate -> isolated validation
                     -> terminal audit -> signed evidence receipt
```

Target artifacts stay private by default. A passing signature proves integrity,
not correctness, originality or legal clean-room status.

## Where the project stands

| Area | Current position |
|---|---|
| Research program | M0-M8 complete; full research release gate verified. |
| Production | **Not qualified yet.** Autonomous qualification is underway under the [production ledger](docs/production-readiness-ledger.md). |
| First production-development exploration | Three new Python development tasks, nine local-model calls, **zero verified repairs**; this utility lane is stopped at its authorized cap. |
| Historical benchmark | 25 Python/C/C++/Rust tasks, 75 selected recorded calls, **0 verified repairs**. |
| Controlled compatibility experiment | M7: **8 passing tests, 1 failure**; complete negative evidence, not a working cache. |
| Private real-world demonstration | M8: one bounded C repair with verified baseline failure and repaired success. Not full Xodus/Wine/game compatibility. |
| Audit coverage | Synthetic calibration/holdout detect seeded copies, but false flags exceed the frozen target; external membership/scanning remain unavailable. No originality, EACH-P3 or legal-certification claim. |
| Operations | Isolated interruption, timeout, quota, corruption, concurrency and temporary-key recovery drills implemented; independent production acceptance pending. |
| API validation boundary | **P1 BLOCKED after actual independent REVISE.** Matching sandboxed process JSON does not authenticate Python API return and cannot verify a repair. |

See [development evidence](docs/development-status.md) for exact source
revisions, gate results and limitations. Independent AI review supports
engineering qualification; it does not confer production readiness.

## What you get

- Hash-bound specifications and declared input provenance.
- Deterministic `FixtureModel` demonstrations and explicit local-model adapters.
- Scoped textual patches and no-network container execution.
- Terminal audit: discovered reference material never goes back to Builder.
- Private JSON/Markdown receipts, Ed25519 signatures and retained-file checks.
- A rerunnable historical benchmark with honest failure reporting.

EACH is not a hosted service, autonomous upstream contributor, legal
certifier or correctness oracle. Human review is required before adopting a
candidate. [Claims and non-claims](docs/claims-and-nonclaims.md) are authoritative.

## Set up on an Apple Silicon Mac

The exercised local-model backend is MLX on Apple Silicon. Python-only
harness checks can run elsewhere, but that does not qualify another host for
strong execution or local-model inference. Windows is not the production
execution platform described here.

### 1. Install prerequisites and clone

With [Homebrew](https://brew.sh/) already installed:

```bash
brew install git uv docker colima jq
git clone https://github.com/dragoshont/EACH.git
cd EACH
uv python install 3.12
uv sync --locked
uv run each --help
uv run each doctor
```

`doctor` must pass required checks. A missing Docker daemon may be an optional
warning for basic CLI inspection, but it blocks the strong isolated demo.

### 2. Start a dedicated container profile

Keep EACH separate from your other Docker workloads:

```bash
colima start --profile each --cpu 4 --memory 8 --activate=false
docker --context colima-each info
docker --context colima-each pull \
  python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
uv run each doctor
```

Dependency/image preparation needs network access; sealed candidate execution
does not. Never run imported target code on the host as an isolation substitute.
The executor uses the explicit `colima-each` context, not your default context.

### 3. Run the no-model demonstration

```bash
uv run each demo hello-repair
```

This uses a **canned FixtureModel repair**, not AI inference. It should show a
failing baseline, passing repaired validation and private receipt locations.
It does not measure local-model usefulness.

### 4. Run checks

```bash
uv run pytest -q
uv run each doctor
bash gates/checks.sh
```

For the optional audit/model integrations on the Mac:

```bash
uv sync --locked --extra audit --extra models
uv run --extra audit --extra models pytest -q
```

Pass the extras explicitly when needed: a later plain `uv sync` may remove
optional packages. Container-dependent tests skip when the dedicated daemon is
unavailable; a skip is not a successful isolation test.

## Using real local models

The model catalog requires exact snapshots already present on disk. Installing
the `models` extra does **not** download model weights.

For the exercised original Granite 8B Code Instruct 128K snapshot, after
reviewing its license, storage and memory requirements, explicitly opt in:

```bash
uv run --extra models python - <<'PY'
from pathlib import Path
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="ibm-granite/granite-8b-code-instruct-128k",
    revision="bed93d8de15bb9bb55cb1da10ae860e2883f4254",
    cache_dir=str(Path.home() / ".each/models/.hf_cache"),
)
PY
```

This downloads large original publisher weights. Do not accept gated terms
automatically or treat model licensing as licensing of generated patches.
See [model provenance](docs/model-provenance.md) for identities, conversion
limitations and actual evaluation results.

The model bake-off and historical benchmarks additionally need provisioned
runtime images. See the setup limitations below before invoking:

```bash
uv run --extra audit --extra models each model bakeoff \
  granite-8b-code-instruct-128k-mlx --max-attempts 3
uv run --extra audit --extra models each benchmark run \
  granite-8b-code-instruct-128k-mlx --smoke --max-attempts 3
```

These are real inference/validation operations, not quick health checks.
An unsuccessful repair returns nonzero and still needs honest evidence.

### Benchmark image setup limitation

Dockerfiles live under `docker/benchmark-runtime`,
`docker/benchmark-native-runtime` and `docker/m8-native-runtime`.
The current harness references exact locally provisioned image digests.
Rebuilding a Dockerfile does not guarantee the same digest, and those local
images are not promised to be available from a public registry.

Consequently a fresh clone can run the pinned base-image fixture, but full
historical/native workflows may require image provisioning and explicit
digest reconciliation. Production qualification tracks reproducible
installation of these workflows; **do not bypass digest enforcement with a
mutable tag** or assume a successful `doctor` validates every model/image.

## Verify a receipt

```bash
uv run each verify /absolute/path/to/receipt.json
uv run each verify /absolute/path/to/receipt.json --full
```

The first command checks the signed receipt's declarations. `--full` also
requires actual retained input files and verifies their hashes. If they live
in a separate recovery root:

```bash
uv run each verify /absolute/path/to/receipt.json \
  --full --artifact-root /absolute/path/to/retained-inputs
```

Use `--public-key /absolute/path/to/public.pem` to verify against an explicitly
trusted public key. Declaration-only historical/demo receipts can return
UNAVAILABLE for full-file verification; do not relabel that PASS.

Private data defaults to `~/.each/`:

| Directory | Purpose |
|---|---|
| `runs/` | Run receipts, trajectories and retained evidence. |
| `specs/` | Draft and approved immutable specifications. |
| `models/` | Local model snapshots and hashes. |
| `keys/` | Local signing keys; never commit or publish private keys. |

`EACH_HOME` can select another private store. Use a real, permission-restricted
path, not a symlinked location. Back up keys and evidence together according
to the documented trust/retention policy; never publish the whole directory.
The [operator runbook](docs/operator-runbook.md) explains actual supported
verification, partial receipts, exact-owned-resource reconciliation and private
backup/restore boundaries.

## Command reference

| Command | Purpose |
|---|---|
| `each doctor` | Required and optional environment health. |
| `each demo hello-repair` | Deterministic isolated fixture demonstration. |
| `each model bakeoff MODEL` | Real local-model fixture evaluation. |
| `each issue import URL` / `show TASK` | Cached, hashed, explicitly untrusted GitHub issue intake. |
| `each spec build TASK` / `approve TASK --human ID` | Separate spec drafting and actual human approval. An identity string is not proof of consent. |
| `each benchmark run MODEL` | Historical tasks; `--smoke` selects five Python tasks and `--python-only` excludes native tasks. |
| `each benchmark retain-materials TASK --out PATH` | Material recovery; verify recovered hashes against the original receipt. |
| `each verify RECEIPT --full` | Signature plus retained-input verification. |

Run `uv run each COMMAND --help` for exact arguments. There is no advertised
general `each run`, hosted API or daemon.

## Troubleshooting

| Symptom | Action |
|---|---|
| Docker warning or failed isolation | Check `docker --context colima-each info`; start the dedicated profile. Do not fall back to host execution. |
| Image digest unavailable | Provision the exact permitted image; a rebuilt image needs deliberate identity reconciliation. Do not substitute a tag silently. |
| Model unavailable | Check optional dependencies, exact snapshot revision and catalog cache layout. Never silently substitute another model. |
| Context budget exceeded | Reduce the approved task envelope or evaluate a supportable model under recorded policy. Do not hide truncation or discard the failure. |
| Full verification unavailable/failed | Restore genuine matching retained files and use the correct public key. Never edit a signed receipt to match new bytes. |
| Audit UNAVAILABLE | Report the missing tool/corpus and reduced coverage. It is not a clean audit or originality proof. |

## Roadmap, contribution and license

Start with the [production-readiness ledger](docs/production-readiness-ledger.md)
for the backward plan, actionable work packets and proposed qualification
targets. [The mandate](docs/EACH_BOOTSTRAP_MANDATE.md) and
[milestone prompts](docs/EACH_MILESTONE_PROMPTS.md) preserve the research scope.
The [threat model](docs/threat-model.md) and
[attestation documentation](docs/attestation.md) explain the trust boundaries.

The [measured production-development contract](docs/production-development-contract.md)
records the exact observed Mac/model row, budgets, sandboxed Python
process-response boundary and blocked development commands. It does not qualify a
production release or authorize additional sampling after the bounded cap.
Its [mandatory review correction](docs/observer-review-corrections.md) narrows
the evidence claim to process responses, **not the production goal**. The
original API-repair goal remains unmet; the exhausted development entry point
now exits BLOCKED before model loading.

The independent P3/P4 continuation adds [measured audit fixtures and ceilings](docs/audit-qualification.md)
and [operational fault/recovery controls](docs/operator-runbook.md), not a new
repair experiment. The audit holdout failed its benign false-flag target.
Passing operational regressions do not replace independent R4 review.
See [the frozen P3/P4 evidence](docs/production-p3p4-evidence.md) for actual
source identities, test counts and the failed/pending acceptance disposition.

Contribute harness code, reproducible tests and sanitized evidence. Do not
include private target patches, prompts, credentials, model weights or signing
keys in an issue, commit or pull request. The Xodus demonstration stays private
and shadow-only; no upstream AI implementation submission is authorized.

**Apache-2.0.** See [LICENSE](LICENSE) and [NOTICE](NOTICE).
