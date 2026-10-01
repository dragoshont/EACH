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

**M0** (repository/bootstrap health) and **M1** (deterministic hello-repair
vertical slice) are complete and verified. M2-M8 are in progress under the
user-authorized sequential program.

The user-authorized program is sequential **M0-M8**:
repository health, deterministic fixture repair, local models, issue/spec
intake, terminal provenance auditing, attestation, historical benchmarks,
controlled compatibility demonstration, and finally a private Xodus shadow
demonstration.

Real model downloads wait for the deterministic isolated demo to pass.
Target patches stay private by default, and EACH will not open an upstream
Xodus PR.

## Claims and non-claims

See [docs/claims-and-nonclaims.md](docs/claims-and-nonclaims.md) for the
authoritative statement. In short: EACH can record exactly what a Builder
model was allowed to see, which model produced a patch, how it was tested,
and what post-generation similarity/license checks ran. It does **not**
certify legal clean-room status, originality, or upstream acceptability.

## Quick start

```bash
uv sync
uv run pytest
uv run each doctor
```

`each doctor` reports every check explicitly: required checks (Python
3.12+, git, a writable `~/.each/` private store) must pass; optional checks
(uv itself, a reachable no-network container runtime) are reported as
`WARN` when absent rather than silently skipped or faked as passing.

### Deterministic hello-repair vertical slice (M1)

```bash
uv run each demo hello-repair
```

Runs the full M1 pipeline end to end: an approved, hash-verified immutable
spec for a trivial local fixture bug
(`examples/hello-repair/`) -> a sanitized worktree containing only the
declared in-scope files -> a deterministic, non-inferential `FixtureModel`
-> a scoped unified-diff patch, validated and applied by the harness -> a
real no-network container executor (`docker --context colima-each`, pinned
base-image digest, scrubbed environment) -> a deterministic failing-then-
passing test run -> an explicit `UNAVAILABLE` audit stub (never a
fabricated PASS) -> a private JSON + Markdown receipt under
`~/.each/runs/<run-id>/`.

Adversarial evidence (real outbound-network denial, host-secret
non-inheritance, forbidden/scope/traversal-path rejection, symlink-escape
rejection, malformed-diff rejection, and approved-spec hash-mismatch
rejection) lives in `tests/unit/` and `tests/adversarial/`
(`uv run pytest`); the container-dependent adversarial tests self-skip, not
silently pass, when `docker --context colima-each` is unreachable.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Development mandate

- [Start here](docs/START_HERE_EACH.md)
- [Complete bootstrap mandate](docs/EACH_BOOTSTRAP_MANDATE.md)
- [Milestone-specific prompts](docs/EACH_MILESTONE_PROMPTS.md)
- [User-directed development scope and first acceptance matrix](docs/DEVELOPMENT_CONTROL.md)

The user explicitly authorized continuation beyond the handoff's initial
M0/M1 stopping point. Acceptance criteria, sensitive human-approval gates, and
information-flow boundaries still apply.
