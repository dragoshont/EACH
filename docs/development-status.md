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
| M6 | Real 5-task smoke, then 22 real historical permissive repairs benchmarked against the local Granite-3B-code/MLX checkpoint and the real no-network container. See `docs/benchmarks/m6-granite-3b-code-instruct-mlx-20261002.md`: 0/22 verified repairs, 18/22 honestly rejected pre-generation on a measured context-budget limit (exact token counts recorded, no silent truncation), 4/22 genuinely attempted end-to-end. Accepted as valid M6 evidence per the project's own criterion (genuine input construction and real attempts, not a required success rate). |
| M7-M8 | Not started. M7/M8 need a genuine new human approval on their own sensitive spec; the M3 approval does not extend to them. |

The latest checks cover 192 tests with zero skips, owned-code Ruff clean, real
signature verification against an actual produced receipt, and the real
benchmark run referenced above. Receipts, trajectories, weights, keys, and
working target artifacts remain outside the public repository.

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
