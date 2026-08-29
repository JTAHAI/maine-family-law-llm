"""Bounded ephemeral cancellation capabilities, scoped to a local matter/session.

No prompt, private text, worker token, or path is serialized. Restart discards
approvals; the independently bounded worker cannot continue indefinitely.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from .local_agent_context_service import LocalAgentContextError, digest


class LocalAgentRunStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._rows: dict[str, dict[str, Any]] = {}

    def register(self, run_id: str, scope: dict, client: Any) -> None:
        with self._lock:
            now = time.monotonic()
            self._rows = {
                key: row
                for key, row in self._rows.items()
                if row["expires"] > now or row["state"] in {"running", "canceling"}
            }
            if len(self._rows) >= 256:
                raise LocalAgentContextError("local_agent_run_capacity", 429)
            if run_id in self._rows:
                raise LocalAgentContextError("local_agent_run_replayed")
            self._rows[run_id] = {
                "scope": digest(scope),
                "client": client,
                "binding": digest(client.model_binding),
                "expires": now + 300,
                "state": "preview",
            }

    def _row(self, run_id: str, scope: dict) -> dict:
        row = self._rows.get(run_id)
        if not row or row["scope"] != digest(scope):
            raise LocalAgentContextError("local_agent_run_unavailable", 404)
        if row["expires"] <= time.monotonic() and row["state"] not in {"running", "canceling"}:
            raise LocalAgentContextError("local_agent_run_expired")
        return row

    def claim(self, run_id: str, scope: dict, model_binding: dict):
        with self._lock:
            row = self._row(run_id, scope)
            if row["state"] == "canceled":
                raise LocalAgentContextError("fast_interchange_generation_canceled")
            if row["state"] != "preview" or row["binding"] != digest(model_binding):
                raise LocalAgentContextError("local_agent_run_approval_changed")
            row["state"] = "running"
            return row["client"]

    def cancel(self, run_id: str, scope: dict) -> dict:
        with self._lock:
            row = self._row(run_id, scope)
            if row["state"] in {"completed", "failed", "canceled"}:
                return {"status": row["state"], "review_required": True}
            row["state"] = "canceled" if row["state"] == "preview" else "canceling"
            client = row["client"]
        # Control HTTP must not hold the map lock or block another matter.
        client.cancel()
        with self._lock:
            return {"status": row["state"], "review_required": True}

    def finish(self, run_id: str, scope: dict, *, failed: bool = False) -> bool:
        with self._lock:
            row = self._row(run_id, scope)
            canceled = row["state"] in {"canceling", "canceled"}
            row["state"] = "canceled" if canceled else "failed" if failed else "completed"
            return canceled
