# EACH — Evidence-Audited Cleanroom Harness
## Comprehensive Zero-Context Bootstrap Handoff for Architrave

**Project:** EACH — Evidence-Audited Cleanroom Harness  
**Repository:** expected public repository `dragoshont/EACH` — verify before first push  
**Primary development machine:** Apple Silicon MacBook Pro M5 Max, 128 GB unified memory  
**Primary agent/orchestrator:** Architrave, used through GitHub Copilot  
**Date of handoff:** 2026-10-01  
**Revision:** v2 — authoritative M0–M8 milestone protocol corrected and expanded  
**Status:** greenfield public OSS project; architecture and implementation mandate  
**Primary language:** Python unless a component has a compelling reason otherwise  
**Initial license recommendation:** Apache-2.0  
**Initial demonstration domain:** ordinary permissively licensed historical software-repair tasks  
**Hard demonstration domain after v0.1:** Xodus/xgameruntime *shadow* compatibility experiments on macOS, with no implication that AI-generated runtime code is upstream-acceptable

---

# 0. Read this first

You are receiving this document with **no prior conversational context**.

The user has already created a GitHub repository named **EACH**. Treat the repository as the public home of a new open-source project called:

> **EACH — Evidence-Audited Cleanroom Harness**

The project is intended to answer a narrow but increasingly important engineering question:

> Can an autonomous or semi-autonomous coding system produce a software patch while preserving a detailed, reproducible, independently inspectable record of **what the model was allowed to know, what exact model produced the patch, what tools it used, what tests it ran, and what evidence exists about the provenance of the generated source?**

EACH is **not** a system for declaring code legally clean-room, copyright-safe, or upstream-acceptable.

EACH is a system for generating and preserving **authoring-provenance evidence**.

That distinction is fundamental. Never weaken it for marketing.

The user’s motivating case is Xodus, an open-source project implementing compatibility for Xbox PC / GDK software outside Windows. Xodus and Wine have strict clean-room and LLM contribution policies. The user would like to experimentally explore AI-assisted compatibility work without pretending that an AI provenance process overrides upstream project policy.

The first release of EACH must therefore be useful **even if Xodus never accepts a line produced by it**.

The project succeeds if it becomes a generally useful, open, local, reproducible harness for provenance-sensitive autonomous software repair.

---

# 1. Prime directive

Build **the smallest serious end-to-end system** that can:

1. ingest a bounded software-repair task, initially from a GitHub issue or local fixture;
2. classify its provenance sensitivity;
3. construct or accept a sanitized, immutable specification packet;
4. create a sanitized source worktree at an exact revision;
5. invoke a fixed local coding model;
6. constrain the model’s information and tool access;
7. let the model produce candidate patches;
8. compile and execute deterministic validation;
9. record the full model/tool/test trajectory;
10. perform independent post-generation attribution/similarity/license checks;
11. create cryptographically bound provenance/attestation artifacts;
12. label the result honestly;
13. keep generated implementation private by default where publication could contaminate future clean-room efforts;
14. optionally publish the harness, specs, receipts, benchmarks, or explicitly AI-lineage code when the user chooses.

Do **not** build another general-purpose coding agent.

Reuse or wrap existing agent machinery where appropriate.

EACH’s value is the **firewall, evidence model, policy engine, reproducibility, and attestation chain**.

---

# 2. The claim EACH is allowed to make

Good claim:

> EACH is an open-source, reproducible, provenance-first software-repair harness that records the coding model, permitted input diet, execution environment, full trajectory, validation results, and post-generation attribution evidence.

Also acceptable:

> EACH treats source authorship as a software-supply-chain event and makes the inputs to AI-assisted source generation attestable.

Do **not** claim:

- “AI clean-room certified”
- “copyright safe”
- “legally clean”
- “guaranteed non-infringing”
- “proves a model never saw copyrighted code”
- “proves original authorship”
- “makes LLM code acceptable to Wine”
- “solves DCO”
- “solves code provenance”
- “first coding agent with provenance”

Those statements are unsupported or false.

The project should explicitly say:

> EACH produces **provenance evidence, not legal conclusions**.

---

# 3. Why this project exists

Several relevant systems already solve parts of the problem.

## 3.1 Autonomous issue-to-patch systems already exist

Examples include:

- SWE-agent
- mini-SWE-agent
- OpenHands
- AutoCodeRover
- Agentless
- commercial coding agents
- GitHub Copilot coding agent

Therefore GitHub issue → source edit → tests → patch is not the novelty.

## 3.2 Local and offline coding agents already exist

Local model servers, llama.cpp, MLX, Ollama, LM Studio, local OpenAI-compatible endpoints, mini-SWE-agent local-model support, and many agent harnesses already exist.

Therefore “runs locally” is not the novelty.

## 3.3 Generated-code attribution already exists commercially

Commercial systems such as Tabnine, GitHub Copilot code referencing, and Amazon Q can identify some generated text that resembles public code and surface source/license information.

Therefore post-generation public-code matching is not the novelty.

## 3.4 Open training-corpus membership tools exist

BigCode / Data Portraits and related research provide mechanisms for querying or estimating membership/overlap with documented model training corpora.

Therefore training-corpus checking itself is not the novelty.

## 3.5 Software-supply-chain attestations already exist

in-toto and SLSA provide mature concepts and formats for proving how artifacts were built.

Therefore signed supply-chain metadata itself is not the novelty.

## 3.6 The interesting intersection

The working thesis is:

> What is still uncommon is an **open and independently reproducible composition** that treats the *authoring act itself* as an attestable supply-chain step and combines:
>
> - issue intake;
> - information-diet control;
> - immutable behavioral/spec packets;
> - fixed model identity/weights;
> - constrained execution;
> - full trajectory capture;
> - real compilation/testing;
> - corpus/source/license audit;
> - signed provenance receipts;
> - explicit assurance levels.

Do not assert uniqueness until a literature/product review in EACH itself supports it.

The README should phrase this as a project hypothesis, not a fact.

---

# 4. Important prior art to ground in

Before architecture changes, inspect current versions of these projects and papers.

## Agent execution

### mini-SWE-agent
https://github.com/SWE-agent/mini-swe-agent

Relevant because:
- small implementation;
- linear message history;
- Bash-oriented execution;
- local models via LiteLLM/OpenAI-compatible endpoints;
- designed to remain understandable.

Local model docs:
https://github.com/SWE-agent/mini-swe-agent/blob/main/docs/models/local_models.md

Do not blindly fork it. First determine whether:
- importing/wrapping it as a dependency,
- vendoring a minimal adapter,
- or reusing its process model

gives the best auditability.

### SWE-agent
https://github.com/SWE-agent/SWE-agent

Useful for:
- issue-driven workflows;
- trajectory concepts;
- environment pinning;
- reproducibility patterns.

### Agentless
https://github.com/OpenAutoCoder/Agentless

Useful architectural idea:
- localize;
- generate candidate patches;
- validate;
- rerank.

For provenance-sensitive work, fewer autonomous tools may be better.

---

# 5. Provenance / attribution prior art

## BigCode StarCoder / StarCoderBase

Model card:
https://huggingface.co/bigcode/starcoderbase

Important facts to verify and preserve:
- 15.5B parameters;
- The Stack v1.2;
- opt-out requests excluded;
- 8192-token context;
- base/FIM model, not an instruction-following agent;
- OpenRAIL-M license;
- model access may require accepting Hugging Face conditions.

Do not treat “trained on The Stack” as proof that every training item had correct licensing metadata.

## OctoCoder / CommitPackFT

Inspect:
https://huggingface.co/bigcode/octocoder
and BigCode CommitPackFT dataset documentation.

Potential advantage:
- much more naturally suited to change/patch-style instructions than StarCoderBase;
- relatively inspectable data lineage.

Potential disadvantage:
- additional instruction-tuning data complicates the provenance story.

## IBM Granite Code

Canonical project:
https://github.com/ibm-granite/granite-code-models

IBM states that Granite Code models were trained on “license-permissible” data under IBM governance/legal review.

Advantages:
- 3B/8B/20B/34B sizes;
- code fixing/editing ability;
- Apache-2.0 model distribution;
- stronger practical capability.

Disadvantage:
- training corpus is not independently queryable in the same manner as The Stack.

EACH must support model-policy adapters rather than hard-code a single “approved” model.

---

# 6. Supply-chain provenance prior art

## in-toto

Canonical:
https://github.com/in-toto/in-toto

Use it as inspiration and preferably as an implementation dependency for stage attestations.

EACH should not invent a bespoke cryptographic provenance format if in-toto/DSSE can represent the necessary claims.

## SLSA

Use SLSA concepts for provenance vocabulary, but note:

Traditional build provenance answers:

> how did this artifact get built?

EACH additionally wants to record:

> what information and model contributed to authoring this source patch?

That authoring provenance is the project’s focus.

---

# 7. Current upstream-policy motivation

The motivating environment includes projects where AI-generated implementation is currently unacceptable.

The important lesson is:

> EACH must not be designed as a policy bypass.

A project may reject generated code for reasons including:
- clean-room concerns;
- uncertain training provenance;
- DCO/authorship;
- copyright/licensing;
- maintainership norms;
- review burden.

EACH can improve evidence.

It cannot dictate what another project accepts.

The project should make policy an explicit input:

```yaml
promotion_policy:
  ai_generated_source_allowed: false
  ai_review_allowed: true
  ai_research_allowed: true
  external_behavioral_testing_allowed: true
```

Then EACH can faithfully say:

> This candidate is useful for private validation, but this policy does not permit promotion.

---

# 8. Core terminology

Use these terms consistently.

## Scout

A high-capability agent allowed to access:
- GitHub;
- public web;
- public documentation;
- repository issue metadata.

It finds and classifies work.

It is **not** automatically part of the sealed authoring chain.

## Evidence packet

Machine-readable observations and public contracts.

Contains facts, not implementation suggestions.

## Spec packet

Immutable, approved inputs supplied to a builder.

It defines exactly what the builder is allowed to know.

## Builder

The local coding model plus constrained patch-generation loop.

## Executor

Runs approved read/build/test commands against the sanitized worktree.

## Validator

Determines whether the candidate satisfies acceptance tests and regression gates.

## Auditor

Runs post-generation source/corpus/license/similarity checks.

The auditor is terminal: it may accept/reject/flag.

It must not leak source matches back into the builder.

## Shadow patch

A candidate generated through AI lineage that is useful for private testing but not presumed promotable upstream.

## Promotion

Moving a result into a destination repository under its contribution policy.

## Receipt

A structured set of signed/hashed records covering one EACH run.

---

# 9. Non-negotiable information-flow rule

The most important property in EACH is not filesystem isolation.

It is **information-flow isolation**.

A builder must receive only:

1. the approved target source subset;
2. public interface definitions explicitly whitelisted;
3. approved public documentation explicitly whitelisted;
4. the immutable spec packet;
5. compiler output;
6. deterministic test output;
7. generic harness control messages.

It must not receive:

- search-engine results during generation;
- GitHub results discovered mid-generation;
- disassembly;
- decompiler output;
- proprietary implementation source;
- forbidden repository source;
- post-generation similarity matches;
- “here is how upstream X implemented this” from the auditor;
- hidden Scout notes;
- a previous AI patch when a clean retry is intended.

The audit stage occurs **after** generation.

If auditing finds a suspicious source match:

> reject/flag the candidate.

Do not give the matching code back to the builder and ask it to “rewrite differently.”

That would turn the provenance system into laundering.

---

# 10. Threat model

