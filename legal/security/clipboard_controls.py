"""Privacy contract for client-side clipboard handling.

Clipboard contents belong to the operating system.  This service deliberately
stores no clipboard text, hashes, previews, or history; it only supplies a
bounded, review-required policy that the shipped local UI enforces at the
explicit copy gesture.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClipboardSafetyPolicy:
    sensitive_clear_seconds: int = 90

    def as_dict(self) -> dict[str, object]:
        seconds = max(30, min(int(self.sensitive_clear_seconds), 5 * 60))
        return {
            "status": "pass",
            "clipboard_reading": "never",
            "clipboard_history_stored": False,
            "sensitive_copy_requires_explicit_confirmation": True,
            "sensitive_app_originated_clear_seconds": seconds,
            "clear_cancellation": ["window_blur", "page_hide", "visibility_change", "copy_or_cut_event"],
            "review_required": True,
            "notice": "Sensitive clipboard text is not read back or logged. Timed clearing runs only while the local workbench remains active.",
        }


__all__ = ["ClipboardSafetyPolicy"]
