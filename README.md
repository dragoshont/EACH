# EACH

## Start here

**EACH records evidence about code written by a declared local model.** It
captures the exact model and inputs, generated candidate, isolated build/tests,
terminal attribution checks and signed receipt. Use it to answer:

> Which model bytes authored this change, what information did they receive,
> and what independently controlled checks did the result actually pass?

EACH produces **authoring-provenance evidence**, not proof that code is correct,
original, legally clean or suitable for production. Target source, prompts,
responses and candidates stay private by default.

### Quick start on an Apple Silicon Mac

```bash
brew install git uv docker colima jq
git clone https://github.com/dragoshont/EACH.git
cd EACH

uv python install 3.12
uv sync --locked
uv run each doctor

# The deterministic demo uses the pinned no-network container profile.
colima start --profile each --cpu 4 --memory 8 --activate=false
docker --context colima-each pull \
  python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

# Safe harness demonstration: canned FixtureModel, not neural inference.
uv run each demo hello-repair

# Repository verification.
bash gates/checks.sh
```

The demo should reproduce a failing baseline, validate the canned repair in an
isolated container and print private receipt paths. Verify a receipt with:

```bash
uv run each verify /absolute/path/to/receipt.json
uv run each verify /absolute/path/to/receipt.json --full
```

For real local models:

```bash
uv sync --locked --extra models --extra audit
```

This installs runtimes only—it does **not** download weights. EACH intentionally
has no “run any Hugging Face model” fallback. An exact checkpoint enters the
catalog only after its base/post-training lineage, licenses, publisher hashes,
conversion and runtime are reviewed. Model-specific dossiers are under
[`docs/model-qualifications/`](docs/model-qualifications/).

## What it is for

```text
public question / observations -> approved spec -> declared local model
                               -> scoped candidate -> isolated validation
                               -> terminal audit -> signed evidence receipt
```

**EACH** (Evidence-Audited Cleanroom Harness) is a local CLI that records
what a coding model received, what it generated, how the candidate was
validated, and which source-attribution checks actually ran.

## Current reality

EACH now has a practical path to local models with inspectable training
lineage that can generate and compile real code. It does **not yet** have a
reliable Xodus repair model.

The same two public Xodus optional-output bugs were evaluated with a protected
six-case oracle:

| Exact model family | Best sandbox result | Best console result | Verified fixes |
|---|---:|---:|---:|
| Broken pinned baseline | 4/6 | 4/6 | — |
| StarCoderBase 15.5B | 4/6 | 4/6 | **0/2** |
| OctoCoder 15.5B | 4/6 | 4/6 | **0/2** |
| CrystalCoder 7B | No compiling candidate | No compiling candidate | **0/2** |
| K2 65B, local 8-bit | 4/6 | 3/6 | **0/2** |
| CodeGen2.5-7B-multi, local 8-bit | 1/6 | Cases not run | **0/2** |

These are absolute behavioral results, not numbers of newly repaired cases or
comparisons against a preferred patch. The baseline already passes 4/6; some
models merely reproduce that behavior, while others fix one case and regress
another. Only 6/6 after a failing baseline counts as a verified repair.
StarCoderBase, OctoCoder, K2 and CodeGen2.5 all produced at least one compiling
candidate, proving that provenance-qualified models can author executable code;
none completed either fixed repair.

Detailed evidence:

- [Two-model and follow-up evaluation ledger](docs/two-model-evaluation-ledger.md)
- [Finite exact-checkpoint registry](docs/model-qualifications/registry.json)
- [K2-65B dossier](docs/model-qualifications/k2-progress.md)
- [CodeGen2.5-multi dossier](docs/model-qualifications/codegen25-multi.md)
- [CrystalCoder dossier](docs/model-qualifications/crystalcoder.md)

### Provenance and licensing mean different things

EACH can establish that a checkpoint's declared training stages and exact
artifact are inspectable enough for bounded research. It cannot provide blanket
legal clearance:

- CrystalCoder and CodeGen2.5-multi use Apache-2.0 model licenses, while their
  underlying source records retain attribution and heterogeneous-license risks.
