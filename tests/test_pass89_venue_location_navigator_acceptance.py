from pathlib import Path
from fastapi.testclient import TestClient
from legal.matter.venue_location_navigator import VenueLocationNavigatorStore
from maine_family_law_llm import api as api_module
def authority():return {"authority_id":"authority_001","source_id":"fictional-official-court-source","source_hash":"a"*64,"citation":"Fictional court location source","title":"Fictional official court location","freshness_status":"fresh"}
def payload():return {"workspace_id":"venue_location_001","reviewer_safe_id":"reviewer_001","location_label":"Fictional public court location","contact_label":"Fictional public contact","unresolved_facts":["Residency fact requires review."],"authority_source_id":"fictional-official-court-source","user_confirmed":True}
def test_pass89_encrypted_navigator_is_non_determinative(tmp_path:Path):
 root=tmp_path/"m";root.mkdir();s=VenueLocationNavigatorStore(root,encryption_key="fictional-test-key");w=s.create(payload(),authority=authority());assert w["venue_determined"] is False and w["filing_ready"] is False;assert "Fictional public court location" not in s.path.read_text(encoding="utf-8");assert s.source("venue_location_001")["source"]["lane"]=="official_authority"
def test_pass89_requires_confirmation(tmp_path:Path):
 root=tmp_path/"m";root.mkdir();s=VenueLocationNavigatorStore(root,encryption_key="fictional-test-key")
 try:s.create(payload()|{"user_confirmed":False},authority=authority())
 except Exception as exc:assert str(exc)=="venue_location_confirmation_required"
 else:raise AssertionError("confirmation required")
def test_pass89_api_and_production_assets(monkeypatch,tmp_path:Path):
 a,b=tmp_path/"a",tmp_path/"b";a.mkdir();b.mkdir();active={"root":a};monkeypatch.setattr(api_module,"active_case_root",lambda:active["root"]);monkeypatch.setattr(api_module,"inspect_source",lambda _:{"status":"pass","source_card":{**authority(),"source_span_preview":"Fictional span"}});monkeypatch.setenv("MAINE_MATTER_STORE_KEY","fictional-test-key");c=TestClient(api_module.app);assert c.post("/api/venue-location-workspaces",json=payload()).status_code==200;assert c.get("/api/venue-location-workspaces/venue_location_001/authority/source").status_code==200;active["root"]=b;assert c.get("/api/venue-location-workspaces/venue_location_001").status_code==404;assert Path("src/maine_family_law_llm/api.py").read_bytes()==Path("maine_family_law_llm/api.py").read_bytes();t=Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8");assert "Venue and court-location navigator" in t and "/api/venue-location-workspaces" in t
