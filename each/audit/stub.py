"""M1 audit stub: explicit UNAVAILABLE status for all audit checks.

Real provenance audit is implemented in a later milestone. This module
exists so every receipt has a consistent `audit` section from M1 onward,
and so "not yet implemented" is never silently indistinguishable from
"passed" (see docs/EACH_BOOTSTRAP_MANDATE.md on audit honesty).
"""

from __future__ import annotations

AUDIT_CHECKS = (
    "signature-presence",
    "material-declaration-consistency",
    "license-compatibility",
    "provenance-chain",
)


def audit_stub() -> dict[str, object]:
    return {
        "result": "UNAVAILABLE",
        "reason": "audit implementation not yet built (scheduled for a later milestone)",
        "checks": {name: "UNAVAILABLE" for name in AUDIT_CHECKS},
    }
