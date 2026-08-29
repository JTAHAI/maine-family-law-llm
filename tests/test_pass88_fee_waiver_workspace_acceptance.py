from pathlib import Path
from fastapi.testclient import TestClient
from legal.matter.fee_waiver_workspace import FeeWaiverWorkspaceStore
from maine_family_law_llm import api as api_module


def _authority(): return {"authority_id":"authority_001","source_id":"fictional-official-fee-source","source_hash":"a"*64,"citation":"Fictional fee source fixture","title":"Fictional official fee source","exact_span":"Fictional exact span.","freshness_status":"fresh"}
def _payload(): return {"workspace_id":"fee_waiver_001","reviewer_safe_id":"reviewer_001","purpose_label":"Fictional fee question","authority_source_id":"fictional-official-fee-source","facts":[{"fact_id":"fact_001","label":"Household size","user_entered_value":"Fictional user-entered value"}],"user_confirmed":True}


def test_pass88_encrypted_workspace_keeps_facts_unverified(tmp_path: Path):
    root=tmp_path/"fictional-matter";root.mkdir();store=FeeWaiverWorkspaceStore(root,encryption_key="fictional-test-key")
    workspace=store.create(_payload(),authority=_authority())
    assert workspace["eligibility"] == "not_determined" and workspace["filing_ready"] is False
    assert workspace["facts"][0]["state"] == "user_entered_unverified"
    assert "Fictional user-entered value" not in store.path.read_text(encoding="utf-8")
    assert store.source("fee_waiver_001")["source"]["lane"] == "official_authority"


def test_pass88_refuses_unconfirmed_and_duplicate_facts(tmp_path: Path):
    root=tmp_path/"fictional-matter";root.mkdir();store=FeeWaiverWorkspaceStore(root,encryption_key="fictional-test-key")
    try: store.create(_payload()|{"user_confirmed":False},authority=_authority())
    except Exception as exc: assert str(exc)=="fee_waiver_confirmation_required"
    else: raise AssertionError("confirmation is required")
    duplicate=_payload();duplicate["facts"]=[{"fact_id":"fact_001","label":"A","user_entered_value":"x"},{"fact_id":"fact_001","label":"B","user_entered_value":"y"}]
    try: store.create(duplicate,authority=_authority())
    except Exception as exc: assert str(exc)=="fee_waiver_fact_duplicate"
    else: raise AssertionError("duplicate user-entered fact must fail closed")


def test_pass88_canonical_api_resolves_authority_and_scopes_workspace(monkeypatch,tmp_path:Path):
    a,b=tmp_path/"a",tmp_path/"b";a.mkdir();b.mkdir();active={"root":a};monkeypatch.setattr(api_module,"active_case_root",lambda:active["root"]);monkeypatch.setattr(api_module,"inspect_source",lambda _:{"status":"pass","source_card":{**_authority(),"source_span_preview":"Fictional exact span."}});monkeypatch.setenv("MAINE_MATTER_STORE_KEY","fictional-test-key")
    client=TestClient(api_module.app);created=client.post("/api/fee-waiver-workspaces",json=_payload());assert created.status_code==200
    source=client.get("/api/fee-waiver-workspaces/fee_waiver_001/authority/source");assert source.status_code==200 and source.json()["source"]["citation"]=="Fictional fee source fixture"
    active["root"]=b;assert client.get("/api/fee-waiver-workspaces/fee_waiver_001").status_code==404


def test_pass88_production_assets_are_mirrored_and_operable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes()==Path("maine_family_law_llm/api.py").read_bytes();assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes()==Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text=Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8");assert "Fee and waiver information" in text and "/api/fee-waiver-workspaces" in text and "Create information workspace" in text