- K2 uses an Apache-2.0 model license, but its published mixture includes
  ODC-By sources and a CC-BY-NC-SA-4.0 Pile-of-Law stage. It is authorized here
  only for private bounded research—not commercial-use clearance.
- StarCoder's stronger Python-continuation checkpoint remains gated behind
  BigCode OpenRAIL-M acceptance. EACH will not accept gated terms for a user.
- Granite Code 34B was rejected because its exact base-training lineage includes
  unpublished/incompletely inspectable phase-2 material.
- StarCoder2 remains blocked by unresolved synthetic-teacher ancestry.

Current source-bound gates pass **746 tests with 12 optional skips** and
**760 tests with all extras**, plus Ruff and `each doctor`. Production remains
**not qualified**; see the [production ledger](docs/production-readiness-ledger.md).

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

**Experimental preview—not a production release.** These instructions describe
`v0.1.0-alpha.1` on the public default branch. The prerelease tag identifies the
reviewed source; it does not imply production qualification.

With [Homebrew](https://brew.sh/) already installed:

```bash
brew install git uv docker colima jq
git clone https://github.com/dragoshont/EACH.git
cd EACH
git checkout v0.1.0-alpha.1
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

**Training-data provenance is a prerequisite, not a model preference.**
EACH uses only eligible models with clear base and
post-training dataset lineage. Public weights, exact hashes or a model
license are not sufficient. The current exact reviewed catalog entries are
`starcoderbase-mlx`, `octocoder-mlx`, `crystalcoder-transformers`,
`k2-65b-mlx` and `codegen25-7b-multi-mlx`. Authorization is checkpoint-
specific and does not extend to another size, revision, chat/instruct variant
or family member. K2 is retained as **research-only**, outside the strict
approved-source Builder track. Historical Qwen capability trials do not
qualify this product. See [model eligibility](docs/model-provenance.md) and the
[finite registry](docs/model-qualifications/registry.json).
The [provenance-first evaluation plan](docs/provenance-first-evaluation-plan.md)
puts model/data access and lineage qualification ahead of runtime and repair
tests, and names the candidate models and current blockers.

The model catalog requires exact snapshots already present on disk. Installing
the `models` extra does **not** download model weights.

K2 and CodeGen2.5 provisioning/conversion evidence is intentionally more
specific than a copy-paste download command: original publisher files,
conversion records and local output hashes must all match the catalog pins.
Follow their dossiers rather than substituting a similarly named community
conversion. A successful load is still only runtime evidence; the current
fixed-task ledger records zero verified repairs.

The following is a historical artifact-provisioning reference, **not approval
to generate targets or a recommendation to download weights now**.
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

The following Granite bake-off/benchmark commands are **historical workflow references**.
They return an eligibility error (exit 2) before model loading or inference.
After a model is genuinely qualified, these workflows also require provisioned
runtime images; see the setup limitations below.

```bash
uv run --extra audit --extra models each model bakeoff \
  granite-8b-code-instruct-128k-mlx --max-attempts 3
uv run --extra audit --extra models each benchmark run \
  granite-8b-code-instruct-128k-mlx --smoke --max-attempts 3
```

When eligibility is enabled for a reviewed model, these are real
inference/validation operations, not health checks. Historical unsuccessful
repairs remain nonzero outcomes with evidence.

For the qualified original StarCoderBase checkpoint, authenticated model access
must already be granted. Provisioning retains approximately 63 GB of original
publisher FP32 shards and converts to approximately 31 GB of local FP16
safetensors. It requires 120 GiB free disk, verifies the original publisher
hashes and every saved tensor, and records the precision conversion:

```bash
uv run --extra models python -m each.models.provision_starcoderbase
```

Provisioning does not run inference. Do not repeat it over an existing or
partial conversion; preserve and inspect existing artifacts first. The
`starcoderbase-mlx` loader verifies the conversion/output identities and binds
the training-lineage dossier into its model manifest.

For a bounded **fixture wiring check** with this base completion model:

```bash
uv run --extra audit --extra models each model bakeoff \
  starcoderbase-mlx --proposal-format fim --max-attempts 1
```

This does not run the private Xodus task. FIM reconstructs the fixture body
from the model's response, then uses the existing scoped patch and isolated
test pipeline. All failed attempts and original inputs remain private.

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
