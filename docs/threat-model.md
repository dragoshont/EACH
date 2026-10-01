# Threat model

This document is created at M0 and updated at every milestone that changes
an isolation boundary or discovers a new mitigation gap. It is a working
engineering document, not a certification.

## Threats

### T1 — Network leakage

The Builder or its tools fetch implementation knowledge during generation
(web search, package registries, DNS lookups).

Mitigation: no network in the strong-isolation execution profile; **enforced
and tested** (not merely documented, see M1 adversarial evidence); network
policy recorded in the receipt.

### T2 — Hidden agent context

A framework silently injects repository history, global memories, prior
chats, or web results into the Builder's context.

Mitigation: explicit context constructor; the exact prompt/messages sent to
the model are logged; linear trajectory; no undeclared retrieval-augmented
generation.

### T3 — Training-data memorization

The model emits source code it memorized during pretraining, independent of
anything in the current spec.

Mitigation: model provenance metadata (exact weights/revision hash);
corpus-membership/search adapters where available; similarity scanning
(M4); an honest residual-risk statement. **Not fully solvable** — this is
why EACH never claims originality certification.

### T4 — Spec contamination

A Scout agent sees restricted material and silently folds it into a
"clean-looking" spec.

Mitigation: every spec fact carries an origin classification
(`PUBLIC_API_DOC`, `PUBLIC_ISSUE`, `MODEL_INFERENCE`, `RESTRICTED`, ...,
see M3); human approval gate for sensitive tasks; deterministic observation
collectors kept separate from the Scout.

### T5 — Audit feedback contamination

The Auditor discovers a forbidden source match and that match is fed back
into another Builder attempt, teaching the model the forbidden
implementation.

Mitigation: the Auditor is a **terminal boundary** (M4) — a flagged run is
rejected and archived; a retry starts fresh from the original approved
spec, never from audit findings.

### T6 — Existing target-source contamination

The sanitized worktree itself already contains AI-derived or
provenance-unknown code before EACH ever touches it.

Mitigation: target provenance classification is recorded; the receipt
records the exact target source SHA and its declared trust class.

### T7 — Tool escape

The Builder uses shell access to inspect network state, credentials, the
parent filesystem, Git history/remotes, or other forbidden locations.

Mitigation: sandboxed executor; explicit read/write scopes; a command
policy (allow/deny lists, enforced, not merely prompted); environment
variable scrubbing; no inherited secrets; no SSH agent; no Git
fetch/pull/clone/remote access (see M1 adversarial tests).

### T8 — Publication contaminates future clean-room work

An AI-authored shadow patch becomes public, and a future human
implementer of the same feature is unknowingly tainted by having seen it.

Mitigation: shadow artifacts are **private by default**; public
publication is always an explicit, separate, acknowledged step (see
`docs/EACH_BOOTSTRAP_MANDATE.md` §46, publication modes).

### T9 — False legal confidence

A user treats "no similarity match found" as proof of legal safety.

Mitigation: assurance levels are explicitly technical/engineering labels,
never "certified"; every receipt restates its limitations; see
`docs/claims-and-nonclaims.md`.

## Assurance levels

A receipt's assurance level is a property of *that specific run*, not a
fixed property of the tool.

| Level | Name | Minimum evidence |
|---|---|---|
| EACH-P0 | Untracked | Model/source unknown; unrestricted network; incomplete trajectory. Ordinary, unaudited AI code. |
| EACH-P1 | Recorded | Model/provider identified; prompt/trajectory recorded; target revision recorded; patch hash recorded. |
| EACH-P2 | Isolated | P1 **plus**: fixed model revision/hash; exact allowed inputs hashed; no-egress execution *verified* (not assumed); environment manifest; tool allowlist; no undeclared retrieval. |
| EACH-P3 | Dataset-auditable | P2 **plus**: model has documented/queryable training provenance; post-generation corpus/source checks executed; license/source evidence recorded; no disallowed match over policy thresholds. |
| EACH-P4 | Deterministic-generation | No neural model authors the promotable source (e.g. an approved declarative spec drives a deterministic generator); generator source/revision recorded; output reproducible byte-for-byte. |

P4 does not automatically mean legally clean-room. These labels represent
evidence properties only, and every receipt restates that explicitly:

```json
{
  "assurance": "EACH-P2",
  "legal_certification": false,
  "cleanroom_certification": false
}
```

### M1 status

M1 implements only the container executor profile (`--network none`,
scrubbed environment, dropped capabilities, no host home or SSH-agent
mount, `docker --context colima-each` against a pinned base-image digest).
A configuration that cannot back that profile (network enabled, or an
unpinned/mutable image tag) is rejected at executor-construction time
rather than silently claimed as isolated.

The assurance level in each receipt is derived per-run, not hardcoded: it
is only **EACH-P2** when that run's own isolation probe (the same
`NETWORK_PROBE_SCRIPT` used by the adversarial tests, executed through the
run's actual executor configuration) genuinely observed a denied outbound
connection. Any other outcome — including an unexpected probe result —
downgrades honestly to **EACH-P1** rather than crashing or over-claiming.
It does **not** claim EACH-P3, since no corpus/source similarity check or
documented model-training provenance exists yet (the M1 audit step is an
explicit `UNAVAILABLE` stub, never a fabricated PASS). The real,
historical outbound-network-denial probe recorded during bootstrap is
evidence for *that* probe only; it is never substituted for a given run's
own isolation evidence.

No native-macOS executor profile exists in M1; native host execution is
explicitly not implemented and not used as a substitute for container
isolation ("native host execution is not a strong-profile proxy").

## Known limitations as of M1

- No model has been integrated yet beyond `FixtureModel` (a deterministic,
  non-inferential canned response); T3 is not yet exercisable and will be
  revisited starting at M2.
- No Auditor exists yet; T4/T5/T9 mitigations are designed but not yet
  mechanically enforced — `each/audit/stub.py` returns an explicit
  `UNAVAILABLE` result rather than a fabricated PASS. Tracked for M3/M4.
- No attestation/signing exists yet; receipts are not yet tamper-evident.
  Tracked for M5.
- The container executor currently runs as the image's default user
  (root inside the container's own user namespace, not the host); a
  non-root `--user` mapping was attempted but deferred because Colima's
  default bind-mount UID mapping made it unreliable in this environment.
  This does not weaken network/secret isolation (verified in
  `tests/adversarial/test_container_isolation.py`) but is a residual
  defense-in-depth gap, tracked for a later milestone.
- The patch applier (`each/patch.py`) supports only textual unified-diff
  hunks (via `unidiff`); it does not yet handle binary diffs, renames, or
  mode changes. Out of scope for hello-repair; revisit if a later
  milestone's real-world fixtures require it.

