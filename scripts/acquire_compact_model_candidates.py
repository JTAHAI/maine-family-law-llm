"""Pinned, bounded public research downloads; no model admission or activation.

All files stay in one repository-owned directory. Existing valid files are reused,
partial files are resumed only after byte verification by a complete final hash.
Neither model repository code nor pickle files are accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

from legal.security.strict_json import strict_json_load_path, strict_json_loads

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/model-candidates/compact-fleet-20260908"
MAX_MODEL_BYTES = 1_500_000_000
CATALOG = {
    "minilm-span-reader": {
        "repo": "deepset/minilm-uncased-squad2",
        "revision": "934656cdda79824eabf503ed56e15c01ddbdbe3f",
        "kind": "extractive_qa_research_candidate_not_legal_specialist",
        "license": "cc-by-4.0",
        "files": [
            "README.md",
            "config.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "model.safetensors",
        ],
        "weights_sha256": "240478c7251d5e55be35feb47177054b960259b9328af662ea3cee87ce9755a6",
        "selected_runtime_bytes": 722_650_377,
    },
    "mixedbread-reranker-comparison": {
        "repo": "mixedbread-ai/mxbai-rerank-xsmall-v1",
        "revision": "b5c6e9da73abc3711f593f705371cdbe9e0fe422",
        "kind": "generic_passage_relevance_comparison_not_legal_specialist",
        "files": [
            "LICENSE",
            "README.md",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "added_tokens.json",
            "spm.model",
            "model.safetensors",
        ],
        "weights_sha256": "a29bc212faf59c136ad0fd5712ecd2346e7b32c44a25b690625bc9ecebb14b8f",
        "selected_runtime_bytes": 722_650_377,
    },
    "text-relation-nli": {
        "repo": "cross-encoder/nli-deberta-v3-small",
        "revision": "fa2804872c3b4bd748f38c0185cc85775361e735",
        "kind": "generic_text_relation_research_candidate_not_legal_verifier",
        "files": [
            "README.md",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "added_tokens.json",
            "model.safetensors",
        ],
        "weights_sha256": "ebc79588dd73ccfb6a3f6078519cfbf512c5305384c5ea1845bc71cd32216e86",
        # Existing selected runtime + Python audit, not a qualified native closure.
        "selected_runtime_bytes": 722_639_020,
    },
    "qwen3-compact-comparison": {
        "repo": "unsloth/Qwen3-1.7B-GGUF",
        "revision": "d7f544eead698dbd1f15126ef60b45a1e1933222",
        "kind": "general_generator_comparison_not_legal_specialist",
        "files": ["README.md", "Qwen3-1.7B-Q6_K.gguf"],
        "weights_sha256": "6a9cadec4883df6f3efcf337103479dcc6a3efa9f5f8cc64a904dba57808207a",
        "upstream_license": {
            "repo": "Qwen/Qwen3-1.7B",
            "revision": "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
            "size": 11343,
            "blobId": "6634c8cc3133b3848ec74b9f275acaaa1ea618ab",
        },
    },
    "qwen-drafting-base": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "revision": "91cad51170dc346986eccefdc2dd33a9da36ead9",
        "kind": "general_generator_candidate_for_source_bound_adaptation",
        "files": ["LICENSE", "README.md", "qwen2.5-1.5b-instruct-q5_k_m.gguf"],
        "weights_sha256": "b46661073c18e5b56a41fa320975f866a00def1ff08feef4718e013258896f8c",
    },
    "legal-passage-reranker": {
        "repo": "narcolepticchicken/legalbenchrag-cuad-topone-reranker",
        "revision": "ce341fa4fce71a445664ed382fd77ff65fc4806c",
        "kind": "contract_passage_relevance_specialist_candidate",
        "files": [
            "README.md",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "model.safetensors",
            "config_sentence_transformers.json",
        ],
        "weights_sha256": "f5d4bf917d7da08c3c1ec8fa346b64505787abed6e785c4ec8bc9c122568ac86",
    },
}


def safe_url(url: str) -> None:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or not (
            host
            in {
                "huggingface.co",
                "github.com",
                "release-assets.githubusercontent.com",
                "raw.githubusercontent.com",
            }
            or host.endswith(".hf.co")
            or host.endswith(".huggingface.co")
        )
    ):
        raise ValueError("candidate_download_origin_forbidden")


def get(session, url, **kwargs):
    for _ in range(6):
        safe_url(url)
        response = session.get(url, allow_redirects=False, timeout=(15, 60), **kwargs)
        if response.status_code not in {301, 302, 303, 307, 308}:
            try:
                response.raise_for_status()
            except Exception:
                response.close()
                raise
            return response
        from urllib.parse import urljoin

        url = urljoin(url, response.headers["Location"])
        response.close()
    raise ValueError("candidate_download_redirect_limit")


def bounded_json(response, maximum=2_000_000):
    chunks, size = [], 0
    for chunk in response.iter_content(8192):
        size += len(chunk)
        if size > maximum:
            raise ValueError("candidate_metadata_size_exceeded")
        chunks.append(chunk)
    return strict_json_loads(b"".join(chunks), max_bytes=maximum, require_object=True)


def local_path(directory: Path, name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,180}", name):
        raise ValueError("candidate_filename_invalid")
    target = directory / name
    for item in [target, *target.parents]:
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError("candidate_link_forbidden")
    if ROOT / "dist" not in target.resolve().parents:
        raise ValueError("candidate_output_must_be_repository_dist")
    return target


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify_file(path: Path, row: dict) -> str:
    if path.stat().st_size != row["size"]:
        raise ValueError("candidate_size_mismatch")
    sha = file_hash(path)
    if row.get("lfs"):
        if sha != row["lfs"]["sha256"]:
            raise ValueError("candidate_hash_mismatch")
    else:
        digest = hashlib.sha1(f"blob {row['size']}\0".encode(), usedforsecurity=False)
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != row["blobId"]:
            raise ValueError("candidate_metadata_hash_mismatch")
    return sha


def download(session, url: str, target: Path, row: dict) -> str:
    size = row["size"]
    if type(size) is not int or not 0 < size < MAX_MODEL_BYTES:
        raise ValueError("candidate_size_budget_exceeded")
    if target.exists():
        return verify_file(target, row)
    partial = local_path(target.parent, target.name + ".partial")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > size:
        raise ValueError("candidate_partial_size_invalid")
    if offset < size:
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        with get(session, url, stream=True, headers=headers) as response:
            if offset and (
                response.status_code != 206
                or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")
            ):
                raise ValueError("candidate_resume_not_supported")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ValueError("candidate_encoded_response_forbidden")
            with partial.open("ab" if offset else "xb") as handle:
                for block in response.iter_content(1024 * 1024):
                    offset += len(block)
                    if offset > size:
                        raise ValueError("candidate_download_overflow")
                    handle.write(block)
    sha = verify_file(partial, row)
    partial.rename(target)
    return sha


def acquire(key: str, *, session=None) -> dict:
    candidate = CATALOG[key]
    session = session or requests.Session()
    session.trust_env = False
    repo, revision = candidate["repo"], candidate["revision"]
    with get(
        session,
        f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true",
        stream=True,
    ) as r:
        info = bounded_json(r)
    license_id = candidate.get("license", "apache-2.0")
    if license_id not in {"apache-2.0", "cc-by-4.0"}:
        raise ValueError("candidate_license_not_allowlisted")
    if info.get("sha") != revision or info.get("cardData", {}).get("license") != license_id:
        raise ValueError("candidate_revision_or_license_mismatch")
    inventory = {row["rfilename"]: row for row in info["siblings"]}
    rows = [inventory[name] for name in candidate["files"]]
    if any(
        type(row.get("size")) is not int or not 0 < row["size"] < MAX_MODEL_BYTES for row in rows
    ):
        raise ValueError("candidate_size_budget_exceeded")
    upstream_license = candidate.get("upstream_license")
    total = sum(row["size"] for row in rows) + (upstream_license["size"] if upstream_license else 0)
    if total + candidate.get("selected_runtime_bytes", 0) >= MAX_MODEL_BYTES:
        raise ValueError("candidate_complete_package_exceeds_budget")
    weights = [r for r in rows if r["rfilename"].endswith((".gguf", ".safetensors"))]
    if len(weights) != 1 or weights[0]["lfs"]["sha256"] != candidate["weights_sha256"]:
        raise ValueError("candidate_pinned_weights_mismatch")
    directory = local_path(OUTPUT, key)
    if shutil.disk_usage(ROOT).free < total + 2 * 1024**3:
        raise ValueError("candidate_insufficient_disk_headroom")
    directory.mkdir(parents=True, exist_ok=True)
    receipts = []
    for row in rows:
        name = row["rfilename"]
        sha = download(
            session,
            f"https://huggingface.co/{repo}/resolve/{revision}/{name}",
            local_path(directory, name),
            row,
        )
        receipts.append({"path": name, "bytes": row["size"], "sha256": sha})
        print(f"Verified {key}/{name}: {row['size']} bytes", flush=True)
    if upstream_license:
        sha = download(
            session,
            f"https://huggingface.co/{upstream_license['repo']}/resolve/"
            f"{upstream_license['revision']}/LICENSE",
            local_path(directory, "LICENSE"),
            upstream_license,
        )
        receipts.append({"path": "LICENSE", "bytes": upstream_license["size"], "sha256": sha})
    receipt = {
        "schema_version": "mfl_compact_candidate_acquisition_v1",
        "id": key,
        "source": repo,
        "revision": revision,
        "license_declared": {"apache-2.0": "Apache-2.0", "cc-by-4.0": "CC-BY-4.0"}[license_id],
        "license_evidence": "LICENSE"
        if "LICENSE" in candidate["files"] or upstream_license
        else "README.md",
        "kind": candidate["kind"],
        "total_bytes": total,
        "maximum_bytes": MAX_MODEL_BYTES,
        "files": receipts,
        "acquired_at": datetime.now(UTC).isoformat(),
        "production_admitted": False,
        "model_quality_verified": False,
        "contains_private_matter_data": False,
        "review_required": True,
    }
    if upstream_license:
        receipt["upstream_license"] = upstream_license
    path = local_path(directory, "acquisition.json")
    if not path.exists():
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    else:
        existing = strict_json_load_path(path, max_bytes=256_000, require_object=True)
        if {k: v for k, v in existing.items() if k != "acquired_at"} != {
            k: v for k, v in receipt.items() if k != "acquired_at"
        }:
            raise ValueError("candidate_existing_receipt_mismatch")
        return existing
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=CATALOG)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if not args.download:
        print(json.dumps(CATALOG[args.candidate], indent=2))
        return
    print(json.dumps(acquire(args.candidate), indent=2))


if __name__ == "__main__":
    main()
