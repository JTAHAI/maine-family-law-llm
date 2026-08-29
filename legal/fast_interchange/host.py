"""Host-owned offline release selection; no UI paths, discovery or downloads."""

from __future__ import annotations

import os
from pathlib import Path

from .admission import AdmissionAuthority, digest
from .worker import FastInterchangeError, HotSwapRegistry


def load_operator_registry() -> HotSwapRegistry:
    names = {
        "root": "MFL_FAST_INTERCHANGE_ARTIFACT_ROOT",
        "release_registry": "MFL_FAST_INTERCHANGE_RELEASE_REGISTRY",
        "artifact_registry": "MFL_FAST_INTERCHANGE_ARTIFACT_REGISTRY",
        "admission_catalog": "MFL_FAST_INTERCHANGE_ADMISSION_CATALOG",
    }
    values = {key: os.environ.get(name, "") for key, name in names.items()}
    trust = os.environ.get("MFL_FAST_INTERCHANGE_ADMISSION_TRUST", "")
    state = os.environ.get("MFL_FAST_INTERCHANGE_STATE_ROOT", "")
    pack_root = os.environ.get("MFL_FAST_INTERCHANGE_PACK_ROOT", "")
    if pack_root and trust and state and not any(values.values()):
        from app.services.model_pack_service import load_active_pack

        try:
            return load_active_pack(
                Path(pack_root), AdmissionAuthority(trust_path=Path(trust), state_root=Path(state))
            )
        except Exception as exc:
            raise FastInterchangeError("fast_interchange_active_pack_unavailable") from exc
    if not all(values.values()) or not trust or not state:
        raise FastInterchangeError("fast_interchange_operator_admission_required")
    return HotSwapRegistry.load(
        **values,
        admission_authority=AdmissionAuthority(trust_path=Path(trust), state_root=Path(state)),
    )


def release_identity(registry, release, *, allow_test_only: bool = False) -> dict:
    selected = registry.select(release.model_id, allow_test_only=allow_test_only)
    if selected != release:
        raise FastInterchangeError("fast_interchange_release_binding_mismatch")
    identity = release.public()
    identity["runtime_abi"] = release.runtime_abi
    identity["prompt_template_sha256"] = release.prompt_template_sha256
    identity["evidence_basis"] = (
        "synthetic_test_only" if release.admission == "test_only" else "signed_admission"
    )
    identity["catalog_sha256"] = digest(registry.signed_catalog) if registry.signed_catalog else ""
    if release.admission != "test_only":
        grant = registry.admission(release)
        identity["admission_scope"] = grant.scope
        identity["evaluation_dataset_kind"] = grant.evaluation.dataset_kind
    return identity