Create `docs/threat-model.md` early.

At minimum include:

## T1 — Network leakage

Builder or tools fetch implementation knowledge during generation.

Mitigation:
- no network in strong-isolation execution profile;
- enforce and test, do not merely document;
- record network policy in receipt.

## T2 — Hidden agent context

Framework injects repository history, global memories, prior chats, or web results.

Mitigation:
- explicit context constructor;
- log exact prompt/messages;
- linear trajectory;
- no undeclared RAG.

## T3 — Training-data memorization

Model emits source learned during pretraining.

Mitigation:
- model provenance metadata;
- corpus membership/search where possible;
- similarity scanning;
- honest residual-risk statement.

Not fully solvable.

## T4 — Spec contamination

Scout sees restricted material and converts it into a “clean” spec.

Mitigation:
- classify source origins;
- spec source citations;
- human approval gate for sensitive tasks;
- deterministic observation collectors.

## T5 — Audit feedback contamination

Auditor discovers a forbidden source match and feeds it to builder.

Mitigation:
- auditor is terminal;
- no content-bearing feedback into candidate generation.

## T6 — Existing target-source contamination

Sanitized worktree itself already contains AI-derived or provenance-unknown code.

Mitigation:
- target provenance classification;
- receipt records source SHA and declared trust class.

## T7 — Tool escape

Builder uses shell to inspect network, credentials, parent filesystem, Git history, or forbidden locations.

Mitigation:
- sandbox;
- read/write scopes;
- command policy;
- environment scrub;
- no inherited secrets;
- deny SSH/Git remotes/network tools.

## T8 — Publication contaminates future clean-room work

AI shadow patch becomes public and future human implementers see it.

Mitigation:
- shadow artifacts private by default;
- public publication must be explicit.

## T9 — False legal confidence

Users treat “no match found” as proof.

Mitigation:
- assurance levels explicitly technical;
- no “certified” language;
- every receipt states limitations.

---

# 11. Assurance levels

Implement a machine-readable assurance level.

Suggested initial levels:

## EACH-P0 — Untracked

- model/source unknown or opaque;
- unrestricted network;
- incomplete trajectory.

Useful only as ordinary AI code.

## EACH-P1 — Recorded

- model/provider identified;
- prompt/trajectory recorded;
- target revision recorded;
- patch hash recorded.

## EACH-P2 — Isolated

P1 plus:
- fixed model revision/hash where technically available;
- exact allowed inputs hashed;
- no-egress execution *verified*;
- environment manifest;
- tool allowlist;
- no undeclared retrieval.

## EACH-P3 — Dataset-auditable

P2 plus:
- model has sufficiently documented/queryable training provenance;
- post-generation corpus/source checks executed;
- license/source evidence recorded;
- no disallowed match over configured policy thresholds.

## EACH-P4 — Deterministic-generation

No neural model authors the promotable source.

For example:
- approved declarative spec;
- deterministic generator;
- generator source/revision recorded;
- output reproducible byte-for-byte.

P4 does not automatically mean legally clean-room.

These labels represent evidence properties only.

Each receipt must include:

```json
{
  "assurance": "EACH-P2",
  "legal_certification": false,
  "cleanroom_certification": false
}
```

---

# 12. Architecture overview

Target conceptual architecture:

```text
                        PUBLIC / CONNECTED ZONE

      GitHub issue ─────────────┐
      public docs ──────────────┤
      Scout agent ──────────────┤
                                ▼
                        ┌─────────────────┐
                        │ Intake / Policy │
                        └───────┬─────────┘
                                │
                         source classification
                                │
                                ▼
                        ┌─────────────────┐
                        │ Evidence Packet │
                        └───────┬─────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │   Spec Gate     │
                        │ approve + hash  │
                        └───────┬─────────┘
                                │
                   ═════════════╪══════════════
                         INFORMATION FIREWALL
                   ═════════════╪══════════════
                                │
                                ▼
                     SANITIZED AUTHORING ZONE

                    ┌──────────────────────┐
                    │ sanitized worktree   │
                    │ immutable spec       │
                    │ allowed docs only    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Local fixed model    │
                    │ Builder              │
                    └──────────┬───────────┘
                               │
                        candidate patches
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Executor / Validator │
                    │ compile + tests      │
                    └──────────┬───────────┘
                               │
                      accepted candidate
                               │
                   ════════════╪════════════
                          TERMINAL BOUNDARY
                   ════════════╪════════════
                               │
                               ▼
                        AUDIT / CONNECTED ZONE

                    ┌──────────────────────┐
                    │ corpus/source audit  │
                    │ license scan         │
                    │ static similarity    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ in-toto / receipt    │
                    │ sign/hash/archive    │
                    └──────────┬───────────┘
                               │
                      pass / reject / flag
                               │
                               ▼
                          Shadow result
```

---

# 13. Repository structure

Start with this shape unless implementation proves a simpler arrangement.

```text
EACH/
├── README.md
├── LICENSE
├── NOTICE
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── AGENTS.md
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .editorconfig
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── candidate.yml
│   │   ├── provenance-bug.yml
│   │   └── model-adapter.yml
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── schemas.yml
│   │   └── docs.yml
│   └── labeler.yml
├── docs/
│   ├── architecture.md
│   ├── threat-model.md
│   ├── claims-and-nonclaims.md
│   ├── assurance-levels.md
│   ├── information-flow.md
│   ├── model-provenance.md
│   ├── spec-gate.md
│   ├── sandboxing.md
│   ├── attestation.md
│   ├── audit.md
│   ├── benchmark.md
│   ├── remote-control.md
│   └── xodus-shadow-demo.md
├── schemas/
│   ├── issue.schema.json
│   ├── evidence.schema.json
│   ├── spec.schema.json
│   ├── model.schema.json
│   ├── environment.schema.json
│   ├── run.schema.json
│   ├── audit.schema.json
│   └── receipt.schema.json
├── each/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── hashing.py
│   ├── policy.py
│   ├── paths.py
│   ├── intake/
│   │   ├── github.py
│   │   ├── local.py
│   │   └── classify.py
│   ├── spec/
│   │   ├── packet.py
│   │   ├── approve.py
│   │   └── sanitize.py
│   ├── worktree/
│   │   ├── create.py
│   │   └── manifest.py
│   ├── models/
│   │   ├── base.py
│   │   ├── openai_compat.py
│   │   ├── transformers_local.py
│   │   └── policy.py
│   ├── builder/
│   │   ├── loop.py
│   │   ├── context.py
│   │   ├── tools.py
│   │   └── trajectory.py
│   ├── executor/
│   │   ├── base.py
│   │   ├── container.py
│   │   ├── native_macos.py
│   │   └── tart.py
│   ├── validate/
│   │   ├── commands.py
│   │   └── result.py
│   ├── audit/
│   │   ├── exact.py
│   │   ├── ngram.py
│   │   ├── ast.py
│   │   ├── license.py
│   │   ├── corpus.py
│   │   └── report.py
│   ├── attest/
│   │   ├── intoto.py
│   │   └── receipt.py
│   └── publish/
│       ├── policy.py
│       └── github.py
├── policies/
│   ├── default.yml
│   ├── permissive-oss.yml
│   ├── shadow-only.yml
│   └── examples/
├── models/
│   ├── README.md
│   └── manifests/
├── benchmarks/
│   ├── README.md
│   ├── corpus/
│   ├── tasks/
│   ├── expected/
│   └── scripts/
├── examples/
│   ├── hello-repair/
│   ├── spec-only/
│   └── shadow-patch/
├── scripts/
│   ├── bootstrap-macos.sh
│   ├── doctor.sh
│   ├── fetch-model.py
│   ├── run-benchmark.sh
│   └── smoke.sh
└── tests/
    ├── unit/
    ├── integration/
    ├── fixtures/
    └── adversarial/
```

Do not create all empty folders blindly.

Implement incrementally.

But preserve this conceptual separation.

---

# 14. Run artifact structure

Runs must not pollute the public repo by default.

Recommended:

```text
~/.each/
├── config.yml
├── keys/
├── models/
├── cache/
└── runs/
    └── 20261001T190000Z-abc123/
        ├── intake.json
        ├── evidence.json
        ├── spec.json
        ├── spec.sha256
        ├── materials.json
        ├── model.json
        ├── environment.json
        ├── trajectory.jsonl
        ├── commands.jsonl
        ├── patch.diff
        ├── validation.json
        ├── audit.json
        ├── receipt.json
        ├── receipt.sig
        └── artifacts/
```

The repository may contain sanitized example receipts.

Never commit:
- model weights;
- private keys;
- GitHub tokens;
- user credentials;
- proprietary source;
- unapproved shadow patches.

---

# 15. CLI contract

Aim for a simple `each` CLI.

Potential commands:

```bash
each doctor
each init
each policy show
each issue import <url>
each issue classify <id>
each evidence add <id> ...
each spec build <id>
each spec show <id>
each spec approve <id>
each worktree create <id>
each model list
each model doctor <model>
each run <id>
each run status <run-id>
each validate <run-id>
each audit <run-id>
each attest <run-id>
each receipt show <run-id>
each publish receipt <run-id>
each publish patch <run-id> --ack-ai-lineage
each benchmark list
each benchmark run <suite>
```

Do not require a daemon for v0.1.

A poller/daemon can come later.

CLI first.

---

# 16. MacBook Pro bootstrap

The user has a new M5 Max MacBook Pro with 128 GB unified memory dedicated primarily to AI and this project.

A number of developer tools may already be installed.

Therefore `bootstrap-macos.sh` must be **idempotent**:
- detect;
- report;
- install missing prerequisites only;
- do not overwrite local configuration silently.

## 16.1 Baseline checks

Run:

```bash
sw_vers
uname -a
uname -m
xcode-select -p || true
git --version
python3 --version
brew --version || true
gh --version || true
copilot --version || true
rustc --version || true
cargo --version || true
cmake --version || true
ninja --version || true
jq --version || true
```

Save output to a local bootstrap receipt.

## 16.2 Install Homebrew only if absent

Use the official Homebrew installer.

Do not embed third-party curl-pipe installers other than canonical vendor instructions.

## 16.3 Recommended packages

Install only if absent:

```bash
brew install \
  git \
  gh \
  jq \
  yq \
  cmake \
  ninja \
  pkg-config \
  ripgrep \
  fd \
  tree-sitter \
  uv
```

Optional later:

```bash
brew install openai/tools/tart
```

Tart is an open-source VM tool for Apple Silicon using Apple Virtualization.framework and is useful for stronger macOS/Linux sandbox experiments.

Canonical:
https://github.com/openai/tart

Do not make Tart mandatory for the first smoke test.

## 16.4 Xcode command-line tools

Ensure Xcode/CLT is present.

For C/C++ benchmark work:
- clang;
- lldb;
- SDK headers

must work.

Do not require full Xcode unless a test requires it.

## 16.5 Rust

Install via canonical rustup only if absent.

Rust is not required for EACH core initially, but useful for target projects such as Xodus.

## 16.6 Python

Prefer Python 3.12 for EACH unless a dependency proves incompatible.

Use `uv` for:
- environment;
- lockfile;
- command execution.

Example:

```bash
uv python install 3.12
uv venv --python 3.12
uv sync
```

Keep the lockfile in Git.

---

# 17. GitHub setup

Expected repository is likely:

```text
dragoshont/EACH
```

Do not assume.

Verify:

```bash
gh auth status
gh repo view EACH
```

If more than one repository matches, stop and ask.

Clone:

