# First production-development support contract

This is a measured **development envelope**, not production qualification,
human adoption approval, or a release go/no-go. The research release and its
receipts remain historical.

**Correction, 2026-10-03: P1 API-return acceptance is BLOCKED.** Actual
independent adversarial/security review returned REVISE. The observer below
measures sandboxed process responses, not authenticated Python API returns.
No narrower production outcome has been approved; the original repair goal
remains unmet. The exhausted development command now exits BLOCKED before
model loading or generation.

## Observed row (2026-10-03)

**Historical capability comparison only.** The user subsequently reaffirmed
clear training-data provenance as a mandatory model eligibility rule.
Qwen's artifact identity does not establish that lineage; this row is not a
qualified production Builder. No current catalog entry is approved, and new
catalog loading fails closed. Preserve these measurements and negative receipts,
but do not count them as evaluation of provenance-qualified models.

| Surface | Observation |
|---|---|
| Host | Apple Silicon arm64, macOS 27.0.1, 128 GiB unified RAM |
| Tools | Python 3.12.14, uv 0.12.21, mlx-lm 0.32.0 |
| Builder | Existing `qwen2.5-coder-14b-instruct-mlx`, original publisher bf16 weights; no download/conversion |
| Snapshot | `aedcc2d42b622764e023cf882b6652e646b95671`, folded identity `630c0b55faf71a55` |
| Config / tokenizer SHA-256 | `9051fe83840dcd3a0f7e9f5b3372fc3927419eb56983273eac2dc635a5da7eae` / `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539` |
| Manifest / cold load | 18.42 s hashing, 10.16 s loading |
| Separate calibration | Arithmetic-only generation: 0.50 s, two response characters; not repair utility |
| Measured memory | 30,105,452,544 bytes peak RSS; 29,613,533,436 bytes MLX peak |
| Disk | 1,042,471,239,680 bytes free at calibration |
| Executor | Dedicated `colima-each`, existing pinned benchmark image `each-benchmark-runtime@sha256:6150f4259b1dc7590817dd7d31021c2f56de367463a970d8ab04e1e9d371e4dc` |

Exact individual weight/file hashes are retained locally in the support
contract and model manifest. A snapshot name alone is not artifact verification.
Unknown machines and other model snapshots remain unmeasured/unsupported.

## Bounded development limits

- Standalone Python functions using JSON arguments/results, standard-library
  imports only, no persistent state, side-effectful APIs, third-party dependency
  provisioning, or package/native test runners.
- Source at most 8,192 UTF-8 bytes; input plus reserved output at most 8,192
  tokens; output at most 2,048 tokens.
- Full-source proposals are converted through the existing strict parser and
  deterministic diff helper, then existing scoped patch/preimage checks.
- Three eligible tasks maximum, three local-model attempts per task maximum.
  Stop on the first useful candidate; no new weight acquisition or endless tuning.
- 300 seconds per generation; 15 seconds per observed case; 1,200-second
  reported task ceiling; 64 GiB MLX memory allocation limit; 20 GiB disk reserve.
  The task ceiling is checked/reported, not an OS-wide hard watchdog.
- The calibration proves loading, not worst-case throughput. These deliberately
  conservative engineering caps allow roughly 600 times the short calibration
  duration for generation and more than twice the observed MLX allocation.
  Overruns are failures to qualify, not hidden successful runs.

## Sandboxed process-response observation — not API-return authentication

The host observer keeps expected outputs, response accounting and comparison
outside the candidate container. Each case launches a fresh, no-egress container
with the **entire target worktree read-only**. Only a function invocation and its
input enter it. No hidden expected answers, test sources or observer comparison
logic are mounted. Candidate import and the worker serializer nevertheless share
one Python interpreter. Candidate code can print matching JSON and exit before
the requested function returns, or monkeypatch serialization to substitute a
response. The host checks JSON values/types and process-response shape, **not**
actual function execution or return authenticity.

The signed observation records include case IDs/status, expected/complete-response counts,
observer/worker/contract hashes, and the source hash captured before execution.
Empty, malformed or deeply nested unparseable JSON, forged pytest text, and
unexpected/skipped process outputs are incomplete. **Valid matching JSON with
exit zero can match the process-response observation even on early exit or
result substitution.** Fresh/read-only containers do not authenticate API return.
Actual executor and benchmark regressions demonstrate both attacks.

Matching response-only observations now end the observation benchmark as
`REPAIRED_RUN_INCONCLUSIVE`, never `REPAIR_VERIFIED`, with
`apiReturnAuthenticated: false`. No token, captured serializer reference or
sentinel proxy is presented as a stronger boundary. Candidate-JSON
`RecursionError` is handled narrowly as incomplete; signed negative receipts
retain the deterministic fixture trajectory/patch and declared inputs.

These controls do not satisfy the original unrestricted-Python API contract,
make native validators independent, prove correctness or establish TEE
protection. A genuine stronger boundary or explicitly authorized changed
qualified contract is necessary before P1 acceptance; neither exists here.
Signatures establish integrity, not correctness or human consent.

## Task custody and claims

The first eligible development task is the public MIT-licensed humanize
negative-file-size historical repair. Its original source and `LICENCE` are
pinned at the pre-fix revision; the historical implementation/fix tests are
never Builder input. Only the public behavioral contract and original source
are supplied. Full source, prompt, completion and target patch stay private.
Engineering spec approval is labelled accurately, not as a human spec ceremony.

All humanize fixes/variants belong to the development cluster and must be
excluded from future qualification holdouts. Arithmetic calibration and harness
spoof fixtures are separate from repair development and all holdouts. No holdout
has been selected or consumed. Freeze sampling frame, exclusions, clusters,
identifiers and answer/test custody before future holdout execution.

The ledger's 10/30 utility, 90%/5% audit and 30-run/three-workflow/seven-day pilot
defaults are retained as engineering qualification targets **before** holdout
use; there is no measured-result-based lowering or fabricated human consent.
Human production go/no-go remains a later dependency.

Optional audit comparisons with no corpus remain UNAVAILABLE. A validated
repair is not an audit-qualified repair, EACH-P3, originality proof, upstream
approval, or legal certification. Independent/security/policy review of the
frozen implementation remains required before production acceptance.

## Reproduce the development packet

After normal README setup, only on the measured Mac with the already-installed
snapshot and dedicated executor:

```bash
uv run python -m each.production_development
uv run python -m each.production_development --task one-byte-float
uv run python -m each.production_development --task yotta-rollover
```

These are historical command references. They now return exit **2**, a bounded
`BLOCKED`/`API_RETURN_AUTHENTICATION_UNAVAILABLE` response, and zero model calls.
The former generation path is not exposed. Existing private signed receipts,
retained inputs and summaries remain unchanged; do not publish them or targets.

The authorized first exploration has exhausted its three-task/nine-call cap;
these commands are reproducibility references, **not** permission to keep
sampling this lane. There were zero verified repairs. All three negative signed
receipts and all declared retained inputs verify. The one-byte packet produced
unchanged original source; the rollover candidates failed meaningful regression
cases when the recorded response was decoded and observed without new inference.
Literal Markdown in Python docstrings is preserved by the corrected decoder;
ambiguous separate presentation blocks remain rejected.
