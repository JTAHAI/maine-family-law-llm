"""Synthetic declaration tests, not artifact or model quality qualification."""

import base64
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.fast_interchange.admission import AdmissionAuthority, AdmissionError, canonical, digest
from legal.fast_interchange.compact_admission import CompactDeclarationVerifier


@pytest.fixture
def compact(tmp_path, monkeypatch):
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", str(tmp_path / "vault"))
    private = Ed25519PrivateKey.generate()  # Ephemeral synthetic test key, never exported.
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    trust = dict(
        schema_version="fast_interchange_admission_trust_v1",
        revision=1,
        minimum_catalog_sequence=1,
        trusted_keys={
            "fictional-test-key": dict(
                public_key_base64=base64.b64encode(
                    private.public_key().public_bytes_raw()
                ).decode(),
                not_before=past,
                expires_at=future,
                test_only=True,
            )
        },
        revoked_key_ids=[],
        revoked_release_ids=[],
        approved_download_origins=[],
    )
    trust_path = tmp_path / "trust.json"
    trust_path.write_bytes(canonical(trust))
    authority = AdmissionAuthority(
        trust_path=trust_path, state_root=tmp_path / "state", allow_test_keys=True
    )
    model = dict(
        schema_version="compact_file_inventory_v1",
        kind="model",
        files=[dict(path="model.safetensors", bytes=100, sha256="a" * 64, role="weights")],
    )
    runtime = dict(
        schema_version="compact_file_inventory_v1",
        kind="runtime",
        files=[dict(path="python.exe", bytes=200, sha256="b" * 64, role="runtime")],
    )
    grant = dict(
        release_id="fictional-release",
        model_id="fictional-model",
        scope="development",
        task=dict(
            kind="typed_source_field_review",
            capability="evidence_review",
            runtime_abi="compact_span_research_v1",
            field_type="clock_time",
            basis="reported_event",
            policy_sha256="c" * 64,
        ),
        model_inventory_sha256=digest(model),
        runtime=dict(
            format="python_cpu_safetensors",
            inventory_sha256=digest(runtime),
            qualification_report_sha256=None,
            qualification_status="inventory_only",
            execution_device="cpu",
            precision="fp32",
            max_context_tokens=512,
            max_resident_bytes=3 * 1024**3,
        ),
        rights=dict(
            license_identifiers=["SYNTHETIC-NOT-A-MODEL"],
            rights_evidence_sha256="d" * 64,
            notices_inventory_sha256="e" * 64,
            redistribution_permitted=True,
        ),
        evaluation=dict(
            dataset_kind="synthetic",
            sample_count=1,
            report_sha256="f" * 64,
            dataset_sha256="1" * 64,
            reviewer_approval_sha256=None,
        ),
        review_required=True,
        promotion_authority=False,
    )
    payload = dict(
        schema_version="compact_admission_declaration_v1",
        catalog_id="compact-fictional",
        sequence=1,
        published_at=past,
        expires_at=future,
        grants=[grant],
    )

    def sign(value):
        return dict(
            payload=deepcopy(value),
            key_id="fictional-test-key",
            signature_base64=base64.b64encode(private.sign(canonical(value))).decode(),
        )

    return dict(
        authority=authority,
        trust=trust,
        trust_path=trust_path,
        model=model,
        runtime=runtime,
        payload=payload,
        sign=sign,
        policies={"typed_source_field_review:clock_time:reported_event": "c" * 64},
    )


def verify(f, envelope=None, authority=None):
    return CompactDeclarationVerifier(authority or f["authority"]).verify(
        envelope if envelope is not None else f["sign"](f["payload"]),
        model_inventory=f["model"],
        runtime_inventory=f["runtime"],
        expected_policies=f["policies"],
    )


def grant(f):
    return f["payload"]["grants"][0]


