"""Pinned notice acquisition and installed-wheel comparison; no install/admission.

The upstream license is supplementary: this does not prove that the wheel was
built from the tagged source, audit Rust dependencies, or certify compliance.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import io
import json
import re
import stat
import zipfile
from datetime import UTC, datetime
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

import requests

from scripts.acquire_compact_model_candidates import OUTPUT, local_path

VERSION = "0.22.2"
DIRECTORY = OUTPUT / "runtime-notices" / f"tokenizers-{VERSION}"
WHEEL = {
    "name": "tokenizers-0.22.2-cp39-abi3-win_amd64.whl",
    "url": "https://files.pythonhosted.org/packages/65/71/0670843133a43d43070abeb1949abfdef12a86d490bea9cd9e18e37c5ff7/tokenizers-0.22.2-cp39-abi3-win_amd64.whl",
    "bytes": 2747786,
    "sha256": "c9ea31edff2968b44a88f97d784c2f16dc0729b8b143ed004699ebca91f05c48",
}
LICENSE = {
    "name": "LICENSE.tokenizers.txt",
    "url": "https://raw.githubusercontent.com/huggingface/tokenizers/f383101a26663708484cac0727792aad74f78234/LICENSE",
    "bytes": 11357,
    "git_blob_sha1": "261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64",
    "sha256": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
}
SOURCE_COMMIT = "f383101a26663708484cac0727792aad74f78234"
INFO = f"tokenizers-{VERSION}.dist-info"


def checked_bytes(content, pin):
    if len(content) != pin["bytes"]:
        raise ValueError("notice_artifact_size_mismatch")
    sha = hashlib.sha256(content).hexdigest()
    if "sha256" in pin and sha != pin["sha256"]:
        raise ValueError("notice_artifact_hash_mismatch")
    if "git_blob_sha1" in pin:
        blob = hashlib.sha1(
            f"blob {len(content)}\0".encode() + content, usedforsecurity=False
        ).hexdigest()
        if blob != pin["git_blob_sha1"]:
            raise ValueError("notice_source_blob_mismatch")
    return sha


def acquire(pin, directory=DIRECTORY, *, session=None):
    """At most one fixed HTTPS request; bounded memory, no extraction or redirects."""
    path = local_path(directory, pin["name"])
    if path.exists():
        if path.stat().st_size != pin["bytes"]:
            raise ValueError("notice_artifact_size_mismatch")
        checked_bytes(path.read_bytes(), pin)
        return path
    directory.mkdir(parents=True, exist_ok=True)
    # No ambient proxy credentials, netrc, or automatic redirect to another host.
    owned = session is None
    session = requests.Session() if owned else session
    session.trust_env = False
    try:
        with session.get(
            pin["url"],
            stream=True,
            allow_redirects=False,
            timeout=(10, 20),
            headers={"Accept-Encoding": "identity"},
        ) as response:
            if response.status_code != 200:
                raise ValueError("notice_download_http_failure")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ValueError("notice_encoded_response_forbidden")
            content = bytearray()
            for chunk in response.iter_content(64 * 1024):
                if len(content) + len(chunk) > pin["bytes"]:
                    raise ValueError("notice_download_overflow")
                content.extend(chunk)
            checked_bytes(content, pin)
        # Exclusive creation preserves any prior artifact. No partial is published
        # before the entire small payload has passed the source pin.
        with path.open("xb") as handle:
            handle.write(content)
        return path
    finally:
        if owned:
            session.close()


def wheel_members(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= 100 or sum(e.file_size for e in entries) > 12_000_000:
            raise ValueError("notice_wheel_budget_exceeded")
        names, result = set(), {}
        for entry in entries:
            name = entry.filename
            path = PurePosixPath(name)
            if (
                not name
                or entry.orig_filename != name
                or name != path.as_posix()
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or ":" in name
                or name.casefold() in names
                or entry.flag_bits & 1
                or stat.S_ISLNK(entry.external_attr >> 16)
                or entry.is_dir()
                or not (name.startswith("tokenizers/") or name.startswith(INFO + "/"))
            ):
                raise ValueError("notice_wheel_member_invalid")
            names.add(name.casefold())
            result[name] = archive.read(entry)
    info = BytesParser().parsebytes(result.get(INFO + "/METADATA", b""))
    if info.get("Name") != "tokenizers" or info.get("Version") != VERSION:
        raise ValueError("notice_wheel_identity_mismatch")
    if INFO + "/RECORD" not in result or "tokenizers/tokenizers.pyd" not in result:
        raise ValueError("notice_wheel_inventory_incomplete")
    return result


def inspect_installed(dist, directory=DIRECTORY):
    """Recheck immutable source pins and installed payload, never trust a receipt."""
    if dist.metadata.get("Name") != "tokenizers" or dist.version != VERSION:
        raise ValueError("notice_installed_version_mismatch")
    artifacts, contents = [], []
    for pin in (WHEEL, LICENSE):
        path = local_path(directory, pin["name"])
        if path.stat().st_size != pin["bytes"]:
            raise ValueError("notice_artifact_size_mismatch")
        raw = path.read_bytes()
        artifacts.append({"path": path.name, "bytes": len(raw), "sha256": checked_bytes(raw, pin)})
        contents.append(raw)
    members = wheel_members(contents[0])
    expected = set(members) - {INFO + "/RECORD"}
    installed = {str(p).replace("\\", "/") for p in dist.files or ()}
    installed = {p for p in installed if not p.endswith((".pyc", ".pyo"))}
    allowed_installer = {INFO + "/" + p for p in ("RECORD", "INSTALLER", "REQUESTED")}
    if expected - installed or installed - expected - allowed_installer:
        raise ValueError("notice_installed_inventory_mismatch")
    root = Path(dist.locate_file("")).resolve(strict=True)
    compared = []
    for name in sorted(expected):
        path = Path(dist.locate_file(name))
        # Reject link components, including in the read-only external runtime.
        for component in (path, *path.parents):
            if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
                raise ValueError("notice_installed_link_forbidden")
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("notice_installed_path_outside_runtime")
        if path.stat().st_size != len(members[name]):
            raise ValueError("notice_installed_payload_mismatch")
        raw = path.read_bytes()
        if raw != members[name]:
            raise ValueError("notice_installed_payload_mismatch")
        compared.append(
            {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        )
    return {
        "schema_version": "compact_tokenizers_supplemental_notice_v1",
        "package": "tokenizers",
        "version": VERSION,
        "source_commit": SOURCE_COMMIT,
        "source_license_url": LICENSE["url"],
        "wheel_url": WHEEL["url"],
        "artifacts": artifacts,
        "installed_payload": compared,
        "installed_payload_matches_pinned_wheel": True,
        "supplemental_notice_present": True,
        "wheel_build_from_source_commit_proven": False,
        "transitive_native_notices_qualified": False,
        "license_compliance_approved": False,
        "production_admitted": False,
        "ga_ready": False,
        "limitations": [
            "Release-tag license plus PyPI artifact match; no reproducible-build attestation.",
            "Supplemental notice is not installed into or packaged with the runtime by this tool.",
            "Native dependencies, final package and model quality remain separate release gates.",
        ],
    }


def execute(run_id, *, download=False):
    if re.fullmatch(r"[a-z0-9-]{1,24}", run_id) is None:
        raise ValueError("notice_run_id_invalid")
    output = local_path(OUTPUT, f"tokenizers-notice-proof-{run_id}.json")
    if output.exists():
        raise ValueError("preserve_prior_evidence")
    if download:
        for pin in (WHEEL, LICENSE):
            acquire(pin)
    report = inspect_installed(metadata.distribution("tokenizers"))
    report["timestamp"] = datetime.now(UTC).isoformat()
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "evidence": output.name,
                "matched_files": len(report["installed_payload"]),
                "ga_ready": False,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--acquire", action="store_true", help="Acquire only the two pinned public artifacts"
    )
    args = parser.parse_args()
    execute(args.run_id, download=args.acquire)
