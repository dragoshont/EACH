# EACH historical benchmark report: benchmark-suite-20261002T102321Z (primary M6 evidence)

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

> **Correction history / cache-contamination disclosure.** An independent
> adversarial review (run deliberately as both a GPT-family and a
> Claude-family pass before accepting this milestone) found that
> `materialize_task_sources` (`each/benchmark.py`) cached each task's
> extracted repo source tree keyed only by `task.task_id`, with no check
> that the cached content actually matched `task.pre_fix_sha`. The on-disk
> cache was found to contain source extracted under an earlier, unrelated
> invocation for at least one task (`requests-netrc-empty-default`'s cached
> `src/requests/utils.py` held the *fixed* line
> `if _netrc and any(_netrc):` instead of the real buggy `if _netrc:`),
> meaning an earlier version of this report (produced before this fix) may
> have shown the model fix-contaminated source for some tasks. This was
> fixed by keying the cache path on both `task.task_id` and
> `task.pre_fix_sha` (so a different sha can never silently reuse another
> sha's cached directory; see `materialize_task_sources`), purging the
> entire contaminated cache, and adding a regression test
> (`tests/unit/test_benchmark_source_cache.py`). **This report reflects a
> fresh suite run (`benchmark-suite-20261002T102321Z`) produced entirely
> after that fix**, with every one of the 22 tasks' baseline pytest run
> (real container execution, before any generation attempt) independently
> confirmed to genuinely fail (exit code 1, a real historical bug) --
> ruling out contaminated/fix-version source for this report's evidence.
> The earlier, contamination-era run is superseded and not retained as M6
> evidence.

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

## Repair-capability result: 0/22 applicable patches, genuine attempts of highly variable quality

No task produced an applicable patch. 65 of the 66 real generation calls
returned a completion that omitted the required exact `BEGIN_PATCH`/
`END_PATCH` markers (`PATCH_REJECTED: completion missing BEGIN_PATCH/
END_PATCH markers`); exactly one attempt (`more-itertools-one-only-falsy-
custom-exception`, attempt 2) instead returned a syntactically valid diff
that parsed but contained no actual file changes -- a placeholder-template
diff with no real edits (`PATCH_REJECTED: diff parsed but contains no file
changes`) -- not a diff that failed to apply to real content. All 22 tasks'
final outcomes were `PATCH_REJECTED: completion missing BEGIN_PATCH/
END_PATCH markers`, since the non-marker rejection occurred on a non-final
attempt that was retried. Even on retries that explicitly told the model
its previous attempt was rejected and to "follow the format exactly," no
attempt produced the required markers. Manual inspection of a sample of
raw completions (private; not reproduced here, per the no-model-output-in-
sanitized-docs policy) shows the content quality is **highly variable
across tasks, not uniformly competent**:

- A minority are on-topic edits within the right general area of the
  file, but not the true fault site (e.g. two of the `packaging` task's
  three attempts edit the condition of the `while "--" in value:`
  hyphen-condensing loop in `canonicalize_name` -- the third only edits
  the comment above that loop -- which is conceptually related to the
  task's double-hyphen normalization bug and in the same file, but the
  real bug is in the separate `is_normalized_name` function's
  `_normalized_regex` check a few lines below, which none of the three
  attempts touch -- so even this closest example is adjacent to, not a
  correct fix for, the actual fault).
- Several target clearly unrelated code (e.g. one task's completion edits
  an unrelated string/bytes-length helper far from the actual bug; another
  edits an unrelated exception class's `__init__`; another edits an
  unrelated classmethod in a different part of the same file).
- Some are non-functional or degenerate edits: a literal unified-diff
  **template with placeholder text** (`<original line>` / `<fixed line>`)
  rather than real content; a no-op line that is identical before and
  after the `-`/`+` markers; an edit that changes a docstring's doctest
  example rather than the function body.
- All of these -- competent, off-target, and degenerate alike -- share the
  same universal failure: none ever produces the bare `BEGIN_PATCH`/
  `END_PATCH` markers the prompt instructs, consistently preferring a
  Markdown ` ```python `/` ```diff ` fence with a conventional
  `--- a/...` / `+++ b/...` or bare `@@` hunk header instead.

This is genuine negative evidence of an instruction-following and
code-localization limitation of this checkpoint/prompt combination for
this exact task distribution, not a harness defect: the harness's patch
extraction is intentionally strict (exact markers required) per the
mandate's no-silent-leniency requirement, and loosening it purely to
manufacture a pass would bias the benchmark result rather than measure
real repair utility. The variable localization quality is also genuine
signal (not a harness artifact) -- the diff-blind excerpter supplies the
same pre-fix function/call-graph context regardless of outcome, so a
degenerate or off-target completion reflects the model's own generation,
not a starved or malformed prompt.

Per the project's explicit acceptance criterion, a 0/22 `REPAIR_VERIFIED`
(here: 0/22 even `PATCH_REJECTED`-surviving) result is valid M6 evidence
when input construction is genuine/diff-blind and real generation attempts
were made wherever the budget allowed -- which this run satisfies for all
22 tasks, not just the 4 the smaller checkpoint could reach.

- Tasks (overall catalog coverage): 22
- Generation-eligible (>=1 real `model.complete()` call): 22 / 22
- Real generation calls across the suite: 66 (22 tasks x up to 3 attempts)
- Verified repairs: 0 / 22
- Applicable patches produced (any attempt): 0 / 22

| Task | Repo | License | Outcome | Attempts | Generation calls | Assurance |
|---|---|---|---|---|---|---|
| requests-netrc-empty-default | psf/requests | Apache-2.0 | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| requests-encoding-header-bare-param | psf/requests | Apache-2.0 | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| click-multi-long-option-name-inference | pallets/click | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| click-flag-default-map-help-text | pallets/click | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| itsdangerous-timestamp-signer-future-age | pallets/itsdangerous | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| tqdm-format-num-negative-leading-zero | tqdm/tqdm | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| markupsafe-split-returns-list | pallets/markupsafe | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| markupsafe-tuple-interpolation | pallets/markupsafe | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| cachetools-rrcache-popitem-custom-choice | tkem/cachetools | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| cachetools-tlru-overwrite-expired | tkem/cachetools | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| dateutil-parser-nan-decimal-error | dateutil/dateutil | Apache-2.0 / BSD-3-Clause (dual) | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| tabulate-empty-table-maxheadercolwidths | astanin/python-tabulate | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| attrs-preinit-kwonly-default-syntaxerror | python-attrs/attrs | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| attrs-disable-validators-nested-context | python-attrs/attrs | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| wcwidth-center-padding-off-by-one | jquast/wcwidth | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| packaging-normalized-name-double-hyphen | pypa/packaging | Apache-2.0 / BSD-2-Clause (dual) | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| packaging-direct-url-case-insensitive-scheme | pypa/packaging | Apache-2.0 / BSD-2-Clause (dual) | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| more-itertools-one-only-falsy-custom-exception | more-itertools/more-itertools | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| more-itertools-numeric-range-reversed-empty | more-itertools/more-itertools | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| boltons-bits-length-bound-check | mahmoud/boltons | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| toolz-interpose-empty-sequence | pytoolz/toolz | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |
| pathspec-gitwildmatch-negated-bracket-range | cpburnz/python-pathspec | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | 3 | EACH-P2 |

Isolation evidence was recorded for every task: each real container
execution's outbound-network probe returned the numeric Linux
`ENETUNREACH` denial (`errno 101`), not a timeout/refusal ambiguity. Audit
result is honestly `UNAVAILABLE` for all 22 tasks (terminal audit only runs
after a `REPAIR_VERIFIED` candidate, per the M4 terminal-audit-boundary
fix in commit `994413b`; none of these 22 tasks ever reached that state).
Every one of the 22 tasks' baseline pytest run (before any generation
attempt) was independently confirmed to exit non-zero with the genuine
historical test failure. A sample of signed receipts from this suite were
independently re-verified with `each verify` against the trusted public
key; all PASS.

No patch text, model prompt/completion content, or known-fix source is
included in this sanitized summary. Full private receipts (one per task,
including every rendered prompt, raw completion, and generation parameter)
remain under `~/.each/runs`.
