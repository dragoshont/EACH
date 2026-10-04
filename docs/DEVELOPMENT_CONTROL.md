# Autonomous EACH development

## User-directed scope

The user authorized all milestones M0-M8 and requested Architrave on the Mac,
with development driven over SSH from the Windows Copilot app. Milestones stay
sequential and acceptance-gated; completing one is not permission to omit the
next milestone's prerequisites.

Repository: <https://github.com/dragoshont/EACH>.
Exercised development host: private Apple Silicon Mac with 128 GiB unified
memory; hostnames, SSH aliases and local checkout paths are intentionally not
published. Architrave source: canonical
<https://github.com/dragoshont/architrave>.

## First acceptance matrix

| Milestone | Criterion | Required evidence |
|---|---|---|
| M0 | Correct public repository and no conflicting license | GitHub metadata and recorded remote |
| M0 | Architrave knowledge profile | Canonical installation, adopted config, durable Run |
| M0 | Python 3.12 and uv project | Locked dependencies; successful `uv sync` |
| M0 | Usable foundation | `uv run pytest`; `uv run each doctor`; README, threat model, ordinary CI |
| M1 | Immutable approved fixture spec | Canonical spec hash; mismatch rejection |
| M1 | Sanitized, declared materials | Exact source/test/material identities; no Git history |
| M1 | Deterministic repair | Failing baseline; FixtureModel diff; passing repaired tests |
| M1 | Constrained patch application | Malformed diff, forbidden path, traversal, and symlink rejection |
| M1 | Strong executor | Real container with no network, scrubbed environment, no home or SSH-agent mount |
| M1 | Adversarial isolation evidence | Outbound connection fails; inherited secret is absent |
| M1 | Honest receipt | Private JSON and Markdown; material/trajectory/test hashes; unavailable audit checks explicit |

## Continuation

The [dual-lane launch addendum](EACH_DUAL_LANE_ADDENDUM.md) now makes model
qualification finite. Verify the retained exact StarCoderBase artifact and use
it as initial Builder if authorized; finish the defined OctoCoder work and
record other candidate blockers without delaying launch. Do not repeat passed
milestones or require a successful repair as proof of model provenance.
The exact-artifact [registry](model-qualifications/registry.json) keeps lineage,
runtime, rights evidence and capability outcomes separate.

Use `docs/EACH_MILESTONE_PROMPTS.md` for the milestone-specific work, with the
user-authorized continuation to the next milestone only after the current gate
passes. Do not download coding models before M1 passes.

For every milestone record target SHA, criteria and individual results, files,
commands, private artifact paths, threat-model changes, limitations, and the next
smallest slice. Preserve this evidence in Architrave's ignored durable Run store
and the user's private EACH run store; public summaries must be sanitized.

Sensitive M7/M8 specs still need actual human approval. If the user is
unavailable, prepare the review packet and mark that gate blocked rather than
inventing approval. Do not accept model access terms, expose shadow candidate
source to cloud review, or submit an upstream PR.
