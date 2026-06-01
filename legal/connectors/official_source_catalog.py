from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legal.connectors.base import SourceTarget


OFFICIAL_SOURCE_TARGETS: tuple[SourceTarget, ...] = (
    SourceTarget(
        target_id='me-revisor-title-4-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/4/title4ch0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=2,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Courts and court officers; family division/statutory court structure',
    ),
    SourceTarget(
        target_id='me-revisor-title-4-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/4/title4.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Courts and court officers; family division/statutory court structure full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-5-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/5/title5ch0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=2,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Protection from harassment and administrative records overlaps',
    ),
    SourceTarget(
        target_id='me-revisor-title-5-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/5/title5.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Protection from harassment and administrative records overlaps full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-14-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/14/title14ch0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=2,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Court procedure and civil remedies overlaps',
    ),
    SourceTarget(
        target_id='me-revisor-title-14-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/14/title14.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Court procedure and civil remedies overlaps full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-15-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/15/title15ch0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=2,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Criminal procedure and protection-order overlaps',
    ),
    SourceTarget(
        target_id='me-revisor-title-15-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/15/title15.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Criminal procedure and protection-order overlaps full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-17a-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/17-a/title17-Ach0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=2,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Maine Criminal Code overlaps with domestic violence and family safety',
    ),
    SourceTarget(
        target_id='me-revisor-title-17a-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/17-a/title17-A.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Maine Criminal Code overlaps with domestic violence and family safety full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-18c-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/18-c/title18-Cch0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=1,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Probate Code overlaps with guardianship and adoption-adjacent issues',
    ),
    SourceTarget(
        target_id='me-revisor-title-18c-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/18-c/title18-C.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=1,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Probate Code overlaps with guardianship and adoption-adjacent issues full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-19-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/19/title19ch0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=1,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Domestic relations legacy provisions',
    ),
    SourceTarget(
        target_id='me-revisor-title-19-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/19/title19.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=1,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Domestic relations legacy provisions full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-19a-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=1,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Domestic Relations core family-law title',
    ),
    SourceTarget(
        target_id='me-revisor-title-19a-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/19-a/title19-A.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=1,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Domestic Relations core family-law title full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-revisor-title-22-index',
        source_class='statute_title_index',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/22/title22ch0sec0.html',
        parser_name='maine_revisor_title_index',
        priority=1,
        freshness_strategy='revisor_data_extracted_timestamp',
        notes='Health and welfare / child protective services overlaps',
    ),
    SourceTarget(
        target_id='me-revisor-title-22-pdf',
        source_class='statute_title_pdf',
        jurisdiction='maine',
        url='https://legislature.maine.gov/statutes/22/title22.pdf',
        parser_name='pdf_snapshot',
        expected_content_type='application/pdf',
        priority=1,
        freshness_strategy='retrieved_timestamp_and_pdf_metadata',
        notes='Health and welfare / child protective services overlaps full PDF snapshot for hash/diff comparison.',
    ),
    SourceTarget(
        target_id='me-courts-civil-rules',
        source_class='court_rules_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/rules/rules-civil.html',
        parser_name='maine_rules_index',
        priority=1,
        freshness_strategy='page_updated_or_retrieved_timestamp',
        notes='Maine Rules of Civil Procedure including family division rules.',
    ),
    SourceTarget(
        target_id='me-courts-appellate-rules',
        source_class='court_rules_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/rules/rules-appellate.html',
        parser_name='maine_rules_index',
        priority=1,
        freshness_strategy='page_updated_or_retrieved_timestamp',
        notes='Maine Rules of Appellate Procedure for appeal preservation and record issues.',
    ),
    SourceTarget(
        target_id='me-courts-evidence-rules',
        source_class='court_rules_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/rules/rules-evidence.html',
        parser_name='maine_rules_index',
        priority=1,
        freshness_strategy='page_updated_or_retrieved_timestamp',
        notes='Maine Rules of Evidence for proof and admissibility issues.',
    ),
    SourceTarget(
        target_id='me-courts-probate-rules',
        source_class='court_rules_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/rules/rules-probate.html',
        parser_name='maine_rules_index',
        priority=1,
        freshness_strategy='page_updated_or_retrieved_timestamp',
        notes='Maine Rules of Probate Procedure for guardianship/adoption-adjacent work.',
    ),
    SourceTarget(
        target_id='me-courts-forms-index',
        source_class='court_forms_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/forms/index.html',
        parser_name='maine_forms_index',
        priority=1,
        freshness_strategy='page_updated_or_retrieved_timestamp',
        notes='Maine Judicial Branch official forms landing page.',
    ),
    SourceTarget(
        target_id='me-courts-records-access-policy',
        source_class='court_policy_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/help/records.html',
        parser_name='maine_rules_index',
        priority=2,
        freshness_strategy='page_updated_or_retrieved_timestamp',
        notes='Maine Judicial Branch court-records help page for public-access, privacy, and sealed-record checks.',
    ),
    SourceTarget(
        target_id='me-lawcourt-opinions-2019',
        source_class='law_court_opinion_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/courts/sjc/lawcourt/2019/index.html',
        parser_name='maine_law_court_opinion_index',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_opinion_links',
        notes='Maine Supreme Judicial Court / Law Court published opinions index for 2019; included as a stable seventh opinion-year baseline when no current-year index is published yet.',
    ),
    SourceTarget(
        target_id='me-lawcourt-opinions-2025',
        source_class='law_court_opinion_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/courts/sjc/lawcourt/2025/index.html',
        parser_name='maine_law_court_opinion_index',
        priority=1,
        freshness_strategy='retrieved_timestamp_and_opinion_links',
        notes='Maine Supreme Judicial Court / Law Court published opinions index for 2025.',
    ),
    SourceTarget(
        target_id='me-lawcourt-opinions-2024',
        source_class='law_court_opinion_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/courts/sjc/lawcourt/2024/index.html',
        parser_name='maine_law_court_opinion_index',
        priority=1,
        freshness_strategy='retrieved_timestamp_and_opinion_links',
        notes='Maine Supreme Judicial Court / Law Court published opinions index for 2024.',
    ),
    SourceTarget(
        target_id='me-lawcourt-opinions-2023',
        source_class='law_court_opinion_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/courts/sjc/lawcourt/2023/index.html',
        parser_name='maine_law_court_opinion_index',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_opinion_links',
        notes='Maine Supreme Judicial Court / Law Court published opinions index for 2023.',
    ),
    SourceTarget(
        target_id='me-lawcourt-opinions-2022',
        source_class='law_court_opinion_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/courts/sjc/lawcourt/2022/index.html',
        parser_name='maine_law_court_opinion_index',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_opinion_links',
        notes='Maine Supreme Judicial Court / Law Court published opinions index for 2022.',
    ),
    SourceTarget(
        target_id='me-lawcourt-opinions-2021',
        source_class='law_court_opinion_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/courts/sjc/lawcourt/2021/index.html',
        parser_name='maine_law_court_opinion_index',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_opinion_links',
        notes='Maine Supreme Judicial Court / Law Court published opinions index for 2021.',
    ),
    SourceTarget(
        target_id='me-lawcourt-opinions-2020',
        source_class='law_court_opinion_index',
        jurisdiction='maine',
        url='https://www.courts.maine.gov/courts/sjc/lawcourt/2020/index.html',
        parser_name='maine_law_court_opinion_index',
        priority=2,
        freshness_strategy='retrieved_timestamp_and_opinion_links',
        notes='Maine Supreme Judicial Court / Law Court published opinions index for 2020.',
    )
)


