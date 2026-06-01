from __future__ import annotations

from io import BytesIO


def extract_pdf_text(content: bytes, *, max_pages: int | None = None) -> str:
    """Extract text from a PDF snapshot using pypdf.

    The source snapshot remains the authoritative artifact. This helper only
    derives text for parsers/builders so official rule PDFs can satisfy parsed
    authority gates without baking any corpus into the repository.
    """
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depends on optional runtime packaging
        raise RuntimeError("pypdf is required for PDF text extraction") from exc

    reader = PdfReader(BytesIO(content))
    page_text: list[str] = []
    pages = reader.pages[:max_pages] if max_pages is not None else reader.pages
    for page in pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            page_text.append(extracted)
    return "\n\n".join(page_text)
