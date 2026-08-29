"""Synthetic completion contracts, not model-quality or hardware evidence."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_fast_interchange_worker import _FakeBackend, _registry

from legal.fast_interchange.worker import (
    FastInterchangeError,
    HotSwapManager,
    TransformersPeftAdapterBackend,
    create_worker_app,
)


@pytest.mark.parametrize(
    "fault", ["length", "missing_stop", "tool_call", "role", "content", "multiple"]
)
def test_manager_quarantines_incomplete_or_non_text_completion(tmp_path, fault):
    registry = _registry(tmp_path)
    release = registry.select("family-evidence-small-r1", allow_test_only=True)

    class UnsafeBackend(_FakeBackend):
        def complete(self, **kwargs):
            response = super().complete(**kwargs)
            choice = response["choices"][0]
            if fault == "length":
                choice["finish_reason"] = "length"
            elif fault == "missing_stop":
                choice.pop("finish_reason")
            elif fault == "tool_call":
                choice["message"]["tool_calls"] = [{"name": "unsafe"}]
            elif fault == "role":
                choice["message"]["role"] = "system"
            elif fault == "content":
                choice["message"]["content"] = {"secret": "synthetic-canary"}
            elif fault == "multiple":
                response["choices"].append(choice.copy())
            return response

    backend = UnsafeBackend()
    manager = HotSwapManager(registry=registry, backend=backend, allow_test_only=True)
    with pytest.raises(FastInterchangeError, match="fast_interchange_completion_invalid"):
        manager.complete(release=release, messages=[{"role": "user", "content": "fictional"}])
    assert manager.status()["quarantined"] is True
    assert manager.status()["requests"] == 0
    assert backend.clears >= 3
    with pytest.raises(FastInterchangeError, match="worker_quarantined"):
        manager.complete(release=release, messages=[{"role": "user", "content": "fictional"}])


def test_worker_api_withholds_partial_text_and_discloses_quarantine(tmp_path):
    registry = _registry(tmp_path)

    class PartialBackend(_FakeBackend):
        def complete(self, **kwargs):
            response = super().complete(**kwargs)
            response["choices"][0]["finish_reason"] = "length"
            response["choices"][0]["message"]["content"] = "FICTIONAL-PARTIAL-CANARY"
            return response

    manager = HotSwapManager(registry=registry, backend=PartialBackend(), allow_test_only=True)
    # Keep a generated test value out of public-source secret scanners. It is
    # intentionally not a credential, fixture literal, or environment value.
    token = "x" * 64
    client = TestClient(
        create_worker_app(
            manager=manager, registry=registry, worker_token=token, allow_test_only=True
        )
    )
    request = {
        "model": "family-evidence-small-r1",
        "messages": [{"role": "user", "content": "fictional"}],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 1024,
        "stream": False,
    }
    response = client.post(
        "/v1/chat/completions", json=request, headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 400
    assert response.json() == {"error": {"code": "fast_interchange_completion_invalid"}}
    assert response.headers["Cache-Control"] == "no-store"
    assert "FICTIONAL-PARTIAL-CANARY" not in response.text
    assert token not in response.text
    assert client.get("/healthz").json()["status"] == "quarantined"
    assert (
        client.post(
            "/v1/chat/completions", json=request, headers={"Authorization": "Bearer " + token}
        ).status_code
        == 503
    )


class _Tensor:
    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]))

    def to(self, _device):
        return self

    def __getitem__(self, index):
        return _Row(self.rows[index])


class _Row(list):
    def __getitem__(self, index):
        value = super().__getitem__(index)
        return _Row(value) if isinstance(index, slice) else value

    def tolist(self):
        return list(self)


def _backend(*, prompt_tokens=3, output_tokens=None, eos=2):
    state = {"generated": False, "decoded": False}

    class Tokenizer:
        eos_token_id = eos

        def __call__(self, _prompt, **options):
            state["tokenizer_options"] = options
            return {"input_ids": _Tensor([[1] * prompt_tokens])}

        def decode(self, _tokens, **_options):
            state["decoded"] = True
            return "fictional complete response"

    class Model:
        generation_config = SimpleNamespace(eos_token_id=eos)

        def parameters(self):
            yield SimpleNamespace(device="cpu")

        def generate(self, **options):
            state["generated"] = True
            state["generation_options"] = options
            return _Tensor([[1] * prompt_tokens + (output_tokens or [7, 2])])

    backend = TransformersPeftAdapterBackend(allow_cpu=True)
    backend._tokenizer = Tokenizer()
    backend._model = Model()
    backend._torch = SimpleNamespace(no_grad=nullcontext)
    return backend, state


def test_backend_rejects_prompt_over_budget_without_truncation_or_generation():
    backend, state = _backend(prompt_tokens=2049)
    with pytest.raises(FastInterchangeError, match="fast_interchange_context_limit_exceeded"):
        backend.complete(
            release=SimpleNamespace(model_id="fictional-model"),
            messages=[{"role": "user", "content": "fictional"}],
        )
    assert state["tokenizer_options"]["truncation"] is False
    assert state["generated"] is False


@pytest.mark.parametrize("shape", [(1, 0), (0, 3), (2, 3), (3,), ()])
def test_backend_rejects_empty_or_malformed_tokenization_before_generation(shape):
    backend, state = _backend()
    tensor = _Tensor([[1, 1, 1]])
    tensor.shape = shape
    backend._tokenizer = lambda *_args, **_kwargs: {"input_ids": tensor}
    with pytest.raises(FastInterchangeError, match="fast_interchange_tokenization_invalid"):
        backend.complete(
            release=SimpleNamespace(model_id="fictional-model"),
            messages=[{"role": "user", "content": "fictional"}],
        )
    assert state["generated"] is False
    assert state["decoded"] is False


def test_backend_rejects_missing_input_ids_before_generation():
    backend, state = _backend()
    backend._tokenizer = lambda *_args, **_kwargs: {}
    with pytest.raises(FastInterchangeError, match="fast_interchange_tokenization_invalid"):
        backend.complete(
            release=SimpleNamespace(model_id="fictional-model"),
            messages=[{"role": "user", "content": "fictional"}],
        )
    assert state["generated"] is False


@pytest.mark.parametrize(
    "tokens,eos",
    [([7] * 1024, 2), ([7] * 1023 + [2], 2), ([7, 8], 2), ([7, 2], None)],
    ids=["budget-no-eos", "forced-eos-at-budget", "missing-eos", "unknown-eos"],
)
def test_backend_refuses_to_call_unterminated_output_complete(tokens, eos):
    backend, state = _backend(output_tokens=tokens, eos=eos)
    with pytest.raises(FastInterchangeError, match="fast_interchange_completion_incomplete"):
        backend.complete(
            release=SimpleNamespace(model_id="fictional-model"),
            messages=[{"role": "user", "content": "fictional"}],
        )
    assert state["decoded"] is False


@pytest.mark.parametrize("eos", [2, [2, 3]])
def test_backend_accepts_explicit_eos_and_preserves_fixed_generation(eos):
    backend, state = _backend(eos=eos)
    result = backend.complete(
        release=SimpleNamespace(model_id="fictional-model"),
        messages=[{"role": "user", "content": "fictional"}],
    )
    assert result["choices"][0]["finish_reason"] == "stop"
    assert state["generation_options"]["use_cache"] is False
    assert state["generation_options"]["do_sample"] is False
    assert state["generation_options"]["max_new_tokens"] == 1024
