from __future__ import annotations
from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as api_module


def _rows():
    return [{"evidence_id":"A","title":"Fictional record A","source_hash":"a"*64,"text":"A","source_type":"note","page_number":1},{"evidence_id":"B","title":"Fictional record B","source_hash":"b"*64,"text":"B","source_type":"note","page_number":2}]


def test_entity_resolution_requires_explicit_confirmation_and_is_reversible(monkeypatch, tmp_path: Path):
    root=tmp_path/'fictional'; root.mkdir(); rows=_rows()
    monkeypatch.setattr(api_module,'active_case_root',lambda:root); monkeypatch.setattr(api_module,'load_case_search_records',lambda _:rows); client=TestClient(api_module.app)
    created=client.post('/api/evidence/entity-resolution/candidates',json={'candidate_id':'C','entity_label':'Fictional Person','left_record_id':'A','right_record_id':'B'})
    assert created.status_code==200 and created.json()['candidate']['merge_status']=='not_merged'
    bad=client.post('/api/evidence/entity-resolution/candidates/C/confirm',json={'confirmation':'guess'})
    confirmed=client.post('/api/evidence/entity-resolution/candidates/C/confirm',json={'confirmation':'confirm_same_entity','reviewer_notes':'fictional reviewer'})
    revoked=client.post('/api/evidence/entity-resolution/candidates/C/revoke',json={'reviewer_notes':'fictional correction'})
    assert bad.status_code==400 and bad.json()['detail']=='entity_resolution_explicit_confirmation_required'
    assert confirmed.status_code==200 and confirmed.json()['candidate']['merge_status']=='logical_merge_active'
    assert revoked.status_code==200 and revoked.json()['candidate']['merge_status']=='reversed'
    source=client.get('/api/evidence/entity-resolution/candidates/C/left/source')
    assert source.status_code==200 and len(source.json()['source']['source_token'])==64


def test_entity_resolution_rejects_foreign_or_same_record(monkeypatch, tmp_path: Path):
    root=tmp_path/'fictional'; root.mkdir(); rows=_rows()
    monkeypatch.setattr(api_module,'active_case_root',lambda:root); monkeypatch.setattr(api_module,'load_case_search_records',lambda _:rows); client=TestClient(api_module.app)
    foreign=client.post('/api/evidence/entity-resolution/candidates',json={'candidate_id':'F','entity_label':'Fictional','left_record_id':'A','right_record_id':'OTHER'})
    same=client.post('/api/evidence/entity-resolution/candidates',json={'candidate_id':'S','entity_label':'Fictional','left_record_id':'A','right_record_id':'A'})
    assert foreign.status_code==400 and foreign.json()['detail']=='source_record_not_found_in_active_matter'
    assert same.status_code==400 and same.json()['detail']=='entity_resolution_records_must_differ'


def test_entity_resolution_ui_is_mirrored():
    root=Path(__file__).resolve().parents[1]; src=(root/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8'); mirror=(root/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
    assert src==mirror and 'installEntityResolutionControl' in src and 'Revoke merge' in src
    assert '/api/evidence/entity-resolution/candidates/${encodeURIComponent(candidateId)}/${encodeURIComponent(side)}/source' in src
    assert 'Inspect left source' in src and 'Inspect right source' in src
    assert 'data-entity-resolution-action="confirm"' in src
    assert 'entityResolutionDelegationBound' in src