def test_verified_declaration_is_not_artifact_runtime_or_production_admission(compact):
    result = verify(compact)
    assert result["selected_bytes"] == 300
    assert result["declaration_signature_verified"] is True
    assert result["review_required"] is True
    for key in ("artifact_bytes_verified", "runtime_qualified", "production_admitted", "runnable"):
        assert result[key] is False
    assert result["grants"][0]["evaluation"]["reviewer_approval_sha256"] is None
    path = compact["authority"].state_path
    assert b"compact-fictional" not in path.read_bytes()
    before = path.read_bytes(), path.stat().st_mtime_ns
    verify(compact)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize(
    "path,value",
    [
        (("task", "field_type"), "money"),
        (("task", "basis"), "source_field"),
        (("task", "policy_sha256"), "2" * 64),
        (("task", "runtime_abi"), "fast_interchange_hotswap_v1"),
        (("task", "capability"), "drafting"),
        (("task", "extra"), "untrusted"),
        (("runtime", "execution_device"), "cuda"),
        (("runtime", "max_context_tokens"), 513),
        (("runtime", "max_resident_bytes"), 3 * 1024**3 + 1),
        (("runtime", "qualification_status"), "qualified"),
        (("runtime", "inventory_sha256"), "3" * 64),
        (("rights", "redistribution_permitted"), False),
        (("rights", "license_identifiers"), [""]),
        (("evaluation", "sample_count"), True),
        (("evaluation", "dataset_kind"), "attorney_reviewed"),
        (("evaluation", "report_sha256"), "not-a-hash"),
        (("model_inventory_sha256",), "4" * 64),
        (("scope",), "production"),
        (("review_required",), False),
        (("review_required",), 1),
        (("promotion_authority",), 0),
        (("promotion_authority",), True),
        (("extra",), "unknown"),
    ],
)
def test_signed_invalid_or_wrong_task_declarations_fail_without_state(compact, path, value):
    node = grant(compact)
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(AdmissionError):
        verify(compact)
    assert not compact["authority"].state_path.exists()


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/absolute",
        "C:/escape",
        "a\\b",
        "CON.txt",
        "a/NUL",
        "a/../b",
        "a//b",
        "a./b",
        "name:stream",
        "file ",
        "ü.txt",
    ],
)
def test_unsafe_inventory_names_fail(compact, path):
    compact["model"]["files"][0]["path"] = path
    grant(compact)["model_inventory_sha256"] = digest(compact["model"])
    with pytest.raises(AdmissionError, match="compact_declaration_invalid"):
        verify(compact)


@pytest.mark.parametrize("kind", ["model", "runtime"])
@pytest.mark.parametrize(
    "change", ["case_duplicate", "ancestor", "oversize", "zero", "boolean", "wrong_role", "tamper"]
)
def test_inventory_closure_declaration_rejects_ambiguity(compact, kind, change):
    inventory = compact[kind]
    row = inventory["files"][0]
    if change in {"case_duplicate", "ancestor"}:
        other = deepcopy(row)
        other["role"] = "notice"
        other["path"] = (
            row["path"].upper() if change == "case_duplicate" else row["path"] + "/child"
        )
        inventory["files"].append(other)
    elif change in {"oversize", "zero", "boolean"}:
        row["bytes"] = {"oversize": 1_500_000_000, "zero": 0, "boolean": True}[change]
    elif change == "wrong_role":
        row["role"] = "notice"  # Missing weights/runtime, respectively.
    else:
        row["sha256"] = "0" * 64
    if change != "tamper":
        if kind == "model":
            grant(compact)["model_inventory_sha256"] = digest(inventory)
        else:
            grant(compact)["runtime"]["inventory_sha256"] = digest(inventory)
    if kind == "runtime" and change == "zero":
        # Real distributions contain empty __init__.py and py.typed files.
        # Actual bytes/hash still require the separate locked verifier.
        assert verify(compact)["selected_bytes"] == 100
    else:
        with pytest.raises(AdmissionError):
            verify(compact)


def test_combined_runtime_and_model_strictly_under_limit(compact):
    compact["model"]["files"][0]["bytes"] = 800_000_000
    compact["runtime"]["files"][0]["bytes"] = 700_000_000
    grant(compact)["model_inventory_sha256"] = digest(compact["model"])
    grant(compact)["runtime"]["inventory_sha256"] = digest(compact["runtime"])
    with pytest.raises(AdmissionError, match="compact_dependency_size_limit"):
        verify(compact)


def test_unsigned_tampered_or_oversized_envelope_never_advances(compact):
    envelope = compact["sign"](compact["payload"])
    envelope["payload"]["sequence"] = 2
    for bad in (envelope, {}, {"junk": "x" * 256_001}):
        with pytest.raises(AdmissionError, match="compact_declaration_invalid"):
            verify(compact, bad)
    assert not compact["authority"].state_path.exists()


@pytest.mark.parametrize(
    "change,error",
    [
        ("revoke_key", "signing_key_untrusted"),
        ("revoke_release", "release_revoked"),
        ("unknown_key", "signing_key_untrusted"),
        ("expired_key", "signing_key_expired"),
        ("expired_catalog", "catalog_expired_or_future"),
        ("future_catalog", "catalog_expired_or_future"),
        ("test_key", "test_signer_forbidden"),
    ],
)
def test_trust_denials(compact, change, error):
    envelope = compact["sign"](compact["payload"])
    if change == "revoke_key":
        compact["trust"]["revoked_key_ids"] = [envelope["key_id"]]
    elif change == "revoke_release":
        compact["trust"]["revoked_release_ids"] = [grant(compact)["release_id"]]
    elif change == "unknown_key":
        envelope["key_id"] = "unknown-key"
    elif change == "expired_key":
        compact["trust"]["trusted_keys"][envelope["key_id"]]["expires_at"] = compact["payload"][
            "published_at"
        ]
    elif change == "expired_catalog":
        compact["payload"]["expires_at"] = compact["payload"]["published_at"]
        envelope = compact["sign"](compact["payload"])
    elif change == "future_catalog":
        compact["payload"]["published_at"] = compact["payload"]["expires_at"]
        envelope = compact["sign"](compact["payload"])
    else:
        compact["authority"].allow_test_keys = False
    compact["trust_path"].write_bytes(canonical(compact["trust"]))
    with pytest.raises(AdmissionError, match=error):
        verify(compact, envelope)
    assert not compact["authority"].state_path.exists()


