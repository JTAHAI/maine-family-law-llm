from __future__ import annotations
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.clock_skew import ClockSkewError, ClockSkewMonitor
from maine_family_law_llm import api

def _headers(): return {'X-User-Role':'reviewer','X-Tenant-Id':'fictional-tenant','X-MFLL-Client-Session':'a'*48}
def test_pass148_detects_material_skew_without_network_or_rewriting(tmp_path:Path):
 wall=[1000.0];mono=[10.0];m=ClockSkewMonitor(tmp_path,encryption_key='fictional-clock-key',session_id='same-session',wall_clock=lambda:wall[0],monotonic_clock=lambda:mono[0])
 assert m.check(actor_role='reviewer',tenant_id='fictional-tenant')['status']=='baseline_established'
 wall[0]=1010.;mono[0]=20.;assert m.check(actor_role='reviewer',tenant_id='fictional-tenant')['status']=='within_tolerance'
 wall[0]=2000.;mono[0]=30.;report=m.check(actor_role='reviewer',tenant_id='fictional-tenant')
 assert report['material_skew_detected'] is True and report['timestamps_rewritten'] is False and report['network_time_checked'] is False
 assert set(report['affected_review_domains'])=={'audit_ordering','deadline_candidates','authority_freshness','timestamp_certificates'}
 assert m.verify()['audit_chain_valid'] is True and str(tmp_path).encode() not in m.path.read_bytes()
 with pytest.raises(ClockSkewError,match='tenant_mismatch'):m.check(actor_role='reviewer',tenant_id='other-tenant')
def test_pass148_canonical_route_ui_and_inventory(monkeypatch:pytest.MonkeyPatch,tmp_path:Path):
 matter=tmp_path/'fictional-matter';matter.mkdir();monkeypatch.setenv('MAINE_MATTER_STORE_KEY','fictional-clock-key');monkeypatch.setattr(api,'active_case_root',lambda:matter)
 response=TestClient(api.app).get('/api/runtime/clock-skew',headers=_headers());assert response.status_code==200;assert response.json()['timestamps_rewritten'] is False
 root=Path(__file__).resolve().parents[1]
 for relative in ('src/maine_family_law_llm/ui','maine_family_law_llm/ui'):
  assert 'id="clock-skew-refresh"' in (root/relative/'workbench.html').read_text(encoding='utf-8');assert '/api/runtime/clock-skew' in (root/relative/'workbench.js').read_text(encoding='utf-8')
 registered={(method,str(route.path)) for route in production_app.routes for method in (getattr(route,'methods',None) or set()) if method not in {'HEAD','OPTIONS'}}
 assert EndpointInventory().compare_to_registered(registered,surface='production')['status']=='pass'
