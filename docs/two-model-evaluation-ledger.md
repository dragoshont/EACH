# Two-model repair evaluation ledger

Primary matrix scope: **StarCoderBase and OctoCoder**; a separately authorized
CrystalCoder follow-up is recorded below. This ledger separates proposal
delivery from behavioral correctness. Receipt integrity is not repair success.
Private sources, completions, candidates and Auditor findings stay private.
Results are not production, legal, Wine or Xodus certification.

**Executed scope: two fixed tasks, two original models, two task profiles,
plus one zero-call parser replay.** A separately qualified CrystalCoder
evaluation is recorded below because the initial two models produced no fix.
Batch SHA-256:
`30a3052ad0199208c6bc41e014d57f11cbc4d1425d0bf1b7c67d83f1ad3c4ec7`.
The user directed immediate evaluation after this exact batch was displayed.
Four calls ran; no retry, additional model or second profile was added.

## Models

| Model | Exact publisher revision | Retained local artifact | Status |
|---|---|---|---|
| StarCoderBase 15.5B | `88ec5781ad071a9d9e925cd28f327dea22eb5188` | Locally verified FP16 conversion; artifact suffix `97c8813f705fc8c1` | AUTHORIZED |
| OctoCoder 15.5B | `0f863c63e38ba80fc2c4010f34a7f46d537a9eee` | Locally verified FP16 conversion; artifact suffix `553d84a480a0c794` | AUTHORIZED |

Use the official qualified loader. No family fallback, new model, fine-tuning,
or outer-agent target implementation is part of this evaluation.

## Tasks and source origins

Common upstream baseline:
`xodus-gaming/xgameruntime@791710510d9ba0746bbd60754215eb321800e4f0`.
Permitted source: `xsystem.c`. Public GDK documentation revision:
`7d9199cfc63c9541bc65cc0b60c940b7e5baafe2`.

