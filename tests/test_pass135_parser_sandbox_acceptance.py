from __future__ import annotations
import sys
import pytest
from legal.security.parser_sandbox import ParserSandbox, ParserSandboxError

def test_parser_sandbox_refuses_non_worker_and_scrubs_network_environment() -> None:
    sandbox = ParserSandbox(5)
    with pytest.raises(ParserSandboxError, match="executable_not_allowed"):
        sandbox.run(["not-python", "-c", "x"], env={})
    with pytest.raises(ParserSandboxError, match="command_not_allowed"):
        sandbox.run([sys.executable, "-c", "print('x')"], env={})
    result = sandbox.run([sys.executable, "-m", "legal.document_intelligence.worker", "docling", "missing"], env={"HTTP_PROXY":"http://bad", "HTTPS_PROXY":"http://bad"})
    assert result.returncode in {0, 1, 2}
    assert sandbox.status()["network"] == "blocked_by_environment"
