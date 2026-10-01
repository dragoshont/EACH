# EACH — Ready-to-Paste Architrave Milestone Prompts
## M0 through M8

Use these sequentially. Each prompt assumes `docs/EACH_BOOTSTRAP_MANDATE.md` contains the corrected v2 comprehensive handoff.

---

# M0 + M1 — Bootstrap and deterministic vertical slice

Read `docs/EACH_BOOTSTRAP_MANDATE.md` completely and treat it as the zero-context product/architecture mandate for this repository.

Execute **only M0 and M1**.

Preserve the core thesis: EACH produces authoring-provenance evidence, not legal or clean-room certification.

Use Architrave's knowledge profile, YAGNI, durable Run state, deterministic verification, and adversarial review.

Before coding:
1. inspect the repository and remote;
2. verify repository visibility/license/current contents;
3. verify the Mac development environment;
4. adopt/install Architrave if needed;
5. create the smallest acceptance matrix for M0/M1.

The required M1 vertical slice is:

`local fixture issue -> approved immutable spec -> FixtureModel -> constrained unified diff -> verified no-network executor -> deterministic failing/passing tests -> audit stub -> JSON + Markdown receipt`

Mandatory adversarial evidence:
- outbound networking fails inside the strong executor;
- inherited secrets are absent;
- patch/path escape is rejected;
- symlink escape is rejected;
- spec hash mismatch is rejected.

Do not:
- download a real coding model;
- add GitHub automation;
- add Xodus;
- add a daemon, UI, database, RAG, cloud backend, or custom cryptography.

Stop after M0/M1 PASS and report exact evidence plus the smallest M2 plan.

---

# M2 — Local model integration and bake-off

Read the mandate and the completed M0/M1 Run evidence first.

Execute **only M2**.

Add real local-model support without weakening the proven deterministic pipeline.

Requirements:
- model adapter boundary;
- exact model manifest;
- weights/config/tokenizer hashes;
- runtime/version/quantization/conversion-chain recording;
- complete prompt/response trajectory;
- bounded attempts;
- unified-diff output;
- no native model tool-calling requirement.

Evaluate the viable options among:
- StarCoderBase 15.5B;
- OctoCoder;
- IBM Granite Code.

Evaluate actual Apple Silicon backends instead of assuming support:
- Transformers/PyTorch MPS;
- MLX/MLX-LM where supported;
- llama.cpp/GGUF only with recorded conversion provenance.

Use identical fixtures and policy for comparison.

Select an initial Builder using both:
1. repair usefulness;
2. provenance observability.

Do not start GitHub issue intake yet.

Acceptance:
- at least one local model makes a real recorded patch attempt;
- zero cloud inference;
- exact model artifact identity appears in receipt;
- trajectory is complete;
- FixtureModel remains CI-safe.

Stop and report the bake-off evidence.

---

# M3 — GitHub issue intake and spec gate

Read the mandate plus M0–M2 evidence.

Execute **only M3**.

Implement:
- `each issue import <url>`;
- intake hashing/caching;
- origin classification;
- immutable spec construction;
- explicit human spec approval.

Key invariant:

**GitHub issue text and Scout output are not Builder inputs merely because they exist.**

Sensitive specs must be able to reject:
- MODEL_INFERENCE;
- UNKNOWN;
- RESTRICTED.

Use one small permissively licensed real issue for the demonstration.

Add prompt-injection tests showing that issue/repository text cannot change command or information policy.

Do not add provenance auditors beyond existing stubs unless required for M3.

Stop after demonstrating:
`public issue -> intake -> approved spec -> declared Builder material set`.

---

# M4 — Provenance audit MVP

Read the mandate and prior milestone receipts.

Execute **only M4**.

Implement post-generation audit:
- exact/substring;
- normalized n-grams;
- one Tree-sitter AST similarity path;
- mature license scanner if practical;
- pluggable corpus-membership adapter.

Use PASS / FLAG / FAIL / UNAVAILABLE, not one provenance score.

The Auditor is a **terminal boundary**.

Prove with an adversarial test that a discovered matching source cannot be supplied back to Builder for a rewrite.

Create fixtures for:
- exact copied permissive snippet;
- renamed copy;
- common boilerplate;
- semantic equivalent;
- corpus match if infrastructure is available.

Stop with audit-quality and false-positive/false-negative observations.

---

# M5 — Attestation and tamper verification

Read the mandate and prior receipts.

Execute **only M5**.

Implement integrity/attestation:
- sorted artifact hash manifest;
- `each verify`;
- local signing key outside repo;
- receipt signature;
- in-toto/DSSE integration if it remains YAGNI-compatible.

Add tamper tests:
- patch mutation;
- spec mutation;
- validation mutation;
- missing material.

All must fail verification.

Do not confuse successful signature verification with clean-room proof.

Stop with a third-party-verifiable example receipt and M6 benchmark plan.

---

# M6 — Historical benchmark

Read the mandate and all previous milestone evidence.

Execute **only M6**.

Build:
- first 5-task smoke benchmark;
- then 20-task meaningful benchmark.

Tasks must be historical repairs from permissively licensed projects with known fixes hidden from Builder.

Mix C/C++/Rust/Python where feasible.

Record:
- compile/test success;
- attempts;
- patch size;
- tokens/time;
- audit coverage;
- forbidden access attempts;
- assurance level.

Compare viable model candidates under identical packets.

Do not expose known human solution until generation/audit has completed.

Publish a conservative sanitized report including failures.

Stop after the 20-task evidence report.

---

# M7 — Controlled clean-room-style demonstration

Read the mandate and M0–M6 evidence.

Execute **only M7**.

Select one bounded compatibility/API problem with:
- public interface;
- public documentation;
- deterministic black-box observations if documentation is insufficient;
- no proprietary implementation material.

Create:
- observation packet;
- immutable human-approved spec;
- sealed Builder run;
- validation;
- audit;
- attestation;
- shadow-only result.

The final receipt must make the full information flow understandable.

It must explicitly say:
- legal clean-room certification: NO;
- upstream acceptability: destination project decision.

Do not use Xodus for M7 unless there is a compelling reason. Prefer a simpler demonstration that validates the method.

Stop with a complete research-grade receipt.

---

# M8 — Xodus shadow demonstration

Read the mandate, all prior EACH receipts, and **freshly re-check current Xodus contribution/clean-room policies before doing anything**.

Execute **only M8**.

Select one bounded Xodus/xgameruntime issue.

Do not choose an entire subsystem.

Create and enforce `policies/xodus-shadow.yml` with:
- AI source upstream promotion: false;
- private patch by default;
- strict information-origin policy;
- no proprietary source/decompilation;
- terminal audit;
- no cloud-LLM review of candidate source in strict run.

Pin:
- Xodus/xgameruntime source SHA;
- issue/PR state;
- policy source/date.

Construct the spec only from approved sources and observations.

Run the sealed local Builder.

Validate in the private shadow fork/environment.

Produce:
- shadow patch;
- validation result;
- audit result;
- receipt;
- explicit limitations.

Do **not** open an upstream PR.

Stop and report whether the experiment proved that the behavioral spec was sufficient, regardless of whether the code can be contributed.

---

# Rule for every milestone

After every milestone, return:

- target SHA;
- acceptance matrix;
- PASS/FAIL for every criterion;
- exact files changed;
- exact commands/tests;
- receipts/artifacts;
- threat-model changes;
- known limitations;
- next smallest milestone plan.

Never silently advance after an unmet acceptance criterion.
