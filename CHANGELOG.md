# Changelog

## Unreleased

- Add a public, reproducible model-artifact provisioner for the large evaluated
  checkpoints without publishing weights.
- Expand behavioral evaluation beyond the two optional-output functions while
  preserving fixed baselines and private raw outputs.
- Reduce macOS-specific setup friction and add tested support for another host
  platform without weakening the isolation claim.

## v0.1.0-alpha.1 — first public preview

### Shipped

- Local CLI with environment diagnostics, immutable specs, scoped patch
  application, receipt verification and deterministic `hello-repair` demo.
- No-egress container executor with pinned image identity, scrubbed environment,
  protected validator mounts and per-run isolation evidence.
- Hash-bound private receipts with Ed25519 signatures and optional retained-file
  verification.
- Terminal attribution audit architecture: audit findings are never returned to
  the Builder.
- Exact-checkpoint model registry and sanitized exploratory results for
  StarCoderBase, OctoCoder, CrystalCoder, K2 and CodeGen2.5-multi.
- macOS CI for dependency lock, package build, Ruff, unit/adversarial tests and
  `each doctor`.

### Release hygiene

- Root Apache-2.0 license and third-party MIT/Apache/LGPL source notices
  inventoried.
- Gitleaks 8.30.1 used for full-history and working-tree scans. Generic-key
  findings were manually reviewed as published SHA-256 artifact pins; no live
  credential was identified. This scan reduces risk but does not prove absence.
- No model weights, private run directories, signing keys, credentials or
  private Xodus patches are release assets.

### Known limitations

- Experimental preview, not production qualified.
- Deterministic fixture success does not demonstrate neural-model usefulness.
- The published Xodus matrix contains **zero complete verified fixes**.
- Local-model evaluation is Apple-Silicon-specific and requires separately
  reviewed, locally provisioned weights.
- Dataset inspectability and model-weight licenses do not provide blanket
  source-code, generated-output or legal clearance.
- External corpus-membership and license-scanning coverage remains incomplete.

See [`docs/claims-and-nonclaims.md`](docs/claims-and-nonclaims.md),
[`docs/threat-model.md`](docs/threat-model.md) and
[`docs/two-model-evaluation-ledger.md`](docs/two-model-evaluation-ledger.md).
