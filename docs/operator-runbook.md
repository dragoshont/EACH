# Local operator runbook

This is the **tested development support row**, not a production release:
arm64 Apple Silicon, macOS 27.0.1, 128 GiB RAM, Python 3.12.14. The recorded
local-model row remains uv 0.12.21 / mlx-lm 0.32.0 and the existing exact
Qwen14 snapshot in [the contract](production-development-contract.md).
This P3/P4 continuation loaded no model and made no real inference calls.
Other hosts remain unqualified.

**Mandatory review correction:** P1 API-return acceptance is BLOCKED.
The observer measures sandboxed process responses, not authenticated Python
returns. Valid-JSON early exit and serializer substitution can match those
responses. Matching responses are now inconclusive for API repair verification;
read-only/fresh containers and signatures do not fix that trust boundary.
The original production goal has not been replaced with a response-only product.

## Preflight and limits

```bash
uv run each doctor
docker --context colima-each info
uv run each --help
```

`doctor` is not a model/image/repair qualification test. Keep the dedicated
context and pinned images; never fall back to host execution or a mutable tag.
For non-interactive SSH, include `/opt/homebrew/bin` on PATH. Missing Docker
causes container tests to skip; that is not a successful operational exercise.

The unchanged measured budgets are 8 KiB source, 8,192 context tokens including
reserved output, 2,048 output tokens, 300 seconds/generation, 15 seconds/case,
64 GiB MLX allocation, 20 GiB disk reserve, and reported 1,200 seconds/task.
The task ceiling is not an OS-wide watchdog. The exhausted three-task/nine-call
utility packet must not be rerun under this authorization.

Receipt finalization additionally preflights four times its serialized payload,
declared material sizes and 1 MiB headroom. This is advisory, not a filesystem
quota, global retention limit, reservation against concurrent writers, or
guarantee against power loss. A quota failure raises ENOSPC, never success.
There is no supported automatic prune, general resume/replay, or key rotation
CLI. Do not invent such commands or delete evidence to make a run pass.

## Evidence and partial outcomes

Private storage defaults to `~/.each`; `EACH_HOME` selects a real outside-checkout
directory. The private root and keys/runs directories are set to 0700;
`Receipt.write` also sets its final run directory to 0700 and writes new
receipt/draft files as 0600.

**Materials modes depend on the actual retention path.** When
`Receipt.write(..., materials_source=...)` performs its own copy, it explicitly
sets copied materials directories to 0700 and files to 0600. The observation
benchmark instead retains inputs through `build_worktree` and an excerpt write
before receipt finalization; that path does **not** enforce those per-material
modes. Creation/umask and pre-existing or inherited modes apply (typically
0755 directories/0644 files with umask 022). Privacy there relies on the
owner-only private root/ancestor directories, not universally owner-only
materials leaves. No actual exposure was observed in the bounded exercises.

Symlinked roots, artifacts, signing-key leaves and locks are refused.
These are local filesystem controls, not Keychain, encryption, HSM or TEE
protection. The same-user/key-holder/host/Docker administrator remains trusted.
Existing historical files are not recursively rewritten or deleted.

For each new finalization:

| File | Meaning |
|---|---|
| `receipt.pending.json` | Complete unsigned recovery draft saved before copying/signing; NOT a verified receipt. |
| `receipt.signed.pending.json` | Complete fsynced signed staging file if signing/finalization reached that point. |
| `receipt.json` | Atomically published complete signed JSON; never overwritten by another writer. |
| `receipt.md`, `materials/` | Private human projection and declared retained inputs. |

Drafts are retained, not silently discarded. A missing final receipt is an
incomplete run. Neither an unsigned draft nor exit zero from report generation
is a repair success. Restore genuine declared files; never edit signed bytes
or manufacture missing trajectories. If disk exhaustion happens before the
draft is durable, or the host is killed before finalization, evidence can still
be incomplete: stop and report that limit rather than assert zero data-loss.
Candidate-output JSON recursion errors are now incomplete and retained as
signed negative benchmark evidence, rather than escaping finalization.

## Interruptions and resource reconciliation

Use Ctrl-C/SIGINT against the **exact owned harness PID**. The supported
standalone observation benchmark now stops retries and signs an honest partial
receipt for interruption during baseline, generation or candidate validation.
Actual SIGINT during candidate execution and exact-container-CID SIGKILL drills
preserved the deterministic fixture trajectory/patch and verified retained
inputs. No MLX generation-interruption or arbitrary host SIGKILL/power-failure
durability is claimed.

The executor cleans only its exact owned container. If the host dies first,
reconcile the recorded owned container identity before retrying:

```bash
docker --context colima-each inspect "$OWNED_CID"
docker --context colima-each kill --signal KILL "$OWNED_CID"
docker --context colima-each rm --force "$OWNED_CID"
```

Set `OWNED_CID` only from verified ownership evidence. Never use broad name
filters, process-name killing, `docker prune`, or another project's containers.
No container/resource is touched merely because it has an EACH-like name.
A target process killed during observation is incomplete, not a passing test.
Conversely, matching JSON followed by exit zero is only a process-response
match; it does not prove the requested API returned. The benchmark cannot
turn that response-only match into `REPAIR_VERIFIED`.

Fresh candidate validation now uses a separate sanitized worktree from
baseline, with the same preimage manifest. Actual Colima probes showed stale
read lengths after in-place overwrites of baseline-read files: host stat was
54 bytes while the container read 23. A fresh path/inode removes that reproduced
mechanism; the actual regression compares container/host byte hashes before
the observer runs. No sleep-based fix or host execution substitute is used.
The old negative firstslice receipts remain unchanged.

## Verify, back up and recover

Use an explicitly trusted original public key:

```bash
uv run each verify "$RECEIPT" --full \
  --public-key "$TRUSTED_PUBLIC_KEY" \
  --artifact-root "$RETAINED_INPUT_ROOT"
```

Exit zero requires signature AND retained-input checks to pass. Missing,
corrupt or symlinked declared input fails full verification; signature-only
verification does not establish input availability or correctness.
The CLI prints verification status, not prompt/completion/source contents.

Stop active writers before a consistent private backup. Choose a new,
owner-only destination outside every checkout; copy `keys/`, `runs/` and the
approved `specs/` together with permissions preserved. Do not publish the
backup, include model weights unnecessarily, or print PEM contents. Keep a
separately trusted copy/fingerprint of the original public key.

Restore into a **new** owner-only directory, never over the user key/history.
Point `EACH_HOME` there, compare the restored public key with the trusted
original, then run full verification against each retained receipt/input set.
The actual temporary-key restore drill recovered byte-identical private/public
keys, original signed receipt and retained inputs and passed the CLI above.
That test never rotated, deleted, or restored over the user's actual key.

If the private key is missing while its public identity or stored receipts
survive, signing now refuses and asks for original-key restoration. A corrupt
private key is not regenerated. Missing/corrupt public data can be recovered
from the unchanged existing private key. Loss of all keys plus all local
receipt indicators cannot be distinguished from first use; external backups
and an independently trusted public identity remain necessary.

See [audit limitations](audit-qualification.md) and the
[production ledger](production-readiness-ledger.md). Independent R4 review,
repair usefulness, release packaging, pilot and human go/no-go are still open.
