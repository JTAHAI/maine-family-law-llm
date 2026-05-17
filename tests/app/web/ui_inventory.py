from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UIViewSpec:
    name: str
    path: str
    file: str
    purpose: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "path": self.path, "file": self.file, "purpose": self.purpose}


REQUIRED_UI_VIEWS: tuple[UIViewSpec, ...] = (
    UIViewSpec("matter_dashboard", "/", "dashboard.tsx", "matter list and recent activity"),
    UIViewSpec("ask_maine_family_law", "/ask", "ask.tsx", "source-grounded Q&A"),
    UIViewSpec("upload_documents", "/upload", "upload.tsx", "matter document intake"),
    UIViewSpec("source_library", "/sources", "source-library.tsx", "browse admitted sources"),
    UIViewSpec("authority_matrix", "/authority", "authority-matrix.tsx", "authority analysis"),
    UIViewSpec("timeline", "/timeline", "timeline.tsx", "case timeline"),
    UIViewSpec("evidence_map", "/evidence", "evidence.tsx", "fact-to-evidence map"),
    UIViewSpec("draft_workspace", "/draft", "draft-workspace.tsx", "review-required drafting"),
    UIViewSpec("citation_report", "/citations", "citation-report.tsx", "citation verification"),
    UIViewSpec("quote_report", "/quotes", "quote-report.tsx", "quote-report verification"),
    UIViewSpec("filing_readiness_gate", "/filing-ready", "filing-ready.tsx", "export blockers"),
    UIViewSpec("human_review_queue", "/review-queue", "human-review-queue.tsx", "attorney review"),
    UIViewSpec("settings_data_policy", "/settings", "settings-data-policy.tsx", "data policy controls"),
    UIViewSpec("admin_eval_dashboard", "/admin/evals", "admin-eval-dashboard.tsx", "eval and release gate visibility"),
)


class UIViewInventory:
    def __init__(self, web_pages_dir: str | Path) -> None:
        self.web_pages_dir = Path(web_pages_dir)

    def validate(self) -> dict[str, Any]:
        existing = {path.name for path in self.web_pages_dir.glob("*.tsx")}
        required = {view.file for view in REQUIRED_UI_VIEWS}
        missing = sorted(required - existing)
        return {
            "status": "pass" if not missing else "fail",
            "required_count": len(required),
            "existing_count": len(existing),
            "missing": missing,
            "views": [view.as_dict() for view in REQUIRED_UI_VIEWS],
        }