def _target_from_config(row: dict[str, Any]) -> SourceTarget:
    return SourceTarget(
        target_id=str(row.get("target_id", "")),
        source_class=str(row.get("source_class", "")),
        jurisdiction=str(row.get("jurisdiction", "")),
        url=str(row.get("url", "")),
        parser_name=str(row.get("parser_name", "")),
        expected_content_type=str(row.get("expected_content_type") or "text/html"),
        priority=int(row.get("priority", 1) or 1),
        freshness_strategy=str(row.get("freshness_strategy") or "retrieved_timestamp"),
        notes=str(row.get("notes") or ""),
    )


def _load_targets_from_config() -> list[SourceTarget]:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_path = repo_root / "configs" / "maine_official_source_targets.json"
    loaded = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = loaded.get("targets", [])
    if not isinstance(rows, list):
        raise ValueError("configs/maine_official_source_targets.json targets must be a list")
    return [_target_from_config(row) for row in rows if isinstance(row, dict)]


def load_official_source_targets() -> list[SourceTarget]:
    targets = _load_targets_from_config()
    if not targets:
        targets = list(OFFICIAL_SOURCE_TARGETS)
    problems = [problem for target in targets for problem in target.validate()]
    if problems:
        raise ValueError("invalid official source catalog: " + "; ".join(problems))
    return targets


def _load_rows_from_source_target_catalog(path: str | Path) -> list[dict[str, Any]]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        rows = loaded
    elif isinstance(loaded, dict):
        rows = loaded.get("targets", [])
    else:
        raise ValueError("source target catalog must be a JSON array or an object with a targets array")
    if not isinstance(rows, list):
        raise ValueError("source target catalog targets must be a list")
    return [row for row in rows if isinstance(row, dict)]


def load_source_targets_from_file(path: str | Path) -> list[SourceTarget]:
    targets = [_target_from_config(row) for row in _load_rows_from_source_target_catalog(path)]
    problems = [problem for target in targets for problem in target.validate()]
    if problems:
        raise ValueError("invalid source target catalog: " + "; ".join(problems))
    return targets
