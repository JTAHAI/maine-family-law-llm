"""Run in the existing ML environment: real Qwen/PEFT gradient equivalence."""

import copy

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("peft")
pytest.importorskip("transformers")

from peft import LoraConfig, get_peft_model
from transformers import Qwen3Config, Qwen3ForCausalLM

from scripts.train_mfl_native_pilot import answer_only_head_window


@pytest.mark.parametrize("prompt_tokens", [1, 4, 9])
def test_qwen_peft_answer_tail_keeps_identical_loss_and_gradients(prompt_tokens):
    torch.set_num_threads(2)
    torch.manual_seed(9009)
    config = Qwen3Config(vocab_size=67, hidden_size=32, intermediate_size=64,
                         num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
                         head_dim=8, max_position_embeddings=64, attention_dropout=0.0)
    original = get_peft_model(Qwen3ForCausalLM(config), LoraConfig(
        r=2, lora_alpha=4, lora_dropout=0.0, task_type="CAUSAL_LM", target_modules=["q_proj", "v_proj"],
    )).eval()
    optimized = copy.deepcopy(original)
    inputs = torch.tensor([[2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]])
    labels = inputs.clone()
    labels[:, :prompt_tokens] = -100
    full = original(input_ids=inputs, attention_mask=torch.ones_like(inputs), labels=labels)
    window = answer_only_head_window(labels, prompt_tokens)
    short = optimized(input_ids=inputs, attention_mask=torch.ones_like(inputs), **window)
    assert short.logits.shape[1] == inputs.shape[1] - prompt_tokens + 1
    torch.testing.assert_close(full.loss, short.loss, rtol=1e-6, atol=1e-6)
    full.loss.backward()
    short.loss.backward()
    compared = 0
    for (name, a), (other_name, b) in zip(original.named_parameters(), optimized.named_parameters(), strict=True):
        assert name == other_name
        if a.requires_grad:
            assert a.grad is not None and b.grad is not None
            torch.testing.assert_close(a.grad, b.grad, rtol=1e-5, atol=1e-6)
            compared += 1
    assert compared > 0


def test_answer_window_cannot_drop_all_prompt_or_answer_tokens():
    labels = torch.tensor([[-100, 3, 5]])
    for boundary in (0, 3, 4):
        with pytest.raises(ValueError):
            answer_only_head_window(labels, boundary)
