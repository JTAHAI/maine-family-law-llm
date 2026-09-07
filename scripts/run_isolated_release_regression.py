"""Run every collected test in sequential fresh interpreters with coverage accounting.

Evidence and the single owned fixture root stay in repository dist. Authority
tests must supply synthetic repo identities rather than use external scratch.
No tests are deselected or retried to manufacture a passing aggregate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def junit_identity(nodeid: str) -> tuple[str, str]:
    module, separator, tail = nodeid.partition("::")
    if not separator or not module.endswith(".py"):
        raise ValueError(f"Invalid collected test ID: {nodeid}")
    before, bracket, parameters = tail.partition("[")
    parts = before.split("::")
    classname = module[:-3].replace("/", ".").replace("\\", ".")
    if len(parts) > 1:
        classname += "." + ".".join(parts[:-1])
    return classname, parts[-1] + bracket + parameters


def audit_junit(path: Path, expected: list[str]) -> dict:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    expected_keys = Counter(junit_identity(nodeid) for nodeid in expected)
    actual_keys = Counter((case.get("classname", ""), case.get("name", "")) for case in cases)
    failures = [
        f"{case.get('classname')}::{case.get('name')}"
        for case in cases
        if case.find("failure") is not None or case.find("error") is not None
    ]
    skips = [
        {
            "test": f"{case.get('classname')}::{case.get('name')}",
            "reason": case.find("skipped").get("message", ""),
        }
        for case in cases
        if case.find("skipped") is not None
    ]
    return {
        "coverage_matches_collection": actual_keys == expected_keys,
        "tests": len(cases),
        "failed_or_error": len(failures),
        "passed": len(cases) - len(failures) - len(skips),
        "skipped": len(skips),
        "failures": failures,
        "skip_reasons": skips,
        "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def partition_modules(nodeids: list[str], limit: int) -> list[list[str]]:
    modules: dict[str, list[str]] = {}
    for nodeid in nodeids:
        modules.setdefault(nodeid.partition("::")[0], []).append(nodeid)
    batches: list[list[str]] = []
    current: list[str] = []
    for items in modules.values():
        if current and len(current) + len(items) > limit:
            batches.append(current)
            current = []
        current.extend(items)
    if current:
        batches.append(current)
    return batches


def write_report(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_workspace(output: Path):
    directory = output.resolve(strict=True)
    dist = (ROOT / "dist").resolve()
    if directory == dist or not directory.is_relative_to(dist):
        raise ValueError("Fixture storage must remain in repository dist")
    return tempfile.TemporaryDirectory(prefix="fixtures-", dir=directory)


def snapshot_source(output: Path) -> tuple[Path, dict]:
    """Use a real, small source identity with sibling authority fixtures.

    Never copy ignored build/model caches or use links back to writable source.
    Each byte is hashed so this remains verification of the dirty worktree,
    rather than an untraceable clean checkout or a weakened authority guard.
    """
    output = output.resolve(strict=True)
    if not output.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("Source snapshot must stay in repository dist")
    listed = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
    ).decode("utf-8").split("\0")
    files = []
    total = 0
    for relative in sorted(set(filter(None, listed))):
        path = ROOT / relative
        if not path.exists():  # Preserve tracked deletions from the worktree.
            continue
        resolved = path.resolve(strict=True)
        if (
            not resolved.is_relative_to(ROOT.resolve())
            or Path(relative).parts[0] in {"dist", ".git"}
            or any(
                item.is_symlink() or getattr(item, "is_junction", lambda: False)()
                for item in (path, *path.parents)
                if item.is_relative_to(ROOT)
            )
        ):
            raise ValueError("Source snapshot contains forbidden link or path")
        if path.is_file():
            files.append((relative, path))
            total += path.stat().st_size
    if total > 256 * 1024**2 or shutil.disk_usage(output).free < total + 1024**3:
        raise ValueError("Source snapshot exceeds bounded disk budget")
    snapshot = output / "source-snapshot"
    snapshot.mkdir()
    rows = []
    digest = hashlib.sha256()
    for relative, source in files:
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        file_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
        size = destination.stat().st_size
        rows.append({"path": relative, "size": size, "sha256": file_hash})
        digest.update(f"{relative}\0{size}\0{file_hash}\n".encode())
    proof = {
        "source": str(ROOT), "snapshot": str(snapshot), "bytes": total,
        "files": rows, "tree_sha256": digest.hexdigest(),
        "includes_uncommitted_source": True, "includes_ignored_model_or_build_data": False,
    }
    write_report(output / "source-snapshot.json", proof)
    return snapshot, proof


def stop_owned_test_process(process, env: dict) -> None:
    """Stop only the launched test tree, including Windows venv children."""
    if sys.platform == "win32":
        result = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            cwd=ROOT, env=env, capture_output=True, timeout=20, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 and process.poll() is None:
            raise RuntimeError("Unable to stop owned test process tree")
    else:
        process.kill()
    process.wait(timeout=15)


def run_command(
    command: list[str], log: Path, timeout: int, env: dict, *, cwd: Path | None = None
) -> dict:
    started = time.monotonic()
    peak_rss = 0
    try:
        import psutil
    except ImportError:
        psutil = None
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            command,
            cwd=cwd or ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        last_progress = started
        while process.poll() is None:
            if psutil is not None:
                try:
                    peak_rss = max(peak_rss, psutil.Process(process.pid).memory_info().rss)
                except psutil.Error:
                    pass
            if time.monotonic() - started > timeout:
                stop_owned_test_process(process, env)
                return {
                    "exit_code": process.returncode,
                    "timed_out": True,
                    "seconds": round(time.monotonic() - started, 3),
                    "peak_sampled_parent_rss": peak_rss,
                }
            if time.monotonic() - last_progress >= 30:
                print(f"Still running {log.stem}: {time.monotonic() - started:.0f}s", flush=True)
                last_progress = time.monotonic()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    return {
        "exit_code": process.returncode,
        "timed_out": False,
        "seconds": round(time.monotonic() - started, 3),
        "peak_sampled_parent_rss": peak_rss,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-tests", type=int, default=250)
    parser.add_argument("--batch-timeout", type=int, default=1800)
    parser.add_argument("--snapshot-source", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "dist") or output == ROOT / "dist":
        parser.error("Evidence must be a dedicated repository dist child")
    if output.exists() or args.batch_tests < 1 or args.batch_timeout < 60:
        parser.error("Use a new evidence directory and positive batch limits")
    output.mkdir(parents=True)
    source_root, snapshot = snapshot_source(output) if args.snapshot_source else (ROOT, None)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(source_root) + os.pathsep + str(source_root / "src")
    collection_command = [sys.executable, "-m", "pytest", "-o", "addopts=", "--collect-only", "-q"]
    collected = subprocess.run(
        collection_command, cwd=source_root, env=env, capture_output=True, text=True, timeout=180
    )
    (output / "collection.log").write_text(collected.stdout + collected.stderr, encoding="utf-8")
    nodeids = [
        line.strip()
        for line in collected.stdout.splitlines()
        if line.startswith(("tests/", "tests\\")) and "::" in line
    ]
    report = {
        "schema": "mfl.isolated-full-regression.v1",
        "status": "running",
        "python": sys.version,
        "interpreter": sys.executable,
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "collection_command": collection_command,
        "collection_exit": collected.returncode,
        "collected": len(nodeids),
        "collection_sha256": hashlib.sha256("\n".join(nodeids).encode()).hexdigest(),
        "batches": [],
        "retries": 0,
        "deselections": 0,
        "source_root": str(source_root),
        "source_snapshot_tree_sha256": snapshot["tree_sha256"] if snapshot else None,
        "legal_or_installed_app_certification": False,
    }
    report_path = output / "summary.json"
    if collected.returncode or not nodeids or len(nodeids) != len(set(nodeids)):
        report["status"] = "collection_failed"
        write_report(report_path, report)
        return 1
    write_report(output / "collection.json", {"nodeids": nodeids})
    batches = partition_modules(nodeids, args.batch_tests)
    started = time.monotonic()
    # Owned, ephemeral fixture storage only; never reuse or delete user paths.
    with fixture_workspace(output) as temporary:
        env["TEMP"] = temporary
        env["TMP"] = temporary
        for index, expected in enumerate(batches, 1):
            name = f"batch-{index:02d}"
            argfile = output / f"{name}.args"
            argfile.write_text("\n".join(expected) + "\n", encoding="utf-8")
            junit = output / f"{name}.xml"
            command = [
                sys.executable,
                "-m",
                "pytest",
                "-o",
                "addopts=",
                "-q",
                "--tb=short",
                "@" + str(argfile),
                "--basetemp=" + str(Path(temporary) / name),
                "--junitxml=" + str(junit),
            ]
            print(f"Starting {name}/{len(batches)}: {len(expected)} tests", flush=True)
            result = run_command(
                command, output / f"{name}.log", args.batch_timeout, env, cwd=source_root
            )
            result.update(name=name, command=command, expected=len(expected))
            if junit.exists():
                result.update(audit_junit(junit, expected))
            else:
                result.update(
                    coverage_matches_collection=False,
                    tests=0,
                    passed=0,
                    failed_or_error=0,
                    skipped=0,
                )
            report["batches"].append(result)
            write_report(report_path, report)
            print(
                f"Finished {name}: exit={result['exit_code']}, "
                f"passed={result['passed']}, failed={result['failed_or_error']}, "
                f"skipped={result['skipped']}",
                flush=True,
            )
    report["temporary_fixture_root_removed"] = not Path(temporary).exists()
    report["seconds"] = round(time.monotonic() - started, 3)
    report["totals"] = {
        key: sum(row[key] for row in report["batches"])
        for key in ("tests", "passed", "failed_or_error", "skipped")
    }
    report["status"] = (
        "pass"
        if all(
            row["exit_code"] == 0 and row["coverage_matches_collection"]
            for row in report["batches"]
        )
        and report["totals"]["tests"] == len(nodeids)
        else "fail"
    )
    write_report(report_path, report)
    print(json.dumps({"status": report["status"], **report["totals"]}), flush=True)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
