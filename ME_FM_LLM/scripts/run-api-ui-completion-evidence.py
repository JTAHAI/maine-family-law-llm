#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.contracts import APICompletionPolicy, EndpointInventory, OpenAPICompletionAuditor
from app.api.main import app
from app.web.ui_contracts import UICompletionAuditor


def build_evidence() -> dict:
    registered = set()
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in {"GET", "POST"} and str(path).startswith("/api"):
                registered.add((method, str(path)))
    endpoint_report = EndpointInventory().compare_to_registered(registered)
    openapi_report = OpenAPICompletionAuditor().audit(app.openapi()).as_dict()
    ui_report = UICompletionAuditor(ROOT / "app/web/pages").audit().as_dict()
    policy = APICompletionPolicy().evidence().as_dict()
    status = "pass" if endpoint_report["status"] == openapi_report["status"] == ui_report["status"] == "pass" else "fail"
    return {
        "stage": "enterprise_pass_39_pass_40_production_api_web_ui_completion",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint_inventory": endpoint_report,
        "openapi_completion": openapi_report,
        "api_completion_policy": policy,
        "ui_completion": ui_report,
        "status": status,
        "completed_passes": [39, 40],
        "remaining_passes": 11,
        "legal_readiness": "API and UI completion foundations are installed; GA still requires model governance, injection defense, security implementation, compliance evidence, SRE, release eval, red team, pilot, RC, and shipped operations evidence.",
    }


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "sample-evidence" / "smoke_evidence_pass39_pass40_api_ui_completion.json"
    evidence = build_evidence()
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
