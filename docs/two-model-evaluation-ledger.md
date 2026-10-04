# Two-model repair evaluation ledger

Scope: **StarCoderBase and OctoCoder only**. This ledger separates proposal
delivery from behavioral correctness. Receipt integrity is not repair success.
Private sources, completions, candidates and Auditor findings stay private.
Results are not production, legal, Wine or Xodus certification.

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

## Harnesses and repeat matrix

| Harness profile | Builder output | Model-native prompt | What changes |
|---|---|---|---|
| H1: function replacement | Complete selected function, not a diff or whole file | Base: FIM; OctoCoder: documented Question/Answer | Runner derives the diff mechanically |
| H2: function-body completion | Selected function body, with original signature and surrounding file retained | Base: FIM; OctoCoder: documented Question/Answer | Less output to reproduce; same behavioral tests |

These are **two concrete EACH harness profiles**, not claims that Pi,
OpenCode or the original BigCode evaluator has been executed. The same oracle,
source, requirements and isolation apply to both profiles. One completion per
model/task/profile gives eight cells; failures remain in the denominator.

| Model | S / H1 | S / H2 | C / H1 | C / H2 |
|---|---|---|---|---|
| StarCoderBase | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| OctoCoder | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

Each cell records exact Spec/material hashes, model/runtime identity, actual
prompt/output, sampling, input tokens, response characters, completion time,
proposal acceptance, build exit, named behavioral cases, audit execution,
receipt verification and private evidence references. Missing metrics remain
UNAVAILABLE. Do not count four passing cells as four distinct fixes: S and C
are only **two distinct issues**.

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

Therefore the first meaningful comparison is H1 versus H2 above, not installing
a tool loop and assuming that it improves capability. External harnesses are
**investigated, not installed/evaluated**. Do not report otherwise.
