"""Bounded PDF raster derivatives. Private worker IPC is ephemeral and encrypted.

No PDF JavaScript, forms environment, URLs or external resources are executed.
This is a timed local process boundary, not an OS-level network sandbox claim.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import secrets
import struct
import tempfile
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from legal.security.durable_io import read_bounded_regular_file

MAX_PDF_BYTES = 32 * 1024 * 1024
MAX_PNG_BYTES = 8 * 1024 * 1024
MAX_EDGE = 1600
KEY_ENV = "MFL_PDF_PREVIEW_EPHEMERAL_KEY"
_REQUEST_AAD = b"mfl-pdf-preview-request-v1"
_RESPONSE_AAD = b"mfl-pdf-preview-response-v1"
_SLOT = threading.BoundedSemaphore(1)


class PdfPreviewError(ValueError):
    def __init__(self, code: str, status_code: int = 422):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _encrypt(key: bytes, data: bytes, aad: bytes) -> bytes:
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, data, aad)


def _decrypt(key: bytes, data: bytes, aad: bytes) -> bytes:
    return AESGCM(key).decrypt(data[:12], data[12:], aad)


def _validate_png(data: bytes, width: int, height: int) -> None:
    if (len(data) < 33 or len(data) > MAX_PNG_BYTES
            or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR"
            or struct.unpack(">II", data[16:24]) != (width, height)
            or not 1 <= width <= MAX_EDGE or not 1 <= height <= MAX_EDGE):
        raise PdfPreviewError("record_preview_raster_invalid")


def render_worker(path: Path) -> dict[str, Any]:
    """Called only inside the fixed document worker; never emit private errors."""
    encoded_key = os.environ.pop(KEY_ENV, "")
    try:
        key = bytes.fromhex(encoded_key)
        if len(key) != 32:
            raise ValueError("key")
        envelope = read_bounded_regular_file(path, max_bytes=MAX_PDF_BYTES * 2)
        request = json.loads(_decrypt(key, envelope, _REQUEST_AAD))
        data = base64.b64decode(request["pdf"], validate=True)
        page_number = request["page"]
        if (not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES
                or type(page_number) is not int or not 1 <= page_number <= 100_000
                or hashlib.sha256(data).hexdigest() != request["source_sha256"]):
            raise PdfPreviewError("record_preview_input_invalid")
        # Do not initialize PDFium's interactive form/JavaScript environment.
        import pypdfium2 as pdfium

        with closing(pdfium.PdfDocument(data)) as document:
            count = len(document)
            if not 1 <= page_number <= count <= 100_000:
                raise PdfPreviewError("record_preview_page_invalid")
            with closing(document[page_number - 1]) as page:
                width, height = page.get_size()
                if (not all(math.isfinite(n) and 0 < n <= 100_000 for n in (width, height))
                        or min(width, height) / max(width, height) < .001):
                    raise PdfPreviewError("record_preview_dimensions_invalid")
                scale = min(2.0, (MAX_EDGE - 1) / max(width, height))
                with closing(page.render(scale=scale, draw_annots=True)) as bitmap:
                    with bitmap.to_pil() as raster:
                        output = io.BytesIO()
                        raster.save(output, format="PNG")
                        png = output.getvalue()
                        raster_width, raster_height = raster.size
        _validate_png(png, raster_width, raster_height)
        result = {
            "png": base64.b64encode(png).decode("ascii"),
            "sha256": hashlib.sha256(png).hexdigest(), "source_sha256": request["source_sha256"],
            "page": page_number, "page_count": count,
            "width": raster_width, "height": raster_height,
        }
        ciphertext = _encrypt(key, json.dumps(result).encode("utf-8"), _RESPONSE_AAD)
        return {"status": "pass", "ciphertext": base64.b64encode(ciphertext).decode("ascii")}
    except PdfPreviewError as exc:
        return {"status": "blocked", "code": exc.code}
    except Exception:
        # Native parser exceptions can include document text or paths.
        return {"status": "blocked", "code": "record_preview_render_failed"}


def render_pdf_preview(data: bytes, page: int) -> dict[str, Any]:
    if type(page) is not int or not 1 <= page <= 100_000:
        raise PdfPreviewError("record_preview_page_invalid")
    if not data.startswith(b"%PDF-"):
        raise PdfPreviewError("record_preview_pdf_required", 415)
    if len(data) > MAX_PDF_BYTES:
        raise PdfPreviewError("record_preview_input_too_large", 413)
    if not _SLOT.acquire(blocking=False):
        raise PdfPreviewError("record_preview_busy", 503)
    try:
        from .service import _run_worker

        key = secrets.token_bytes(32)
        source_hash = hashlib.sha256(data).hexdigest()
        request = json.dumps({"pdf": base64.b64encode(data).decode("ascii"),
                              "page": page, "source_sha256": source_hash}).encode("utf-8")
        # Even if a process crashes, no plaintext PDF or page image is on disk.
        with tempfile.TemporaryDirectory(prefix="mfl-pdf-preview-") as temporary:
            path = Path(temporary) / "request.enc"
            path.write_bytes(_encrypt(key, request, _REQUEST_AAD))
            reply = _run_worker("pdf_preview", path, timeout=25, worker_env={KEY_ENV: key.hex()})
        if reply.get("status") == "timeout":
            raise PdfPreviewError("record_preview_timeout", 504)
        if reply.get("status") != "pass":
            # The worker response is not trusted to choose a public error string.
            code = reply.get("code")
            if code not in {"record_preview_page_invalid", "record_preview_dimensions_invalid"}:
                code = "record_preview_render_failed"
            raise PdfPreviewError(code)
        raw = base64.b64decode(reply["ciphertext"], validate=True)
        if len(raw) > MAX_PNG_BYTES * 2:
            raise PdfPreviewError("record_preview_raster_invalid")
        result = json.loads(_decrypt(key, raw, _RESPONSE_AAD))
        png = base64.b64decode(result.pop("png"), validate=True)
        if (result["source_sha256"] != source_hash or result["page"] != page
                or type(result["page_count"]) is not int or not page <= result["page_count"] <= 100_000
                or result["sha256"] != hashlib.sha256(png).hexdigest()
                or type(result["width"]) is not int or type(result["height"]) is not int):
            raise PdfPreviewError("record_preview_binding_invalid")
        _validate_png(png, result["width"], result["height"])
        return {**result, "data": png, "review_required": True}
    except PdfPreviewError:
        raise
    except Exception as exc:
        raise PdfPreviewError("record_preview_render_failed") from exc
    finally:
        _SLOT.release()
