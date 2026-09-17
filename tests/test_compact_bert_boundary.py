"""Scalar relevance and fixed BERT architecture; not model-quality certification."""

from types import SimpleNamespace

import pytest

from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange.compact_reranker import scalar_relevance, validate_ranker_architecture


def config():
    return dict(
        model_type="bert",
        architectures=["BertForSequenceClassification"],
        hidden_size=384,
        num_hidden_layers=6,
        num_attention_heads=12,
        intermediate_size=1536,
        vocab_size=30522,
        max_position_embeddings=512,
        id2label={"0": "LABEL_0"},
        label2id={"LABEL_0": 0},
    )


@pytest.mark.parametrize("tokenizer", ["BertTokenizer", "BertTokenizerFast"])
def test_fixed_scalar_architecture_accepted(tokenizer):
    validate_ranker_architecture(config(), {"tokenizer_class": tokenizer})


@pytest.mark.parametrize(
    "key,value",
    [
        ("architectures", ["CustomModel"]),
        ("architectures", []),
        ("num_attention_heads", 6),
        ("hidden_size", 385),
        ("model_type", "custom"),
        ("num_labels", 2),
        ("num_labels", True),
        ("num_labels", 1.0),
        ("id2label", {"0": "LABEL_0", "1": "LABEL_1"}),
        ("label2id", {"LABEL_0": False}),
        ("is_decoder", True),
        ("is_decoder", 0),
        ("add_cross_attention", True),
    ],
)
def test_other_or_malformed_architecture_is_rejected(key, value):
    with pytest.raises(LocalModelError) as error:
        validate_ranker_architecture({**config(), key: value}, {"tokenizer_class": "BertTokenizer"})
    assert error.value.code == "fast_interchange_reranker_architecture_invalid"


@pytest.mark.parametrize("name", [None, "AutoTokenizer", "CustomTokenizer"])
def test_other_tokenizer_is_rejected(name):
    with pytest.raises(LocalModelError):
        validate_ranker_architecture(config(), {"tokenizer_class": name})


@pytest.mark.parametrize("shape", [(), (1,), (1, 2), (2, 1), (1, 1, 1), (0, 1)])
def test_non_scalar_logits_are_not_silently_truncated(shape):
    value = SimpleNamespace(shape=shape, reshape=lambda _: pytest.fail("must not read logits"))
    with pytest.raises(LocalModelError) as error:
        scalar_relevance(value)
    assert error.value.code == "fast_interchange_reranker_score_shape_invalid"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_score_is_rejected(value):
    with pytest.raises(LocalModelError):
        scalar_relevance(SimpleNamespace(shape=(1, 1), reshape=lambda _: [value]))


def test_raw_scalar_remains_relevance_not_probability():
    assert scalar_relevance(SimpleNamespace(shape=(1, 1), reshape=lambda _: [-3.25])) == -3.25
