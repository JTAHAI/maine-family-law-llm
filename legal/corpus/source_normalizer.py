from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url, url) if base_url else url
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def slugify(value: str, *, max_length: int = 80) -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug[:max_length].strip("-") or "item"


def stable_source_id(prefix: str, locator: str) -> str:
    digest = hashlib.sha256(locator.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(prefix, max_length=40)}-{digest}"