def test_production_denied_even_with_claimed_human_native_evidence_and_non_test_key(compact):
    compact["trust"]["trusted_keys"]["fictional-test-key"]["test_only"] = False
    compact["trust_path"].write_bytes(canonical(compact["trust"]))
    grant(compact)["scope"] = "production"
    grant(compact)["evaluation"].update(
        dataset_kind="attorney_reviewed", reviewer_approval_sha256="9" * 64
    )
    grant(compact)["runtime"].update(
        qualification_status="qualified", qualification_report_sha256="8" * 64
    )
    with pytest.raises(AdmissionError, match="compact_production_qualification_not_implemented"):
        verify(compact)


def test_rollback_conflict_inspection_and_invalid_nonadvancement(compact):
    verify(compact, authority=compact["authority"].inspection_only())
    assert not compact["authority"].state_path.exists()
    compact["payload"]["sequence"] = 2
    verify(compact)
    before = compact["authority"].state_path.read_bytes()
    compact["payload"]["sequence"] = 1
    with pytest.raises(AdmissionError, match="catalog_rollback"):
        verify(compact, authority=compact["authority"].inspection_only())
    compact["payload"]["sequence"] = 2
    grant(compact)["evaluation"]["sample_count"] = 2
    with pytest.raises(AdmissionError, match="catalog_sequence_conflict"):
        verify(compact)
    compact["payload"]["sequence"] = 3
    grant(compact)["task"]["field_type"] = "money"
    with pytest.raises(AdmissionError, match="policy_binding_mismatch"):
        verify(compact)
    assert compact["authority"].state_path.read_bytes() == before


def test_ranker_requires_own_policy_and_abi(compact):
    grant(compact)["task"] = dict(
        kind="record_passage_ranking",
        capability="evidence_review",
        runtime_abi="compact_ranker_research_v1",
        policy_sha256="7" * 64,
    )
    with pytest.raises(AdmissionError, match="policy_binding_mismatch"):
        verify(compact)
    compact["policies"] = {"record_passage_ranking": "7" * 64}
    assert verify(compact)["runnable"] is False


def test_duplicate_grants_rejected(compact):
    compact["payload"]["grants"].append(deepcopy(grant(compact)))
    with pytest.raises(AdmissionError, match="compact_duplicate_grant"):
        verify(compact)


def test_corrupted_state_cannot_be_silently_reinitialized(compact):
    verify(compact)
    compact["authority"].state_path.write_bytes(b"{}")
    with pytest.raises(AdmissionError, match="admission_state_unavailable"):
        verify(compact)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"payload":{},"payload":{}}',
        b'{"n":NaN}',
        b"\xff",
        b"[]",
        b'{"x":' + b"[" * 14 + b"0" + b"]" * 14 + b"}",
    ],
)
def test_untrusted_raw_json_rejects_ambiguity_and_complexity(compact, raw):
    with pytest.raises(AdmissionError, match="compact_declaration_invalid"):
        verify(compact, raw)
    assert not compact["authority"].state_path.exists()


def test_signed_raw_bytes_preserve_exact_declaration_semantics(compact):
    envelope = canonical(compact["sign"](compact["payload"]))
    compact["model"] = canonical(compact["model"])
    compact["runtime"] = canonical(compact["runtime"])
    assert verify(compact, envelope)["selected_bytes"] == 300


def test_trust_revision_rollback_fails_closed(compact):
    compact["trust"]["revision"] = 2
    compact["trust_path"].write_bytes(canonical(compact["trust"]))
    verify(compact)
    compact["trust"]["revision"] = 1
    compact["trust_path"].write_bytes(canonical(compact["trust"]))
    with pytest.raises(AdmissionError, match="trust_rollback"):
        verify(compact)


@pytest.mark.parametrize(
    "section,key",
    [
        ("rights", "rights_evidence_sha256"),
        ("rights", "notices_inventory_sha256"),
        ("evaluation", "dataset_sha256"),
        ("evaluation", "report_sha256"),
    ],
)
def test_signature_binds_rights_and_evaluation(compact, section, key):
    envelope = compact["sign"](compact["payload"])
    envelope["payload"]["grants"][0][section][key] = "0" * 64
    with pytest.raises(AdmissionError, match="compact_declaration_invalid"):
        verify(compact, envelope)
    assert not compact["authority"].state_path.exists()
