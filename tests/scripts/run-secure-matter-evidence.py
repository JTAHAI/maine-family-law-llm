#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evidence.matter_work_product import MatterWorkProductBuilder
from legal.matter.document_ingestor import MatterDocumentIngestor
from legal.matter.matter_store import MatterStore
from legal.matter.models import Matter


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "smoke_evidence_pass35_pass36_secure_matter_evidence.json"
    data_root = Path("/tmp/maine-family-law-llm-pass35-pass36-evidence-script").resolve()
    if data_root.exists():
        shutil.rmtree(data_root)
    project_root = Path("/tmp/maine-family-law-llm-pass35-pass36-repo-placeholder").resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    matter = Matter(matter_id="matter-pass35-36", tenant_id="tenant-pass35-36", title="Matter evidence packet")
    ingestor = MatterDocumentIngestor()
    docs = [
        ingestor.ingest_document(
            matter_id=matter.matter_id,
            tenant_id=matter.tenant_id,
            filename="motion_to_modify.txt",
            text=(
                "Motion to modify parental rights and responsibilities. "
                "On 01/03/2026 the child moved to a new school. "
                "Child support should be reviewed."
            ),
        )
    ]
    store = MatterStore(data_root / "matter_store", project_root=project_root, encryption_key="pass35-pass36-script-key")
    store.create_matter(matter)
    encrypted_paths = [str(store.store_document(doc)) for doc in docs]
    report = ingestor.build_intake_report(matter, docs)
    work_product = MatterWorkProductBuilder().build(
        report,
        authorities=[
            {
                "source_id": "statute-19a-1653",
                "citation": "19-A M.R.S. § 1653",
                "title": "Parental rights and responsibilities",
                "source_class": "statute_section_reference",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh",
                "issue_labels": ["parental_rights_responsibilities", "child_support"],
            }
        ],
    ).to_dict()
    evidence = {
        "stage": "pass35_pass36_secure_matter_evidence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "encrypted_paths": encrypted_paths,
        "matter_training_allowed": matter.training_allowed,
        "document_training_allowed": [doc.private_data_allowed_for_training for doc in docs],
        "document_audit_event_counts": [len(doc.audit_history) for doc in docs],
        "intake_report": ingestor.report_as_dict(report),
        "work_product": work_product,
        "status": "pass"
        if encrypted_paths
        and not any(doc.private_data_allowed_for_training for doc in docs)
        and work_product["timeline"]
        and work_product["evidence_map"]
        and work_product["authority_matrix"]
        else "fail",
    }
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
