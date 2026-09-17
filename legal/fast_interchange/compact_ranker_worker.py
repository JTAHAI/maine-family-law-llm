"""Private, fixed JSON pipe protocol for the research ranker; no socket listener."""

from __future__ import annotations

import hashlib
import sys
from contextlib import redirect_stdout
from pathlib import Path

from legal.security.strict_json import strict_json_loads

from .admission import canonical
from .compact_cpu import PinnedFile
from .compact_network_guard import GUARD_VERSION, PythonNetworkDenied, PythonNetworkGuard
from .compact_ranker_process import ERROR_KINDS, MAX_PIPE_BYTES, sanitize_failure
from .compact_reranker import CompactPassageReranker
from .compact_source_imports import source_import_policy, source_only_active


def main(*, engine_type=CompactPassageReranker, operation="rank"):
    engine = None
    packet = None
    guard = None
    try:
        guard = PythonNetworkGuard()
        while True:
            if not source_only_active():
                raise RuntimeError("compact_source_import_policy_missing")
            raw = sys.stdin.buffer.readline(MAX_PIPE_BYTES + 1)
            if not raw:
                return 0
            if len(raw) > MAX_PIPE_BYTES or not raw.endswith(b"\n"):
                return 2
            packet = strict_json_loads(raw, max_bytes=MAX_PIPE_BYTES, require_object=True)
            if set(packet) != {"action", "arguments", "request_id", "request_sha256"}:
                return 2
            arguments = packet["arguments"]
            if hashlib.sha256(canonical(arguments)).hexdigest() != packet["request_sha256"]:
                return 2
            with redirect_stdout(sys.stderr):
                if packet["action"] == "warm" and engine is None and set(arguments) == {"files"}:
                    files = tuple(
                        PinnedFile(Path(row["path"]), row["bytes"], row["sha256"])
                        for row in arguments["files"]
                    )
                    engine = engine_type(files, research_only=True)
                    getattr(engine, operation)(
                        query="Where is the fictional folder?",
                        matter_id="synthetic-warm",
                        passages=[
                            {
                                "source_id": "synthetic-warm",
                                "lane": "private_record",
                                "matter_id": "synthetic-warm",
                                "text": "A fictional folder rests on a table.",
                            }
                        ],
                    )
                    result = {
                        "status": "warm",
                        "forward_passes": 1,
                        "model_sha256": next(
                            r.sha256 for r in files if r.path.suffix == ".safetensors"
                        ),
                        "review_required": True,
                        "production_admitted": False,
                        "network_guard": GUARD_VERSION,
                        "source_import_policy": source_import_policy(),
                    }
                elif (
                    packet["action"] == operation
                    and engine is not None
                    and set(arguments) == {"query", "passages", "matter_id"}
                ):
                    result = getattr(engine, operation)(**arguments)
                else:
                    return 2
            guard.check()
            response = {
                "request_id": packet["request_id"],
                "request_sha256": packet["request_sha256"],
                "ok": True,
                "result": result,
            }
            encoded = canonical(response) + b"\n"
            if len(encoded) > MAX_PIPE_BYTES:
                return 2
            remaining = memoryview(encoded)
            while remaining:
                written = sys.stdout.buffer.write(remaining)
                if not written:
                    return 2
                remaining = remaining[written:]
            sys.stdout.buffer.flush()
            packet = arguments = result = response = raw = encoded = remaining = None
    except Exception as caught:
        # No traceback containing records, local paths or environment secrets.
        # Optional dependency loaders wrap their root failures. Classify the
        # cause without exposing its message or traceback.
        exc = caught
        if guard is not None and guard.denied:
            exc = PythonNetworkDenied()
        else:
            for _ in range(6):
                if exc.__cause__ is None:
                    break
                exc = exc.__cause__
        if isinstance(packet, dict) and {"request_id", "request_sha256"} <= set(packet):
            missing = getattr(exc, "name", None)
            error = sanitize_failure(
                {
                    "phase": getattr(engine, "phase", "protocol"),
                    "kind": type(exc).__name__ if type(exc).__name__ in ERROR_KINDS else "Error",
                    "winerror": getattr(exc, "winerror", None),
                    "module": missing.split(".")[0] if isinstance(missing, str) else "unspecified",
                },
                warm=packet.get("action") == "warm",
            )
            if error is None:
                error = {
                    "phase": "protocol",
                    "kind": "Error",
                    "winerror": None,
                    "module": "unspecified",
                }
            response = {
                "request_id": packet["request_id"],
                "request_sha256": packet["request_sha256"],
                "ok": False,
                "result": error,
            }
            sys.stdout.buffer.write(canonical(response) + b"\n")
            sys.stdout.buffer.flush()
        return 2
    finally:
        if engine is not None:
            engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
