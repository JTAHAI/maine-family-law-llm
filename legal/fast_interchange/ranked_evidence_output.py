"""Independent exact-span boundary for review shortlists, not factual answers."""

from hashlib import sha256

from legal.agent_runtime.contracts import ContextSource, canonical_json

from .evidence_output import verify_selected_evidence_spans


def verify_ranked_evidence_spans(rows: tuple, sources: tuple[ContextSource, ...]) -> dict:
    """Accept 1–3 distinct, non-overlapping exact excerpts from every record.

    Keep the original one-excerpt verifier strict. Every additional span passes
    that same verifier in a complete record set. Scores do not enter this gate.
    """
    blockers = []
    groups = {i: [] for i in range(1, len(sources) + 1)}
    if not isinstance(rows, tuple) or not 1 <= len(rows) <= 24 or not 1 <= len(sources) <= 8:
        blockers.append("evidence_review_ranked_spans_invalid")
    else:
        for row in rows:
            if not isinstance(row, dict) or type(row.get("reference")) is not int:
                blockers.append("evidence_review_ranked_spans_invalid")
                continue
            group = groups.get(row["reference"])
            if group is None:
                blockers.append("evidence_review_ranked_spans_invalid")
                continue
            group.append(row)
        if any(not 1 <= len(group) <= 3 for group in groups.values()):
            blockers.append("evidence_review_ranked_coverage_invalid")
    if not blockers:
        first = tuple(group[0] for group in groups.values())
        for index, group in groups.items():
            intervals = []
            for row in group:
                candidate = list(first)
                candidate[index - 1] = row
                checked = verify_selected_evidence_spans(tuple(candidate), sources)
                blockers.extend(checked["blockers"])
                if checked["blockers"]:
                    continue
                start, end = row["start_offset"], row["end_offset"]
                if any(start < old_end and end > old_start for old_start, old_end in intervals):
                    blockers.append("evidence_review_ranked_overlap_invalid")
                intervals.append((start, end))
    report = {
        "schema_version": "evidence_ranked_spans_boundary_v1",
        "status": "withheld" if blockers else "candidate_passages_review_required",
        "display_mode": "withheld" if blockers else "ranked_candidate_extracts_only",
        "review_required": True,
        "factual_claims_verified": False,
        "legal_claims_verified": False,
        "relevance_verified": False,
        "abstention_calibrated": False,
        "completeness_verified": False,
        "source_spans": [] if blockers else [dict(row) for row in rows],
        "suppressed_spans": [],
        "partial_extracts_available": False,
        "blockers": sorted(set(blockers)),
    }
    report["report_sha256"] = sha256(canonical_json(report)).hexdigest()
    return report
