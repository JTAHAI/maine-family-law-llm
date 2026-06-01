from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GAPass:
    number: int
    phase: str
    title: str
    status: str
    next: bool = False
    external_dependency: bool = True
    repo_prep_status: str = "not_started"
    completion_evidence: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "GAPass":
        return cls(
            number=int(row["pass"]),
            phase=str(row.get("phase") or ""),
            title=str(row.get("title") or ""),
            status=str(row.get("status") or "open"),
            next=bool(row.get("next", False)),
            external_dependency=bool(row.get("external_dependency", True)),
            repo_prep_status=str(row.get("repo_prep_status") or "not_started"),
            completion_evidence=tuple(str(item) for item in row.get("completion_evidence") or ()),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.number,
            "phase": self.phase,
            "title": self.title,
            "status": self.status,
            "next": self.next,
            "external_dependency": self.external_dependency,
            "repo_prep_status": self.repo_prep_status,
            "completion_evidence": list(self.completion_evidence),
        }


@dataclass
class GAPassCountReport:
    status: str
    generated_at: str
    total_true_ga_passes: int
    true_ga_completed: int
    true_ga_remaining: int
    completed_passes: list[int] = field(default_factory=list)
    remaining_passes: list[int] = field(default_factory=list)
    next_true_ga_pass: int | None = None
    next_true_ga_title: str | None = None
    counting_rule: str = ""
    repo_prep_summary: dict[str, int] = field(default_factory=dict)
    phases_remaining: dict[str, int] = field(default_factory=dict)
    passes: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "total_true_ga_passes": self.total_true_ga_passes,
            "true_ga_completed": self.true_ga_completed,
            "true_ga_remaining": self.true_ga_remaining,
            "completed_passes": self.completed_passes,
            "remaining_passes": self.remaining_passes,
            "next_true_ga_pass": self.next_true_ga_pass,
            "next_true_ga_title": self.next_true_ga_title,
            "counting_rule": self.counting_rule,
            "repo_prep_summary": self.repo_prep_summary,
            "phases_remaining": self.phases_remaining,
            "warnings": self.warnings,
            "passes": self.passes,
        }


class GAPassTracker:
    """Formal counter for the true Pass 19-51 GA roadmap.

    This intentionally refuses to count repo prep, fixture smoke evidence, and dry-run harness
    work as true GA completion. Only rows explicitly marked complete in the audited tracker
    reduce the formal remaining count.
    """

    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.tracker_path = self.project_root / "configs" / "maine_true_ga_pass_tracker.json"

    def load(self) -> tuple[str, list[GAPass], list[int]]:
        raw = json.loads(self.tracker_path.read_text(encoding="utf-8"))
        passes = [GAPass.from_dict(row) for row in raw.get("passes", [])]
        completed = sorted(int(item) for item in raw.get("current_true_ga_completed_passes", []))
        return str(raw.get("counting_rule") or ""), passes, completed

    def report(self) -> GAPassCountReport:
        warnings: list[str] = []
        counting_rule, passes, configured_completed = self.load()
        by_number = {item.number: item for item in passes}
        row_completed = sorted(item.number for item in passes if item.status == "complete")
        completed = sorted(set(configured_completed) | set(row_completed))
        unknown_completed = [item for item in completed if item not in by_number]
        if unknown_completed:
            warnings.append(f"completed_passes_not_in_tracker:{unknown_completed}")
        if configured_completed != row_completed:
            warnings.append(
                "completed_passes_status_mismatch:"
                f"configured={configured_completed}:row_status={row_completed}"
            )
        numbers = [item.number for item in passes]
        if len(numbers) != len(set(numbers)):
            warnings.append("duplicate_pass_numbers_in_tracker")
        expected_numbers = list(range(19, 52))
        if sorted(numbers) != expected_numbers:
            warnings.append("tracker_pass_numbers_not_contiguous_19_51")
        remaining = [item.number for item in passes if item.number not in completed]
        next_pass = next((item for item in passes if item.number in remaining), None)
        next_marked = sorted(item.number for item in passes if item.next)
        expected_next = [next_pass.number] if next_pass else []
        if next_marked != expected_next:
            warnings.append(f"next_pass_marker_mismatch:marked={next_marked}:expected={expected_next}")
        repo_prep_summary: dict[str, int] = {}
        phases_remaining: dict[str, int] = {}
        for item in passes:
            repo_prep_summary[item.repo_prep_status] = repo_prep_summary.get(item.repo_prep_status, 0) + 1
            if item.number in remaining:
                phases_remaining[item.phase] = phases_remaining.get(item.phase, 0) + 1
        structural_ok = bool(passes) and len(passes) == 33 and min(by_number) == 19 and max(by_number) == 51
        status = "pass" if structural_ok and not warnings else "blocked"
        if not structural_ok:
            warnings.append("tracker_count_or_range_invalid")
        return GAPassCountReport(
            status=status,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_true_ga_passes=len(passes),
            true_ga_completed=len([item for item in completed if item in by_number]),
            true_ga_remaining=len(remaining),
            completed_passes=[item for item in completed if item in by_number],
            remaining_passes=remaining,
            next_true_ga_pass=next_pass.number if next_pass else None,
            next_true_ga_title=next_pass.title if next_pass else None,
            counting_rule=counting_rule,
            repo_prep_summary=repo_prep_summary,
            phases_remaining=phases_remaining,
            passes=[item.as_dict() for item in passes],
            warnings=warnings,
        )
