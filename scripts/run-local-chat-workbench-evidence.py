#!/usr/bin/env python3
"""Emit evidence for the non-technical local chat workbench."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maine_family_law_llm.local_workbench_ui import render_local_workbench_html


def build_report(repo_root: Path) -> dict[str, object]:
    html = render_local_workbench_html()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    api_py = (repo_root / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    required_paths = [
        "START_LOCAL_CHAT.ps1",
        "START_LOCAL_CHAT.cmd",
        "START_LOCAL_TEST.ps1",
        "STOP_LOCAL_TEST.ps1",
        "scripts/run-local-api.ps1",
        "scripts/run-local-api.sh",
        "src/maine_family_law_llm/local_workbench_ui.py",
    ]
    missing = [path for path in required_paths if not (repo_root / path).is_file()]
    required_html_markers = [
        "id=\"question\"",
        "id=\"ask-button\"",
        "fetch('/ask'",
        "Retrieved source cards",
        "data-source-card",
        "not legal advice",
    ]
    html_lower = html.lower()
    missing_html = []
    for marker in required_html_markers:
        haystack = html_lower if marker == "not legal advice" else html
        needle = marker.lower() if marker == "not legal advice" else marker
        if needle not in haystack:
            missing_html.append(marker)
    required_api_markers = [
        "@app.get(\"/\"",
        "@app.get(\"/workbench\"",
        "@app.post(\"/api/chat\")",
        "@app.post(\"/api/ask\")",
    ]
    missing_api = [marker for marker in required_api_markers if marker not in api_py]
    required_readme_markers = [
        "For non-technical local testing",
        ".\\START_LOCAL_CHAT.ps1",
        "http://127.0.0.1:8000/",
        "Download",
    ]
    missing_readme = [marker for marker in required_readme_markers if marker not in readme]
    blockers = []
    blockers.extend(f"missing_path:{path}" for path in missing)
    blockers.extend(f"missing_html_marker:{marker}" for marker in missing_html)
    blockers.extend(f"missing_api_marker:{marker}" for marker in missing_api)
    blockers.extend(f"missing_readme_marker:{marker}" for marker in missing_readme)
    return {
        "schema": "maine_family_law_llm.local_chat_workbench_evidence.v1",
        "status": "pass" if not blockers else "fail",
        "workbench_url": "http://127.0.0.1:8000/",
        "api_docs_url": "http://127.0.0.1:8000/docs",
        "nontechnical_start_script": "START_LOCAL_CHAT.ps1",
        "api_aliases": ["/ask", "/api/ask", "/api/chat"],
        "source_cards_visible": "data-source-card" in html,
        "readme_updated": not missing_readme,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    report = build_report(args.repo_root.resolve())
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.require_ready and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
