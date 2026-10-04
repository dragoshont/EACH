# EACH historical benchmark report: benchmark-suite-20261002T104225Z (pilot, context-limited)

> **Status: limited-coverage pilot, not the primary M6 evidence.** This
> checkpoint's declared 2048-token context limited real model.complete() calls
> to 4/22 historical tasks (18/22 rejected before any generation call). See
> `m6-granite-8b-code-instruct-128k-20261002.md` for the primary 22/22
> generation-eligible M6 run on the same tasks/policy with a larger-context
> checkpoint. This file is preserved as honest context-coverage evidence, not
> superseded or deleted.

> **Correction history.** This report has been regenerated twice from the
> same underlying bug/fix task definitions, each time after discovering a
> real defect in the harness or its cached evidence, not by re-running until
> a nicer-looking result appeared:
>
> 1. A harness bug (fixed in commit `898f2d7`) mislabeled 3 tasks
>    (`markupsafe-split-returns-list`, `markupsafe-tuple-interpolation`,
>    `cachetools-rrcache-popitem-custom-choice`) as `REPAIR_NOT_VERIFIED`
>    when every one of their attempts was actually `PATCH_REJECTED`: a task
>    that exhausts every attempt on a rejected/malformed completion, without
>    ever successfully applying a patch, defaulted to a seeded
>    `"REPAIR_NOT_VERIFIED"` outcome instead of its real last-attempt outcome.
> 2. A second, independent-review-discovered defect: `materialize_task_sources`
>    cached each task's extracted repo tree keyed only by `task.task_id`, with
>    no check that the cached content actually matched `task.pre_fix_sha`. The
>    on-disk cache for this run's tasks was found to contain source extracted
>    under an earlier, unrelated invocation for at least one task
>    (`requests-netrc-empty-default`'s cached `src/requests/utils.py` held the
>    *fixed* line `if _netrc and any(_netrc):` instead of the real buggy
>    `if _netrc:`), meaning earlier runs of this report may have shown the
>    model fix-contaminated source for some tasks. This was fixed by keying
>    the cache path on both `task.task_id` and `task.pre_fix_sha` (so a
>    different sha can never silently reuse another sha's cached directory),
>    purging the entire contaminated cache, and adding a regression test
>    (`tests/unit/test_benchmark_source_cache.py`). **This file reflects a
>    fresh suite run (`benchmark-suite-20261002T104225Z`) produced entirely
>    after both fixes**, with every one of the 22 tasks' baseline pytest runs
>    independently confirmed to genuinely fail (real historical bug, not
>    contaminated fix-version source) before any generation attempt.

Model: `granite-3b-code-instruct-mlx` (local MLX checkpoint; zero cloud target
inference). The checkpoint's `config.json` declares
`max_position_embeddings=2048`, `model_type=llama`, `rope_scaling=null` -- a
real, measured constraint, not an assumption.

The harness validates the exact rendered prompt token count plus reserved
output against the declared limit *before* calling `model.generate`, never
truncating or mutating the prompt silently, and uses a deterministic,
diff-blind, AST-based source excerpter (`select_prompt_excerpt` in
`each/benchmark.py`) that narrows large files to the specific
functions/methods the pre-fix test references (plus their local call graph),
labels every kept block with its true absolute line numbers (patch hunks are
line-number-anchored against the real file), and caps oversized leading
docstrings. The excerpter never reads the fix commit, diff, or test outcome --
only the pre-fix bug file and pre-fix test file.

Even with this excerpting, only 4 of the 22 real historical tasks have a
rendered prompt that fits the checkpoint's real 2048-token budget for at
least one real generation call; 18 are rejected before any generation call
with an exact `BUILDER_CONTEXT_BUDGET_EXCEEDED` token count. Of those 4:
`boltons-bits-length-bound-check` fits on attempt 1, receives one real
generation/patch-extraction attempt (rejected: malformed diff), then its
retry's appended feedback text pushes attempt 2 over budget, correctly
ending the task rather than silently retrying or degrading; the other 3
(`markupsafe-split-returns-list`, `markupsafe-tuple-interpolation`,
`cachetools-rrcache-popitem-custom-choice`) fit the budget for all 3
attempts, but every attempt's completion was rejected (missing
BEGIN_PATCH/END_PATCH markers, or a patch that does not apply cleanly to the
real pre-fix file) -- no patch was ever applied for any of these 4 tasks.
This is a measured property of the pinned checkpoint's small context window
and output budget combined with genuine real-world file/test complexity,
not a harness defect. Per the project's explicit acceptance criterion, a
0/22 `REPAIR_VERIFIED` result is valid M6 evidence when input construction
is genuine/diff-blind and real generation attempts were made wherever the
budget allowed -- which this run satisfies.

