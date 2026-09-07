from types import SimpleNamespace

from legal.model_orchestration import hardware


def test_local_nvidia_probe_is_bounded_and_reports_available_vram(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(hardware.shutil, "which", lambda name: "nvidia-smi.exe")

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            stdout=(
                "0, GPU-FICTIONAL-A, Fictional GPU A, 4096, 2048, 7.5\n"
                "1, GPU-FICTIONAL-B, Fictional GPU B, 12288, 10240, 8.6\n"
            )
        )

    monkeypatch.setattr(hardware.subprocess, "run", run)
    profile = hardware.profile_hardware(tmp_path)
    assert profile.gpu_name == "Fictional GPU B"
    assert profile.vram_bytes == 12288 * 1024**2
    assert profile.available_vram_bytes == 10240 * 1024**2
    assert profile.gpu_compute_capability == 8.6
    assert profile.details["gpus"][1]["compute_capability"] == 8.6
    assert calls[0][1]["timeout"] == 3
    assert calls[0][1]["capture_output"] is True
    assert "no_gpu_hint_detected" not in profile.warnings


def test_gpu_probe_failure_falls_back_without_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(hardware.shutil, "which", lambda name: None)
    profile = hardware.profile_hardware(tmp_path)
    assert profile.details["gpus"] == []
