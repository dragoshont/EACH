# Final adversarial review

Reviewed commit: `478a1de8dfb808274f5fa67754ccb1aeb614c112`.

Requested reviewer: GPT-6 Astra, high reasoning, long-context tier. An exact
one-million-token allocation was not exposed by the invocation interface and
is not claimed. The independent reviewer inspected public harness code and
source-free evidence only, never private target candidates or trajectories.

**Final verdict: REVISE; terminal non-PASS for this attempt.**
The review sequence was FAIL, REVISE, REVISE. The repository's bounded-review
rule stops automatic revisions after the third non-PASS.

## Verified checks

The coordinator independently ran the exact reviewed commit on the Mac:
configured gates passed with 278 tests and three optional AST skips; the
audit-enabled suite passed all 281 tests with no skips; lint and doctor passed.
These checks do not override the independent review's uncovered boundary cases.

## Remaining findings

| Finding | Severity | Evidence | Minimum correction |
|---|---|---|---|
| Full verification can succeed without all materials | Blocker | `each/cli.py` accepts `UNAVAILABLE` as a successful materials result under `--full`; a test asserts success after deleting the entire directory. | Require both signature and actual materials verification to PASS for full mode; retain signature-only historical verification separately. |
| Destination roots can escape through symlinks | Blocker | `Receipt.write` trusts a resolved `materials` symlink as its boundary; private-root checks do not cover all descendant roots before writes. | Anchor child destinations to the validated private root and reject symlinked roots before creation or copying. |
| Missing integrity evidence can still imply P2 | Blocker | M8 defaults an absent `materials_integrity` to PASS; validation files remain mounted writable. | Treat unperformed checks as unverified and protect harness-owned validation inputs during execution. |
| Failure trajectories omit executed work | Major | Patch/application and command results are stored after classification; expected failures can prevent partial receipt finalization. | Record application and each build/run result immediately; preserve truthful partial receipts. |
| Evidence freshness and recovery grants are incomplete | Major | Artifact registration stamps the current baseline without validating producer-time revision; a resolved checkpoint can justify repeated retry grants. | Validate execution revision when registering evidence and make interruption recovery grants single-use. |
| Historical outcome claims are unsupported | Major | Public status describes separate corrected M7/M8 runs that were not supplied as verified evidence. | Remove unsupported rerun/cause assertions; preserve the original signed receipts and their limitations. |

## Historical experiment limits

The coordinator verified only these original private receipt summaries:

| Experiment | Recorded result | Attempts | Repaired exit code | Audit | Declaration signature |
|---|---|---|---|---|---|
| `m7-clean-room-lru-cache-real` | `REPAIR_NOT_VERIFIED` | 3 | Absent | UNAVAILABLE | PASS |
| `m8-xsystem-sandboxid-opt-20261002` | `REPAIR_NOT_VERIFIED` | 3 | Absent | UNAVAILABLE | PASS |

Those records are immutable historical evidence, not fresh demonstrations of
the corrected harness, successful compatibility implementations, or proof that
the specifications were sufficient. The requested adversarial analysis has
been performed; full project acceptance has **not** been achieved.

No target retry, model download, new framework, private-source publication, or
upstream Xodus PR is justified by this review. Resume requires an explicit
coordinator/user decision on the remaining bounded corrections.
