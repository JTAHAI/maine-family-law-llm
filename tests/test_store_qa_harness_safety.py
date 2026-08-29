from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qualify-v700-qa-msix.ps1"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell parameter binding")


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["-NotARealParameter", "rejected"], "NamedParameterNotFound"),
        (["-QaIdentity", "TAHAIWebServices.MaineFamilyLawLLM"], "ParameterArgumentValidationError"),
        (
            ["-QaIdentity", "TAHAIWebServices.MaineFamilyLawLLM.QA" + "a" * 32],
            "ParameterArgumentValidationError",
        ),
    ],
)
def test_qa_script_rejects_unsafe_parameters_before_execution(arguments, expected):
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode != 0
    assert expected in completed.stdout + completed.stderr


def test_qa_script_preserves_an_existing_work_directory(tmp_path):
    package = tmp_path / "fictional.msix"
    package.write_bytes(b"not-a-real-package")
    work = tmp_path / "existing-qa"
    work.mkdir()
    marker = work / "preserve.txt"
    marker.write_text("fictional existing evidence", encoding="utf-8")
    evidence = tmp_path / "evidence-not-created"
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(SCRIPT),
            "-FinalMsix",
            str(package),
            "-WorkRoot",
            str(work),
            "-EvidenceRoot",
            str(evidence),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode != 0
    assert "qa_work_root_must_be_new" in completed.stdout + completed.stderr
    assert marker.read_text(encoding="utf-8") == "fictional existing evidence"
    assert not evidence.exists()


def test_default_qa_identity_is_unique_and_within_manifest_limit():
    command = r"""
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        $env:MFL_QA_SCRIPT, [ref]$null, [ref]$null)
    $parameter = $ast.ParamBlock.Parameters | Where-Object {
        $_.Name.VariablePath.UserPath -eq 'QaIdentity'
    }
    $factory = [scriptblock]::Create($parameter.DefaultValue.Extent.Text)
    @(1..32 | ForEach-Object { & $factory }) | ConvertTo-Json -Compress
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        env={**os.environ, "MFL_QA_SCRIPT": str(SCRIPT)},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    identities = json.loads(result.stdout)
    assert len(set(identities)) == 32
    assert all(38 <= len(identity) <= 50 for identity in identities)
    assert all(
        identity.startswith("TAHAIWebServices.MaineFamilyLawLLM.QA") for identity in identities
    )


@pytest.mark.parametrize(
    ("detail", "reason"),
    [
        ("Deployment failed with HRESULT: 0x80080204", "qa_manifest_invalid"),
        ("error 0xC00CE169: manifest maxLength constraint", "qa_manifest_invalid"),
        ("Deployment failed with HRESULT: 0x80073CFF", "qa_registration_host_policy"),
        ("unspecified deployment failure", "qa_registration_failed"),
    ],
)
def test_qa_failure_classification_does_not_hide_harness_defects(detail, reason):
    command = r"""
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        $env:MFL_QA_SCRIPT, [ref]$null, [ref]$null)
    $function = $ast.Find({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq 'Get-QARegistrationFailureReason'
    }, $true)
    . ([scriptblock]::Create($function.Extent.Text))
    Get-QARegistrationFailureReason $env:MFL_QA_FAILURE
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        env={**os.environ, "MFL_QA_SCRIPT": str(SCRIPT), "MFL_QA_FAILURE": detail},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert result.stdout.strip() == reason
