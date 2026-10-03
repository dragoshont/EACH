# Model qualification and dual-lane launch rule

User-directed addendum, 2026-10-03. This governs the current launch cycle.
It does not erase historical evidence or loosen information-flow boundaries.

## Two deliberately separate lanes

The **Frontier lane** pursues practical compatibility progress. It may use
opaque models and AI-generated source. Its work is not presumed upstreamable.
Only a connected Scout inspects that lane to identify candidate questions.

The **provenance lane** produces authoring-provenance evidence. An explicitly
authorized exact local Builder artifact authors target implementation from:

- explicitly approved upstream source at an exact revision;
- approved public interfaces and documentation;
- independently established behavioral evidence;
- the immutable, genuinely approved Spec packet;
- deterministic compiler/test feedback permitted by that packet.

Never admit Frontier source, diffs, implementation descriptions, algorithms,
helper structure, call graphs, model reasoning, hidden Scout context,
unrestricted retrieval, proprietary implementation, or terminal Auditor matches.
An implementation-derived claim without independent support is
`REPRO_REQUIRED`, not a behavioral fact.

The permitted sequence is:

```text
Frontier result -> candidate question -> independent verification
-> evidence -> immutable Spec approval -> sealed local Builder
-> validation -> terminal audit -> signed retained receipt
```

Summarizing or rewriting a dirty implementation is not this experiment.

## Exact-artifact authorization

The machine-readable [qualification registry](model-qualifications/registry.json)
records exact checkpoints and converted artifacts, not model families.
Decisions use `AUTHORIZED`, `BLOCKED`, `DEFERRED`, `REJECTED`, or
`EVALUATION_PENDING`. Unknown evidence remains `UNKNOWN`.

Assess artifact identity, pretraining, post-training, synthetic ancestry,
source/license evidence, local runtime provenance and repair capability
separately. Public weights, dataset access and license fields do not establish
training lineage. Architectural similarity does not establish inherited weights.
A failed patch does not invalidate otherwise verified authoring provenance.

For this cycle:

1. Verify the retained StarCoderBase lineage, original artifacts, conversion and
   signed runtime evidence. If they verify, authorize the exact artifact as the
   **initial/reference Builder**, even if the first repair failed.
2. Finish only the defined OctoCoder evaluation and record a terminal decision.
   Its StarCoder continuation and post-training data need their own evidence.
3. Retain StarCoder2 as blocked on verified unresolved synthetic ancestry.
   Do not reopen it without primary evidence directly resolving that blocker.
4. Assess Comma v0.1-2T once from available primary documents, without delaying
   launch, downloading weights or running another model evaluation.
   Retain Common Pile's license-metadata/laundering caveat. A Llama-style
   architecture is not evidence of Llama-weight ancestry.

Then stop model research for this launch cycle. Insufficient evidence warrants
`BLOCKED` or `DEFERRED`; it does not warrant an indefinite search. No custom
fine-tuning or additional model-family survey before a separately approved
later milestone.

## Launch and task boundary

**One authorized exact checkpoint plus the required isolation and receipt
gates is enough to launch.** Do not wait for a stronger Builder, multiple
authorized models, or resolution of every candidate. Preserve passed milestone
evidence rather than repeating completed gates without a relevant change.

Choose one small real Xodus/xgameruntime issue, independently fetch current
upstream and contribution policy, and establish Builder facts from permitted
evidence. A failed real repair is a valid research result. Do not force success
or substitute the outer agent for target generation.

Sensitive Spec approval remains a distinct, genuine, hash-bound human action.
The addendum authorizes execution of the program, not fabricated approval of an
unseen Spec. Preserve patch privacy, current destination policies, required
security gates and terminal audit. No upstream PR.

The separate private `dragoshont/xodus-provenance` repository stores sanitized
policies, model identities, evidence/spec packets, target revisions, receipt
summaries and policy snapshots. It is not a fork of the dirty tree and must
never expose a dirty repository remote to Builder.

## Claims

EACH may report that exact artifact X produced a patch from declared inputs Y
under isolation Z, with trajectory, validation, attribution audit and bound
receipt R. That does not establish legal clean-room status, copyright safety,
DCO compliance, Wine/Xodus acceptance, or absence of training-data memorization.
Independent bounded review is not an unobserved cross-family release gate.
