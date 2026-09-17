"""Fixed generic-comparison profile, never a legal-specialist admission."""

from types import SimpleNamespace

import pytest
from test_compact_bert_boundary import config

from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange.compact_cpu import PinnedFile
from legal.fast_interchange.compact_reranker import (
    CompactPassageReranker,
    validate_ranker_architecture,
)
from scripts.acquire_compact_model_candidates import CATALOG
from scripts.verify_compact_reranker import execute


def deberta_config():
    return {
        **config(),
        "model_type": "deberta-v2",
        "architectures": ["DebertaV2ForSequenceClassification"],
        "num_hidden_layers": 12,
        "num_attention_heads": 6,
        "vocab_size": 128100,
        "relative_attention": True,
        "position_biased_input": False,
        "pos_att_type": ["p2c", "c2p"],
        "type_vocab_size": 0,
    }


def test_comparison_is_pinned_permissive_and_unadmitted():
    item = CATALOG["mixedbread-reranker-comparison"]
    assert len(item["revision"]) == 40 and len(item["weights_sha256"]) == 64
    assert "LICENSE" in item["files"]
    assert "not_legal_specialist" in item["kind"]
    assert item["selected_runtime_bytes"] + 152862657 < 1500000000
    assert not any(p.endswith((".py", ".bin", ".pt")) for p in item["files"])


def test_exact_profile_and_tokenizer():
    validate_ranker_architecture(
        deberta_config(), {"tokenizer_class": "DebertaV2Tokenizer"}, deberta=True
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("num_attention_heads", 12),
        ("num_hidden_layers", 24),
        ("vocab_size", 30522),
        ("relative_attention", 1),
        ("type_vocab_size", False),
        ("pos_att_type", ["c2p"]),
        ("architectures", ["DebertaV2ForTokenClassification"]),
        ("num_labels", 3),
    ],
)
def test_changed_profile_rejected(key, value):
    with pytest.raises(LocalModelError):
        validate_ranker_architecture(
            {**deberta_config(), key: value},
            {"tokenizer_class": "DebertaV2Tokenizer"},
            deberta=True,
        )


def test_profiles_cannot_be_relabelled():
    with pytest.raises(LocalModelError):
        validate_ranker_architecture(deberta_config(), {"tokenizer_class": "BertTokenizer"})
    with pytest.raises(LocalModelError):
        validate_ranker_architecture(
            config(), {"tokenizer_class": "DebertaV2Tokenizer"}, deberta=True
        )


def test_unallowlisted_weight_rejected_before_import_or_lock(tmp_path, monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: SimpleNamespace(available=8 * 1024**3))
    engine = CompactPassageReranker(
        (PinnedFile(tmp_path / "model.safetensors", 10, "f" * 64),), research_only=True
    )
    with pytest.raises(LocalModelError) as error:
        engine.warm()
    assert error.value.code == "fast_interchange_reranker_candidate_not_allowlisted"
    assert engine._model is None
    engine.close()


def test_report_runner_refuses_unapproved_paths():
    with pytest.raises(ValueError, match="candidate_not_allowlisted"):
        execute("reranker-test.json", "extract-selection-holdout-v2.json", candidate="../other")