- Tasks: 22
- Verified repairs: 0 / 22
- Rejected before any generation call, exact token counts recorded: 18 / 22
- Reached >=1 real generation call (generation-eligible): 4 / 22
- Of the 4 generation-eligible tasks, patch successfully applied: 0 / 4

| Task | Repo | License | Outcome | Attempts | Assurance |
|---|---|---|---|---|---|
| requests-netrc-empty-default | psf/requests | Apache-2.0 | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (7472 tokens) + reserved output (512 tokens) = 7984 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| requests-encoding-header-bare-param | psf/requests | Apache-2.0 | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (7304 tokens) + reserved output (512 tokens) = 7816 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| click-multi-long-option-name-inference | pallets/click | BSD-3-Clause | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (5440 tokens) + reserved output (512 tokens) = 5952 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| click-flag-default-map-help-text | pallets/click | BSD-3-Clause | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (26675 tokens) + reserved output (512 tokens) = 27187 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| itsdangerous-timestamp-signer-future-age | pallets/itsdangerous | BSD-3-Clause | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (1574 tokens) + reserved output (512 tokens) = 2086 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| tqdm-format-num-negative-leading-zero | tqdm/tqdm | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (9668 tokens) + reserved output (512 tokens) = 10180 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| markupsafe-split-returns-list | pallets/markupsafe | BSD-3-Clause | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | EACH-P2 |
| markupsafe-tuple-interpolation | pallets/markupsafe | BSD-3-Clause | PATCH_REJECTED: patch does not apply cleanly to markupsafe/__init__.py: stale or mismatched context/removed lines starting at line 22 | 3 | EACH-P2 |
| cachetools-rrcache-popitem-custom-choice | tkem/cachetools | MIT | PATCH_REJECTED: completion missing BEGIN_PATCH/END_PATCH markers | 3 | EACH-P2 |
| cachetools-tlru-overwrite-expired | tkem/cachetools | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (2482 tokens) + reserved output (512 tokens) = 2994 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| dateutil-parser-nan-decimal-error | dateutil/dateutil | Apache-2.0 / BSD-3-Clause (dual) | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (8691 tokens) + reserved output (512 tokens) = 9203 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| tabulate-empty-table-maxheadercolwidths | astanin/python-tabulate | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (16090 tokens) + reserved output (512 tokens) = 16602 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| attrs-preinit-kwonly-default-syntaxerror | python-attrs/attrs | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (18247 tokens) + reserved output (512 tokens) = 18759 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| attrs-disable-validators-nested-context | python-attrs/attrs | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (5558 tokens) + reserved output (512 tokens) = 6070 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| wcwidth-center-padding-off-by-one | jquast/wcwidth | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (4373 tokens) + reserved output (512 tokens) = 4885 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| packaging-normalized-name-double-hyphen | pypa/packaging | Apache-2.0 / BSD-2-Clause (dual) | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (1922 tokens) + reserved output (512 tokens) = 2434 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| packaging-direct-url-case-insensitive-scheme | pypa/packaging | Apache-2.0 / BSD-2-Clause (dual) | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (3169 tokens) + reserved output (512 tokens) = 3681 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| more-itertools-one-only-falsy-custom-exception | more-itertools/more-itertools | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (32589 tokens) + reserved output (512 tokens) = 33101 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| more-itertools-numeric-range-reversed-empty | more-itertools/more-itertools | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (30897 tokens) + reserved output (512 tokens) = 31409 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| boltons-bits-length-bound-check | mahmoud/boltons | BSD-3-Clause | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (1576 tokens) + reserved output (512 tokens) = 2088 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 2 | EACH-P2 |
| toolz-interpose-empty-sequence | pytoolz/toolz | BSD-3-Clause | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (7083 tokens) + reserved output (512 tokens) = 7595 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |
| pathspec-gitwildmatch-negated-bracket-range | cpburnz/python-pathspec | MIT | BUILDER_CONTEXT_BUDGET_EXCEEDED: rendered prompt (3744 tokens) + reserved output (512 tokens) = 4256 tokens exceeds this checkpoint's declared max_position_embeddings (2048) | 1 | EACH-P2 |

Every one of the 22 tasks' baseline pytest run (real container execution,
before any generation attempt) was independently confirmed to exit non-zero
with a genuine test failure matching the historical bug, ruling out the
cache-contamination defect described above for this run's evidence.

No patch text, model prompt/completion content, or known-fix source is
included in this sanitized summary. Full private receipts (one per task)
remain under ~/.each/runs.
