from __future__ import annotations

import argparse
import json
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app.local_api_service import ensure_local_service, run_local_service, stop_local_service
from app.runtime_support import build_runtime_context, configure_runtime_environment, local_about_links, log_exception, open_path_or_url
from maine_family_law_llm.case_corpus_builder import create_sample_case_build
from maine_family_law_llm.version import APP_DISPLAY_NAME, GITHUB_REPOSITORY_URL, STORE_MISSION_TAGLINE, VERSION


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _run_smoke_workflow(output_path: Path | None = None) -> dict[str, object]:
    context = configure_runtime_environment(build_runtime_context(mode="store"))
    service = ensure_local_service(context)
    smoke_case_root = context.writable_root / "smoke" / "example_case_build"
    if smoke_case_root.exists():
        shutil.rmtree(smoke_case_root)
    sample = create_sample_case_build(
        context.bundle_root,
        output_root=smoke_case_root.parent,
        case_name="Store Smoke Example Family Matter",
    )
    answer_payload = _post_json(
        service.url + "api/ask",
        {
            "question": "What Maine sources should I check before drafting a parental rights motion?",
            "answer_style": "plain_language",
            "matter_context": "",
        },
    )
    links = local_about_links(context)
    result = {
        "application_version": VERSION,
        "bundle_root": str(context.bundle_root),
        "runtime_mode": context.mode,
        "launch_result": "pass",
        "api_health_result": service.healthy,
        "local_service_url": service.url,
        "fictional_sample_workflow_result": sample.proof_json_path.exists(),
        "sample_case_root": str(sample.case_root),
        "github_link_verification": GITHUB_REPOSITORY_URL,
        "fork_guide_exists": links["fork_guide"].exists(),
        "privacy_policy_exists": links["privacy_policy"].exists(),
        "answer_grounded": bool(answer_payload.get("grounded")),
        "answer_failure_class": str(answer_payload.get("failure_class", "")),
        "external_data_boundary_verification": not str(sample.case_root).startswith(str(context.bundle_root)),
        "store_message": STORE_MISSION_TAGLINE,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    stop_local_service(context)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--serve-local-api", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-json", default="")
    args, _ = parser.parse_known_args(argv)

    context = configure_runtime_environment(build_runtime_context(mode="store"))
    try:
        if args.serve_local_api:
            return run_local_service(args.port, context)
        if args.smoke_test:
            output = Path(args.smoke_json).expanduser().resolve() if args.smoke_json else None
            _run_smoke_workflow(output)
            return 0
        from app.launcher import main as launcher_main

        return launcher_main(runtime_context=context)
    except Exception as exc:
        log_exception(context, exc)
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_DISPLAY_NAME,
            (
                "The Microsoft Store runtime could not start cleanly.\n\n"
                f"{exc.__class__.__name__}: {exc}\n\n"
                "Open the local logs under %LOCALAPPDATA%\\MaineFamilyLawLLM\\logs and then use the Help/About panel to open troubleshooting guidance."
            ),
            parent=root,
        )
        root.destroy()
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
