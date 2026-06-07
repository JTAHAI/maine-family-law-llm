from __future__ import annotations


class RedFlagPresenter:
    def present(self, red_flags: list[str]) -> dict[str, object]:
        flags = [str(flag) for flag in red_flags if flag]
        return {
            "has_red_flags": bool(flags),
            "summary": "Red flags need attention before relying on this output." if flags else "No red flags detected by this deterministic check.",
            "red_flags": flags,
        }
