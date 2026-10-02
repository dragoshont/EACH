# Development status

The user authorized **M0-M8**, with YAGNI and sequential acceptance gates.
The full program is **not complete**.

| Milestone | Current evidence |
|---|---|
| M0 | Package, Apache-2.0 license, CLI doctor, ordinary CI, and canonical Architrave knowledge profile established. |
| M1 | Independently verified: 51 tests, real failing/passing fixture, exact material identities, fail-closed numeric no-egress evidence, read-only container root, and real timeout cleanup. |
| M2 | Independently verified local Granite 3B Instruct/MLX repair, recorded full model/config/tokenizer artifact hashes, actual runtime/parameters, and rendered prompts. No cloud target inference. |
| M3 | Intake/spec workflow implemented; genuine user approval received on 2026-10-02 for the pinned BSD-3-Clause review packet. |
| M4 | Terminal auditor (copy/renaming/boilerplate heuristics plus a real Tree-sitter comparison) runs only after a validated candidate; audit rejection is terminal and never reaches another Builder attempt in the same run. |
| M5 | Receipt signature binds the entire canonical payload (model/spec/assurance/certification/attempt fields) plus diagnostic stage hashes, using a local signing key outside the repository; real tamper rejection (patch/spec/validation mutation, missing material) verified. |
| M6 | Real 5-task smoke, then 22 real historical permissive repairs benchmarked against the real no-network container, across two local models. 3B pilot (`granite-3b-code-instruct-mlx`, see `docs/benchmarks/m6-granite-3b-code-instruct-mlx-20261002.md`): only 4/22 tasks reached real generation calls under its declared 2048-token context (18/22 honestly rejected pre-generation with exact token counts; 0/4 eligible tasks produced an applicable patch). Primary 128K-context run (`granite-8b-code-instruct-128k-mlx`, original ibm-granite publisher weights, no conversion; see `docs/benchmarks/m6-granite-8b-code-instruct-128k-20261002.md`): all 22/22 tasks reached real generation (66 genuine `model.complete()` calls total), confirming the context-budget fix; 0/22 verified repairs -- 65/66 attempts' completions omitted the required BEGIN_PATCH/END_PATCH markers and the remaining attempt returned a placeholder-template diff with no real file changes, a genuine instruction-following/localization limitation of varying severity across tasks, not a harness defect (patch extraction is intentionally strict). An independent dual-family adversarial review (GPT-family and Claude-family) found and the coordinator fixed a real evidence-integrity defect before acceptance: the benchmark source cache was keyed only by task id, letting a stale cache entry from an earlier sha silently masquerade as the pre-fix source (confirmed for one task); fixed by keying the cache on task id + exact pre-fix sha, purging the contaminated cache, adding a regression test, and regenerating both benchmark reports from a clean re-run with every task's baseline independently confirmed to genuinely fail beforehand. Accepted as valid M6 evidence per the project's own criterion (genuine input construction and real attempts, not a required success rate). |
| M7-M8 | Not started. M7/M8 need a genuine new human approval on their own sensitive spec; the M3 approval does not extend to them. |

The latest checks cover 196 tests with zero skips, owned-code Ruff clean, real
signature verification against actual produced receipts (spot-verified across
both M6 benchmark runs), and the real benchmark runs referenced above.
Receipts, trajectories, weights, keys, and working target artifacts remain
outside the public repository.

## Recorded user approval

Review task `pallets-itsdangerous-410-review`, based on
[pallets/itsdangerous#410](https://github.com/pallets/itsdangerous/issues/410)
in the BSD-3-Clause project:

- Target commit: `096c8d42545d3b68ea21a4f890fb2b2d8979c0bd`.
- Editable paths: `src/itsdangerous/url_safe.py`, `src/itsdangerous/serializer.py`.
- Validation: Python compileall and upstream URL-safe tests.
- Draft hash: `88226ec2f82b6a4ca4b8c2e2967a621377b48c45e762fa1c6514274be920ed72`.

This is approval of a spec/policy packet, not generated implementation or
legal certification. The user explicitly approved this unchanged draft on
2026-10-02. Its sealed approved-packet hash is
`168aa1265149cca0ba46ae5a74ab3b82b457858a5c86a4eb765f751feafceb24`.

The earlier automated `octocat/Hello-World` demonstration was incorrectly
described as human-approved and permissively licensed. Its approval was
performed by the agent, and GitHub reports no repository license. Its immutable
private records are retained as historical evidence, not treated as valid
acceptance evidence. The replacement human-judgment checkpoint is now resolved
with the actual user decision.

Resume the existing Run, not a duplicate conductor. Continue
M4-M8 only after their own requirements pass; retain private shadow outputs and
never open an upstream Xodus PR.
