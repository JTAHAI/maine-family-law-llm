"""Bounded, ambiguity-free JSON parsing for security and release evidence.

The standard library parser accepts duplicate object keys and non-finite
numbers.  Those values are unsafe in signed, hashed, or independently reviewed
evidence because different tools may interpret them differently.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legal.security.durable_io import DurableIOError, read_bounded_regular_file


class StrictJSONError(ValueError):
    """Raised when JSON is malformed, ambiguous, oversized, or too complex."""


def _reject_constant(value: str) -> None:
    raise StrictJSONError(f"non_finite_number:{value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate_key:{key}")
        result[key] = value
    return result


def _validate_tree(value: Any, *, max_depth: int, max_items: int) -> None:
    item_count = 0
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            raise StrictJSONError("maximum_depth_exceeded")
        item_count += 1
        if item_count > max_items:
            raise StrictJSONError("maximum_item_count_exceeded")
        if isinstance(current, float) and not math.isfinite(current):
            raise StrictJSONError("non_finite_number")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def strict_json_loads(
    data: str | bytes,
    *,
    max_bytes: int = 8 * 1024 * 1024,
    max_depth: int = 64,
    max_items: int = 200_000,
    require_object: bool = False,
) -> Any:
    if isinstance(data, bytes):
        raw = data
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StrictJSONError("invalid_utf8") from exc
    elif isinstance(data, str):
        text = data
        raw = text.encode("utf-8")
    else:
        raise StrictJSONError("json_input_type_invalid")
    if len(raw) > max_bytes:
        raise StrictJSONError("maximum_bytes_exceeded")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except StrictJSONError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise StrictJSONError("invalid_json") from exc
    _validate_tree(value, max_depth=max_depth, max_items=max_items)
    if require_object and not isinstance(value, dict):
        raise StrictJSONError("object_required")
    return value


def strict_json_load_path(
    path: str | Path,
    *,
    max_bytes: int = 8 * 1024 * 1024,
    max_depth: int = 64,
    max_items: int = 200_000,
    require_object: bool = False,
) -> Any:
    file_path = Path(path)
    try:
        raw = read_bounded_regular_file(file_path, max_bytes=max_bytes)
    except DurableIOError as exc:
        code = str(exc)
        if code == "maximum_bytes_exceeded":
            raise StrictJSONError("maximum_bytes_exceeded") from exc
        raise StrictJSONError("json_file_unavailable") from exc
    return strict_json_loads(
        raw,
        max_bytes=max_bytes,
        max_depth=max_depth,
        max_items=max_items,
        require_object=require_object,
    )
