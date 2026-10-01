# EACH development

Read `docs/EACH_BOOTSTRAP_MANDATE.md` and
`docs/EACH_MILESTONE_PROMPTS.md` before implementation. The authoritative
milestones are in sections 121-131 of the mandate.

The user explicitly authorized autonomous progression through **M0-M8**.
Complete and verify each milestone before advancing. This overrides the
handoff's initial M0/M1 stopping instruction, not its acceptance criteria or
information-flow boundaries.

EACH produces authoring-provenance evidence, not legal certification.
The harness may be developed with Copilot/Architrave; target generation must
use the declared FixtureModel or local model, never the outer cloud agent.
Keep the Auditor terminal and target artifacts private by default.

Use the Architrave knowledge profile, durable Run state, small vertical slices,
deterministic gates, and independent adversarial review. Do not build a UI,
daemon, database, RAG system, hosted backend, or custom cryptography.
Never publish model weights, credentials, signing keys, private target patches,
or an upstream Xodus PR.

Do not fabricate human approval of a sensitive spec, accept gated-model terms
on the user's behalf, or convert unavailable evidence into PASS. Record a
genuine blocker and continue only independent work permitted by the mandate.

The development execution host is the user's Apple Silicon Mac, reached as
`m5.hont.ro` over SSH. The Windows app workspace is the coordination checkout.
Use dedicated feature checkouts, never overwrite another project's files, and
never run imported target code on the host in strong mode.
