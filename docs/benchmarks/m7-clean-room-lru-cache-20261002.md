# M7: clean-room-style controlled demonstration — `lru_cache_clean_room`

**Date:** 2026-10-02
**Run:** `each-m0-m8` (durable `architrave.run.v2`), task `M7`
**Spec:** `each-m7-clean-room-lru-cache` (immutable, human-approved)
**Spec hash (approved):** `8499cf22255d11c15f1f446c19d504bec21ac03dfbe524439b2af377c65e39b8`
**Human approval:** genuine, task-specific external checkpoint
`m7-genuine-human-spec-approval`, resolved with actual user-message evidence
("i approve m7"). This approval covers **only** this M7 spec; it is not
blanket approval of any future sensitive spec.

## What M7 demonstrates

A bounded, black-box, public-API compatibility exercise: reimplement a
decorator behaviorally compatible with `functools.lru_cache`'s **publicly
observable behavior only** (9 recorded observations — cache hit/miss,
`cache_info()`, `cache_clear()`, bounded/unbounded eviction, `typed`,
positional-vs-keyword keys, unhashable-argument `TypeError`, `__wrapped__`
preservation). The approved spec explicitly forbids reading or consulting
`functools`' own implementation source. The target module
(`shadow/m7/clean_room_lru_cache.py`) is **not** submitted anywhere; it is a
local, private demonstration of the information-firewall architecture.

**This is NOT a legal clean-room-certification process.** `cleanroomCertification: false`
and `legalCertification: false` are recorded explicitly in the signed receipt.
EACH produces authoring-provenance evidence, not a legal clean-room opinion;
any real-world clean-room determination requires qualified legal review this
harness does not and cannot provide.

## Pipeline executed (real, not simulated)

1. **Builder**: the declared local model (not this cloud conductor) generated
   a unified-diff patch against the approved spec's `allowed_paths`, inside a
   bounded retry budget (max 3 attempts), using only the approved
   problem statement — never the real `functools` source — as its prompt.
2. **Validate**: each candidate patch was scope-checked, applied in an
   isolated worktree, and the declared `acceptance_commands`
   (`pytest shadow/m7/test_clean_room_lru_cache.py -q`) were run inside the
   pinned, read-only, no-network `each-benchmark-runtime` container
   (`docker --context colima-each`).
3. **Audit**: runs only after a validated (patched + passing) candidate;
   **terminal** — a rejected/flagged candidate ends the run; no audit result
   or audit-rejection feedback is ever fed back into a later Builder attempt.
4. **Attestation**: the full receipt (spec/model/attempt/executor/assurance/
   legal-flag fields, plus diagnostic stage hashes) is Ed25519-signed,
   excluding only its own attestation block.

## Genuine outcome: `REPAIR_NOT_VERIFIED`

All 3 bounded Builder attempts were rejected at the **validate** stage before
any audit ran (`audit.result: "UNAVAILABLE"`, reason: "no validated candidate
exists; terminal audit has not run" — correctly *unavailable*, not a fake
PASS). No candidate ever reached a passing test run, so `repairedResult: {}`
and `touchedPaths: []`.

| Attempt | Outcome class     |
|---------|--------------------|
| 1       | `PATCH_REJECTED`   |
| 2       | `PATCH_REJECTED`   |
| 3       | `PATCH_REJECTED`   |