```bash
mkdir -p ~/src
cd ~/src
gh repo clone dragoshont/EACH
cd EACH
```

If the remote path differs, use the verified path.

Make repository public only if it is already intended to be public.

Do not expose any shadow run artifacts.

---

# 18. Architrave installation

Canonical Architrave repository:

https://github.com/dragoshont/architrave

Architrave is the user’s cross-platform, judge-gated build-agent harness.

Do not rewrite Architrave inside EACH.

Use it as the *outer project builder/orchestrator*.

Current documented GitHub Copilot plugin install path:

```bash
copilot plugin marketplace add dragoshont/architrave
copilot plugin install architrave@architrave
```

Then clone Architrave itself if the per-repo installer is needed:

```bash
cd ~/src
gh repo clone dragoshont/architrave
```

For EACH, use Architrave’s **knowledge repository profile**, because EACH is primarily:
- code;
- schemas;
- docs;
- CLI;
- automation;
- benchmarks;

not a product UI.

From the EACH repo:

```bash
~/src/architrave/tools/install.sh --profile knowledge .
```

If Codex project roles are explicitly desired later:

```bash
~/src/architrave/tools/install.sh --profile knowledge --codex .
```

Do not duplicate Architrave skills into EACH.

After adoption:
- inspect `architrave.config.json`;
- set real test/build commands;
- keep provider/model bindings local;
- preserve Architrave’s YAGNI and durable-run principles.

Recommended initial checks in `architrave.config.json` should call:

```text
uv run pytest
uv run ruff check .
uv run pyright each
```

Only add tools once dependencies exist.

If Ruff/Pyright are not chosen, use equivalent explicit checks.

---

# 19. Copilot usage

The user already uses GitHub Copilot.

Use Copilot/Architrave to build **EACH itself**.

This cloud/closed model is not part of EACH’s sealed Builder.

That distinction is important.

EACH source code can be built with ordinary AI assistance.

The provenance experiment concerns code generated *by EACH for target repairs*.

Add a repository note:

> The EACH harness itself may be AI-assisted. EACH receipts describe target patch generation; they do not imply the harness source was authored under its own sealed process.

Avoid recursive purity theater.

---

# 20. Local-model runtime strategy

Do not commit to a single runtime on day one.

The Mac is powerful enough to evaluate several candidates.

Implement a model adapter boundary first.

Minimum interface:

```python
class Model:
    def identity(self) -> ModelIdentity: ...
    def complete(self, messages, *, max_tokens, temperature, seed=None) -> ModelResponse: ...
```

The identity must record:
- provider/family;
- model;
- exact revision;
- local path;
- relevant file hashes;
- tokenizer hash;
- quantization;
- runtime;
- runtime version;
- context limit;
- temperature;
- seed support.

---

# 21. Initial model bake-off

Run a controlled evaluation of at least:

## Candidate A — StarCoderBase 15.5B

Why:
- strong documented lineage;
- The Stack v1.2;
- fixed old model;
- especially interesting for contamination studies.

Caveats:
- not instruction-tuned;
- 8192 context;
- may require Hugging Face license acceptance;
- likely weak as an autonomous agent.

Use as a **provenance baseline**, not necessarily the winning builder.

## Candidate B — OctoCoder

Why:
- StarCoder lineage;
- patch/instruction behavior;
- CommitPackFT provenance.

Verify current model/license/data documentation before use.

## Candidate C — Granite Code

Try a practical size such as 20B or 34B if the Mac runtime is stable.

Why:
- better software-repair capability;
- IBM’s license-permissible training claim;
- strong code editing.

Caveat:
- weaker independent training-corpus inspectability.

---

# 22. Inference runtime on Apple Silicon

Do not invent compatibility.

Benchmark the viable backends.

## Path 1 — Hugging Face Transformers + PyTorch MPS

This is the conservative baseline for models whose architecture is well-supported by Transformers.

Benefits:
- closest to original model format;
- fewer conversion questions.

Costs:
- potentially slower than MLX;
- memory/runtime behavior must be measured.

## Path 2 — MLX / MLX-LM

Apple MLX is highly attractive for local inference.

MLX-LM provides a local OpenAI-compatible HTTP server for supported models.

Canonical:
https://github.com/ml-explore/mlx-lm

However:
- not every architecture/model has the same support;
- tool calling is model/template dependent;
- server behavior is evolving.

Do not claim StarCoder/OctoCoder works through MLX until tested.

If a trustworthy conversion exists:
- record source model;
- conversion command;
- conversion tool revision;
- quantization;
- output hashes.

A converted model is a distinct model artifact for EACH receipts.

## Path 3 — llama.cpp / GGUF

Only use if model architecture and conversion are supported and the provenance chain can record the exact conversion.

## Path 4 — LM Studio

Useful interactively.

Do not make it the canonical sealed runtime because:
- graphical configuration;
- hidden defaults;
- harder reproducibility.

It can be supported through an OpenAI-compatible adapter later.

---

# 23. Important model-server isolation design

The local inference engine does not need arbitrary tools or repository access.

Treat it as a pure function:

```text
messages -> tokens
```

Preferred architecture:

```text
sandboxed builder orchestrator
        │
        │ audited inference request
        ▼
local inference endpoint
        │
        ▼
fixed model
```

The model server itself:
- must not browse;
- must not read target repo independently;
- must not invoke shell;
- must not have plugin/MCP access;
- only sees request content.

Record every request/response.

If the model server runs outside the sandbox for GPU performance, this is acceptable **only if**:
- the model has no autonomous tools;
- the proxy is narrow;
- all messages are logged;
- it cannot fetch new information.

This is a different threat model from putting a full coding agent outside the sandbox.

Document the distinction.

---

# 24. Do not begin with tool calling

For v0.1, avoid requiring native LLM tool calls.

Use an Agentless/mini-SWE style loop where the controller decides the operation.

Example:

1. controller sends:
   - issue;
   - allowed file inventory;
   - selected source excerpts;
   - acceptance criteria;
2. model returns a patch proposal in a strict format;
3. harness parses/applies patch;
4. harness runs deterministic build/tests;
5. harness sends only errors/test failures back;
6. model attempts a bounded correction.

This dramatically reduces runtime/model complexity.

Native tool calling can be a later adapter.

---

# 25. Builder loop v0.1

Implement something intentionally small.

Pseudo-algorithm:

```python
for attempt in range(policy.max_attempts):
    context = build_context(
        spec=immutable_spec,
        allowed_source=current_allowed_source,
        validation_feedback=previous_validation_feedback,
    )

    response = model.complete(context)

    patch = parse_patch(response)

    if not patch_is_within_scope(patch):
        record("scope_violation")
        continue

    reset_worktree()
    apply_patch(patch)

    compile_result = executor.run(policy.compile_commands)
    test_result = executor.run(policy.test_commands)

    record_everything()

    if compile_result.ok and test_result.ok:
        candidate = patch
        break
```

No web search.

No GitHub search.

No RAG.

No arbitrary task expansion.

---

# 26. Command policy

Do not give the sealed builder unrestricted shell by default.

Define command classes.

## Read-only source operations

Allowed examples:
- `cat`
- `sed`
- `rg`
- `find` within worktree
- compiler queries
- `git diff --no-ext-diff`
- `git status --short`

## Build/test operations

Declared per spec:
- `cmake`
- `ninja`
- `make`
- `cargo test`
- `pytest`
- target-specific test executable.

## Prohibited by default

- `curl`
- `wget`
- `ssh`
- `scp`
- `gh`
- `git fetch`
- `git pull`
- `git clone`
- package managers;
- browser;
- DNS/network tools;
- environment dumps containing secrets;
- parent-directory traversal.

The harness should validate commands before execution.

Never rely on the model to follow a prompt saying “do not use network.”

Enforce.

---

# 27. Sandboxing strategy

EACH needs multiple executor profiles.

## Profile A — Linux container / strongest v0.1 path

Use for ordinary benchmark tasks.

Requirements:
- `--network none`;
- read-only base image;
- only sanitized worktree mounted;
- no host home;
- no SSH agent;
- scrubbed environment;
- resource limits;
- explicit compilers/build tools.

Docker, Podman, or another suitable local runtime is acceptable.

Choose one and make the abstraction portable.

## Profile B — native macOS

Needed for Apple-specific target builds such as parts of Xodus.

Initially classify this as lower assurance unless isolation is proven.

Do not mark EACH-P2 merely because a command was “supposed” not to access the network.

Implement:
- command allowlist;
- environment scrub;
- worktree restriction;
- local firewall/no-egress evidence if possible.

Until verified, receipt should state:

```json
{
  "sandbox": "native-macos",
  "network_isolation_verified": false,
  "maximum_assurance": "EACH-P1"
}
```

## Profile C — Tart VM

Tart:
https://github.com/openai/tart

Tart uses Apple Virtualization.framework and can run macOS/Linux VMs on Apple Silicon.

Use it to investigate stronger platform-native isolation.

Potential benefits:
- disposable snapshot;
- exact macOS image;
- target toolchains;
- SSH automation;
- repeatable VM state.

But do not assume:
- GPU passthrough suitable for LLM inference;
- no-egress mode;
- perfect host isolation.

Verify.

Likely architecture:
- inference on host;
- builder/executor in Tart;
- narrow logged inference channel.

---

# 28. Sanitized worktrees

Never expose the builder to the full developer checkout by default.

Create a sanitized worktree per run.

Record exact:
- repository URL or local source ID;
- commit SHA;
- submodules;
- selected files;
- excluded paths;
- patches applied before run.

For strong profiles:
- `.git` history should be absent or minimized unless policy explicitly permits history;
- remotes removed;
- issue solution commit unavailable;
- hidden tests mounted separately from the builder-visible source when feasible.

Historical benchmark tasks must hide the known human fix.

---

# 29. Spec packet schema

A spec packet is the central artifact.

Suggested shape:

```json
{
  "schema_version": "0.1",
  "task_id": "EACH-0042",
  "target": {
    "repository": "owner/repo",
    "commit": "abc123",
    "language": ["c"]
  },
  "problem": {
    "summary": "Optional output pointer is rejected incorrectly",
    "source": "github-issue",
    "public_issue_url": "..."
  },
  "public_contracts": [
    {
      "type": "documentation",
      "url": "...",
      "sha256": "...",
      "license_class": "public-doc"
    }
  ],
  "observations": [
    {
      "case": "optional_size_null",
      "inputs": {"...": "..."},
      "outputs": {"result": "S_OK"},
      "collector": "..."
    }
  ],
  "allowed_paths": [
    "src/foo.c",
    "include/foo.h"
  ],
  "build": {
    "commands": ["cmake ...", "ninja ..."]
  },
  "acceptance": {
    "commands": ["ctest ..."]
  },
  "forbidden_sources": [
    "proprietary-implementation",
    "decompiler-output"
  ],
  "promotion_policy": "shadow-only",
  "approved_by": "human",
  "approved_at": "...",
  "sha256": "..."
}
```

The spec packet must be immutable after approval.

Change means:
- new version;
- new hash;
- new run.

---

# 30. Evidence origins

Every fact in a sensitive spec should have an origin classification.

Suggested enum:

```text
PUBLIC_API_DOC
PUBLIC_HEADER
PUBLIC_OPEN_SOURCE
PUBLIC_ISSUE
BLACK_BOX_OBSERVATION
USER_ASSERTION
MODEL_INFERENCE
UNKNOWN
RESTRICTED
```

Policy can reject:

```text
MODEL_INFERENCE
UNKNOWN
RESTRICTED
```

