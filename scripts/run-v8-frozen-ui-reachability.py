"""Record production UI asset reachability for a running frozen workbench.

This is deliberately a reachability check, not a substitute for browser-driven
interaction evidence.  It confirms that the running frozen server serves the
production workbench and the safeguards its JavaScript needs to expose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _get_text(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Accept": "text/html,application/javascript,text/css"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.status), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(base_url: str) -> dict[str, object]:
    base_url = base_url.rstrip("/")
    root_status, page = _get_text(f"{base_url}/")
    js_status, workbench_js = _get_text(f"{base_url}/ui-assets/workbench.js?v=8.0.0-ga-b53")
    css_status, workbench_css = _get_text(f"{base_url}/ui-assets/workbench.css?v=8.0.0-ga-b53")
    checks = {
        "production_workbench_served": root_status == 200 and 'data-production-ui="workbench"' in page,
        "frozen_workbench_script_served": js_status == 200 and "citation-insertion-pinpoint-choice" in workbench_js,
        "frozen_workbench_styles_served": css_status == 200 and len(workbench_css) > 1000,
        "both_search_lane_is_static_default": bool(
            re.search(
                r'<button aria-checked="true" class="[^"]*\bis-selected\b[^"]*" '
                r'data-search-mode="both" role="radio" type="button">Both',
                page,
            )
        ),
        "child_impact_lens_is_static_default": '<input checked id="child-impact-lens" type="checkbox"' in page,
        "citation_requires_explicit_multi_span_choice": "Choose one source-provided pinpoint" in workbench_js
        and "citation-insertion-pinpoint" in workbench_js,
        "quote_requires_explicit_multi_span_choice": "Choose one exact source span" in workbench_js
        and "quote-safe-pinpoint" in workbench_js,
        "review_required_remains_visible": "Review required" in page,
    }
    blockers = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "mfl_v8_frozen_ui_reachability_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "execution_level": "frozen_runtime_production_ui_asset_reachability",
        "decision": "PASS" if not blockers else "BLOCKED",
        "checks": {name: "pass" if passed else "fail" for name, passed in checks.items()},
        "asset_hashes": {"document": _hash(page), "workbench_js": _hash(workbench_js), "workbench_css": _hash(workbench_css)},
        "blockers": blockers,
        "notice": "This is frozen production-UI asset reachability, not browser-driven click or screen-reader interaction evidence.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
