"""Candidate inventory from observed imports, never an enforced serving closure."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"
sys.path.insert(0, str(ROOT))
from legal.security.durable_io import read_bounded_regular_file  # noqa: E402
from legal.security.strict_json import strict_json_load_path, strict_json_loads  # noqa: E402

INVENTORY_SHA = "868bc6425f40923a4cfd60e0aca33e73532a7d6c35f5504b0d762fd711ceab12"


def select_observed(rows, traces):
    inventory = {row["path"]: row for row in rows}
    if len(inventory) != len(rows):
        raise ValueError("duplicate_inventory_path")
    observed = set()
    for trace in traces:
        if (
            trace.get("schema") != "compact_observed_runtime_trace_v1"
            or trace.get("observed_only") is not True
        ):
            raise ValueError("not_an_observed_trace")
        for key in ("modules", "opened", "native_mappings"):
            observed.update(trace[key])
    # Retain audit metadata and notices even when not opened during the prompts.
    retained = {
        name
        for name in inventory
        if ".dist-info/" in name
        or Path(name).name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))
    }
    selected = sorted((observed & inventory.keys()) | retained)
    missing = sorted(
        name
        for name in observed
        if name.startswith(("package_runtime/", "python_runtime/")) and name not in inventory
    )
    return dict(
        schema="compact_observed_selection_candidate_v1",
        observed_only=True,
        enforced_import_allowlist=False,
        native_closure_qualified=False,
        production_admitted=False,
        ga_ready=False,
        files=[{k: inventory[name][k] for k in ("path", "bytes", "sha256")} for name in selected],
        selected_files=len(selected),
        selected_bytes=sum(inventory[name]["bytes"] for name in selected),
        unaccounted_observed_runtime_paths=missing,
        observed_windows_files=sorted(name for name in observed if name.startswith("windows/")),
        observed_repository_files=sorted(
            name for name in observed if name.startswith("repository/")
        ),
        unknown_roots=sorted(name for name in observed if name.startswith("unmapped/")),
        observed_cached_bytecode_paths=sorted(
            name for name in observed if name.endswith((".pyc", ".pyo"))
        ),
    )


if __name__ == "__main__":
    target = OUT / "observed-serving-selection-cpu02.json"
    if target.exists():
        raise SystemExit("preserve_prior_evidence")
    raw = read_bounded_regular_file(
        OUT / "ranker-runtime-files-notice-verified-01.jsonl", max_bytes=8_000_000
    )
    if hashlib.sha256(raw).hexdigest() != INVENTORY_SHA:
        raise SystemExit("prior_inventory_changed")
    rows = [
        strict_json_loads(line, max_bytes=4096, require_object=True) for line in raw.splitlines()
    ]
    traces = [
        strict_json_load_path(
            OUT / f"serving-trace-cpu02-{stage}.json", max_bytes=2_000_000, require_object=True
        )
        for stage in (1, 2, 3)
    ]
    result = select_observed(rows, traces)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in (
                    "files",
                    "observed_repository_files",
                    "observed_windows_files",
                    "unaccounted_observed_runtime_paths",
                    "observed_cached_bytecode_paths",
                )
            }
        )
    )
    print(
        json.dumps(
            dict(
                unaccounted_count=len(result["unaccounted_observed_runtime_paths"]),
                bytecode_count=len(result["observed_cached_bytecode_paths"]),
                windows_files=len(result["observed_windows_files"]),
            )
        )
    )