from sensitive builder specs.

This is one of EACH’s strongest features.

---

# 31. Black-box observation packets

When compatibility behavior must be characterized, keep the observation collector separate from the builder.

Example output:

```json
{
  "collector": "each-observer/0.1",
  "reference_platform": "Windows 11",
  "binary_hash": "...",
  "test_program_hash": "...",
  "cases": [
    {
      "case_id": "null_optional",
      "inputs": {
        "buffer": "valid",
        "size_pointer": "null"
      },
      "observable": {
        "return": "S_OK",
        "buffer_text": "RETAIL"
      }
    }
  ]
}
```

Do not record:
- implementation memory;
- decompiled code;
- call-stack internals from prohibited methods;
- proprietary symbols beyond public API references.

EACH can store this evidence even if a destination project later decides its collection method is insufficient.

Policy controls eligibility.

---

# 32. Scout

The Scout can be ChatGPT, Copilot, Architrave, or another powerful connected LLM.

Scout responsibilities:
- watch repositories;
- locate bounded issues;
- identify public docs;
- classify issue type;
- determine whether existing work/PR already covers it;
- suggest whether a task is eligible for a spec;
- create an EACH issue.

Scout must not:
- generate the sealed candidate patch;
- silently add undocumented semantics to the spec;
- hide its source citations;
- mark its own guesses as observations.

The Scout can use a normal frontier model.

That does not contaminate the Builder unless Scout-derived unsupported knowledge enters the approved spec.

---

# 33. GitHub issue workflow

Use GitHub as a visible control plane.

Suggested labels:

```text
each:candidate
each:needs-evidence
each:needs-spec
each:spec-ready
each:spec-approved
each:builder-ready
each:running
each:shadow-pass
each:validation-fail
each:audit-flag
each:audit-pass
each:human-review
each:publishable-receipt

origin:public-docs
origin:black-box
origin:open-source
origin:model-inference
origin:unknown

policy:permissive-oss
policy:shadow-only
policy:no-ai-source

lang:c
lang:cpp
lang:rust
lang:python
```

Do not use labels as security enforcement.

They are metadata.

Policy engine must revalidate the packet.

---

# 34. GitHub automation v0.1

Do not begin with a 24/7 service.

Implement:

```bash
each issue sync
```

that queries ready issues via `gh`.

Later:

```bash
each watch --interval 300
```

can poll.

A local `launchd` job can eventually invoke it.

Do not require GitHub webhooks to a laptop.

---

# 35. Remote control from another machine / third agent

The user may control the M5 Max from another machine.

Support this from day one without making it the primary architecture.

Simplest topology:

```text
Windows / other controller
   Copilot / Architrave
           │
          SSH
           │
           ▼
       M5 Max
       ~/src/EACH
           │
        each CLI
```

Enable Remote Login manually on the Mac if desired.

Prefer public-key authentication.

Do not pass GitHub/HuggingFace secrets over command-line arguments.

## Stronger future remote mode

Create an optional `each-remote` forced-command gateway.

Instead of full shell SSH, a dedicated key could be restricted to commands such as:

```text
each status
each issue sync
each run <id>
each receipt show <id>
```

This is useful if a third-party orchestrator is allowed to trigger EACH but should not have unrestricted Mac shell access.

Do not build this in v0.1 unless remote operation blocks the user.

---

# 36. Model download policy

Model acquisition occurs outside the sealed run.

Downloads belong to the **provisioning stage**.

For every model:
- record canonical source;
- model card;
- license;
- revision/commit;
- file list;
- hashes;
- tokenizer;
- config;
- conversion if any.

Store under:

```text
~/.each/models/<model-id>/<revision>/
```

Model directory is read-only during runs.

## Hugging Face gated models

If StarCoderBase requires acceptance:
- user manually accepts terms;
- use normal Hugging Face token for download;
- never expose token to sealed builder;
- remove token from runtime environment.

The receipt records weights hash, not credentials.

---

# 37. Model manifest

Example:

```json
{
  "schema_version": "0.1",
  "id": "bigcode/starcoderbase",
  "revision": "...",
  "license": "BigCode OpenRAIL-M",
  "weights": [
    {"path": "...", "sha256": "..."}
  ],
  "tokenizer_sha256": "...",
  "runtime": {
    "name": "transformers",
    "version": "..."
  },
  "training_provenance": {
    "class": "documented-corpus",
    "sources": [
      "The Stack v1.2"
    ],
    "membership_tools_available": true
  },
  "notes": [
    "Base model",
    "8192 context"
  ]
}
```

---

# 38. Determinism

Do not promise bit-for-bit model determinism unless measured.

Record:
- seed;
- temperature;
- top-p;
- sampling mode;
- runtime;
- hardware;
- model hashes.

Classify:

```text
replayable-inputs: true
bitwise-reproducible-output: false
```

Model generation can be nondeterministic even with a seed.

Receipts should distinguish:
- input reproducibility;
- environment reproducibility;
- output reproducibility.

---

# 39. Patch format

Prefer unified diff.

The model should not have direct write access in v0.1.

Prompt output contract:

```text
BEGIN_PATCH
diff --git ...
...
END_PATCH
```

Harness:
- parses;
- rejects malformed patch;
- verifies allowed paths;
- rejects binary diffs;
- rejects scope escape;
- applies in disposable worktree.

Later, direct editing may be supported.

Patch-first is more auditable.

---

# 40. Validation feedback

The model may receive:
- compiler errors;
- failing test names;
- test stdout/stderr after redaction.

Do not include hidden expected solution source.

Implement truncation deterministically.

Receipt must record exact feedback.

---

# 41. Post-generation audit

The Auditor is independent from the Builder.

Minimum v0.1 checks:

## Exact/substring

Compare candidate against configured reference corpora where legally/technically available.

## Token n-grams

Normalize:
- whitespace;
- comments optionally;
- trivial formatting.

Report longest/strongest matches.

## AST similarity

Use Tree-sitter when language support exists.

Normalize:
- identifier names;
- literals optionally.

Do not interpret this as proof of derivation.

## License scan

Integrate a mature scanner if practical.

Candidates:
- ScanCode Toolkit;
- other OSS license scanners.

Do not write your own license classifier.

## Corpus membership adapter

For model families with queryable training corpus/membership tools, create an adapter.

Do not block v0.1 on perfect BigCode infrastructure.

Start with pluggable interface and one working backend.

---

# 42. Audit must be terminal

This deserves repetition.

Bad:

```text
Auditor: candidate resembles forbidden Foo.c
Builder: okay, rewrite it differently
```

That contaminates the next generation with forbidden implementation details.

Correct:

```text
Auditor: candidate failed source-similarity policy
Run status: REJECTED
```

A fresh run may occur only from the original approved spec.

Do not expose match content to Builder.

---

# 43. Audit report

Example:

```json
{
  "run_id": "...",
  "patch_sha256": "...",
  "checks": {
    "exact": {
      "status": "PASS",
      "max_match_chars": 24
    },
    "ngram": {
      "status": "PASS",
      "top_score": 0.18
    },
    "ast": {
      "status": "FLAG",
      "top_score": 0.72,
      "reference_class": "public-permissive"
    },
    "license": {
      "status": "PASS"
    },
    "training_corpus": {
      "status": "UNKNOWN",
      "reason": "adapter unavailable"
    }
  },
  "result": "FLAG",
  "legal_conclusion": null
}
```

Do not reduce everything to one magic “provenance score” in v0.1.

Scores invite false certainty.

Use structured evidence.

---

# 44. Attestation

Use in-toto concepts.

Investigate the Python implementation and choose the smallest stable integration.

Each EACH run should eventually produce attestations for:

1. intake;
2. spec approval;
3. worktree materialization;
4. generation;
5. validation;
6. audit;
7. publication.

Bind:
- input hashes;
- output hashes;
- command;
- environment;
- model identity;
- run ID.

Sign locally.

Do not commit the signing private key.

Use an ignored location such as:

```text
~/.each/keys/
```

Public key may live in repo if user chooses.

---

# 45. Receipt

The human-readable receipt is the primary UX.

Example:

```text
EACH receipt
Run: 20261001T...
Task: EACH-42

Target:
  repo: ...
  commit: ...

Spec:
  sha256: ...
  approved: yes
  origins:
    PUBLIC_API_DOC: 2
    BLACK_BOX_OBSERVATION: 3

Builder:
  model: bigcode/octocoder
  revision: ...
  weights sha256: ...
  runtime: ...

Isolation:
  sandbox: container
  network: verified disabled
  secrets inherited: none

Generation:
  attempts: 3
  trajectory sha256: ...

Validation:
  compile: PASS
  tests: 41/41 PASS

Audit:
  exact match: PASS
  ngram: PASS
  AST: FLAG
  training corpus: unavailable
  license: PASS

Assurance:
  EACH-P2

Status:
  SHADOW-PASS

Legal clean-room certification:
  NO

Upstream promotion:
  NOT AUTHORIZED
```

This should render as:
- JSON;
- Markdown;
- terminal summary.

---

# 46. Publication modes

Implement three explicit modes.

## PRIVATE

Nothing leaves local run store.

Default.

## RECEIPT_ONLY

Publish:
- spec if permitted;
- hashes;
- receipt;
- audit result;
- validation;
- no patch.

Useful for compatibility research.

## AI_LINEAGE_PATCH

Publish patch with explicit disclaimer:

> AI-generated / AI-assisted lineage. Not suitable for projects that disallow such code.

Require explicit CLI acknowledgement:

```bash
each publish patch RUN --ack-ai-lineage
```

No automatic upstream PR in v0.1.

---

# 47. Benchmark first, Xodus later

The first EACH benchmark must not be Xodus.

Build confidence on historical, already-fixed, permissively licensed repositories.

Select approximately 20 tasks for v0.1; expand to 50 later.

Criteria:
- C/C++/Rust/Python mix;
- bounded bugs;
- deterministic tests;
- known human solution commit hidden from builder;
- repository license compatible with benchmark use;
- issue text available;
- no network required to run tests after provisioning.

For each task:
- checkout parent of fix;
- create sanitized task;
- hide fix;
- run EACH;
- test candidate;
- compare only after run.

---

# 48. Benchmark metrics

Track:

## Repair quality

- compile success;
- acceptance-test pass;
- regression pass;
- human-fix equivalence class where useful;
- patch size;
- files changed;
- attempts;
- wall time.

## Provenance quality

- receipt completeness;
- undeclared input attempts;
- network attempts;
- forbidden command attempts;
- corpus checks executed;
- audit flags.

## Isolation quality

- can task access internet?
- can it read home directory?
- can it access Git remotes?
- can it inspect hidden solution?
- can it read model provisioning credentials?

## Model comparison

- success rate;
- attempts;
- tokens;
- time;
- provenance class.

Do not compare only “smartness.”

---

# 49. Adversarial benchmark cases

EACH must test itself.

Create fixtures where:

1. hidden solution exists in parent filesystem;
2. Git remote contains fix;
3. network endpoint exposes fix;
4. environment variable contains forbidden hint;
5. issue text includes a poisoned instruction;
6. audit corpus contains exact candidate;
7. candidate changes forbidden file;
8. candidate attempts to add dependency;
9. candidate tries to curl;
10. builder asks to inspect `.git`;
11. spec changes after approval;
12. auditor detects match.

Expected behavior:
- deny;
- record;
- fail safely.

---

# 50. CI

Public GitHub Actions should test **the harness**, not run private model weights.

