from __future__ import annotations

import hashlib
import json
import struct
import zipfile
from pathlib import Path

from legal.release.store_asset_validator import validate_store_assets


def _png(path: Path, *, width: int = 1920, height: int = 1080) -> str:
    data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00" + b"\x00\x00\x00\x00"
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    submission = tmp_path / "submission"; screenshots = submission / "screenshots"; screenshots.mkdir(parents=True)
    digest = _png(screenshots / "fictional.png")
    (screenshots / "MANIFEST.json").write_text(json.dumps({"screenshots": [{"file": "fictional.png", "sha256": digest}]}), encoding="utf-8")
    (screenshots / "CAPTIONS.md").write_text("| File | Caption |\n| --- | --- |\n| `fictional.png` | Fictional demonstration workbench using local-only review safeguards. |\n", encoding="utf-8")
    with zipfile.ZipFile(submission / "MaineFamilyLawLLM_v8.0.0_Store_Screenshots.zip", "w") as archive:
        for name in ("fictional.png", "MANIFEST.json", "CAPTIONS.md"):
            archive.write(screenshots / name, name)
    listing = tmp_path / "listing"; listing.mkdir()
    (listing / "support-information.md").write_text("Privacy: docs/PRIVACY_POLICY_MICROSOFT_STORE.html", encoding="utf-8")
    (listing / "en-US.md").write_text("Local-first review workbench. Not legal advice.", encoding="utf-8")
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps({"public_addon_features": ["fictional_verified_feature"], "release_boundaries": {"review_required": True, "local_only": True}}), encoding="utf-8")
    return submission, listing, scope


def test_pass157_validates_png_hash_caption_scope_privacy_and_archive(tmp_path: Path) -> None:
    submission, listing, scope = _fixture(tmp_path)
    report = validate_store_assets(submission_root=submission, listing_root=listing, release_scope_path=scope)
    assert report["status"] == "pass" and report["screenshot_validation"][0]["width"] == 1920
    assert report["accepted_release_scope"]["feature_ids"] == ["fictional_verified_feature"]


def test_pass157_blocks_tampered_screenshot_private_marker_and_unsubstantiated_claim(tmp_path: Path) -> None:
    submission, listing, scope = _fixture(tmp_path)
    (submission / "screenshots" / "fictional.png").write_bytes(b"not-a-png")
    (listing / "en-US.md").write_text("Store certified enterprise GA ready C:\\Users\\private", encoding="utf-8")
    report = validate_store_assets(submission_root=submission, listing_root=listing, release_scope_path=scope)
    assert report["status"] == "blocked"
    assert "listing_unsubstantiated_claim" in report["blockers"] and "listing_private_marker" in report["blockers"]
