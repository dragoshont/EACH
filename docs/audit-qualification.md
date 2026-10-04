# Bounded audit qualification — 2026-10-03

**Not audit-qualified for production.** The public synthetic suite detects
seeded copies, but exceeds the engineering benign false-flag target. External
training-corpus membership and mature license scanning remain UNAVAILABLE.
There is no EACH-P3, originality or legal-certification claim.

## Corpus and custody

[The manifests](../tests/fixtures/audit-qualification/README.md) are self-authored
Apache-2.0 harness fixtures, not imported/private target code. Calibration and
holdout each contain four disjoint project clusters and 26 labelled units:
eight exact/whitespace copies, four renamed copies, four semantic variants,
and ten novel benign units. Related variants stay in their cluster.

Engineering targets were retained before holdout execution: exact recall 100%,
renamed recall at least 90%, benign false flags at most 5%. Existing matching
thresholds were frozen at their defaults after calibration; no holdout tuning
or invented human consent occurred. The synthetic holdout is now consumed.
Reproduction is regression evidence, not a new blind evaluation. No repair
holdout was selected or consumed.

| Split | Exact detected | Renamed detected | Benign/semantic false flags | Missed seeded matches |
|---|---:|---:|---:|---:|
| Calibration | 8/8 | 4/4 | 1/14 (7.14%) | 0 |
| Disjoint holdout | 8/8 | 4/4 | 1/14 (7.14%) | 0 |

The holdout false flag is `hold-first-position-semantic`. Each split also has
three correctly matched common-code variants; the default FAIL-rejection
policy escalates all three. A correct attribution to a common permissive
idiom is not evidence of inappropriate copying. Raw matches and escalation
are reported separately, without using labels to override matcher outputs.
The tiny correlated synthetic set does not establish population recall/error
rates or independent human authorship.

## Tool identities and actual configuration

- EACH audit `v0.1-mvp`; Tree-sitter **0.26.0**; Python grammar **0.25.0**.
- Exact reference minimum length 20; whitespace normalization.
- Token Jaccard: n=3, FLAG=0.5, FAIL=0.8.
- Python AST node-type sequence: FLAG=0.6, FAIL=0.85.
- Calibration corpus revision:
  `4ed6a4c0ad3936113c87897f5ae7b23c3e8a447f241bbc8522ae197d6a4e7ae8`.
- Holdout corpus revision:
  `a49f65daba75c1150d28b8cb23297a92f67bc2612d681b2f0fe89040b8c36fbf`.
- Manifest SHA-256: calibration
  `7aef0d457e264c3e4ce78850a8f8768feb26adce46c54c91a3f987f2ff8e602b`;
  holdout
  `c18ee916685e518edec05201dc07bbe5613ed938783be1449d83be8c587eaa27`.

Per-unit labels, subject hashes and all independent check statuses are retained
in the continuation Run. No reference source or implementation details are
returned to Builder. The in-memory corpus adapter detected four declared exact
members in each split; it is **not** an external training-corpus membership tool.

## Reproduce the public measurements

From the source checkout with the existing optional audit dependencies:

```bash
uv run --extra audit python -m each.audit.qualification \
  tests/fixtures/audit-qualification/calibration.json
uv run --extra audit python -m each.audit.qualification \
  tests/fixtures/audit-qualification/holdout.json
```

These commands print source-free diagnostic JSON. `thresholdsMet: false` is a
failed qualification measurement, even though producing the report succeeds.
They do not run a model, execute snippets, search the Internet, or load private
targets. Do not mistake report generation exit zero for audit qualification.

## Required versus optional checks

`run_audit(..., required_checks=(...))` records missing required checks,
optional unavailable checks, and `qualifiedForDeclaredChecks`.
`reject_on_audit_flag(..., required_checks=(...))` rejects an omitted,
UNAVAILABLE or malformed required result. Unknown required names raise.
Default existing workflows have no newly invented required-check policy;
their unavailable comparisons still impose a visible coverage ceiling.

Optional absence is not a rejection of unrelated work. A required missing
external membership check blocks its dependent acceptance. Availability does
not make a match a licensing decision: callers must retain the declared policy
and human review boundary. Full production policy/semantic/security acceptance
is pending, not supplied by this implementation.

Two actual matcher defects were reproduced before fixing: the empty string was
treated as a substring/member of every nonempty reference. Empty candidate
source now reports UNAVAILABLE. Installed distribution versions replace the
previous unhelpful `unknown` Tree-sitter version strings.
