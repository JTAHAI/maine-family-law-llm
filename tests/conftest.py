from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (SRC, ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


@pytest.fixture(autouse=True)
def isolated_replay_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tests use different fictional encryption keys, never one shared registry.

    An inherited MFL_IDEMPOTENCY_STATE_ROOT takes priority over the runtime root
    that individual tests configure. Keeping replay state test-owned prevents
    cross-test key collisions and accidental access to a developer's profile.
    A test may still explicitly override this root to exercise persistence.
    """
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "replay-state"))
