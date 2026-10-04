# Public synthetic audit corpus v1

Self-authored harness fixtures, 2026-10-03; covered by EACH's Apache-2.0
LICENSE. No private target content or third-party snippets. Origin is this
directory; identity is the producing Git revision plus SHA-256 of each JSON
manifest, reference snippet, and ordered corpus list.

Each split has four disjoint project clusters: three non-common algorithms and
one common Python idiom. Each supplies exact, whitespace-reformatted, fully
renamed, and independently expressed semantic variants. Ten additional
syntactic/semantic benign units give **26 labelled units per split**. All
variants stay with their cluster. Calibration and holdout share no project/fix
cluster. The common fixture is a correct source match; blindly treating it as
disallowed copying is a separate policy escalation, not a matcher false flag.
Semantic equivalents and unrelated benign units count in the false-flag
denominator. Raw per-check outcomes are retained; no label-dependent override
changes matcher output.

Engineering targets adopted before evaluation: all eight exact/whitespace
units detected, at least 90% of four renamed units, at most 5% false flags on
14 semantic/novel benign units. This tiny synthetic sample is intentionally not
a population estimate, universal corpus, human independence claim, or proof
that a model's training data excludes anything. Existing comparator thresholds
are frozen at their defaults; no holdout-driven tuning is allowed.

The first recorded measurement consumes this synthetic holdout. Later replay
is regression coverage, not a fresh blind evaluation. No repair holdout is
selected or consumed. Corpus-membership via `InMemoryCorpusAdapter` tests only
membership in this declared set. External training-corpus membership and mature
license scanning remain UNAVAILABLE.

Only parse/compare these snippets on the host; do not execute them there.
