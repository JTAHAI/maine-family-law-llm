from pathlib import Path


def test_incremental_local_ocr_contract_is_shipped_and_resumable():
    root=Path(__file__).resolve().parents[1]
    api=(root/'src/maine_family_law_llm/api.py').read_text(encoding='utf-8')
    mirror=(root/'maine_family_law_llm/api.py').read_text(encoding='utf-8')
    ui=(root/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
    assert api==mirror
    for route in ('/api/corpus-ocr/start','/api/corpus-ocr/status','/api/corpus-ocr/cancel'):
        assert route in api and route in ui
    assert 'ocr_explicit_consent_required' in api
    assert 'kernel.create_job' in api and 'resumable' in api and 'ACTIVE_STATUSES' in api
    assert 'Cancel local OCR' in ui and 'aria-label="Local OCR progress"' in ui
    assert 'No document bytes or recognized text will leave this computer' in ui


def test_incremental_ingest_ui_is_mirrored():
    root=Path(__file__).resolve().parents[1]
    assert (root/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8') == (root/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
