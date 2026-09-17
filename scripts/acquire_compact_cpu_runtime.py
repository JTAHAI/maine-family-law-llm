"""Acquire and inventory the pinned upstream CPU engine inside repo dist."""

from __future__ import annotations

import json
import re
import stat
import zipfile

import requests

from scripts.acquire_compact_model_candidates import OUTPUT, download, file_hash, local_path

TAG = "b10865"
SHA256 = "c78058e6baac37e8b0cd3d1da1407ea9677f8d10c5281b3ba94d6dfa4a0265ae"
SIZE = 18_426_211
SOURCE_COMMIT = "d4389a4dd920d24c9592f1dc3badbd69be23bd09"


def engine_member(name):
    return name in {
        "llama-server.exe",
        "llama-server-impl.dll",
        "llama-common.dll",
        "llama.dll",
        "ggml.dll",
        "ggml-base.dll",
        "libomp.dll",
        "mtmd.dll",
    } or bool(re.fullmatch(r"ggml-cpu-[a-z0-9]+\.dll", name))


def main():
    session = requests.Session()
    session.trust_env = False
    OUTPUT.mkdir(parents=True, exist_ok=True)
    archive = local_path(OUTPUT, f"llama-{TAG}-cpu-x64.zip")
    download(
        session,
        f"https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/llama-{TAG}-bin-win-cpu-x64.zip",
        archive,
        {"size": SIZE, "lfs": {"sha256": SHA256}},
    )
    directory = local_path(OUTPUT, "cpu-runtime")
    directory.mkdir(exist_ok=True)
    receipts = []
    with zipfile.ZipFile(archive) as z:
        rows = z.infolist()
        if len(rows) > 128 or sum(r.file_size for r in rows) > 300 * 1024**2:
            raise ValueError("runtime_archive_budget_exceeded")
        names = set()
        for row in rows:
            if row.is_dir():
                continue
            target = local_path(directory, row.filename)
            if row.filename.casefold() in names or stat.S_ISLNK(row.external_attr >> 16):
                raise ValueError("runtime_archive_layout_invalid")
            names.add(row.filename.casefold())
            # The release also contains build/example tools; do not deploy those.
            if not engine_member(row.filename):
                continue
            data = z.read(row)
            if target.exists():
                if target.read_bytes() != data:
                    raise ValueError("runtime_existing_file_mismatch")
            else:
                with target.open("xb") as handle:
                    handle.write(data)
            receipts.append({"path": row.filename, "bytes": len(data), "sha256": file_hash(target)})
    receipt = {
        "schema_version": "mfl_compact_cpu_engine_v1",
        "source": "ggml-org/llama.cpp",
        "source_commit": SOURCE_COMMIT,
        "tag": TAG,
        "archive_sha256": SHA256,
        "files": receipts,
        "production_qualified": False,
    }
    # Do not leave any old examples/RPC tools beside the DLL search directory.
    if {p.name for p in directory.iterdir() if p.suffix.lower() in {".dll", ".exe"}} != {
        row["path"] for row in receipts
    }:
        raise ValueError("runtime_contains_unselected_binaries_remove_verified_old_examples_first")
    license_file = local_path(directory, "LICENSE.llama.cpp.txt")
    download(
        session,
        f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{SOURCE_COMMIT}/LICENSE",
        license_file,
        {"size": 1078, "blobId": "e7dca554bcb802f98408383a864404e3aa4eacca"},
    )
    receipt["notices"] = [{"path": license_file.name, "sha256": file_hash(license_file)}]
    receipt["remaining_notice_review"] = ["OpenMP_runtime_license_and_transitive_notices"]
    target = local_path(directory, "engine-inventory.json")
    # This is a reproducible, unsigned research inventory, not release admission.
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
