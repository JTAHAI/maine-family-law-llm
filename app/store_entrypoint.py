from __future__ import annotations

import argparse
import json
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Source bootstrapping above must precede application imports.
from app.local_api_service import (  # noqa: E402
    ensure_local_service,
    run_local_service,
    stop_local_service,
)
from app.runtime_support import (  # noqa: E402
    build_runtime_context,
    configure_runtime_environment,
    local_about_links,
    log_exception,
)
from maine_family_law_llm.version import (  # noqa: E402
    APP_DISPLAY_NAME,
    GITHUB_REPOSITORY_URL,
    STORE_MISSION_TAGLINE,
    VERSION,
)


def _is_outside_root(path: Path, root: Path) -> bool:
    """Return True only when *path* is outside *root* by path components.

    String-prefix checks are unsafe for sibling names such as ``bundle-old``
    versus ``bundle`` and behave differently across platforms.
    """

    return not path.resolve().is_relative_to(root.resolve())


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
    # The frozen MSIX defaults to Store mode.  Source launchers intentionally
    # pass MFL_RUNTIME_MODE=source so their loopback state cannot collide with
    # an installed package.
    context = configure_runtime_environment(build_runtime_context())
    service = ensure_local_service(context)
    from maine_family_law_llm.case_corpus_builder import create_sample_case_build
    from maine_family_law_llm.local_corpus_index import local_ocr_engine_status

    # Smoke fixtures are runtime data in every mode.  Keeping them under the
    # mode-specific LocalAppData root prevents source qualification from
    # contaminating the repository or a future package payload.
    smoke_case_root = context.runtime_data_root / "smoke" / "example_case_build"
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
            "question": (
                "What Maine sources should I check before drafting a parental rights motion?"
            ),
            "answer_style": "plain_language",
            "matter_context": "",
        },
    )
    links = local_about_links(context)
    ocr_engine = local_ocr_engine_status()
    result = {
        "application_version": VERSION,
        "bundle_root": str(context.bundle_root),
        "runtime_mode": context.mode,
        "launch_result": "pass",
        "api_health_result": service.healthy,
        "local_service_url": service.url,
        "fictional_sample_workflow_result": sample.proof_json_path.exists(),
        "bundled_ocr_available": bool(ocr_engine.get("pdf_ocr_available")),
        "sample_case_root": str(sample.case_root),
        "github_link_verification": GITHUB_REPOSITORY_URL,
        "fork_guide_exists": links["fork_guide"].exists(),
        "privacy_policy_exists": links["privacy_policy"].exists(),
        "answer_grounded": bool(answer_payload.get("grounded")),
        "answer_failure_class": str(answer_payload.get("failure_class", "")),
        "external_data_boundary_verification": _is_outside_root(
            sample.case_root, context.bundle_root
        ),
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
    parser.add_argument(
        "--document-intelligence-worker",
        nargs=2,
        metavar=("ADAPTER", "INPUT"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--document-intelligence-output", default="", help=argparse.SUPPRESS)
    args, _ = parser.parse_known_args(argv)

    # Unattended qualification and service workers must fail with an exit code,
    # never a modal dialog that interrupts the user's desktop or hangs CI.
    unattended = bool(args.serve_local_api or args.smoke_test or args.document_intelligence_worker)
    context = None
    try:
        context = configure_runtime_environment(build_runtime_context(mode="store"))
        if args.document_intelligence_worker:
            from legal.document_intelligence.worker import main as document_worker_main

            worker_argv = list(args.document_intelligence_worker)
            if args.document_intelligence_output:
                worker_argv.extend(("--output", args.document_intelligence_output))
            return document_worker_main(worker_argv)
        if args.serve_local_api:
            return run_local_service(args.port, context)
        if args.smoke_test:
            output = Path(args.smoke_json).expanduser().resolve() if args.smoke_json else None
            _run_smoke_workflow(output)
            return 0
        from app.launcher import main as launcher_main

        return launcher_main(runtime_context=context)
    except Exception as exc:
        if context is not None:
            try:
                # Startup errors can contain private paths or document text.
                # Retain a content-free class/code, not the original exception.
                log_exception(context, RuntimeError(f"runtime_start_failed:{type(exc).__name__}"))
            except Exception:
                # A full/unwritable diagnostic directory must not mask the
                # original failure or open a second error dialog.
                pass
        if unattended:
            if args.smoke_test and args.smoke_json:
                try:
                    from legal.security.durable_io import atomic_write_bytes

                    output = Path(args.smoke_json).expanduser().resolve()
                    atomic_write_bytes(
                        output,
                        json.dumps(
                            {
                                "application_version": VERSION,
                                "launch_result": "fail",
                                "error_code": "runtime_start_failed",
                                "review_required": True,
                            }
                        ).encode("utf-8"),
                        mode=0o600,
                    )
                except Exception:
                    pass
            return 1
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                APP_DISPLAY_NAME,
                "The application could not start.\n\n"
                "Error code: runtime_start_failed.\n\n"
                "Restart the application. If this continues, use the Help/About "
                "troubleshooting guide or contact support. Your saved records "
                "have not been deleted by this error handler.",
                parent=root,
            )
        except Exception:
            pass
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
