"""Acquire one approved public FAST INTERCHANGE base into an external cache.

This utility is intentionally separate from the desktop package.  It obtains
only the public Apache-2.0 Qwen3-0.6B files at an immutable Hugging Face
revision, writes a hash inventory, and refuses to place model bytes inside the
repository.  It never reads matter data, trains adapters, starts a worker, or
changes product admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download


MODEL_ID = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
MODEL_URL = "https://huggingface.co/Qwen/Qwen3-0.6B"
REQUIRED_FILES = (
    "LICENSE",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _inside_external_root(output_root: Path, repository_root: Path) -> Path:
    resolved_output = output_root.resolve(strict=False)
    resolved_repo = repository_root.resolve(strict=True)
    if resolved_output == resolved_repo or resolved_repo in resolved_output.parents:
        raise ValueError("base_output_must_be_outside_repository")
    return resolved_output


def _license_from_card(info: Any) -> str:
    card = getattr(info, "cardData", None) or {}
    getter = getattr(card, "get", None)
    if not callable(getter) or str(getter("license") or "").casefold() != "apache-2.0":
        raise ValueError("base_license_not_apache_2")
    return "Apache-2.0"


def _stage_for_output(output_root: Path, *, resume: bool) -> Path:
    stage = output_root.with_name(output_root.name + ".building")
    if stage.exists() or stage.is_symlink():
        if not resume or stage.is_symlink() or not stage.is_dir():
            raise ValueError("base_stage_exists")
    else:
        stage.mkdir(parents=True)
    return stage


def acquire(*, output_root: Path, repository_root: Path, resume: bool = False) -> dict[str, Any]:
    """Download and inventory the locked public base; never overwrite output."""

    output_root = _inside_external_root(output_root, repository_root)
    if output_root.exists() or output_root.is_symlink():
        raise ValueError("base_output_must_not_exist")
    api = HfApi()
    info = api.model_info(MODEL_ID, revision=MODEL_REVISION, token=False)
    if str(getattr(info, "sha", "")).casefold() != MODEL_REVISION:
        raise ValueError("base_revision_mismatch")
    license_id = _license_from_card(info)
    stage = _stage_for_output(output_root, resume=resume)
    try:
        for name in REQUIRED_FILES:
            cached = Path(
                hf_hub_download(
                    repo_id=MODEL_ID,
                    filename=name,
                    revision=MODEL_REVISION,
                    token=False,
                )
            )
            if not cached.is_file() or cached.is_symlink() or cached.stat().st_size < 1:
                raise RuntimeError(f"base_download_invalid:{name}")
            shutil.copy2(cached, stage / name)
        license_text = (stage / "LICENSE").read_text(encoding="utf-8", errors="replace")
        if "Apache License" not in license_text[:4096]:
            raise ValueError("base_license_text_invalid")
        files = {
            name: {"sha256": _sha256(stage / name), "bytes": (stage / name).stat().st_size}
            for name in REQUIRED_FILES
        }
        provenance = {
            "schema_version": "mfl_fast_interchange_public_base_provenance_v1",
            "model_id": MODEL_ID,
            "official_url": MODEL_URL,
            "revision": MODEL_REVISION,
            "license": license_id,
            "retrieved_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "files_sha256": {name: details["sha256"] for name, details in files.items()},
            "files": files,
            "local_only_after_acquisition": True,
            "contains_matter_data": False,
            "contains_legal_authority_corpus": False,
            "admitted_for_product_use": False,
        }
        (stage / "base-provenance.json").write_bytes(_canonical(provenance))
        stage.replace(output_root)
    except BaseException:
        # An interrupted stage remains external and is never a usable base.
        raise
    return {
        "status": "public_base_acquired",
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "license": license_id,
        "output_root": str(output_root),
        "provenance_sha256": _sha256(output_root / "base-provenance.json"),
        "model_sha256": _sha256(output_root / "model.safetensors"),
        "review_required": True,
        "production_admitted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse an external interrupted staging directory; never replaces a finished base.",
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            acquire(output_root=args.output_root, repository_root=args.repository_root, resume=args.resume),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
