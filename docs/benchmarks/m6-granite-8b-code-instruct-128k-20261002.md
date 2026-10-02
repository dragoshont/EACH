# EACH historical benchmark report: benchmark-suite-20261002T093907Z (primary M6 evidence)

Model: `granite-8b-code-instruct-128k-mlx`, repo
`ibm-granite/granite-8b-code-instruct-128k`, revision
`bed93d8de15bb9bb55cb1da10ae860e2883f4254`, license Apache-2.0, ungated.
These are the **original publisher's own bf16 safetensors**, not a
third-party MLX conversion: `mlx_lm.load()` loads this snapshot directly
(verified: `mlx_lm.utils._get_classes(config)` resolves the declared
`architectures=["LlamaForCausalLM"]`/`model_type="llama"` config to the
generic `mlx_lm.models.llama` implementation; an actual snapshot download,
model load, and test generation were run before this benchmark, not merely
assumed from config inspection). The manifest's `conversionChain` field
honestly records `"none"` rather than reusing the community-conversion-chain
phrasing used for the 3B pilot's `mlx-community` checkpoints. Its
`config.json` declares `max_position_embeddings=128000`, `rope_scaling=null`
-- 62.5x the 3B pilot checkpoint's declared 2048-token budget.

This run used the identical task set, prompt template, diff-blind AST
excerpter, retry policy (max 3 attempts), terminal-audit boundary, and
no-network Colima container executor as the 3B pilot
(`docs/benchmarks/m6-granite-3b-code-instruct-mlx-20261002.md`); only the
model-catalog key changed.

## Honest eligibility result: the context-budget fix is confirmed

All 22/22 historical tasks were generation-eligible under this checkpoint
(vs 4/22 under the 3B checkpoint): every task's excerpted prompt fit within
the declared 128000-token budget (plus the 512-token reserved output) for
all 3 attempts, so every task received 3 genuine `model.complete()` calls
(66 real generation calls total across the suite) rather than being
rejected pre-generation on budget grounds. This confirms the context-budget
defect diagnosed in the 3B pilot was a real, measurable constraint of that
specific checkpoint, not a harness limitation -- the identical excerpting
and policy logic now exercises real repair capability across the whole
catalog once given a checkpoint with adequate context.

## Repair-capability result: 0/22 applicable patches, but genuine attempts

No task produced an applicable patch. Every one of the 66 real generation
calls returned a completion that omitted the required exact `BEGIN_PATCH`/
`END_PATCH` markers (`PATCH_REJECTED: completion missing BEGIN_PATCH/
END_PATCH markers`), even on retries that explicitly told the model its
previous attempt was rejected and to "follow the format exactly." Manual
inspection of the raw completions (private; not reproduced here, per the
no-model-output-in-sanitized-docs policy) shows the model genuinely engaging
with each real bug (correctly identifying the relevant function and
producing a plausible-looking unified-diff body, in several cases targeting
the right lines), but consistently wrapping its diff in a ` ```python `
Markdown code fence with a standard `--- a/...` / `+++ b/...` diff header
instead of the instructed bare `BEGIN_PATCH`/`END_PATCH` markers. This is a
genuine instruction-following limitation of this checkpoint/prompt
combination for this exact output-format contract, not a harness defect:
the harness's patch extraction is intentionally strict (exact markers
required) per the mandate's no-silent-leniency requirement, and loosening
it purely to manufacture a pass would bias the benchmark result rather than
measure real repair utility.

Per the project's explicit acceptance criterion, a 0/22 `REPAIR_VERIFIED`
(here: 0/22 even `PATCH_REJECTED`-surviving) result is valid M6 evidence
when input construction is genuine/diff-blind and real generation attempts
were made wherever the budget allowed -- which this run satisfies for all
22 tasks, not just the 4 the smaller checkpoint could reach.

- Tasks (overall catalog coverage): 22
- Generation-eligible (>=1 real `model.complete()` call): 22 / 22
- Real generation calls across the suite: 66 (22 tasks x up to 3 attempts)
- Verified repairs: 0 / 22
- Applicable patches produced (any attempt): 0 / 22 (all 66 attempts:
  `PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers`)

| Task | Repo | License | Outcome | Attempts | Generation calls | Assurance |
|---|---|---|---|---|---|---|
| requests-netrc-empty-default | psf/requests | Apache-2.0 | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| requests-encoding-header-bare-param | psf/requests | Apache-2.0 | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| click-multi-long-option-name-inference | pallets/click | BSD-3-Clause | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| click-flag-default-map-help-text | pallets/click | BSD-3-Clause | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| itsdangerous-timestamp-signer-future-age | pallets/itsdangerous | BSD-3-Clause | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| tqdm-format-num-negative-leading-zero | tqdm/tqdm | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| markupsafe-split-returns-list | pallets/markupsafe | BSD-3-Clause | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| markupsafe-tuple-interpolation | pallets/markupsafe | BSD-3-Clause | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| cachetools-rrcache-popitem-custom-choice | tkem/cachetools | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| cachetools-tlru-overwrite-expired | tkem/cachetools | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| dateutil-parser-nan-decimal-error | dateutil/dateutil | Apache-2.0 / BSD-3-Clause (dual) | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| tabulate-empty-table-maxheadercolwidths | astanin/python-tabulate | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| attrs-preinit-kwonly-default-syntaxerror | python-attrs/attrs | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| attrs-disable-validators-nested-context | python-attrs/attrs | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| wcwidth-center-padding-off-by-one | jquast/wcwidth | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| packaging-normalized-name-double-hyphen | pypa/packaging | Apache-2.0 / BSD-2-Clause (dual) | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| packaging-direct-url-case-insensitive-scheme | pypa/packaging | Apache-2.0 / BSD-2-Clause (dual) | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| more-itertools-one-only-falsy-custom-exception | more-itertools/more-itertools | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| more-itertools-numeric-range-reversed-empty | more-itertools/more-itertools | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| boltons-bits-length-bound-check | mahmoud/boltons | BSD-3-Clause | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| toolz-interpose-empty-sequence | pytoolz/toolz | BSD-3-Clause | PATCH_REJECTED | 3 | 3 | EACH-P2 |
| pathspec-gitwildmatch-negated-bracket-range | cpburnz/python-pathspec | MIT | PATCH_REJECTED | 3 | 3 | EACH-P2 |

Isolation evidence was recorded for every task: each real container
execution's outbound-network probe returned the numeric Linux
`ENETUNREACH` denial (`errno 101`), not a timeout/refusal ambiguity. Audit
result is honestly `UNAVAILABLE` for all 22 tasks (terminal audit only runs
after a `REPAIR_VERIFIED` candidate, per the M4 terminal-audit-boundary
fix in commit `994413b`; none of these 22 tasks ever reached that state).
A sample of signed receipts (`boltons-bits-length-bound-check`,
`tqdm-format-num-negative-leading-zero`,
`pathspec-gitwildmatch-negated-bracket-range`, and
`requests-netrc-empty-default`) were independently re-verified with
`each verify` against the trusted public key after this report was
produced; all PASS.

No patch text, model prompt/completion content, or known-fix source is
included in this sanitized summary. Full private receipts (one per task,
including every rendered prompt, raw completion, and generation parameter)
remain under `~/.each/runs`.
