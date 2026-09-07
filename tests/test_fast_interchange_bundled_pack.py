from pathlib import Path

import pytest

from legal.fast_interchange import host
from legal.fast_interchange.worker import FastInterchangeError

_EXPLICIT = (
    "MFL_FAST_INTERCHANGE_ARTIFACT_ROOT",
    "MFL_FAST_INTERCHANGE_RELEASE_REGISTRY",
    "MFL_FAST_INTERCHANGE_ARTIFACT_REGISTRY",
    "MFL_FAST_INTERCHANGE_ADMISSION_CATALOG",
)


def _environment(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    external = tmp_path / "external-packs"
    bundled = tmp_path / "bundle" / "store" / "fast-interchange"
    external.mkdir(parents=True)
    bundled.mkdir(parents=True)
    trust = tmp_path / "trust.json"
    trust.write_text("{}", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    for name in _EXPLICIT:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_PACK_ROOT", str(external))
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_BUNDLED_PACK_ROOT", str(bundled))
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_ADMISSION_TRUST", str(trust))
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_STATE_ROOT", str(state))
    return external, bundled


def test_bundled_pack_is_used_only_when_no_operator_pack_is_active(monkeypatch, tmp_path):
    external, bundled = _environment(monkeypatch, tmp_path)
    marker = object()
    observed = {}

    def load(**kwargs):
        observed.update(kwargs)
        return marker

    monkeypatch.setattr(host.HotSwapRegistry, "load", load)
    assert host.load_operator_registry() is marker
    assert observed["root"] == bundled.resolve()
    assert observed["release_registry"] == bundled.resolve() / "releases.json"
    assert not (external / "active.json").exists()


def test_corrupt_active_operator_pack_never_falls_back_to_bundled(monkeypatch, tmp_path):
    external, _bundled = _environment(monkeypatch, tmp_path)
    (external / "active.json").write_text("{}", encoding="utf-8")
    from app.services import model_pack_service

    monkeypatch.setattr(
        model_pack_service,
        "load_active_pack",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("corrupt")),
    )
    monkeypatch.setattr(
        host.HotSwapRegistry,
        "load",
        lambda **_kwargs: pytest.fail("bundled fallback bypassed corrupt active pack"),
    )
    with pytest.raises(FastInterchangeError, match="fast_interchange_active_pack_unavailable"):
        host.load_operator_registry()
