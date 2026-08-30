"""Encrypted, review-required sentence-to-source maps for local drafts.

This module makes support signals inspectable without claiming that a source
proves a fact, resolves a contradiction, or establishes a legal conclusion.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_SENTENCE = re.compile(r"[^\n.!?]+(?:[.!?]+|$)", re.MULTILINE)
_SENTENCE_ABBREVIATION = re.compile(r"\b(?:M\.R\.S\.|M\.R\.|U\.S\.|No\.|Inc\.|Ltd\.)", re.IGNORECASE)
_PROTECTED_PERIOD = "\uff0e"
_TOKEN = re.compile(r"[a-z0-9]+")
_LEGAL = re.compile(
    r"\b(?:\d+(?:-[A-Za-z0-9]+)?\s*(?:M\.R\.S\.|M\.R\.|Maine Rule)|statute|rule|jurisdiction|court must|the law)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:no|not|never|without|did not|does not|cannot|can't|failed to)\b", re.IGNORECASE)
_QUALIFIER = re.compile(r"\b(?:unless|except|however|but|subject to|to the extent|may|might)\b", re.IGNORECASE)
_STOP = frozenset({"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "to", "was", "were", "with"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


def _hash(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _HASH.fullmatch(result):
        raise IntakeWorkbenchError(f"{field}_required")
    return result


def _text(value: Any, field: str, *, limit: int = 20_000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_too_long")
    return result


def _tokens(value: str) -> set[str]:
    return {item for item in _TOKEN.findall(value.casefold()) if item not in _STOP and len(item) > 1}


def _similarity(left: str, right: str) -> float:
    tokens = _tokens(left)
    return len(tokens & _tokens(right)) / max(1, len(tokens))


def _sentence_parts(value: str) -> list[tuple[str, int, int]]:
    """Split text without treating common legal abbreviations as full stops.

    The protected character is one code point, so offsets remain valid for the
    original text.  This is deliberately a small, deterministic parser rather
    than a language-model decision about sentence meaning.
    """
    protected = _SENTENCE_ABBREVIATION.sub(
        lambda match: match.group(0).replace(".", _PROTECTED_PERIOD), value
    )
    return [
        (match.group(0).replace(_PROTECTED_PERIOD, "."), match.start(), match.end())
        for match in _SENTENCE.finditer(protected)
        if match.group(0).strip()
    ]


def _matches_selected_authority_exactly(text: str, authority: Iterable[dict[str, Any]]) -> bool:
    """Identify a substantive exact selected-authority sentence conservatively.

    A source-bound draft can quote an official span without repeating a citation
    in every sentence.  Treat that as a legal-review sentence only when at least
    four substantive tokens have an 0.8-or-higher match to one selected exact
    authority sentence.  Smaller or weaker overlaps remain factual/narrative so
    a shared word such as "child" cannot relabel a private-record statement.
    """
    if len(_tokens(text)) < 4:
        return False
    for source in authority:
        span = str(source.get("exact_span") or "")
        if not span:
            continue
        candidates = [part for part, _, _ in _sentence_parts(span)] or [span]
        if max(_similarity(text, candidate) for candidate in candidates) >= 0.8:
            return True
    return False


class SentenceSupportMapStore:
    """Stores only review work products, not originals or generated prose."""

    schema = "maine_family_law_llm.sentence_support_map.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "19_DRAFTING" / "sentence-support-maps"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("sentence_support_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path:
        return self.root / "sentence-support-maps.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".sentence-support-maps.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "maps": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("sentence_support_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("maps", [])
        state.setdefault("ledger", [])
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, map_id: str, callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            state = self._load()
            result = callback(state)
            prior = str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else ""
            event = {"event_id": f"sentence_map_{uuid.uuid4().hex}", "at": _now(), "action": "create_sentence_support_map", "map_id": map_id, "previous_event_hash": prior, "review_required": True}
            event["event_hash"] = _digest(event)
            state["ledger"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
            return result

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("scope", None)
        result.update({
            "status": "review_required", "review_required": True, "filing_ready": False, "local_only": True,
            "notice": "Source signals are a review aid. They do not decide truth, credibility, admissibility, legal effect, or filing readiness.",
        })
        return result

    def _authority(self, values: Any) -> list[dict[str, Any]]:
        if not isinstance(values, list) or not values or len(values) > 100:
            raise IntakeWorkbenchError("selected_authority_required")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in values:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("selected_authority_invalid")
            authority_id = _id(raw.get("authority_id"), "authority_id")
            if authority_id in seen:
                raise IntakeWorkbenchError("duplicate_authority_id")
            seen.add(authority_id)
            rows.append({
                "authority_id": authority_id, "source_id": _text(raw.get("source_id"), "authority_source_id", limit=240),
                "source_hash": _hash(raw.get("source_hash"), "authority_source_hash"),
                "citation": _text(raw.get("citation"), "authority_citation", limit=500),
                "title": _text(raw.get("title"), "authority_title", limit=500),
                "exact_span": _text(raw.get("exact_span"), "authority_exact_span", limit=4_000, required=False),
                "freshness_status": _text(raw.get("freshness_status"), "authority_freshness", limit=80, required=False) or "unknown",
                "lane": "official_authority",
            })
        return rows

    @staticmethod
    def _records(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for raw in values:
            if not isinstance(raw, dict):
                continue
            record_id = str(raw.get("evidence_id") or raw.get("source_id") or "").strip()
            source_hash = str(raw.get("source_hash") or raw.get("sha256") or "").casefold()
            text = str(raw.get("text") or raw.get("derived_text") or raw.get("text_excerpt") or raw.get("snippet") or "")[:200_000]
            if record_id and _HASH.fullmatch(source_hash) and text.strip():
                rows.append({"record_id": record_id, "source_hash": source_hash, "text": text, "title": str(raw.get("title") or raw.get("source_locator") or record_id)[:300], "page_number": int(raw.get("page_number") or 0), "lane": "private_matter_record"})
        return rows[:10_000]

    @staticmethod
    def _source_card(source: dict[str, Any], *, relationship: str, score: float, sentence: str) -> dict[str, Any]:
        return {
            **{key: value for key, value in source.items() if key != "text"},
            "relationship": relationship, "score": round(score, 3),
            "exact_source_span": str(source.get("text") or source.get("exact_span") or "")[:1_200],
            "sentence_sha256": hashlib.sha256(sentence.encode()).hexdigest(),
        }

    def _sentence_row(self, sentence_id: str, text: str, start: int, end: int, records: list[dict[str, Any]], authority: list[dict[str, Any]]) -> dict[str, Any]:
        legal = bool(_LEGAL.search(text)) or _matches_selected_authority_exactly(text, authority)
        support: list[dict[str, Any]] = []
        contradictions: list[dict[str, Any]] = []
        qualifications: list[dict[str, Any]] = []
        for record in records:
            record_text = str(record["text"])
            spans = [" ".join(part.split()) for part, _, _ in _sentence_parts(record_text)]
            spans = [span for span in spans if span] or [record_text]
            matched_span = max(spans, key=lambda span: _similarity(text, span))
            score = _similarity(text, matched_span)
            if score < 0.35:
                continue
            bound_record = {**record, "text": matched_span}
            negation_conflict = bool(_NEGATION.search(text)) != bool(_NEGATION.search(matched_span))
            if negation_conflict and score >= 0.55:
                contradictions.append(self._source_card(bound_record, relationship="potential_polarity_conflict", score=score, sentence=text))
            elif score >= 0.55:
                support.append(self._source_card(bound_record, relationship="factual_text_match", score=score, sentence=text))
            if score >= 0.35 and _QUALIFIER.search(matched_span):
                qualifications.append(self._source_card(bound_record, relationship="record_qualification_candidate", score=score, sentence=text))
        if legal:
            for source in authority:
                span = str(source.get("exact_span") or "")
                # A verified pinpoint can legitimately contain several sentences.
                # Compare the draft sentence to its best exact sentence within that
                # pinpoint, rather than diluting an otherwise exact match against
                # the entire section.  The returned card remains source-bound to
                # the selected authority and carries only the matched exact span.
                source_spans = [" ".join(part.split()) for part, _, _ in _sentence_parts(span)] or [span]
                matched_span = max(source_spans, key=lambda candidate: _similarity(text, candidate))
                score = _similarity(text, matched_span)
                bound_source = {**source, "exact_span": matched_span}
                stale = str(source.get("freshness_status") or "").casefold() in {"stale", "stale_unknown", "superseded"}
                if span and score >= 0.35 and not stale:
                    support.append(self._source_card(bound_source, relationship="legal_text_match", score=score, sentence=text))
                elif span and score >= 0.35 and stale:
                    qualifications.append(self._source_card(bound_source, relationship="stale_authority_requires_review", score=score, sentence=text))
                if span and score >= 0.35 and bool(_NEGATION.search(text)) != bool(_NEGATION.search(matched_span)):
                    contradictions.append(self._source_card(bound_source, relationship="authority_polarity_conflict", score=score, sentence=text))
                if span and score >= 0.35 and _QUALIFIER.search(matched_span):
                    qualifications.append(self._source_card(bound_source, relationship="authority_qualification_candidate", score=score, sentence=text))
        missing: list[str] = []
        if not support:
            missing.append("no_source_text_match_in_selected_scope")
        if legal and not any(card.get("lane") == "official_authority" for card in support):
            missing.append("legal_sentence_without_current_exact_authority_match")
        if not legal and not any(card.get("lane") == "private_matter_record" for card in support):
            missing.append("factual_sentence_without_private_record_match")
        return {
            "sentence_id": sentence_id, "text": text, "start_offset": start, "end_offset": end,
            "sentence_kind": "legal_or_procedural" if legal else "factual_or_narrative",
            "supports": support[:20], "contradictions": contradictions[:20], "qualifications": qualifications[:20],
            "missing_context": missing, "review_state": "review_required", "review_required": True,
        }

    def create_map(self, payload: dict[str, Any], *, document: dict[str, Any], records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("sentence_support_confirmation_required", 409)
        reviewer_safe_id = _id(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        document_id = _text(document.get("document_id"), "document_id", limit=80)
        revision_id = _text(document.get("current_revision_id"), "revision_id", limit=80)
        content = _text(document.get("content"), "document_content", limit=1_500_000)
        authority = self._authority(payload.get("selected_authority"))
        source_records = self._records(records)
        map_id = "sentence_map_" + _digest({"document_id": document_id, "revision_id": revision_id, "content": content, "authority": authority})[:24]
        sentences = []
        for index, (part, start, end) in enumerate(_sentence_parts(content), start=1):
            value = " ".join(part.split())
            if value:
                sentences.append(self._sentence_row(f"sentence_{index:03d}", value, start, end, source_records, authority))
        if not sentences:
            raise IntakeWorkbenchError("document_sentences_required")

        def callback(state: dict[str, Any]) -> dict[str, Any]:
            state["maps"] = [row for row in state["maps"] if str(row.get("map_id") or "") != map_id]
            result = {
                "map_id": map_id, "document_id": document_id, "revision_id": revision_id,
                "document_content_sha256": hashlib.sha256(content.encode()).hexdigest(), "reviewer_safe_id": reviewer_safe_id,
                "created_at": _now(), "sentences": sentences, "authority": authority,
                "summary": {"sentence_count": len(sentences), "supported_sentences": sum(bool(row["supports"]) for row in sentences), "contradiction_candidates": sum(bool(row["contradictions"]) for row in sentences), "qualification_candidates": sum(bool(row["qualifications"]) for row in sentences), "missing_context_sentences": sum(bool(row["missing_context"]) for row in sentences)},
                "review_required": True, "filing_ready": False,
            }
            state["maps"].append(result)
            return self._public(result)
        return self._mutate(map_id, callback)

    def maps(self, document_id: str, map_id: str = "") -> dict[str, Any]:
        state = self._load()
        rows = [self._public(row) for row in state["maps"] if str(row.get("document_id") or "") == document_id]
        if map_id:
            found = next((row for row in rows if row.get("map_id") == map_id), None)
            if found is None:
                raise IntakeWorkbenchError("sentence_support_map_not_found", 404)
            return {"map": found, "review_required": True}
        return {"maps": rows, "review_required": True, "local_only": True}

    def sentence_source(self, document_id: str, map_id: str, sentence_id: str, lane: str, card_index: int) -> dict[str, Any]:
        result = self.maps(document_id, map_id)["map"]
        sentence = next((row for row in result["sentences"] if row.get("sentence_id") == sentence_id), None)
        if sentence is None:
            raise IntakeWorkbenchError("sentence_support_sentence_not_found", 404)
        collection = {"supports": "supports", "contradictions": "contradictions", "qualifications": "qualifications"}.get(lane)
        if not collection:
            raise IntakeWorkbenchError("sentence_support_lane_invalid")
        cards = list(sentence.get(collection) or [])
        if card_index < 0 or card_index >= len(cards):
            raise IntakeWorkbenchError("sentence_support_card_not_found", 404)
        return {"map_id": map_id, "sentence_id": sentence_id, "source": cards[card_index], "review_required": True}
