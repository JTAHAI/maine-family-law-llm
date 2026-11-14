"""Shared, narrow exceptions for the public source ZIP builder and auditor."""

import hashlib
from pathlib import PurePosixPath

PARSER_FIXTURE = "data/fixtures/parser_regression/malformed_download_v1.bin"
PARSER_FIXTURE_SIZE = 134
_PARSER_FIXTURE_SHA256 = "a19154a63842ec7679ab58d8da06f1f564a57ea5061f0b6e2c013a35acaeb2c7"


def is_python_runtime_module(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        len(parts) == 3
        and parts[:2] == ("legal", "runtime")
        and parts[2].endswith(".py")
        and parts[2][:-3].isidentifier()
    )


def is_pinned_parser_fixture(data: bytes) -> bool:
    return len(data) == PARSER_FIXTURE_SIZE and hashlib.sha256(data).hexdigest() == _PARSER_FIXTURE_SHA256
