"""Explicit, allowlisted Windows OCR prerequisite installation helpers.

The installer never receives user-supplied package names or command arguments.
It only invokes the fixed Tesseract package through Windows Package Manager
after an affirmative local UI action. Matter files are not read by this module.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Callable

from .local_corpus_index import local_ocr_engine_status

TESSERACT_WINGET_ID = "UB-Mannheim.TesseractOCR"
TESSERACT_DOWNLOADS_URL = "https://tesseract-ocr.github.io/tessdoc/Downloads.html"
TESSERACT_WINDOWS_URL = "https://github.com/UB-Mannheim/tesseract/wiki"


def ocr_prerequisite_status(*, platform_name: str | None = None) -> dict[str, Any]:
    platform = platform_name or os.name
    engine = local_ocr_engine_status()
    winget = shutil.which("winget") if platform == "nt" else ""
    return {
        "status": "ready" if engine.get("available") and engine.get("pdf_ocr_available") else "missing",
        "platform": "windows" if platform == "nt" else platform,
        "one_click_available": bool(platform == "nt" and winget),
        "winget_available": bool(winget),
        "engine": engine,
        "package_id": TESSERACT_WINGET_ID,
        "manual_install_url": TESSERACT_DOWNLOADS_URL,
        "windows_installer_url": TESSERACT_WINDOWS_URL,
        "network_disclosure": (
            "The installer contacts Windows Package Manager to download Tesseract. "
            "It does not read or upload matter records."
        ),
        "documents_read": False,
        "documents_uploaded": False,
    }


def install_local_ocr_prerequisites(
    *,
    approved: bool,
    platform_name: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Install the fixed Windows Tesseract package after explicit consent."""

    if not approved:
        return {
            "status": "consent_required",
            "installed": False,
            "message": "Explicit approval is required before installing local OCR prerequisites.",
        }
    platform = platform_name or os.name
    if platform != "nt":
        return {
            "status": "unsupported_platform",
            "installed": False,
            "message": "One-click OCR installation is available only on Windows.",
            "manual_install_url": TESSERACT_DOWNLOADS_URL,
        }
    winget = which("winget")
    if not winget:
        return {
            "status": "manual_install_required",
            "installed": False,
            "message": "Windows Package Manager was not found. Open the manual Tesseract install page.",
            "manual_install_url": TESSERACT_DOWNLOADS_URL,
            "windows_installer_url": TESSERACT_WINDOWS_URL,
        }

    base = [
        winget,
        "install",
        "--id",
        TESSERACT_WINGET_ID,
        "--exact",
        "--accept-package-agreements",
        "--accept-source-agreements",
        "--silent",
        "--disable-interactivity",
    ]
    attempts = [base + ["--scope", "user"], base]
    last_code = -1
    for command in attempts:
        try:
            completed = runner(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=1200,
            )
            last_code = int(completed.returncode)
        except subprocess.TimeoutExpired:
            return {
                "status": "install_timeout",
                "installed": False,
                "message": "The OCR installer did not finish within 20 minutes. Recheck or use the manual install page.",
                "manual_install_url": TESSERACT_DOWNLOADS_URL,
            }
        except Exception:
            return {
                "status": "install_failed",
                "installed": False,
                "message": "The OCR installer could not be started. Use the manual install page, then recheck.",
                "manual_install_url": TESSERACT_DOWNLOADS_URL,
            }
        if last_code == 0:
            engine = local_ocr_engine_status()
            return {
                "status": "installed" if engine.get("available") else "installed_recheck_required",
                "installed": True,
                "message": (
                    "Tesseract installation completed. OCR is ready."
                    if engine.get("available")
                    else "Tesseract installation completed. Use Recheck; a new app session may be required."
                ),
                "engine": engine,
                "documents_read": False,
                "documents_uploaded": False,
            }

    return {
        "status": "install_failed",
        "installed": False,
        "exit_code": last_code,
        "message": "Windows Package Manager could not install Tesseract. Open the manual install page, then recheck.",
        "manual_install_url": TESSERACT_DOWNLOADS_URL,
        "windows_installer_url": TESSERACT_WINDOWS_URL,
    }
