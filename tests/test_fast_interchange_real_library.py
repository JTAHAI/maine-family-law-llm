"""Actual CPU libraries and safetensors with tiny constructed, non-legal weights.

This is a loader/inference test, NOT a trained law model, evaluation corpus,
hardware-performance qualification, or legal-quality certificate. No download.
"""

from __future__ import annotations

import hashlib
import socket
from copy import deepcopy
from dataclasses import asdict, replace
from importlib.metadata import version

import pytest
from test_fast_interchange_artifact_registry import admitted  # noqa: F401
from test_fast_interchange_worker import _release

from legal.fast_interchange.admission import digest
from legal.fast_interchange.worker import (
    ArtifactBinding,
    ArtifactFile,
    ArtifactInventory,
    HotSwapManager,
    HotSwapRegistry,
    TransformersPeftAdapterBackend,
)


def test_actual_cpu_load_inference_and_cleanup_without_network(admitted, tmp_path, monkeypatch):  # noqa: F811
    torch = pytest.importorskip(
        "torch", reason="Actual CPU inference needs the optional ML runtime"
    )
    pytest.importorskip("peft", reason="Actual adapter loading needs the optional PEFT runtime")
    from peft import LoraConfig, get_peft_model
    from tokenizers import Tokenizer
    from tokenizers.decoders import ByteLevel as ByteLevelDecoder
    from tokenizers.models import BPE
    from tokenizers.pre_tokenizers import ByteLevel
    from transformers import AutoTokenizer, PreTrainedTokenizerFast, Qwen2Config, Qwen2ForCausalLM

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    network_attempts = []

    def no_connect(_socket, target):
        network_attempts.append(str(target))
        raise AssertionError("Outbound network is forbidden in this local-library test")

    monkeypatch.setattr(socket.socket, "connect", no_connect)
    root = tmp_path / "tiny-constructed-weights"
    base_dir, adapter_dir = root / "base", root / "adapter"
    base_dir.mkdir(parents=True)
    prior_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    manager = None
    try:
        # A complete byte vocabulary is compatible with the real Qwen loader.
        # Transformers 5 selects Qwen2Tokenizer from model_type and reconstructs
        # BPE; the former four-token WordLevel fixture silently lost all input.
        vocabulary = {"<unk>": 0, "fictional": 1, "<eos>": 2, "<pad>": 3}
        vocabulary.update(
            {token: index + 4 for index, token in enumerate(sorted(ByteLevel.alphabet()))}
        )
        tokenizer_core = Tokenizer(BPE(vocabulary, [], unk_token="<unk>"))
        tokenizer_core.pre_tokenizer = ByteLevel(add_prefix_space=False)
        tokenizer_core.decoder = ByteLevelDecoder()
        tokenizer = PreTrainedTokenizerFast(
            tokenizer_object=tokenizer_core, unk_token="<unk>", eos_token="<eos>", pad_token="<pad>"
        )
        tokenizer.save_pretrained(base_dir)
        config = Qwen2Config(
            vocab_size=len(vocabulary),
            hidden_size=16,
            intermediate_size=32,
            num_hidden_layers=1,
            num_attention_heads=2,
            num_key_value_heads=2,
            max_position_embeddings=256,
            eos_token_id=2,
            pad_token_id=3,
            tie_word_embeddings=False,
        )
        model = Qwen2ForCausalLM(config)
        # Deterministic actual neural inference: input byte -> "fictional" -> EOS.
        # This hand-constructed toy intentionally has NO legal knowledge.
        with torch.no_grad():
            for name, parameter in model.named_parameters():
                parameter.zero_()
                if "norm" in name and name.endswith("weight"):
                    parameter.fill_(1)
            model.model.embed_tokens.weight[:, 0] = 1
            model.model.embed_tokens.weight[1, 0] = 0
            model.model.embed_tokens.weight[1, 1] = 1
            model.lm_head.weight[1, 0] = 1
            model.lm_head.weight[2, 1] = 1
        model.save_pretrained(base_dir, safe_serialization=True)
        reloaded_tokenizer = AutoTokenizer.from_pretrained(
            base_dir, local_files_only=True, trust_remote_code=False
        )
        assert reloaded_tokenizer("[USER]\nFixture source only")["input_ids"]
        adapted = get_peft_model(
            model,
            LoraConfig(
                r=2,
                lora_alpha=4,
                target_modules=["q_proj"],
                task_type="CAUSAL_LM",
                inference_mode=True,
            ),
        )
        adapted.save_pretrained(adapter_dir, safe_serialization=True)

        def artifact(path):
            content = path.read_bytes()
            return ArtifactFile(
                path.relative_to(root).as_posix(), hashlib.sha256(content).hexdigest(), len(content)
            )

        def inventory(paths):
            return ArtifactInventory(
                tuple(sorted((artifact(path) for path in paths), key=lambda row: row.path))
            )

        # Tokenizer inventory is disjoint from the base inventory.
        token_names = {"tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"}
        binding = ArtifactBinding(
            "fictional-real-library-r1",
            "a" * 64,
            "base",
            "adapter",
            inventory(path for path in base_dir.iterdir() if path.name not in token_names),
            inventory(path for path in base_dir.iterdir() if path.name in token_names),
            inventory(path for path in adapter_dir.iterdir() if path.name != "adapter_config.json"),
            artifact(adapter_dir / "adapter_config.json"),
        )
        release = _release(binding.release_id, binding.release_id, "evidence_review", binding)
        release["admission"] = "admitted_for_dev"
        release["prompt_template_sha256"] = hashlib.sha256(
            b"fi-fixed-role-v1:[ROLE]\\nCONTENT;join=\\n"
        ).hexdigest()
        import json

        registry = HotSwapRegistry.from_dicts(
            root=root,
            releases={"schema": "fast_interchange_releases_v1", "releases": [release]},
            artifacts={
                "schema": "fast_interchange_artifacts_v1",
                "bindings": [json.loads(json.dumps(asdict(binding)))],
            },
        )
        payload = deepcopy(admitted["payload"])
        payload["catalog_id"] = "fictional-constructed-weights-catalog"
        payload["release_registry_sha256"] = digest(registry.release_document)
        payload["artifact_registry_sha256"] = digest(registry.artifact_document)
        grant = deepcopy(payload["grants"][0])
        grant.update(
            release_id=release["release_id"],
            model_id=release["model_id"],
            capability="evidence_review",
        )
        grant["compatibility"].update(
            {
                name + "_version": version(name)
                for name in ("torch", "transformers", "peft", "safetensors")
            }
        )
        grant["compatibility"].update(
            prompt_template_sha256=release["prompt_template_sha256"],
            max_context_tokens=64,
            max_new_tokens=8,
        )
        payload["grants"] = [grant]
        registry = replace(
            registry,
            admission_authority=admitted["authority"],
            signed_catalog=admitted["sign"](payload),
        )
        manager = HotSwapManager(
            registry=registry, backend=TransformersPeftAdapterBackend(allow_cpu=True)
        )
        selected = registry.select(release["model_id"], allow_test_only=False)
        for _ in range(2):
            result = manager.complete(
                release=selected, messages=[{"role": "user", "content": "Fixture source only"}]
            )
            assert result["choices"][0]["message"]["content"] == "fictional"
            assert result["choices"][0]["finish_reason"] == "stop"
        assert manager.status()["requests"] == 2
        assert not network_attempts
    finally:
        if manager is not None:
            manager.close()
        torch.set_num_threads(prior_threads)
