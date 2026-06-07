from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_accessibility_style_rules.json"


@dataclass(frozen=True)
class ReadabilityReport:
    word_count: int
    sentence_count: int
    average_words_per_sentence: float
    long_sentence_count: int
    jargon_hits: list[str]
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "average_words_per_sentence": self.average_words_per_sentence,
            "long_sentence_count": self.long_sentence_count,
            "jargon_hits": self.jargon_hits,
            "status": self.status,
        }


class ReadabilityAuditor:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))

    def audit(self, text: str) -> ReadabilityReport:
        sentences = [item.strip() for item in re.split(r"[.!?]+", text or "") if item.strip()]
        words = re.findall(r"[A-Za-z0-9'-]+", text or "")
        sentence_lengths = [len(re.findall(r"[A-Za-z0-9'-]+", sentence)) for sentence in sentences]
        long_sentences = [length for length in sentence_lengths if length > self.config.get("max_average_words_per_sentence", 22)]
        glossary_terms = [
            "jurisdiction",
            "affidavit",
            "guardian ad litem",
            "rule 52 findings",
            "unsupported claim",
        ]
        low = (text or "").lower()
        jargon_hits = [term for term in glossary_terms if term in low]
        avg = round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 2)
        status = "pass"
        if avg > float(self.config.get("max_average_words_per_sentence", 22)):
            status = "warn"
        if len(long_sentences) > int(self.config.get("max_long_sentences", 3)):
            status = "warn"
        return ReadabilityReport(
            word_count=len(words),
            sentence_count=len(sentences),
            average_words_per_sentence=avg,
            long_sentence_count=len(long_sentences),
            jargon_hits=jargon_hits,
            status=status,
        )
