# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parents[1]
ICON_PATH = ROOT / "assets" / "brand" / "focaf_family_law_llm_brand_kit" / "assets" / "favicon" / "favicon.ico"
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
DEBUG_CONSOLE = os.environ.get("MFL_STORE_DEBUG_CONSOLE", "").strip() == "1"

STORE_DOCS = (
    "README_FOR_NONTECHNICAL_USERS.html",
    "HOW_TO_ADD_YOUR_CORPUS.html",
    "HOW_TO_EXPORT_FROM_GMAIL_AND_GOOGLE_WORKSPACE.html",
    "HOW_TO_EXPORT_FROM_OUTLOOK_AND_HOTMAIL.html",
    "HOW_TO_EXPORT_FROM_IPHONE_AND_ANDROID.html",
    "HASH_AND_CHAIN_OF_CUSTODY.html",
    "SYSTEM_REQUIREMENTS.html",
    "TROUBLESHOOTING.html",
    "FORK_FOR_YOUR_STATE.md",
    "PRIVACY_POLICY_MICROSOFT_STORE.html",
)


def collect_flat_files(root: Path, *, destination: str, names: tuple[str, ...]) -> list[tuple[str, str]]:
    return [(str(root / name), destination) for name in names]


def collect_source_package_files(package_root: Path, *, destination: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    allowed_suffixes = {".py", ".html", ".css", ".js", ".svg", ".json"}
    for path in package_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        relative_parent = path.relative_to(package_root).parent
        target = str(Path(destination) / relative_parent).replace("\\", "/")
        results.append((str(path), target))
    return results


datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "data"), "data"),
    (str(ROOT / "sample_question_bank"), "sample_question_bank"),
    (str(ROOT / "LICENSE.md"), "."),
]
datas += collect_flat_files(ROOT / "docs", destination="docs", names=STORE_DOCS)
datas += collect_source_package_files(ROOT / "src" / "maine_family_law_llm", destination="src/maine_family_law_llm")
datas.append((str(ROOT / "src" / "maine_family_law_llm" / "ui"), "maine_family_law_llm/ui"))
datas.append((str(ROOT / "src" / "maine_family_law_llm" / "resources" / "focaf"), "maine_family_law_llm/resources/focaf"))
for package_name in ("fastapi", "uvicorn", "httpx", "pypdf"):
    datas += copy_metadata(package_name)

hiddenimports = ["sqlite3", "_sqlite3"]
for package_name in ("app", "legal", "fastapi", "starlette", "uvicorn", "httpx", "pydantic"):
    hiddenimports += collect_submodules(package_name)

a = Analysis(
    [str(ROOT / "app" / "store_entrypoint.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests", "tkinter.test", "unittest.test"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MaineFamilyLawLLM",
    debug=DEBUG_CONSOLE,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=DEBUG_CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(ICON_PATH),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MaineFamilyLawLLM",
)