CI:
- Python unit tests;
- schemas;
- formatting/lint;
- simulated deterministic model;
- sandbox policy unit tests;
- receipt generation;
- tamper detection;
- sample benchmark with a deterministic fake model.

Do not make CI dependent on:
- Hugging Face tokens;
- local Mac;
- commercial LLM APIs.

---

# 51. Deterministic fake model

Implement early.

Example:

```python
class FixtureModel:
    def __init__(self, responses: list[str]): ...
```

This lets CI reproduce:
- patch application;
- feedback loops;
- receipts;
- audit;
- failure paths

without any model.

This is crucial.

---

# 52. Policy files

Policies define what EACH may do.

Example `policies/permissive-oss.yml`:

```yaml
name: permissive-oss

builder:
  network: deny
  max_attempts: 5
  patch_only: true

inputs:
  allow_origins:
    - PUBLIC_API_DOC
    - PUBLIC_HEADER
    - PUBLIC_OPEN_SOURCE
    - PUBLIC_ISSUE
    - BLACK_BOX_OBSERVATION

tools:
  deny:
    - curl
    - wget
    - ssh
    - gh
    - git-fetch

publication:
  default: private

audit:
  exact: required
  ngram: required
  ast: preferred
  license: required
```

Example `shadow-only.yml`:

```yaml
promotion:
  ai_generated_source_allowed: false
publication:
  patch: explicit-only
```

---

# 53. Human approval

Do not require a human for every ordinary benchmark run.

But for provenance-sensitive clean-room style tasks:
- spec approval should be a distinct action.

CLI:

```bash
each spec approve TASK --human
```

Store:
- user identity;
- timestamp;
- spec hash.

No need for elaborate signatures in v0.1.

Add cryptographic signing later.

---

# 54. Architrave role in implementation

Use Architrave as the outer conductor.

Ask it to preserve:
- YAGNI;
- small vertical slices;
- durable Run state;
- deterministic gates;
- public repo hygiene.

Do not let Architrave “improve” the clean-room Builder by swapping in its own cloud model.

The EACH Builder is a target subsystem with strict boundaries.

Architrave may write EACH’s Python code.

It must not be the sealed target-patch author unless running through EACH itself.

---

# 55. First Architrave mission

The first Architrave Run should produce only the skeleton necessary to demonstrate:

```text
local fixture issue
→ approved spec
→ deterministic FixtureModel
→ candidate diff
→ sandbox execution
→ tests
→ audit
→ receipt
```

No real LLM yet.

This proves architecture before model complexity.

Acceptance:

```bash
uv run each demo hello-repair
```

prints a receipt and exits 0.

The demo repository contains:
- one bug;
- one test;
- one known candidate response.

---

# 56. Second mission — real local model

After deterministic demo:

1. model manifest support;
2. local inference adapter;
3. one small model;
4. same fixture;
5. full trajectory.

Do not add GitHub automation yet.

---

# 57. Third mission — GitHub issue import

Then:

```bash
each issue import https://github.com/.../issues/...
```

creates local intake.

Do not automatically generate a spec.

User/Scout creates evidence/spec.

---

# 58. Fourth mission — benchmark harness

Only then build historical task suite.

Need at least:
- 5 tasks smoke;
- 20 tasks meaningful v0.1;
- 50 tasks later.

---

# 59. Fifth mission — attestation

After run semantics stabilize:
- add in-toto/DSSE;
- sign receipts;
- tamper tests.

Do not make crypto the first blocker.

Hashes first.

---

# 60. Sixth mission — public Scout integration

Add a Scout adapter that can accept:
- manually pasted JSON;
- GitHub issue metadata;
- optional connected LLM output.

The Scout output must itself identify:
- claims;
- sources;
- confidence;
- unsupported inference.

---

# 61. Seventh mission — Xodus shadow demonstration

Only after EACH passes its own benchmark.

Motivating repositories:
- `xodus-gaming/xodus`
- `xodus-gaming/xgameruntime`

Xodus currently has strict contribution rules about LLM use.

Treat all generated xgameruntime implementation as:

```text
SHADOW ONLY
```

unless upstream policy changes explicitly.

The goal is not to submit AI code.

The goal is to demonstrate:

```text
public issue
+ public docs
+ approved black-box observations
→ sealed spec
→ local model candidate
→ macOS/Linux validation
→ provenance receipt
```

---

# 62. Xodus demonstration principles

For a GDK API:

Builder may receive:
- public API signature;
- public Microsoft docs;
- approved open-source Microsoft code only if policy explicitly allows it;
- independently recorded external observations;
- current open Xodus interface/scaffold required to compile.

Builder must not receive:
- Microsoft proprietary implementation;
- disassembly;
- decompilation;
- prohibited tracing;
- hidden LLM RE notes;
- auditor source matches.

Generated patch remains quarantined.

If it proves the behavioral spec is sufficient:
- useful scientific evidence;
- not automatically upstream source.

---

# 63. macOS/Xodus special execution

Xodus demonstration eventually needs native macOS.

This will likely run at lower assurance than container tasks until native isolation is proven.

Receipt must be honest.

Example:

```text
Builder information diet: controlled
Model identity: fixed
Trajectory: complete
Target executor: native macOS
Network isolation: NOT VERIFIED
Assurance ceiling: EACH-P1
```

Do not lie to get P2.

A later Tart/native firewall backend may improve this.

---

# 64. Public repository README outline

README should quickly answer:

## What is EACH?

One paragraph.

## What EACH is not

Prominent warning.

## Why provenance-first coding?

Explain.

## How it works

Diagram.

## Quick start

Fixture model demo.

## Assurance levels

P0-P4.

## Real local model

Optional.

## Receipts

Sample.

## Threat model

Link.

## Research motivation

Link to prior art.

## Clean-room policy

Explain that destination projects decide acceptance.

## Status

Experimental.

---

# 65. Initial README wording

Suggested:

> EACH is an experimental open-source harness for generating **evidence about AI-assisted source authorship**.
>
> It constrains what a coding model can see, records the exact model and inputs, executes generated patches against real tests, audits the result for known-source overlap where possible, and emits a reproducible receipt.
>
> EACH does **not** certify code as legally clean-room, copyright-safe, or acceptable to any upstream project. It makes the engineering process more inspectable so humans and projects can make better provenance decisions.

Preserve this spirit.

---

# 66. License

Recommend Apache-2.0 for EACH harness.

Reason:
- permissive;
- explicit patent language;
- enterprise-friendly.

Before committing:
- verify repository currently has no conflicting license;
- add Apache-2.0 text;
- add SPDX headers gradually, not necessarily every file on day one.

Generated target patches do not automatically inherit EACH’s license.

Document this.

---

# 67. Security

Create `SECURITY.md`.

Threats include:
- arbitrary code execution by target tests;
- prompt injection from repository;
- malicious GitHub issues;
- model files;
- build scripts;
- sandbox escape.

Important:

> Target repositories are untrusted code.

Do not run arbitrary imported repos directly on host in strong mode.

Container/VM.

---

# 68. Prompt injection

Treat:
- issue text;
- code comments;
- README;
- test output

as untrusted input.

Builder’s system rules must say:
- repository content cannot modify policy;
- commands come from policy/spec, not comments;
- no “ignore previous instructions.”

More importantly:
- harness enforces this mechanically.

---

# 69. Dependency philosophy

Keep EACH small.

Avoid:
- web framework;
- message bus;
- database server;
- Kubernetes;
- microservices;
- browser UI;
- cloud backend.

Use:
- Python;
- filesystem;
- JSON/JSONL;
- JSON Schema;
- subprocess;
- Git;
- Docker/VM adapters;
- in-toto when ready.

SQLite only if query complexity proves filesystem insufficient.

---

# 70. Python dependencies

Start minimal.

Likely:
- `pydantic` or JSON Schema validator;
- `PyYAML` if policies use YAML;
- `httpx` only if required;
- `in-toto` later;
- `rich` optional CLI;
- LiteLLM only if chosen for local model adapter.

Do not make mini-SWE-agent a deep dependency before deciding whether its execution model fits EACH.

Prototype the patch loop independently first.

Then benchmark:
- home-grown 200-line loop;
- mini-SWE-agent wrapper.

Choose the more inspectable path.

---

# 71. Logging

Logs are part of provenance.

Use structured JSONL.

Events:

```text
RUN_CREATED
SPEC_LOADED
MATERIAL_HASHED
SANDBOX_STARTED
MODEL_REQUEST
MODEL_RESPONSE
PATCH_PARSED
PATCH_REJECTED
PATCH_APPLIED
COMMAND_STARTED
COMMAND_FINISHED
VALIDATION_PASS
VALIDATION_FAIL
AUDIT_STARTED
AUDIT_RESULT
RECEIPT_CREATED
PUBLICATION
```

Each:
- timestamp;
- monotonic sequence;
- relevant hashes.

Do not log secrets.

---

# 72. Secrets

Before spawning sandbox:
- create minimal environment from allowlist;
- do not inherit whole host env.

Never pass:
- `GITHUB_TOKEN`
- `GH_TOKEN`
- `HF_TOKEN`
- SSH auth socket
- cloud API keys

unless stage explicitly requires them.

Provisioning/Scout can have credentials.

Builder cannot.

---

# 73. Source identity

Record:

```text
repository
commit
tree hash
submodule SHAs
dirty state
```

Reject dirty target source unless policy explicitly permits and hashes diff.

---

# 74. Test identity

Tests matter as much as source.

Record:
- command;
- hidden test bundle hash;
- environment;
- exit code;
- output hash.

Builder should not see hidden test implementation if policy wants a stronger benchmark.

It can receive failure summaries.

---

# 75. Compiler identity

For low-level work record:
- compiler;
- version;
- target;
- SDK;
- relevant flags.

Important for C/C++ compatibility experiments.

---

# 76. Similarity policy

Do not pick arbitrary magic thresholds and claim safety.

Initial system:
- show evidence;
- configurable thresholds;
- flag categories.

Suggested states:

```text
PASS
FLAG
FAIL
UNAVAILABLE
```

Policy chooses how they combine.

---

# 77. Data Portraits / BigCode integration

Treat as optional but important for StarCoder-family P3 experiments.

Tasks:
1. identify currently available official membership/search infrastructure;
2. document limitations;
3. build adapter;
4. cache queries;
5. preserve raw results.

Do not scrape an unofficial service silently.

If official index is unavailable:
- mark check UNAVAILABLE;
- do not downgrade quietly.

---

# 78. Model contamination experiments

EACH itself should test whether provenance scanners detect known overlap.

Create intentionally contaminated fixtures using permissively licensed snippets from the model’s known corpus.

Expected:
- Auditor flags.

Also create:
- common boilerplate;
- independently written equivalent code;
- renamed copy.

Measure:
- false positive;
- false negative.

This makes the research credible.

---

# 79. Research documentation

Add:

```text
docs/research/
  prior-art.md
  model-lineage.md
  attribution-tools.md
  open-questions.md
```

`prior-art.md` should include at minimum:
- Tabnine;
- GitHub Copilot code referencing;
- Amazon Q reference tracker;
- SWE-agent;
- mini-SWE-agent;
- Agentless;
- BigCode/Data Portraits;
- CodeGenLink;
- in-toto/SLSA;
- QEMU/Wine policy discussions.

Do not claim novelty without keeping this current.

---

# 80. Open research questions

Track explicitly:

