# EACH

**Evidence-Audited Cleanroom Harness: authoring-provenance evidence, not
certification.**

EACH is an experimental open-source harness for provenance-sensitive software
repair. Its goal is to record exactly what a coding model was allowed to see,
which model produced a candidate patch, how that patch was tested, and which
post-generation source-attribution checks were available.

EACH does **not** certify legal clean-room status, originality, copyright
safety, DCO compliance, or acceptability to an upstream project. "Cleanroom"
describes an engineering information-isolation pattern, not a legal conclusion.
The harness itself may be AI-assisted; target receipts describe target
generation, not the authorship of the harness.

## Current status

Bootstrap documents are preserved and development is starting on an Apple
Silicon Mac over SSH. No milestone has been declared complete yet.

The user-authorized program is sequential **M0-M8**:
repository health, deterministic fixture repair, local models, issue/spec
intake, terminal provenance auditing, attestation, historical benchmarks,
controlled compatibility demonstration, and finally a private Xodus shadow
demonstration.

Real model downloads wait for the deterministic isolated demo to pass.
Target patches stay private by default, and EACH will not open an upstream
Xodus PR.

## Development mandate

- [Start here](docs/START_HERE_EACH.md)
- [Complete bootstrap mandate](docs/EACH_BOOTSTRAP_MANDATE.md)
- [Milestone-specific prompts](docs/EACH_MILESTONE_PROMPTS.md)
- [User-directed development scope and first acceptance matrix](docs/DEVELOPMENT_CONTROL.md)

The user explicitly authorized continuation beyond the handoff's initial
M0/M1 stopping point. Acceptance criteria, sensitive human-approval gates, and
information-flow boundaries still apply.
