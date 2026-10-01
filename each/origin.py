"""Evidence origin classification for spec packets.

Per docs/EACH_BOOTSTRAP_MANDATE.md section 30/125: every fact that can end
up in a sensitive spec must carry an origin tag, and a sensitive spec must
be able to reject material whose origin is ``MODEL_INFERENCE``,
``UNKNOWN``, or ``RESTRICTED`` — no matter how that material arrived
(including an LLM "Scout" or raw issue text).
"""

from __future__ import annotations

from enum import Enum


class Origin(str, Enum):
    PUBLIC_API_DOC = "PUBLIC_API_DOC"
    PUBLIC_HEADER = "PUBLIC_HEADER"
    PUBLIC_OPEN_SOURCE = "PUBLIC_OPEN_SOURCE"
    PUBLIC_ISSUE = "PUBLIC_ISSUE"
    BLACK_BOX_OBSERVATION = "BLACK_BOX_OBSERVATION"
    USER_ASSERTION = "USER_ASSERTION"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    UNKNOWN = "UNKNOWN"
    RESTRICTED = "RESTRICTED"


# A sensitive spec must reject material carrying any of these origins.
SENSITIVE_REJECTED_ORIGINS = frozenset({Origin.MODEL_INFERENCE, Origin.UNKNOWN, Origin.RESTRICTED})


class SensitiveOriginRejected(RuntimeError):
    """Raised when a sensitive spec's material set contains a rejected origin."""


def check_sensitive_origins(material_origins: dict[str, Origin], *, sensitive: bool) -> None:
    """Enforce the sensitive-spec origin policy.

    ``material_origins`` maps a material/field name (e.g. ``"problem_statement"``)
    to the :class:`Origin` it was actually recorded with. Only applies when
    ``sensitive`` is True; non-sensitive specs may carry any origin (they are
    expected to still declare it honestly for the receipt).
    """
    if not sensitive:
        return
    rejected = {name: origin for name, origin in material_origins.items() if origin in SENSITIVE_REJECTED_ORIGINS}
    if rejected:
        detail = ", ".join(f"{name}={origin.value}" for name, origin in sorted(rejected.items()))
        raise SensitiveOriginRejected(f"sensitive spec rejects material with disallowed origin: {detail}")
