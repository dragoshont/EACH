# Development status

The user authorized **M0-M8**, with YAGNI and sequential acceptance gates.
The full program is **not complete**.

| Milestone | Current evidence |
|---|---|
| M0 | Package, Apache-2.0 license, CLI doctor, ordinary CI, and canonical Architrave knowledge profile established. |
| M1 | Independently verified: 51 tests, real failing/passing fixture, exact material identities, fail-closed numeric no-egress evidence, read-only container root, and real timeout cleanup. |
| M2 | Independently verified local Granite 3B Instruct/MLX repair, recorded full model/config/tokenizer artifact hashes, actual runtime/parameters, and rendered prompts. No cloud target inference. |
| M3 | Intake/spec workflow implemented, but genuine human approval of the live spec is pending. Not accepted. |
| M4-M8 | Not accepted. Partial M4 work is preserved; later stages remain gated. |

The latest independent checks covered 107 tests with zero skips, owned-code
Ruff, and a real local-model repair on the user's Mac. Receipts, trajectories,
weights, keys, and working target artifacts remain outside the public repository.

## Required next decision

Review task `pallets-itsdangerous-410-review`, based on
[pallets/itsdangerous#410](https://github.com/pallets/itsdangerous/issues/410)
in the BSD-3-Clause project:

- Target commit: `096c8d42545d3b68ea21a4f890fb2b2d8979c0bd`.
- Editable paths: `src/itsdangerous/url_safe.py`, `src/itsdangerous/serializer.py`.
- Validation: Python compileall and upstream URL-safe tests.
- Draft hash: `88226ec2f82b6a4ca4b8c2e2967a621377b48c45e762fa1c6514274be920ed72`.

This is approval of a spec/policy packet, not generated implementation or
legal certification. No approval has been obtained for this draft.

The earlier automated `octocat/Hello-World` demonstration was incorrectly
described as human-approved and permissively licensed. Its approval was
performed by the agent, and GitHub reports no repository license. Its immutable
private records are retained as historical evidence, not treated as valid
acceptance evidence. A genuine human-judgment checkpoint now blocks M3.

After approval, resume the existing Run, not a duplicate conductor. Continue
M4-M8 only after their own requirements pass; retain private shadow outputs and
never open an upstream Xodus PR.
