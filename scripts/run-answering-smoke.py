from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
ASK_LOCAL = REPO_ROOT / "scripts" / "ask-local.py"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ASK_LOCAL), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
    )


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="me-fm-answering-smoke-") as tmp:
        root = Path(tmp)
        empty_corpus = root / "empty-corpus"
        empty_corpus.mkdir()

        refusal = run_command(
            [
                "parental rights modification",
                "--corpus",
                str(empty_corpus),
                "--no-ollama",
                "--json",
            ]
        )
        if refusal.returncode != 2:
            failures.append(f"expected no-source exit 2, got {refusal.returncode}")
        else:
            payload = json.loads(refusal.stdout)
            if payload.get("grounded") is not False:
                failures.append("no-source JSON did not report grounded=false")
            if payload.get("warning") != "insufficient_source_material":
                failures.append("no-source JSON warning mismatch")

        corpus = root / "corpus"
        corpus.mkdir()
        (corpus / "parental-rights-demo.txt").write_text(
            "SAMPLE ONLY - NOT LEGAL AUTHORITY. "
            "This sample source mentions parental rights, modification, "
            "citation-grounded answers, and insufficient-source safeguards.",
            encoding="utf-8",
        )

        grounded = run_command(
            [
                "parental rights modification",
                "--corpus",
                str(corpus),
                "--no-ollama",
                "--max-sources",
                "1",
                "--json",
            ]
        )
        if grounded.returncode != 0:
            failures.append(f"expected grounded exit 0, got {grounded.returncode}")
        else:
            payload = json.loads(grounded.stdout)
            if payload.get("grounded") is not True:
                failures.append("grounded JSON did not report grounded=true")
            citations = payload.get("citations") or []
            if len(citations) != 1:
                failures.append("grounded JSON did not return exactly one citation")
            elif citations[0].get("source_id") != "parental-rights-demo.txt":
                failures.append("grounded JSON citation source mismatch")

    if failures:
        print("ANSWERING_SMOKE_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("ANSWERING_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
