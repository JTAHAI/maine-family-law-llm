"""Offline research passage scoring; relevance is not truth or admission.

The resident implementation is intended for the isolated worker. Existing
research callers may use it with explicit close; no production factory uses it.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from contextlib import ExitStack
from threading import Event

import psutil

from legal.security.prompt_injection import PromptInjectionScanner
from legal.security.protected_spans import overlaps_protected_span
from legal.security.strict_json import strict_json_load_path, strict_json_loads

from .admission import canonical
from .compact_cpu import PinnedFile, fail
from .compact_ranker_pins import BERT_SHA256 as BERT_SHA256
from .compact_ranker_pins import MIXEDBREAD_SHA256, verify_ranker_inventory
from .snapshot import validate_safetensors


def validate_ranker_architecture(config, tokenizer_config, *, deberta=False):
    """Only allowlisted scalar BERT/DeBERTa profiles, not arbitrary Auto classes."""
    expected = {
        "model_type": "bert",
        "architectures": ["BertForSequenceClassification"],
        "hidden_size": 384,
        "num_hidden_layers": 6,
        "num_attention_heads": 12,
        "intermediate_size": 1536,
        "vocab_size": 30522,
        "max_position_embeddings": 512,
        "id2label": {"0": "LABEL_0"},
        "label2id": {"LABEL_0": 0},
    }
    tokenizers = {"BertTokenizer", "BertTokenizerFast"}
    if deberta:
        expected.update(
            model_type="deberta-v2",
            architectures=["DebertaV2ForSequenceClassification"],
            num_hidden_layers=12,
            num_attention_heads=6,
            vocab_size=128100,
            relative_attention=True,
            position_biased_input=False,
            pos_att_type=["p2c", "c2p"],
            type_vocab_size=0,
        )
        tokenizers = {"DebertaV2Tokenizer", "DebertaV2TokenizerFast"}
    if (
        canonical({key: config.get(key) for key in expected}) != canonical(expected)
        or type(config.get("num_labels", 1)) is not int
        or config.get("num_labels", 1) != 1
        or config.get("is_decoder", False) is not False
        or config.get("add_cross_attention", False) is not False
        or tokenizer_config.get("tokenizer_class") not in tokenizers
    ):
        fail("reranker_architecture_invalid")


def scalar_relevance(logits):
    # Never silently take the first of several class logits as a relevance score.
    if tuple(logits.shape) != (1, 1):
        fail("reranker_score_shape_invalid")
    score = float(logits.reshape(-1)[0])
    if not math.isfinite(score):
        fail("reranker_score_invalid")
    return score


def rank_input(query: str, passages: list[dict], matter_id: str) -> dict:
    """Copy and validate before model loading; reject rather than mask silently."""
    if not isinstance(query, str) or not query.strip() or len(query) > 4000:
        fail("reranker_query_invalid")
    if (
        not isinstance(matter_id, str)
        or not 1 <= len(matter_id) <= 160
        or not matter_id.strip()
        or not isinstance(passages, list)
        or not 1 <= len(passages) <= 32
    ):
        fail("reranker_scope_invalid")
    try:
        packet = strict_json_loads(
            canonical({"query": query, "passages": passages, "matter_id": matter_id}),
            max_bytes=128_000,
            max_depth=16,
            require_object=True,
        )
    except (TypeError, ValueError, RecursionError):
        fail("reranker_scope_invalid")
    scanner, ids = PromptInjectionScanner(), set()
    if any(row.severity == "high" for row in scanner.scan_user_prompt(query)):
        fail("reranker_instruction_blocked")
    for row in packet["passages"]:
        if (
            not isinstance(row, dict)
            or set(row) - {"source_id", "matter_id", "lane", "text", "metadata"}
            or row.get("matter_id") != matter_id
            or row.get("lane") != "private_record"
            or not isinstance(row.get("source_id"), str)
            or re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", row["source_id"]) is None
            or row["source_id"].casefold() in ids
            or not isinstance(row.get("text"), str)
            or not 1 <= len(row["text"]) <= 12000
            or not isinstance(row.get("metadata", {}), dict)
            or row.get("metadata", {}).get("matter_id", matter_id) != matter_id
        ):
            fail("reranker_scope_invalid")
        ids.add(row["source_id"].casefold())
        if overlaps_protected_span(0, len(row["text"]), row["text"], row.get("metadata")):
            fail("reranker_protected_passage")
        if scanner.scan_document_text(row["text"]):
            fail("reranker_instruction_blocked")
    return packet


class CompactPassageReranker:
    def __init__(self, files: tuple[PinnedFile, ...], *, research_only: bool):
        if research_only is not True:
            fail("compact_production_admission_missing")
        self.files = files
        self._locks = ExitStack()
        self._model = self._tokenizer = self._torch = None
        self.phase = "idle"

    def warm(self):
        if self._model is not None:
            return
        self.phase = "artifact_verification"
        # Do this before optional-library import or trusting a mutable receipt.
        selected_sha256 = verify_ranker_inventory(self.files)
        if psutil.virtual_memory().available < 3 * 1024**3:
            fail("insufficient_available_memory")
        directories = {r.path.parent for r in self.files}
        if len(directories) != 1:
            fail("reranker_inventory_invalid")
        root = next(iter(directories))
        deberta = selected_sha256 == MIXEDBREAD_SHA256
        allowed = {
            "README.md",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "model.safetensors",
            "config_sentence_transformers.json",
        }
        if deberta:
            allowed.remove("config_sentence_transformers.json")
            allowed.update({"LICENSE", "special_tokens_map.json", "added_tokens.json", "spm.model"})
        expected = {r.path.name for r in self.files}
        if expected != allowed or {p.name for p in root.iterdir()} - allowed - {"acquisition.json"}:
            fail("reranker_inventory_invalid")
        try:
            self.phase = "artifact_verification"
            for artifact in self.files:
                artifact.lock(self._locks)
                if artifact.path.suffix == ".json":
                    config = strict_json_load_path(
                        artifact.path,
                        max_bytes=9_000_000
                        if deberta and artifact.path.name == "tokenizer.json"
                        else 2_000_000,
                        # Pinned Unigram vocabulary contains 128k [token, score]
                        # entries. Keep the larger limit local to this artifact.
                        max_items=400_000
                        if deberta and artifact.path.name == "tokenizer.json"
                        else 200_000,
                        require_object=True,
                    )
                    if any(
                        config.get(k) for k in ("auto_map", "auto_mapping", "trust_remote_code")
                    ):
                        fail("remote_code_forbidden")
            config = strict_json_load_path(
                root / "config.json", max_bytes=10000, require_object=True
            )
            tokenizer_config = strict_json_load_path(
                root / "tokenizer_config.json", max_bytes=10000, require_object=True
            )
            validate_ranker_architecture(config, tokenizer_config, deberta=deberta)
            validate_safetensors(root / "model.safetensors", maximum_bytes=150_000_000)
            self.phase = "runtime_import"
            import torch

            if deberta:
                from transformers import DebertaV2ForSequenceClassification, DebertaV2Tokenizer

                model_class, tokenizer_class = (
                    DebertaV2ForSequenceClassification,
                    DebertaV2Tokenizer,
                )
            else:
                from transformers import BertForSequenceClassification, BertTokenizer

                model_class, tokenizer_class = BertForSequenceClassification, BertTokenizer

            previous = torch.get_num_threads()
            torch.set_num_threads(2)
            try:
                self.phase = "model_load"
                self._tokenizer = tokenizer_class.from_pretrained(
                    root, local_files_only=True, trust_remote_code=False
                )
                self._model = (
                    model_class.from_pretrained(
                        root,
                        local_files_only=True,
                        dtype=torch.float32,
                        trust_remote_code=False,
                        use_safetensors=True,
                    )
                    .cpu()
                    .eval()
                )
                self._torch = torch
                self.phase = "warm"
            finally:
                torch.set_num_threads(previous)
        except BaseException:
            self.close()
            raise

    def rank(
        self, *, query: str, passages: list[dict], matter_id: str, cancellation: Event | None = None
    ):
        packet = rank_input(query, passages, matter_id)
        if cancellation and cancellation.is_set():
            fail("generation_canceled")
        self.warm()
        previous = self._torch.get_num_threads()
        self._torch.set_num_threads(2)
        try:
            started, rows = time.monotonic(), []
            with self._torch.inference_mode():
                for index, passage in enumerate(packet["passages"]):
                    if cancellation and cancellation.is_set():
                        fail("generation_canceled")
                    if time.monotonic() - started > 60:
                        fail("generation_timeout")
                    if psutil.virtual_memory().available < 1024**3:
                        fail("insufficient_available_memory")
                    self.phase = "tokenize"
                    tokens = self._tokenizer(
                        query, passage["text"], truncation=False, return_tensors="pt"
                    )
                    if tokens["input_ids"].shape[-1] > 512:
                        fail("reranker_source_too_long")
                    self.phase = "score"
                    score = scalar_relevance(self._model(**tokens).logits)
                    rows.append(
                        {
                            "source_id": passage["source_id"],
                            "source_index": index,
                            "source_sha256": hashlib.sha256(passage["text"].encode()).hexdigest(),
                            "relevance_score": score,
                            "score_meaning": "passage_relevance_only",
                            "review_required": True,
                            "truth_verified": False,
                        }
                    )
            if packet != rank_input(query, passages, matter_id):
                fail("reranker_source_changed")
            return sorted(rows, key=lambda row: (-row["relevance_score"], row["source_index"]))
        finally:
            self._torch.set_num_threads(previous)

    def close(self):
        self._model = self._tokenizer = self._torch = None
        self._locks.close()
