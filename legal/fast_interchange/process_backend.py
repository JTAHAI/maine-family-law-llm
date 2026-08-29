"""Owned inference subprocess with bounded cancellation and hard-stop fallback.

Only the host's fixed internal messages cross this private pipe. Public model
requests never supply Python objects, factories, paths, or executable commands.
"""

from __future__ import annotations

import multiprocessing
import re
import time
from threading import Event
from typing import Any


def _child(connection, cancellation, factory, options):
    backend = factory(**options)
    try:
        while True:
            command = connection.recv()
            action = command["action"]
            try:
                if action == "close":
                    backend.close()
                    connection.send({"ok": True, "result": None})
                    return
                if action == "clear":
                    backend.clear_context()
                    result = None
                else:
                    cancellation.clear()
                    setter = getattr(backend, "set_cancellation", None)
                    if callable(setter):
                        setter(cancellation, command["deadline"])
                    if action == "activate":
                        policy = command["arguments"].pop("compatibility", None)
                        if policy is not None:
                            from .admission import Compatibility

                            backend.configure(Compatibility.model_validate(policy))
                        result = backend.activate(**command["arguments"])
                    elif action == "complete":
                        result = backend.complete(**command["arguments"])
                    else:
                        raise ValueError("internal_action_invalid")
                    backend.clear_context()
                connection.send({"ok": True, "result": result})
            except Exception as exc:
                code = str(getattr(exc, "code", "fast_interchange_backend_failed"))
                if not re.fullmatch(r"fast_interchange_[a-z_]{1,90}", code):
                    code = "fast_interchange_backend_failed"
                connection.send({"ok": False, "code": code})
                # Do not keep an exception traceback containing private inputs.
            finally:
                command = None
                result = None
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        try:
            backend.close()
        finally:
            connection.close()


class IsolatedAdapterBackend:
    def __init__(
        self,
        *,
        factory=None,
        allow_cpu: bool = False,
        cuda_device: int = 0,
        cancellation_grace_seconds: float = 2.0,
    ):
        if factory is None:
            from .worker import TransformersPeftAdapterBackend

            factory = TransformersPeftAdapterBackend
        self._factory = factory
        self._options = {"allow_cpu": allow_cpu, "cuda_device": cuda_device}
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._connection = None
        self._signal = None
        self._cancel: Event | None = None
        self._deadline = 0.0
        self._grace = max(0.1, min(float(cancellation_grace_seconds), 5.0))
        self._compatibility = None

    def configure(self, compatibility) -> None:
        self._compatibility = compatibility.model_dump()

    def set_cancellation(self, event: Event, deadline: float) -> None:
        self._cancel = event
        self._deadline = deadline
        if self._signal is not None:
            self._signal.clear()

    def _start(self) -> None:
        if self._process is not None and self._process.is_alive():
            return
        self._stop()
        parent, child = self._context.Pipe()
        self._signal = self._context.Event()
        self._process = self._context.Process(
            target=_child, args=(child, self._signal, self._factory, self._options), daemon=True
        )
        self._process.start()
        child.close()
        self._connection = parent

    def _stop(self) -> None:
        process, connection = self._process, self._connection
        self._process, self._connection = None, None
        if process is not None:
            if process.is_alive():
                process.terminate()  # Only the child created and owned by this instance.
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            process.close()
        if connection is not None:
            connection.close()

    def _call(self, action: str, **arguments: Any) -> Any:
        from .worker import FastInterchangeError

        if action == "activate":
            self._start()
        if self._connection is None:
            if action in {"clear", "close"}:
                return None
            raise FastInterchangeError("fast_interchange_backend_not_active")
        deadline = self._deadline if action in {"activate", "complete"} else time.monotonic() + 5
        cancel_started = None
        try:
            self._connection.send({"action": action, "arguments": arguments, "deadline": deadline})
            while True:
                if (
                    action in {"activate", "complete"}
                    and self._cancel is not None
                    and self._cancel.is_set()
                ):
                    self._signal.set()
                    cancel_started = cancel_started or time.monotonic()
                    if time.monotonic() - cancel_started >= self._grace:
                        self._stop()
                        raise FastInterchangeError("fast_interchange_generation_canceled")
                if time.monotonic() > deadline:
                    self._stop()
                    raise FastInterchangeError("fast_interchange_generation_timeout")
                if self._connection.poll(0.025):
                    payload = self._connection.recv()
                    if cancel_started is not None:
                        # Termination removes residual Python/tensor references even
                        # if a backend's cooperative cancellation was incomplete.
                        self._stop()
                        raise FastInterchangeError("fast_interchange_generation_canceled")
                    if not payload["ok"]:
                        self._stop()
                        raise FastInterchangeError(payload["code"])
                    return payload["result"]
                if not self._process.is_alive():
                    self._stop()
                    raise FastInterchangeError("fast_interchange_backend_failed")
        except (EOFError, BrokenPipeError, OSError) as exc:
            self._stop()
            raise FastInterchangeError("fast_interchange_backend_failed") from exc

    def activate(self, **kwargs):
        return self._call("activate", compatibility=self._compatibility, **kwargs)

    def complete(self, **kwargs):
        return self._call("complete", **kwargs)

    def clear_context(self) -> None:
        self._call("clear")

    def close(self) -> None:
        try:
            self._call("close")
        finally:
            self._stop()