1. How meaningful is a negative corpus-membership result?
2. Can transformed/multi-source memorization be detected?
3. What exact training-data evidence is sufficient for P3?
4. How should model conversion affect model identity?
5. Can macOS native no-egress execution be verified strongly?
6. Can authoring attestations integrate with Sigstore?
7. How should DCO projects treat AI-lineage receipts?
8. Can declarative spec-to-code paths achieve P4 for wrapper APIs?
9. How do we prevent public shadow patches from contaminating future clean-room work?
10. What should an upstream project be able to require from an EACH receipt?

---

# 81. Declarative deterministic generation

This is a potentially powerful later lane.

Some compatibility functions are simple:
- argument validation;
- enum mapping;
- buffer fill;
- optional pointer behavior;
- HRESULT mapping;
- IPC forwarding.

For these, a human-approved declarative spec may generate C deterministically.

Example:

```yaml
api: XExample
returns: HRESULT
rules:
  - when: output == null
    return: E_POINTER
  - otherwise:
      write:
        output: "RETAIL"
      return: S_OK
```

A deterministic generator:
- has normal authorship;
- can be audited;
- produces reproducible source.

This is potentially more interesting for strict upstreams than AI generation.

But do not build it until actual examples justify it.

---

# 82. Public vs private shadow code

Harness: public.

Docs: public.

Schemas: public.

Benchmarks: public.

Receipts: publishable where sources permit.

AI shadow patches: private by default.

Reason:

> Public AI implementations can become contamination hazards for later human clean-room implementations.

This is not secrecy for its own sake.

Allow explicit publication.

---

# 83. First 10 GitHub issues for EACH

After repository bootstrap, create or track these as milestone tasks.

## #1 — Project foundation
- README
- license
- packaging
- CI
- doctor

## #2 — Schema and receipt model
- run/spec/model/audit schemas

## #3 — Deterministic fixture model
- fixture responses

## #4 — Sanitized worktree
- target SHA
- allowed paths
- patch application

## #5 — Container executor
- no network
- env scrub
- command policy

## #6 — End-to-end fixture demo
- issue → spec → patch → test → receipt

## #7 — Local model adapter
- OpenAI-compatible + identity

## #8 — Local model bake-off
- StarCoderBase / OctoCoder / Granite

## #9 — Audit MVP
- exact/ngram/license

## #10 — Historical benchmark
- first five tasks

Do not create 50 speculative issues.

---

# 84. Milestones

## M0 — Repo healthy

Acceptance:
- fresh clone;
- `uv sync`;
- tests;
- CI;
- Architrave installed;
- doctor.

## M1 — Deterministic loop

Acceptance:
- FixtureModel repairs fixture;
- sandbox;
- receipt.

## M2 — Real local model

Acceptance:
- local model patch attempt recorded;
- exact weights/model identity;
- no cloud call;
- full trajectory.

## M3 — GitHub intake

Acceptance:
- issue import;
- spec approval;
- local run.

## M4 — Audit

Acceptance:
- source similarity checks;
- audit report;
- no audit→builder leakage.

## M5 — Attestation

Acceptance:
- signed/hashed stage artifacts;
- tamper test.

## M6 — Benchmark

Acceptance:
- 20 historical tasks;
- reproducible report.

## M7 — Clean-room-style demo

Acceptance:
- controlled black-box/public-doc spec;
- shadow patch;
- receipt;
- explicit non-promotion.

## M8 — Xodus shadow demo

Only after above.

---

# 85. Mac resource plan

M5 Max 128 GB is ample for the initial candidate models.

Do not consume all memory by default.

Model runner should support:
- max memory target;
- single model loaded;
- idle unload;
- quantized alternatives where provenance identity remains documented.

Record actual:
- peak memory;
- tokens/s;
- prompt processing;
- energy/thermal only if useful.

Performance is secondary to reproducibility for v0.1.

---

# 86. Model comparison protocol

For each model:
- same 5–20 tasks;
- same specs;
- same sandbox;
- same max attempts;
- same feedback policy;
- record exact model artifact.

Report:
- success;
- patch size;
- attempts;
- token count;
- wall time;
- audit availability;
- assurance ceiling.

Do not select model based only on pass rate.

Provenance quality is a dimension.

---

# 87. Seed and multiple candidates

A model can generate multiple candidates.

For v0.1:
- max 3 attempts;
- one trajectory;
- validation feedback allowed.

Later support:
- independent candidate branches with different seeds.

Do not run hundreds of samples.

---

# 88. Context budgeting

One design goal is proving exactly what was shown.

Therefore save a canonical **context manifest** before each model call.

Example:

```json
{
  "message_sha256": "...",
  "materials": [
    {"path": "src/foo.c", "sha256": "...", "lines": "1-200"},
    {"path": "include/foo.h", "sha256": "..."}
  ],
  "spec_sha256": "..."
}
```

This is stronger than just saving prompt text.

---

# 89. Source slicing

Do not show entire repository automatically.

Implement localizer strategies:

v0.1:
- spec-declared files only.

v0.2:
- deterministic `rg` based on symbols/test names.

Later:
- model-assisted localization, but this becomes part of provenance.

Source selection itself can leak information.

Record it.

---

# 90. External LLM review

For ordinary EACH development:
- use Copilot/Architrave freely.

For a target patch with shadow policy:
- cloud LLM review may be permitted if policy says so;
- doing so changes lineage/assurance.

Receipt must say:

```json
"external_ai_review": true
```

For strict experiments:
- no external LLM review of candidate source.

Do not silently use Copilot inline completion in the sanitized worktree.

---

# 91. IDE isolation

If developer opens a shadow candidate in VS Code/Copilot, Copilot may analyze or suggest edits.

That changes lineage.

Therefore:
- shadow run directory should not be opened in an AI-enabled editor for strict receipts;
- published artifact can be reviewed later under a new lineage class.

Document this.

---

# 92. Human inspection

Human viewing of candidate is not automatically forbidden.

But if the same human will later perform a clean-room reimplementation, viewing shadow source may matter.

EACH should support:

```text
source_visibility: hidden
```

where user sees:
- tests;
- milestones;
- receipt;

but not candidate patch until they explicitly reveal it.

Nice later feature.

Do not block v0.1.

---

# 93. User experience target

Eventually:

```bash
each issue import https://github.com/foo/bar/issues/123
each spec build EACH-123
each spec approve EACH-123
each run EACH-123 --model octocoder --policy permissive-oss
```

Then:

```text
✓ sanitized tree
✓ network disabled
✓ model identity bound
✓ attempt 1 compiled
✗ test 3 failed
✓ attempt 2 compiled
✓ 28/28 tests
✓ audit complete

Result: SHADOW-PASS
Assurance: EACH-P2

Receipt:
~/.each/runs/.../receipt.md
```

This should feel excellent.

---

# 94. `each doctor`

Must become a strong diagnostic.

Report:

```text
EACH version
Python
Git
Docker/container runtime
Tart
Xcode/clang
Rust
GH auth
model store
models available
model runtime
network-isolation backend
signing key
Architrave plugin
repo state
```

No secrets.

---

# 95. Developer docs

Add a one-page contributor flow:

```bash
git clone ...
uv sync
uv run pytest
uv run each demo hello-repair
```

If setup is harder, v0.1 has failed its usability goal.

---

# 96. CI matrix

Initial:
- macOS arm64 if GitHub Actions supports required environment for pure tests;
- Ubuntu;
- Python 3.12.

Do not run model inference in CI.

No need for Windows until code requires it.

---

# 97. Versioning

Use semantic versioning when ready.

Before v0.1:
- unreleased.

Schemas must contain explicit `schema_version`.

Receipts must survive software changes.

---

# 98. Audit reproducibility

Auditor tools themselves need identities.

Record:
- tool name;
- version;
- corpus revision;
- config;
- thresholds.

An “audit pass” without audit-tool version is weak evidence.

---

# 99. Model provenance policy interface

Example:

```python
@dataclass
class ProvenanceCapabilities:
    weight_hashable: bool
    training_dataset_documented: bool
    training_membership_queryable: bool
    license_claim_documented: bool
    conversion_chain_recorded: bool
```

Assurance engine derives ceiling.

Do not hard-code:
“StarCoder = safe.”

---

# 100. Model manifests vs claims

Separate:

```text
FACT:
model card says trained on The Stack v1.2

CLAIM:
therefore no problematic source existed in training
```

The second is not justified.

EACH should model:
- vendor/model-author claims;
- independently verified evidence;
- unknowns.

---

# 101. Receipt integrity

At minimum:
- SHA-256 all artifacts;
- root receipt contains Merkle-like manifest or sorted file-hash list.

Later:
- in-toto signatures.

Tamper test:
1. create receipt;
2. modify patch;
3. verify receipt fails.

---

# 102. Crash/recovery

Runs should be resumable where safe.

But generation replay may change output.

State machine:

```text
CREATED
SPEC_APPROVED
MATERIALIZED
GENERATING
VALIDATING
AUDITING
COMPLETE
FAILED
REJECTED
```

If crash during GENERATING:
- mark attempt incomplete;
- next attempt new ID.

Do not pretend to resume inside a model stream.

---

# 103. Source cleanup

Disposable worktree after run:
- archive patch and relevant hashes;
- delete build junk;
- keep only declared run artifacts.

Allow optional debug retention.

---

# 104. Cost model

Local models mean no token bill, but there is compute cost.

Track:
- input tokens;
- output tokens;
- wall time;
- attempts;
- optional energy proxy later.

No need for monetary cost in v0.1.

---

# 105. Performance safety

Model server should not starve Mac.

Default:
- one generation at a time;
- no parallel benchmark agents initially;
- bounded output tokens.

The Mac is also used for AI-related projects.

Avoid system instability.

---

# 106. Research ethics / communications

When discussing results publicly:

Good:

> On 20 historical permissively licensed repair tasks, model X produced 8 test-passing patches under EACH-P2 isolation.

Bad:

> Model X produced 8 clean-room patches.

Be rigorous.

---

# 107. Suggested public tagline

> **EACH: make the coding agent show its work.**

Alternative:

> **Auditable inputs, reproducible runs, evidence-backed AI patches.**

Avoid “clean code” jokes that imply certification.

---

# 108. Architecture decision records

Use ADRs for only consequential decisions.

Initial likely ADRs:

- ADR-001: provenance evidence, not certification
- ADR-002: terminal audit boundary
- ADR-003: private shadow patches by default
- ADR-004: local model adapter architecture
- ADR-005: in-toto-compatible attestations
- ADR-006: container-first strong isolation

Do not ADR trivial choices.

---

# 109. Open-source contribution model

CONTRIBUTING should require for EACH itself:
- normal tests;
- provenance-rule changes require threat-model review.

Do not force EACH contributors to use EACH.

That would hinder adoption.

But contributions to provenance rules should include:
- threat-model implications;
- adversarial tests.

---

# 110. Security boundary tests

Write tests for:
- path traversal;
- symlink escape;
- malicious patch touching `.git`;
- environment secret access;
- shell metacharacters;
- command allowlist;
- network denial;
- spec hash mismatch;
- receipt tamper.

This project executes untrusted code.

Take that seriously.

---

# 111. The first real code to write

Recommended order:

1. project package + CLI;
2. hash utility;
3. run directory;
4. JSON schemas;
5. FixtureModel;
6. patch parser;
7. fixture target;
8. executor;
9. validator;
10. receipt.

Only then:
11. local model.

This sequence gives fast feedback.

---

# 112. What not to build

Do not build:

- browser UI;
- Electron app;
- Kubernetes deployment;
- hosted SaaS;
- vector database;
- RAG system;
- plugin marketplace;
- model trainer;
- custom LLM runtime;
- custom VM hypervisor;
- custom license database;
- custom Git forge;
- custom cryptography.

