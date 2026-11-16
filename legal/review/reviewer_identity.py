"""Operator-provisioned, offline reviewer authentication for filing decisions."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass

_HEX = re.compile(r"[a-f0-9]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")
_MATTER = re.compile(r"[a-f0-9]{16}")


@dataclass(frozen=True)
class ReviewerPrincipal:
    reviewer_id: str
    tenant_id: str
    matter_id: str
    generation: str

    def binding(self) -> dict[str, str]:
        return {
            "reviewer_id": self.reviewer_id, "tenant_id": self.tenant_id,
            "matter_id": self.matter_id, "credential_generation": self.generation,
        }


def _configured() -> tuple[ReviewerPrincipal, str] | None:
    reviewer, tenant, matter, verifier = (
        os.environ.get("MFL_FILING_REVIEWER_" + key, "").strip()
        for key in ("ID", "TENANT", "MATTER_ID", "BEARER_SHA256")
    )
    if not (_ID.fullmatch(reviewer) and _ID.fullmatch(tenant) and _MATTER.fullmatch(matter)
            and _HEX.fullmatch(verifier)):
        return None
    # Domain separation prevents this persisted fingerprint being used as the
    # credential verifier. Rotation or removing configuration revokes approval.
    generation = hashlib.sha256(("mfl-filing-review-v1:" + verifier).encode("ascii")).hexdigest()
    return ReviewerPrincipal(reviewer, tenant, matter, generation), verifier


def authenticate_reviewer(headers: list[str], *, tenant_id: str, matter_id: str) -> ReviewerPrincipal:
    configured = _configured()
    match = re.fullmatch(r"Bearer ([a-f0-9]{64})", headers[0]) if len(headers) == 1 else None
    if configured and match:
        principal, verifier = configured
        digest = hashlib.sha256(match[1].encode("ascii")).hexdigest()
        if (principal.tenant_id == tenant_id and principal.matter_id == matter_id
                and hmac.compare_digest(verifier, digest)):
            return principal
    raise ValueError("filing_reviewer_authentication_required")


def reviewer_binding_current(binding: object, *, matter_id: str) -> bool:
    configured = _configured()
    return bool(configured and configured[0].matter_id == matter_id and configured[0].binding() == binding)


def configured_filing_tenant(matter_id: str) -> str | None:
    configured = _configured()
    return configured[0].tenant_id if configured and configured[0].matter_id == matter_id else None