| Task | Public issue identifying the question | Independently established requirement | Evaluation |
|---|---|---|---|
| S: sandbox ID | [xodus-gaming/xgameruntime#22](https://github.com/xodus-gaming/xgameruntime/issues/22) | [GDK contract](https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xsystem/functions/xsystemgetxboxlivesandboxid?view=gdk-2604): optional `sandboxIdUsed`; required buffer; insufficient-buffer regression | One function, separately compiled and tested |
| C: console ID | [xodus-gaming/xgameruntime#26](https://github.com/xodus-gaming/xgameruntime/issues/26) | [GDK contract](https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xsystem/functions/xsystemgetconsoleid?view=gdk-2604): optional `consoleIdUsed`; required buffer; insufficient-buffer regression | One function, separately compiled and tested |

The raw issue bodies include implementation advice and are **not Builder
input**. Builder inputs are the approved documentation-derived requirements,
the selected function/interface and permitted source context. No private fork
implementation, reference fix, hidden test source or Auditor result is input.

## Existing harness profiles; comparison deferred

| Harness profile | Builder output | Model-native prompt | What changes |
|---|---|---|---|
| H1: function replacement | Complete selected function, not a diff or whole file | Base: FIM; OctoCoder: documented Question/Answer | Runner derives the diff mechanically |
| H2: function-body completion | Selected function body, with original signature and surrounding file retained | Base: FIM; OctoCoder: documented Question/Answer | Less output to reproduce; same behavioral tests |

These are **two concrete EACH harness profiles**, not claims that Pi,
OpenCode or the original BigCode evaluator has been executed. The same oracle,
source, requirements and isolation apply to both profiles. H2 subsequently ran
after H1; the original H1 evidence remains unchanged.

## Fixed task matrix

| Model | S: sandbox ID / H1 | C: console ID / H1 | Distinct verified fixes |
|---|---|---|---|
| StarCoderBase | Candidate compiled; **3/6 cases PASS** | Candidate compiled; **3/6 cases PASS** | **0/2** |
| OctoCoder | **PATCH_REJECTED: no change**; cases NOT RUN | **PATCH_REJECTED: no change**; cases NOT RUN | **0/2** |

## H2 body-profile results and replay

| Model | Sandbox | Console | Distinct verified fixes |
|---|---|---|---:|
| StarCoderBase | Candidate compiled; **4/6 cases PASS** | Candidate compiled; **4/6 cases PASS** | **0/2** |
| OctoCoder, original execution | Body/scope parser rejection | Body/scope parser rejection | **0/2** |
| OctoCoder, zero-call replay | Candidate compiled; **4/6 cases PASS** | Candidate compiled; **4/6 cases PASS** | **0/2** |

The replay consumed only the first complete selected function body and ignored
continued output. It used the retained original completions, made **zero new
model calls**, and did not overwrite the original receipts. Private source-free
result artifact:
`~/.each/oracle/experiments/octocoder-body-replay-v3/results.json`,
SHA-256
`069cbc9f911cee5ed19cedb0baa0244519e5bc1c7926673c7ca659dfc6c15a7d`.

Both replayed OctoCoder candidates matched StarCoderBase's H2 pattern: they
passed the required-buffer NULL, both-outputs NULL, value-plus-size and short-
buffer-with-size cases, but failed both cases where the optional size pointer
was NULL. The parser improvement recovered logic evidence, not a fix.

Each cell records exact Spec/material hashes, model/runtime identity, actual
prompt/output, sampling, input tokens, response characters, completion time,
proposal acceptance, build exit, named behavioral cases, audit execution,
receipt verification and private evidence references. Missing metrics remain
UNAVAILABLE. There are **four cells and two distinct issues**; a model can score
0/2, 1/2 or 2/2 verified fixes. Format failure is not a behavioral-test failure.

### H1 named case results

StarCoderBase produced the same behavioral pattern on both tasks:

| Case | Sandbox | Console |
|---|---|---|
| Optional size output is NULL, valid buffer | FAIL | FAIL |
| Valid buffer and non-NULL size output | FAIL | FAIL |
| Required buffer is NULL | PASS | PASS |
| Both outputs are NULL | PASS | PASS |
| Short buffer, non-NULL size output | PASS | PASS |
| Short buffer, NULL size output | FAIL | FAIL |

This is behavioral evaluation, not comparison to a known patch. The Base
candidates compiled but did not implement the required positive behavior.
OctoCoder returned the selected public function unchanged in both calls, so no
candidate was applied.

### Cell evidence

| Model / task | Spec SHA-256 | Receipt SHA-256 | Input tokens | Completion seconds | Outcome |
|---|---|---|---:|---:|---|
| Base / S | `afe1af765ba112607d8c0786e39af2168f9ef59be1b55a137426f59a5574e699` | `7a4bf937961fa986eae2478f855cd90c814274c2370c65b086c82beb2b6bc983` | 1,839 | 35.512 | 3/6, not verified |
| Base / C | `be4965f244fa77efb63edeacd17e9e3eb38926952fd3f0c0c009914592625387` | `e905adca4693e6dc4be999b9bc5231ffc910632814afda44ad3b505a24568f9d` | 1,767 | 13.116 | 3/6, not verified |
| Octo / S | `afe1af765ba112607d8c0786e39af2168f9ef59be1b55a137426f59a5574e699` | `2d985b875dec42c2b19c872910f3f5a47bb6e857592ff415f8afe63c14e173e4` | 545 | 51.656 | No change |
| Octo / C | `be4965f244fa77efb63edeacd17e9e3eb38926952fd3f0c0c009914592625387` | `550dfcf5c9b2a3dd48890d60b80b892c67928b33094a832be140788a3a884f74` | 609 | 15.749 | No change |

Every receipt and all declared materials verified. Private candidates and raw
responses remain private.

## Existing executions -- not a matched model comparison

| Model | Task / harness | Actual calls | Proposal | Functional evaluation | Outcome |
|---|---|---:|---|---|---|
| Base | hello fixture / diff | 1 | Rejected | Candidate tests not run | PATCH_REJECTED |
| Base | hello fixture / FIM body | 1 | Applied | Baseline 1; candidate 1 | REPAIR_NOT_VERIFIED |
| OctoCoder | hello fixture / Question/Answer diff | 1 | Applied | Baseline 1; candidate 0 | REPAIR_VERIFIED **fixture only** |
| Base | S / whole-file source | 1 | No change | Baseline 1; candidate not run | PATCH_REJECTED |
| OctoCoder | S+C combined / diff | 3 | All rejected: incomplete diffs/missing closing marker | Baseline build 0/test 1; no candidate compiled or tested | PATCH_REJECTED, **zero verified fixes** |

Latest two-fix run:
`octocoder-xsystem-optional-outputs-v1-20261004`.
Receipt SHA-256:
`a235e5d7dde4f5d00e85447116eb9dbd288f60d23ae30e3ab09be3ac85405579`.
Signature and all three declared materials: PASS.
Detailed timing and token metrics remain in private evidence; performance
publication waits for useful repairs and the user's publication decision.
This measures **delivery failure before logic evaluation**, not incorrect
repair behavior.

## Evaluation rules

1. Require an independently reproduced failing baseline for each task.
2. Accept complete function/body source without diff arithmetic or custom
   BEGIN/END markers. Tolerate one complete code fence or an included outer
   closing brace; consume only the selected function, never continued unrelated
   source. Retain the entire raw response. Reject ambiguous/truncated output;
   never invent code.
3. Compile only in the no-network `colima-each-oracle` container with protected
   validators. Do not execute target code on the Mac host.
4. Report named case PASS/FAIL/NOT_RUN. A candidate that exits before returning
   case data is a failure, not a successful test process.
5. Distinguish FORMAT_REJECTED, BUILD_FAILED, TEST_FAILED, EXECUTION_ERROR and
   REPAIR_VERIFIED. Preserve every attempt and its exact private bytes.
6. Run terminal attribution audit only after behavioral success. Never return
   its matches to Builder. Missing coverage remains UNAVAILABLE.
7. Wait for useful repairs before performance publication. No upstream PR.

## Task tailoring learned from the four calls

Future EACH task construction should be model-specific but keep the same public
requirements and behavioral oracle:

- **StarCoderBase:** use body completion, not complete-function regeneration.
  Include the six public expected cases as a compact truth table. Its accepted
  full-function candidates preserved existing error cases but missed the
  positive optional-output behavior.
- **OctoCoder:** use body completion with the official HumanEvalFix ordering:
  `Question: Fix bugs in <entry point> + buggy function + public tests`,
  then `Answer:` and the unchanged function declaration. The generic complete-
  function instruction produced a no-op twice.
- Treat unchanged output as `NO_CHANGE`, not a formatting failure.
- A future repeat is a new approved batch. Do not silently consume deferred H2
  calls or expand the model list.

## CrystalCoder follow-up

CrystalCoder was subsequently authorized and evaluated because the two-model
matrix produced no verified repair. Exact checkpoint:
`LLM360/Crystal@34fc9cd58acd87002560379a95b432147cc9135a`;
artifact suffix `af277cbad887d6d0`. Full lineage and artifact evidence is in
`docs/model-qualifications/crystalcoder.md`.

Its original full-file FIM packet failed closed before generation because the
2,314-2,349 token inputs exceeded the model's declared 2,048-token window.
Function-only FIM reduced inputs to 554-567 tokens and ordinary code
continuation to 559-572 tokens. All generated attempts saturated their exact
512- or 1,024-token output budgets. The sandbox candidates were structurally
incomplete or failed compilation; console candidates failed compilation or
repeated the target signature and were rejected. No behavioral case ran.

| Model | Sandbox | Console | Distinct verified fixes |
|---|---|---|---:|
| CrystalCoder 7B | No compiling candidate | No compiling candidate | **0/2** |

This is a real negative capability result. The harness learned to preflight
context, reduce unrelated source, distinguish truncation from logic failure,
and switch from FIM to plain code continuation. It must not keep increasing
budgets when the model repeats instead of closing the selected function.

The final continuation repeat used the hardened local runtime with network and
private-file denial probes true. Secured receipt SHA-256 values are
`6e03d88280a48644d683a0c367ec11bda3f9b7098ff572942d9500b1a950e141`
(sandbox) and
`d635c463030f99fb26e8a5a51809932ef5aca94c14ed66a1c150a58fdb0f3da6`
(console). Sandbox failed its build; console repeated the selected signature
five times and was structurally rejected. Neither reached behavioral cases.

## K2-65B scale follow-up

K2 was selected after Granite Code 34B failed the strict lineage gate: Granite's
base card identifies an unpublished IBM-filtered FLAN variant and incompletely
enumerated phase-2 language bytes. K2 instead publishes its exact 13.235 TB
preprocessed two-stage sequence, preparation/training code and intermediate
checkpoints. Its mixed source licenses and non-commercial Pile-of-Law stage are
retained as limitations, not converted into legal clearance.

Exact K2 artifact:
`IFM/K2@400af6cd7de09fc9349cc6b5b24db20f778d5b72#sha256:8266ff62e09c6985`.
The 65.286B publisher model was verified, locally converted to 8-bit MLX and
run once per fixed task with no retry.

| Model | Sandbox | Console | Distinct verified fixes |
|---|---|---|---:|
| K2-65B 8-bit | Candidate compiled; **4/6 cases PASS** | Candidate compiled; **3/6 cases PASS** | **0/2** |

This is the first 65B-class result in the ledger. It confirms that larger scale
alone does not solve the optional-output contract. Signed private receipt
SHA-256 values are
`48455a8ac3236aeb4a7852c21294cc2dca25e63cce93b7300d3233cb4fdd8507`
(sandbox) and
`be6d4f51352b40c8eb5907d54c9b930f55bd10f6df80fd44c80e7266894c0a7a`
(console).

## CodeGen2.5 clean code-specialist follow-up

The `mono` checkpoint was rejected because its additional Python stage is not
identified. The selected `Salesforce/codegen25-7b-multi_P` checkpoint is
Apache-2.0 and trained only on the already-inspected StarCoderData stage for
1.4T tokens using repeated epochs and deterministic span-corruption/infill
transformations.

| Model | Sandbox | Console | Distinct verified fixes |
|---|---|---|---:|
| CodeGen2.5-7B-multi 8-bit | Candidate compiled; **1/6 cases PASS** | Signature repeated three times; cases NOT RUN | **0/2** |

Exact artifact suffix: `e164c1a2b77be037`. Private signed receipt SHA-256
values:
`4d693cfa2fb7392545ae549a148d462d17435a22258152342f981e4ac47524d2`
(sandbox) and
`f4c8ebed0f22d113ec5f3b378b27d83fed99cea4c7902c7cc7fc144dc24db485`
(console). Strong HumanEval publication results did not transfer to this
optional-output C repair matrix.

These recommendations are encoded by
`each.xodus_shadow.recommended_xodus_task_profile`; unknown/unqualified models
fail closed rather than inheriting one of these profiles.

The oracle measures extracted C functions with independent ABI stubs, not a
native Windows GDK library, full Wine DLL or whole-game success.
The protected parent rejects a premature child exit or missing case data.
This is not cryptographic authentication of a hostile native program's API
returns; arbitrary malicious native code and same-user interference remain
outside the claimed assurance. Do not relabel the production oracle gap PASS.

## External harness and social evidence

- **Official OctoCoder tooling:** [OctoPack](https://github.com/bigcode-project/octopack)
  supplies training and **BigCode evaluation-harness** instructions, not a
  Pi/OpenCode agent. The [pinned model card](https://huggingface.co/bigcode/octocoder/blob/0f863c63e38ba80fc2c4010f34a7f46d537a9eee/README.md)
  prescribes Question/Answer and reports small-function repair benchmarks.
  Those are publisher results, not EACH/Xodus performance.
- **Independent signal:** [OctoCode-eval](https://github.com/Kirili4ik/OctoCode-eval)
  reports Python HumanEvalFix pass@1 of 31.4 using benchmark-style evaluation.
  It is not a Pi/OpenCode or Xodus result.
- **Pi:** [official model documentation](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/models.md)
  supports compatible local endpoints. Endpoint compatibility alone does not
  establish reliable tool use by these two checkpoints.
- **OpenCode:** [official model documentation](https://opencode.ai/docs/models/)
  says only some models are good at both code generation and tool calling.
  No verified OctoCoder-specific improvement was found in this bounded search.

No external tool-loop installation was used. External harnesses are
**investigated, not installed/evaluated**. The useful idea copied from the
official BigCode evaluator is task shaping—buggy function plus tests and the
model's native prompt—not an autonomous tool loop.