Use existing components.

---

# 113. Initial `pyproject.toml`

Architrave should create it, but target:
- package name `each-harness` if `each` PyPI is unavailable;
- console script `each`;
- Python >=3.12.

Check package namespace availability before publishing.

GitHub repository remains EACH regardless of PyPI package name.

---

# 114. Name collision check

Before publishing to PyPI/homebrew:
- search `each`;
- choose unambiguous package.

Possibilities:
- `each-harness`
- `evidence-audited-cleanroom-harness`

Do not rename GitHub project casually.

---

# 115. GitHub description

Suggested:

> Open, local, reproducible authoring-provenance harness for AI-assisted software repair. Evidence, not certification.

Topics:
- ai
- coding-agents
- provenance
- software-supply-chain
- reproducibility
- code-generation
- program-repair
- clean-room
- in-toto
- local-llm

Do not overstuff.

---

# 116. Model artifacts and Git LFS

Do not store model weights in EACH repo or LFS.

Only manifests.

---

# 117. Benchmark solution confidentiality

Historical human fixes are public upstream, but hidden from Builder.

Benchmark harness may know:
- fix commit SHA.

Do not include fix diff in builder packet.

Audit may compare after generation, but this is **evaluation**, not feedback.

---

# 118. Human-fix similarity metric

For benchmarks, after run:
- compare generated patch with historical fix;
- record semantic/test equivalence and textual similarity.

This is not provenance scanning.

It is repair evaluation.

Keep separate.

---

# 119. Architrave acceptance discipline

For every milestone:
- define acceptance matrix;
- run deterministic checks;
- avoid huge architecture PRs;
- keep product demonstrable.

Use Architrave’s delivery-first behavior.

---

# 120. Suggested initial Architrave prompt after adoption

After this handoff is supplied, the user should be able to tell Architrave:

> Execute Phase M0 and M1 from the EACH bootstrap mandate. Preserve the documented information-flow and claims boundaries. Build only the deterministic fixture-model vertical slice, including a real no-network container test and a human-readable receipt. Do not add local LLM support yet. Run all acceptance checks and stop with an evidence summary.

Architrave should not try to implement the entire document in one pass.

---

# 121. Authoritative milestone execution protocol

The milestone map below is authoritative. If any earlier prose appears to conflict with it, this section wins.

The intended progression is:

```text
M0 — Repository/bootstrap health
M1 — Deterministic end-to-end fixture loop
M2 — Real local model integration and bake-off
M3 — GitHub issue intake + immutable spec workflow
M4 — Provenance audit MVP
M5 — Attestation + tamper verification
M6 — Historical benchmark suite
M7 — Clean-room-style controlled demonstration
M8 — Xodus shadow demonstration
```

Each milestone must be completed, verified, and summarized before the next milestone begins unless the user explicitly authorizes combining adjacent milestones.

---

# 122. M0 — Repository/bootstrap health

Goal:

> A fresh clone of EACH on the M5 Max can bootstrap, run tests, report its environment, and be operated through Architrave without any provenance experiment yet.

Required work:

- verify repository remote/name/visibility;
- install/adopt Architrave knowledge profile;
- establish Apache-2.0 unless the repository already has another intentional license;
- create Python 3.12 + `uv` project;
- create CLI skeleton;
- add `each doctor`;
- add README claims/nonclaims;
- add initial threat-model document;
- add CI for ordinary harness tests;
- add `.gitignore` entries for local runs, models, keys, and shadow artifacts.

Acceptance:

```bash
uv sync
uv run pytest
uv run each doctor
```

must pass or `doctor` must explicitly classify optional missing components.

Do not:
- download coding models;
- implement GitHub issue automation;
- implement Xodus;
- create a daemon/UI/database.

Deliverable:
- M0 evidence summary;
- exact repo SHA;
- environment receipt;
- next M1 plan.

---

# 123. M1 — Deterministic end-to-end fixture loop

Goal:

> Prove the EACH architecture without an LLM.

Build the smallest vertical slice:

```text
local fixture issue
→ immutable approved spec
→ sanitized target worktree
→ deterministic FixtureModel
→ candidate unified diff
→ constrained executor
→ compile/test
→ audit stub
→ receipt
```

Required fixture:

```text
examples/hello-repair/
```

with:
- a trivial bug;
- deterministic failing test before repair;
- deterministic passing test after repair;
- FixtureModel that returns the known repair patch.

Executor requirements:
- strong container/no-egress profile;
- no host home mount;
- scrubbed environment;
- no SSH agent;
- explicit worktree mount;
- negative test proving outbound network access fails.

Adversarial tests:
- scope/path traversal;
- patch touching forbidden file;
- inherited secret unavailable;
- symlink escape;
- malformed diff;
- spec hash mismatch.

Acceptance:

```bash
uv run each demo hello-repair
```

must:
- return success;
- produce JSON and Markdown receipt;
- include material hashes;
- prove tests failed before and passed after patch;
- record no-network evidence.

Stop after M1 and report before M2 unless explicitly authorized to continue.

---

# 124. M2 — Real local model integration and bake-off

Goal:

> Replace FixtureModel with a real local model while preserving the same observable, auditable pipeline.

Implement:
- model adapter interface;
- model manifest schema;
- exact weight/config/tokenizer hashing;
- complete request/response trajectory recording;
- bounded generation attempts;
- no tool calling required;
- unified-diff output contract.

Evaluate at least the viable candidates among:

1. StarCoderBase 15.5B — provenance baseline;
2. OctoCoder — patch/instruction-oriented candidate;
3. IBM Granite Code — practical capability candidate.

Do not assume any of them works with MLX. Test actual runtime support.

Evaluate viable runtimes:
- Transformers/PyTorch MPS;
- MLX/MLX-LM when supported;
- llama.cpp/GGUF only when conversion is supportable and recorded.

For every converted/quantized artifact, record the conversion chain and treat it as a distinct model artifact.

Bake-off requirements:
- same fixture/task set;
- same max attempts;
- same validation;
- same context policy;
- record throughput, peak memory if easy, attempts, tokens, pass/fail;
- separately record provenance capabilities.

Select the initial Builder based on **repair utility + provenance observability**, not raw intelligence alone.

Acceptance:
- at least one real local model completes a recorded generation attempt;
- no cloud inference involved;
- model artifact identity is bound into receipt;
- full trajectory is inspectable;
- the deterministic FixtureModel remains available for CI.

Do not start GitHub issue automation until M2 is verified.

---

# 125. M3 — GitHub issue intake and immutable spec workflow

Goal:

> Import a real public issue while proving that issue text/Scout output is not automatically equivalent to Builder input.

Implement:

```bash
each issue import <github-url>
each issue show <task>
each spec build <task>
each spec approve <task> --human
```

Requirements:
- cache issue metadata/body with URL, retrieval timestamp, and hash;
- preserve source classification;
- issue text is untrusted;
- Scout output is metadata only;
- spec packet is distinct from intake;
- approved spec becomes immutable/hash-bound;
- modifications require a new spec version/hash.

Spec origin classifications must support at least:

```text
PUBLIC_API_DOC
PUBLIC_HEADER
PUBLIC_OPEN_SOURCE
PUBLIC_ISSUE
BLACK_BOX_OBSERVATION
USER_ASSERTION
MODEL_INFERENCE
UNKNOWN
RESTRICTED
```

Sensitive policy must be able to reject `MODEL_INFERENCE`, `UNKNOWN`, and `RESTRICTED`.

Use a small permissively licensed repository/issue for the first live demonstration.

Acceptance:
- imported issue can be converted into a human-approved spec;
- Builder receives only declared spec/materials;
- receipt shows exact materials actually supplied to model;
- poisoned instructions in issue text cannot override policy.

---

# 126. M4 — Provenance audit MVP

Goal:

> Provide useful post-generation source-attribution evidence without pretending it proves originality.

Implement at least:
- exact/substring matching;
- normalized token/n-gram similarity;
- one Tree-sitter AST-normalized comparator;
- mature license scanner integration if practical;
- pluggable training-corpus membership adapter.

States:

```text
PASS
FLAG
FAIL
UNAVAILABLE
```

Do not collapse checks into one “cleanliness score.”

Create adversarial audit fixtures:
- exact permissive copied snippet;
- renamed copy;
- common boilerplate;
- independently written semantic equivalent;
- known corpus match when available.

**Terminal boundary requirement:**

Auditor results must never feed matching source or implementation details back into Builder.

If audit flags a source match:
- reject/flag candidate;
- archive evidence;
- any retry begins again from the original approved spec.

Acceptance:
- injected copy is detected;
- no auditor→builder content leakage occurs;
- audit tool versions/config/corpus revisions are recorded;
- unavailable checks remain explicitly `UNAVAILABLE`.

---

# 127. M5 — Attestation and tamper verification

Goal:

> Make an EACH run cryptographically bound and independently verifiable.

Implement:
- artifact hash manifest;
- `each verify`;
- deterministic receipt verification;
- local signing-key management outside repository;
- in-toto/DSSE integration if mature enough without bloating v0.1 architecture.

Attest stages:
1. intake;
2. spec approval;
3. materialization;
4. generation;
5. validation;
6. audit;
7. publication when relevant.

Never commit private signing keys.

Required tamper tests:
- modify patch after receipt → verification fails;
- modify spec after approval → verification fails;
- modify validation output → verification fails;
- remove declared material → verification fails.

Acceptance:
- a third party with the receipt/public key can verify artifact integrity;
- receipt still explicitly states that integrity/provenance evidence is not legal clean-room certification.

---

# 128. M6 — Historical benchmark suite

Goal:

> Determine whether EACH is actually useful, not merely elegant.

Build:
- 5-task smoke suite first;
- then at least 20 historical issues for meaningful v0.x evidence;
- target ~50 later.

Task requirements:
- permissively licensed repositories;
- known historical fix;
- checkout parent/pre-fix revision;
- known fix hidden from Builder;
- deterministic tests;
- provision dependencies before sealed run where possible;
- mix of C/C++/Rust/Python.

Metrics:

Repair:
- compile success;
- acceptance pass;
- regression pass;
- patch size;
- attempts;
- wall time;
- tokens.

Provenance:
- receipt completeness;
- undeclared access attempts;
- audit coverage;
- flags;
- assurance ceiling.

Isolation:
- internet access attempt;
- host-home access;
- Git remote access;
- hidden-fix access;
- credential access.

Compare model candidates under identical task packets.

Publish a sanitized benchmark report.

Do not publish a leaderboard-style claim from a tiny sample.

Acceptance:
- at least 20 reproducible tasks;
- rerunnable benchmark command;
- documented failures as well as successes;
- no known solution exposed before generation.

---

# 129. M7 — Clean-room-style controlled demonstration

Goal:

> Exercise the information-flow design on a compatibility-style task without claiming legal clean-room status.

Choose a bounded API compatibility problem with:
- public interface/signature;
- public documentation;
- independently recorded black-box observable behavior if needed;
- no proprietary implementation source;
- deterministic local tests.

Build:
- observation packet;
- human-approved immutable spec;
- sealed local-model generation;
- validation;
- audit;
- attestation;
- shadow-only publication policy.

The user must be able to see:

```text
what was publicly known
what was observed
what Builder received
what model produced
what tests proved
what Auditor found
what remains uncertain
```

Explicitly state:

```text
Legal clean-room certification: NO
Upstream acceptability: destination-project decision
```

