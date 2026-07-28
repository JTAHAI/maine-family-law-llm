from __future__ import annotations

import json
import re
from typing import Any

from .models import KnowledgeBundleError

_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def dump_frontmatter(values: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in values.items():
        if not _KEY_RE.fullmatch(key):
            raise KnowledgeBundleError(f"invalid frontmatter key: {key!r}")
        if isinstance(value, str):
            lines.append(f"{key}: {_quote(value)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            lines.append(f"{key}: [{', '.join(_quote(item) for item in value)}]")
        else:
            raise KnowledgeBundleError(
                f"frontmatter value for {key!r} must be a scalar or list of strings"
            )
    lines.append("---")
    return "\n".join(lines)


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw in {"true", "false"}:
        return raw == "true"
    if raw.startswith("{"):
        raise KnowledgeBundleError("unsupported frontmatter object value")
    if raw.startswith('"') or raw.startswith("["):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise KnowledgeBundleError(f"invalid frontmatter JSON scalar: {raw!r}") from exc
        if isinstance(value, list) and not all(isinstance(item, str) for item in value):
            raise KnowledgeBundleError("frontmatter lists may contain only strings")
        if not isinstance(value, (str, list)):
            raise KnowledgeBundleError("unsupported frontmatter value")
        return value
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    raise KnowledgeBundleError("unquoted frontmatter strings are not accepted")


def split_document(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise KnowledgeBundleError("document must begin with frontmatter")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise KnowledgeBundleError("frontmatter closing marker is missing")
    raw_header = text[4:marker]
    body = text[marker + 5 :]
    values: dict[str, Any] = {}
    for line in raw_header.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise KnowledgeBundleError(f"invalid frontmatter line: {line!r}")
        key, raw = line.split(":", 1)
        key = key.strip()
        if not _KEY_RE.fullmatch(key):
            raise KnowledgeBundleError(f"invalid frontmatter key: {key!r}")
        if key in values:
            raise KnowledgeBundleError(f"duplicate frontmatter key: {key}")
        values[key] = _parse_value(raw)
    return values, body
