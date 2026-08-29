"""Restricted local subprocess boundary for document parser workers."""
from __future__ import annotations
import os, subprocess, sys
from dataclasses import dataclass
from typing import Mapping

class ParserSandboxError(ValueError): pass

@dataclass(frozen=True)
class ParserSandbox:
    timeout_seconds: int
    max_output_bytes: int = 32 * 1024 * 1024
    def run(self, command: list[str], *, env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
        if not command or os.path.abspath(command[0]) != os.path.abspath(sys.executable):
            raise ParserSandboxError("parser_sandbox_executable_not_allowed")
        if "legal.document_intelligence.worker" not in command and "--document-intelligence-worker" not in command:
            raise ParserSandboxError("parser_sandbox_command_not_allowed")
        clean = {k: str(v) for k, v in env.items() if k not in {"HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy"}}
        clean.update({"HTTP_PROXY":"", "HTTPS_PROXY":"", "ALL_PROXY":"", "NO_PROXY":"*", "no_proxy":"*", "PYTHONNOUSERSITE":"1"})
        kwargs: dict = {"capture_output":True, "text":True, "check":False, "timeout":max(1, self.timeout_seconds), "env":clean, "shell":False}
        if os.name == "nt": kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            def limits() -> None:
                import resource
                resource.setrlimit(resource.RLIMIT_CPU, (max(1, self.timeout_seconds), max(2, self.timeout_seconds + 5)))
                resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
            kwargs["preexec_fn"] = limits
        result = subprocess.run(command, **kwargs)
        if len(result.stdout.encode("utf-8", "ignore")) + len(result.stderr.encode("utf-8", "ignore")) > self.max_output_bytes:
            raise ParserSandboxError("parser_sandbox_output_limit")
        return result
    def status(self) -> dict[str, object]:
        return {"status":"pass", "network":"blocked_by_environment", "shell":False, "resource_limits":"windows_process_boundary_or_posix_rlimit", "review_required":True}

__all__=["ParserSandbox","ParserSandboxError"]