Acceptance:
- complete receipt;
- information firewall demonstrably enforced;
- candidate remains shadow-only unless user explicitly publishes AI lineage.

---

# 130. M8 — Xodus shadow demonstration

Goal:

> Use EACH on one real Xodus/xgameruntime compatibility issue as a research demonstration, without implying the result is acceptable upstream.

Before starting:
- re-fetch current Xodus policies;
- read current `xodus-gaming/.github` contribution policy;
- read current `xgameruntime` clean-room documentation;
- check active issue/PR overlap;
- pin target SHAs.

Create:

```text
policies/xodus-shadow.yml
```

Minimum policy:
- AI-generated implementation promotable upstream: `false`;
- patch publication: `private` by default;
- external AI review of candidate source: forbidden in strict run;
- allowed evidence origins tightly constrained;
- audit terminal;
- no decompilation/proprietary implementation source;
- no forbidden reverse-engineering methods;
- black-box observation packet required when public docs are insufficient.

Candidate examples may come from actual macOS/Xodus work, but select one bounded function/API—not an entire runtime subsystem.

The output is:

```text
SHADOW PATCH
+
validation evidence
+
audit evidence
+
receipt
```

not an upstream PR.

If the experiment proves a spec is sufficient to solve a blocker, that is useful evidence even when the code itself cannot be contributed.

Acceptance:
- one real compatibility issue processed end-to-end;
- Xodus source/issue/version pinned;
- all information origins classified;
- no claim that Xodus should accept generated code;
- user can choose whether to keep the patch private.

---

# 131. Milestone continuation rule

After each milestone Architrave must produce:

```text
Milestone:
Target SHA:
Acceptance criteria:
PASS/FAIL per criterion:
Files changed:
Commands executed:
Artifacts:
Threat-model findings:
Known limitations:
Deferred work:
Next milestone plan:
```

If acceptance is not met:
- do not silently continue;
- either repair within the milestone or stop with evidence.

# 128. Xodus/Grounding source shortlist

When demonstration phase begins, re-read current:

- https://github.com/xodus-gaming/xodus
- https://github.com/xodus-gaming/xgameruntime
- https://github.com/xodus-gaming/.github/blob/main/CONTRIBUTING.md
- https://github.com/xodus-gaming/xgameruntime-docs
- https://github.com/xodus-gaming/wine

Policies may change.

Pin retrieval date and SHA where possible.

---

# 129. Mac-specific target after EACH is stable

The user’s broader engineering goal is to make Xodus useful on macOS.

EACH is not responsible for solving that architecture.

But EACH may become the shadow implementation lab for individual compatibility issues discovered there.

Keep concerns separate.

---

# 130. Data retention

Default:
- keep run receipts indefinitely;
- keep raw model trajectories;
- keep candidate patches private;
- configurable cleanup for build trees.

Provide:

```bash
each run prune --older-than 30d --build-artifacts
```

later.

Do not delete evidence by default.

---

# 131. Privacy

Issue text and public code are generally public.

But user may use EACH on private repos later.

Receipts must support:
- redacted paths;
- no source snippets;
- hash-only materials.

Do not make public telemetry.

No analytics by default.

---

# 132. Telemetry

Default: none.

If project later collects opt-in metrics:
- no source;
- no prompts;
- no patch;
- explicit consent.

---

# 133. Reproducibility bundle

Eventually:

```bash
each bundle RUN
```

creates:

```text
run.tar.zst
```

containing:
- specs;
- manifests;
- trajectory;
- patch;
- results;
- audit;
- receipt;

subject to publication policy.

No model weights.

---

# 134. Verification command

Eventually:

```bash
each verify receipt.json
```

checks:
- hashes;
- signatures;
- schema;
- artifact existence.

Does not rerun model.

---

# 135. Replay command

Later:

```bash
each replay RUN
```

recreates:
- sanitized worktree;
- validation;
- audit;

and optionally regeneration if model artifact available.

Distinguish:
- validation replay;
- generation replay.

---

# 136. Documentation examples

Keep examples real and small.

Avoid Xodus in landing-page quickstart.

Use toy/permissive repair.

Xodus can be advanced case study.

---

# 137. Public roadmap

Suggested:

```text
v0.1 — deterministic end-to-end receipt
v0.2 — local model + model manifests
v0.3 — issue intake + benchmark
v0.4 — provenance auditors + in-toto
v0.5 — macOS/Tart isolation
v0.6 — compatibility shadow case study
```

Do not bind dates until velocity known.

---

# 138. Definition of success for the first public release

Someone else can:

1. clone EACH;
2. run setup;
3. run a local fixture;
4. see a test-passing generated patch;
5. inspect every builder input;
6. inspect every model interaction;
7. verify patch/test hashes;
8. inspect audit results;
9. understand what EACH proves and what it does not.

That is enough.

---

# 139. Definition of failure

The project is failing if:
- it becomes a generic agent framework;
- receipts omit actual context;
- no-egress is only prompt-based;
- audit results are fed back into generation;
- hidden cloud calls occur;
- claims become legal-sounding;
- provenance is summarized as one opaque score;
- setup requires a distributed system;
- Xodus dominates before baseline works.

---

# 140. Required adversarial review before release

Ask Architrave’s Adversarial Judge:

- Can any undeclared information reach Builder?
- Can Builder access GitHub?
- Can target repo prompt-inject command policy?
- Can a malicious symlink escape worktree?
- Can secrets leak through inherited environment?
- Can audit source leak into retry?
- Can receipt be forged by editing JSON?
- Does assurance engine overclaim when check unavailable?
- Does README imply certification?
- Are generated patches accidentally published?

Fix serious findings.

---

# 141. User workflow on this Mac

Daily use should be simple.

```bash
cd ~/src/EACH
copilot
```

Select Architrave when modifying EACH.

For EACH itself:

```bash
uv run each doctor
uv run each issue sync
uv run each run TASK
```

Long model jobs:
- use `caffeinate`;
- write run state;
- no dependence on terminal staying foreground.

---

# 142. Optional Windows control later

The user may return to a Windows daily-driver pattern.

Do not hard-code Mac-only control plane.

Core CLI must work cross-platform where possible.

Mac-specific:
- model runtime;
- Tart;
- Xcode targets.

Remote:
- SSH.

---

# 143. Build/test commands for Architrave

Once dependencies are present, configure:

```bash
uv run pytest
uv run ruff check .
uv run pyright each
uv run each demo hello-repair
```

Add security/adversarial suite:

```bash
uv run pytest tests/adversarial
```

No full local model run in every gate.

Use explicit benchmark gate.

---

# 144. Documentation source discipline

When README makes claims about prior art/model provenance:
- cite canonical source;
- date access where claim can change.

Do not cite this handoff.

This handoff is a plan, not evidence.

---

# 145. Model cards are claims

Represent model-author statements as:

```text
vendor_claim
```

not independent fact if unverified.

For example:
- IBM says license-permissible;
- BigCode documents The Stack v1.2.

EACH can faithfully record those claims.

---

# 146. Legal review boundary

EACH should include:

> Nothing in EACH is legal advice. Software licenses, copyright, clean-room rules, DCO obligations, and project policies remain the responsibility of the user and destination project.

Do not write pseudo-legal verdict engines.

---

# 147. Clean-room terminology caution

The project name includes “Cleanroom” because the motivating workflow involves information-flow separation.

README should define:

> In EACH, “cleanroom” describes an engineering isolation pattern. It does not assert that a particular run meets a legal clean-room standard.

Prominent.

---

# 148. Research opportunity

If EACH becomes stable, potential paper/research questions:

- measurable authoring provenance;
- training-corpus overlap and repair quality;
- effect of constrained context on repair success;
- open vs opaque model provenance;
- deterministic spec generation;
- audit false-positive/false-negative rates.

Do not let research goals delay usable tooling.

---

# 149. Potential community

Likely interested:
- Wine/compatibility developers;
- emulators;
- protocol reimplementers;
- regulated enterprises;
- defense/government environments;
- OSS maintainers with DCO;
- software-supply-chain researchers;
- local/air-gapped AI users.

But validate through actual users.

---

# 150. Mandatory final instruction to Architrave

Do not execute this entire mandate as one giant change.

Use Architrave’s normal durable Run process.

Start with:

> **M0 + M1 only.**

Before implementation:
1. inspect current EACH repository;
2. verify remote/visibility/license;
3. inspect canonical Architrave instructions;
4. create concise acceptance matrix;
5. identify existing tools rather than reinventing.

Then build the smallest end-to-end deterministic vertical slice.

After M1 passes, stop and report:

- exact files;
- commands;
- evidence;
- threat-model gaps;
- next recommended slice.

Do not begin model downloads until M1 is proven.

---

# 151. First prompt to paste into Architrave

Use this after saving this document in the repository, for example as:

```text
docs/EACH_BOOTSTRAP_MANDATE.md
```

Prompt:

> Read `docs/EACH_BOOTSTRAP_MANDATE.md` completely and treat it as the zero-context product/architecture mandate for this repository.
>
> Execute **only milestones M0 and M1**.
>
> Preserve the core thesis: EACH generates authoring-provenance evidence, not legal/clean-room certification.
>
> Use the repository’s Architrave knowledge profile, YAGNI, durable Run state, deterministic verification, and adversarial review.
>
> Before coding, inspect the current repository, verify its Git remote and existing files, and produce the smallest acceptance matrix that demonstrates:
>
> `local fixture issue -> approved spec -> FixtureModel -> constrained patch -> verified no-network executor -> deterministic tests -> audit stub -> human-readable receipt`
>
> Do not add a real local LLM yet.
> Do not add a daemon, UI, database server, hosted service, RAG, or cloud backend.
> Do not start Xodus integration.
>
> The executor must include a real negative test proving the strong profile cannot make an outbound network connection.
>
> Record every material hash needed for the receipt.
>
> Add adversarial tests for scope/path escape and inherited secrets.
>
> Stop when M0/M1 acceptance passes and give me:
> - architecture actually built;
> - exact verification results;
> - known gaps against this mandate;
> - next smallest M2 plan.
>
> Do not declare the full project complete.

---

# 152. Sources to consult during implementation

These are starting points, not frozen truth.

## Architrave
https://github.com/dragoshont/architrave

## mini-SWE-agent
https://github.com/SWE-agent/mini-swe-agent
https://github.com/SWE-agent/mini-swe-agent/blob/main/docs/models/local_models.md

## SWE-agent
https://github.com/SWE-agent/SWE-agent

## Agentless
https://github.com/OpenAutoCoder/Agentless

## StarCoderBase
https://huggingface.co/bigcode/starcoderbase

## Granite Code
https://github.com/ibm-granite/granite-code-models

## MLX-LM
https://github.com/ml-explore/mlx-lm

## Tart
https://github.com/openai/tart

## in-toto
https://github.com/in-toto/in-toto

## SLSA
https://slsa.dev/

## Xodus — future demonstration
https://github.com/xodus-gaming/xodus
https://github.com/xodus-gaming/xgameruntime
https://github.com/xodus-gaming/.github

---

# 153. Final north-star

The project should make it possible to answer, with inspectable evidence:

> **What exactly did the coding model know, what exactly did it do, and why should I believe this patch came from this controlled process?**

Not:

> “Trust us, the model probably didn’t copy anything.”

And not:

> “The auditor found no match, therefore it is clean.”

The value of EACH is disciplined uncertainty.

A strong EACH receipt should make uncertainty visible instead of hiding it.

That is the product.

---

# End of mandate