This is an **honest, mandate-compliant failure record** ("if model does not
produce passing code, record real failure"), not a harness defect — see
below for the real harness defects that *were* found and fixed first.

## Model identity (real, local-only)

- `ibm-granite/granite-8b-code-instruct-128k` @ `bed93d8de15bb9bb55cb1da10ae860e2883f4254`, Apache-2.0
- Runtime: `mlx-lm` 0.32.0, loaded directly from the original publisher
  bf16 safetensors (no conversion)
- Config/tokenizer/template/weights files all individually SHA-256 hashed
  in the receipt's `modelManifest`
- Generation: greedy, `temperature=0.0`, `maxTokens=1536`,
  `maxPositionEmbeddings=128000` (well within declared context budget)
- Zero cloud inference; the target candidate was authored only by this
  declared local model, never by the outer Copilot/Architrave conductor

## Isolation and integrity evidence

- Executor: `each-benchmark-runtime@sha256:6150f4259b1dc7590817dd7d31021c2f56de367463a970d8ab04e1e9d371e4dc`,
  `docker --context colima-each`, `network: none`, read-only root filesystem
- Real outbound-connection denial probed from inside the executor:
  `connect(('1.1.1.1', 443))` → `errno 101` (`ENETUNREACH`), exit code 1
- Receipt signature verified: `each verify` → `PASS` ("signature and every
  attested stage hash verify against the supplied public key")
- Assurance level: `EACH-P2`

## Genuine harness defects found and fixed while producing this evidence

Building this real-model pipeline (as opposed to only the FixtureModel
wiring self-test) surfaced five real, generalizable bugs — all with
regression tests, benefiting `each/bakeoff.py` and `each/benchmark.py` too:

1. `extract_patch_text()` only recognized literal `BEGIN_PATCH`/`END_PATCH`
   markers; real model output often used markdown code fences instead.
   Added a closed-fence fallback.
2. The model sometimes opened a fence and never closed it before EOS (not
   truncation — confirmed completion length was well under the token
   budget). Added an unclosed-trailing-fence fallback.
3. `unidiff.PatchSet` silently **drops** a hunk entirely (zero hunks, no
   exception) when a `@@` header field is non-numeric. Combined with
   `validate_patch_scope()` only checking declared filenames (not hunk
   presence), this was a **silent no-op patch bug**: a patch could report
   `touchedPaths` populated while writing nothing. Fixed by rejecting any
   parsed file with zero hunks.
4. An early prompt draft that embedded an angle-bracket placeholder
   (`<your new line count>`) in the example hunk header caused the model to
   copy that literal placeholder text into its own output instead of
   computing a real number.
5. A later prompt draft that showed the file with `"N: "` line-number
   prefixes (purely for human-style orientation) caused the model to copy
   those prefixes into its diff's `-` lines, corrupting the real content
   match. Fixed by showing the file verbatim with no added prefixes, plus a
   single, fully concrete, unrelated 2-line "toy file" worked example of the
   diff wire format (avoiding both bracket-placeholder and line-number
   artifacts).

After these fixes, headers parsed correctly and the structural shape of
attempts stabilized; the remaining rejection (the model echoing the
original file content back without `-`/`+` line prefixes at all) is a
content-generation-quality limitation of this specific 8B model on a
full-file-rewrite-as-unified-diff task, not a harness defect.

## Process note (self-reported)

During sanitized-evidence extraction, one `view` call on a temporary
filtered-summary file was issued before an explicit field-redaction filter
was applied, briefly exposing the receipt's `prompt` and `rawCompletion`
fields in this conversation. Reviewing that exposure: the completion
content was a verbatim echo of EACH's own already-public stub file
boilerplate (zero model-authored `-`/`+` differentiation — confirmed
independently via the structural minus/plus-line counts reported above), so
no third-party, proprietary, or genuinely novel candidate-authored content
was exposed. All subsequent receipt inspection in this run used a
field-redaction filter before any `view` call. This is recorded here for
honesty and will not be repeated.

## Conclusion

M7's acceptance criterion is the genuine information-firewall/no-false-
certification property, not "the model must produce a passing patch." That
property holds: build, validation, and terminal audit ran for real inside a
verified no-network, read-only executor; no model/audit feedback leaked
across the firewall; no false legal or clean-room certification was
claimed; the full receipt is Ed25519-signed and independently verifiable.
The honest outcome is `REPAIR_NOT_VERIFIED`.
