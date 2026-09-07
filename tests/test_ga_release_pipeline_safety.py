"""Build-script safety checks; do not install/uninstall any real package."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_ci_builds_one_unsigned_candidate_without_exporting_private_keys():
    workflow = (ROOT / ".github/workflows/build-msix.yml").read_text()
    assert workflow.index("pip install") < workflow.index("python -m pytest")
    assert workflow.count("./scripts/build-msix.ps1") == 1
    assert "./scripts/build-store-runtime.ps1" not in workflow
    assert "./scripts/test-store-runtime.ps1" not in workflow
    assert "-Unsigned" in workflow
    assert "dist/store/msix/**" not in workflow
    assert "dist/store/msix/*.msix" in workflow
    assert "./scripts/install-test-msix.ps1" not in workflow
    assert "./scripts/uninstall-test-msix.ps1" not in workflow
    assert "NOT_EVALUATED" in workflow


def test_install_and_wack_require_the_exact_candidate():
    for name in ("install-test-msix.ps1", "run-wack.ps1"):
        script = (ROOT / "scripts" / name).read_text()
        assert "explicit exact candidate -PackagePath" in script
        assert "dist\\release\\v7" not in script
        assert "dist\\release\\v8" not in script
    install = (ROOT / "scripts/install-test-msix.ps1").read_text()
    assert "-not $IsolatedTestEnvironment" in install
    assert "dev-certificate-path.txt" not in install


def test_uninstall_has_no_implicit_production_target():
    script = (ROOT / "scripts/uninstall-test-msix.ps1").read_text()
    assert "TAHAIWebServices.MaineFamilyLawLLM" not in script
    assert "$_.PackageFullName -ceq $PackageFullName" in script
    assert "-not $IsolatedTestEnvironment" in script
    assert "$packages.Count -ne 1" in script


def test_production_identity_never_silently_creates_dev_signer():
    script = (ROOT / "scripts/build-msix.ps1").read_text()
    guard = "if (-not $Unsigned -and -not $CertificatePfxPath -and -not $UseDevIdentity)"
    assert guard in script
    assert script.index(guard) < script.index("Remove-Item")


@pytest.mark.parametrize("development", [False, True])
def test_qa_identity_block_cannot_inherit_the_real_store_identity(development):
    shell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not shell:
        pytest.skip("PowerShell is required to execute the Windows package identity block")
    # Execute only the AST-selected, pure identity block: no build, certificate,
    # filesystem mutation, installation or uninstallation is performed.
    command = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
  (Join-Path $PWD 'scripts/build-msix.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Package script syntax invalid' }
$blocks = @($ast.FindAll({param($node)
  $node -is [System.Management.Automation.Language.IfStatementAst] -and
  $node.Extent.Text.StartsWith('if ($UseDevIdentity)')
}, $true))
if ($blocks.Count -ne 1) { throw 'Expected one identity block' }
$config = Get-Content -LiteralPath store/msix/identity.example.json -Raw | ConvertFrom-Json
$IdentityName = $config.identity_name
$Publisher = $config.publisher
$PublisherDisplayName = $config.publisher_display_name
$PackageDisplayName = $config.package_display_name
$UseDevIdentity = __DEVELOPMENT__
. ([scriptblock]::Create($blocks[0].Extent.Text))
@{name=$IdentityName; publisher=$Publisher; display=$PackageDisplayName} | ConvertTo-Json -Compress
""".replace("__DEVELOPMENT__", "$true" if development else "$false")
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    identity = json.loads(result.stdout)
    production = json.loads((ROOT / "store/msix/identity.example.json").read_text())
    if development:
        assert identity["name"] == "MaineFamilyLawLLM.LocalQA"
        assert identity["name"] != production["identity_name"]
        assert identity["publisher"] != production["publisher"]
        assert identity["display"].endswith("(Local QA)")
    else:
        assert identity["name"] == production["identity_name"]
        assert identity["publisher"] == production["publisher"]
