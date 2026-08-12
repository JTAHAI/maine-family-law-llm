from __future__ import annotations

import json
from pathlib import Path

from .schemas import RUN_STATUSES

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_deliberation_state_machine.json"


class DeliberationStateMachineError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DeliberationStateMachine:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.states = {str(item) for item in payload.get("states", [])}
        self.allowed_transitions = {
            str(source): {str(target) for target in targets}
            for source, targets in (payload.get("allowed_transitions") or {}).items()
        }

    def validate_state(self, state: str) -> None:
        if state not in self.states or state not in RUN_STATUSES:
            raise DeliberationStateMachineError("invalid_state", f"Unsupported deliberation state: {state}")

    def can_transition(self, state: str, target: str) -> bool:
        self.validate_state(state)
        self.validate_state(target)
        return target in self.allowed_transitions.get(state, set())

    def transition(self, state: str, target: str) -> str:
        if not self.can_transition(state, target):
            raise DeliberationStateMachineError("invalid_transition", f"Invalid deliberation transition: {state} -> {target}")
        return target

    def assert_terminal(self, state: str) -> None:
        self.validate_state(state)
        if self.allowed_transitions.get(state):
            raise DeliberationStateMachineError("state_not_terminal", f"The state is not terminal: {state}")
