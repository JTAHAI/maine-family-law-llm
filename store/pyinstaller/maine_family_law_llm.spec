# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import importlib.util
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ROOT = Path(SPECPATH).resolve().parents[1]
ICON_PATH = ROOT / "assets" / "brand" / "focaf_family_law_llm_brand_kit" / "assets" / "favicon" / "favicon.ico"
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
DEBUG_CONSOLE = os.environ.get("MFL_STORE_DEBUG_CONSOLE", "").strip() == "1"
FEATURE_TIER = os.environ.get("MFL_STORE_FEATURE_TIER", "essential").strip().lower()
if FEATURE_TIER not in {"essential", "full"}:
    raise ValueError(f"unsupported MFL_STORE_FEATURE_TIER: {FEATURE_TIER}")
FULL_DOCUMENT_INTELLIGENCE = FEATURE_TIER == "full"

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
    allowed_suffixes = {".py", ".html", ".css", ".js", ".svg", ".json", ".pdf", ".csv"}
    for path in package_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        relative_parent = path.relative_to(package_root).parent
        target = str(Path(destination) / relative_parent).replace("\\", "/")
        results.append((str(path), target))
    return results


def collect_installed_package_files(package_name: str, *, destination: str) -> list[tuple[str, str]]:
    spec = importlib.util.find_spec(package_name)
    if spec is None or not spec.submodule_search_locations:
        return []
    root = Path(next(iter(spec.submodule_search_locations))).resolve()
    results: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() == ".pyc":
            continue
        relative_parent = path.relative_to(root).parent
        target = str(Path(destination) / relative_parent).replace("\\", "/")
        results.append((str(path), target))
    return results


def collect_runtime_submodules(package_name: str) -> list[str]:
    """Discover importable Python files without importing heavyweight packages.

    ``PyInstaller.utils.hooks.collect_submodules`` starts an isolated child
    interpreter for each package.  On the full offline tier that means an
    optional document-intelligence package can spend minutes importing model
    stacks before the build reaches its first analysis pass.  A timeout there
    produces an incomplete hidden-import list.  The Store build already
    installs every dependency into a normal filesystem location, so a bounded
    filesystem walk is both deterministic and sufficient for these dynamic
    imports.  It never executes package code, discovers tests, or follows
    bytecode/cache trees.
    """

    def _include(module_name: str) -> bool:
        parts = module_name.split(".")
        if module_name.startswith("torch.testing._internal") or ".testing._internal." in module_name:
            return False
        if any(part == "tests" or part.startswith("test") for part in parts):
            return False
        return True

    specification = importlib.util.find_spec(package_name)
    locations = getattr(specification, "submodule_search_locations", None) if specification else None
    if not locations:
        return [package_name] if _include(package_name) else []
    modules: set[str] = {package_name}
    for location in locations:
        root = Path(location)
        if not root.is_dir():
            continue
        for candidate in root.rglob("*.py"):
            if "__pycache__" in candidate.parts:
                continue
            relative = candidate.relative_to(root).with_suffix("")
            parts = list(relative.parts)
            if parts and parts[-1] == "__init__":
                parts.pop()
            module_name = ".".join([package_name, *parts]) if parts else package_name
            if _include(module_name):
                modules.add(module_name)
    return sorted(modules)


datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "data"), "data"),
    (str(ROOT / "sample_question_bank"), "sample_question_bank"),
    (str(ROOT / "LICENSE.md"), "."),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
]
datas += collect_source_package_files(ROOT / "configs", destination="configs")
datas += collect_flat_files(ROOT / "docs", destination="docs", names=STORE_DOCS)
datas += collect_flat_files(ROOT / "licenses", destination="licenses", names=(
    "A-market-ecm-lawyer-plugin-MIT.md", "Google-knowledge-catalog-Apache-2.0.md",
    "Paparusi-legal-ai-agent-MIT.md", "pablospe-docx-editor-MIT.md", "whisper.cpp-MIT.md",
    "NotoSans-OFL-1.1.md", "OCRmyPDF-sRGB-Zlib.md",
))
datas += collect_source_package_files(ROOT / "src" / "maine_family_law_llm", destination="src/maine_family_law_llm")
# Keep the legal runtime tree available as source so PyInstaller's frozen app
# can import the same modules the desktop runtime imports at startup.
datas += collect_source_package_files(ROOT / "legal", destination="src/legal")
# Collect ui assets without __pycache__ directories
datas += collect_source_package_files(ROOT / "src" / "maine_family_law_llm" / "ui", destination="maine_family_law_llm/ui")
# ``docx-editor`` resolves its XML/comment templates relative to ``__file__``.
# PyInstaller's bytecode archive makes the module importable but does not
# materialize those package-relative files for the frozen executable.  Ship the
# compact package tree explicitly so paragraph inspection and comment creation
# do not fail only after a user imports a private DOCX.
datas += collect_installed_package_files("docx_editor", destination="docx_editor")
if FULL_DOCUMENT_INTELLIGENCE:
    datas += collect_installed_package_files("en_core_web_lg", destination="en_core_web_lg")
    # PEFT and Accelerate are lazily imported by the optional FAST INTERCHANGE
    # worker.  Hidden imports alone place pure modules in PyInstaller's PYZ
    # archive, but the worker also uses package-resource discovery at runtime.
    # Copy the importable package trees as data so an admitted external LoRA
    # release can run with no installer or network lookup.  This intentionally
    # excludes all legal weights, adapters, registries, and credentials.
    for package_name in ("peft", "accelerate", "safetensors"):
        datas += collect_installed_package_files(package_name, destination=package_name)
    datas += copy_metadata("en-core-web-lg")
    # OCRmyPDF loads fallback fonts and its ICC profile as package resources.
    # Module/metadata collection alone omits them and breaks searchable PDFs.
    for package_name in ("presidio_analyzer", "tldextract", "docling", "docling_core", "docling_ibm_models", "rapidocr", "docling_parse", "ocrmypdf"):
        datas += collect_data_files(package_name)
# ``docx`` is the import package; the installed distribution whose metadata
# must accompany the frozen runtime is named ``python-docx``.
for package_name in ("fastapi", "uvicorn", "httpx", "python-multipart", "pypdf", "pypdfium2", "cryptography", "python-docx", "docx-editor"):
    datas += copy_metadata(package_name)
if FULL_DOCUMENT_INTELLIGENCE:
    for package_name in ("docling", "docling-slim", "docling-core", "docling-ibm-models", "docling-parse", "rapidocr", "presidio-analyzer", "tldextract", "ocrmypdf", "spacy", "sqlite-vec", "qdrant-client", "pikepdf", "fpdf2", "uharfbuzz"):
        datas += copy_metadata(package_name)
    # FAST INTERCHANGE is an optional, external-artifact lane.  Its full-tier
    # worker must be able to load an independently admitted LoRA adapter with
    # no installer/download at run time.  These packages contain runtime code
    # only; legal weights, adapters, registries, and secrets remain external.
    for package_name in ("peft", "accelerate", "safetensors"):
        datas += copy_metadata(package_name)

# python-multipart is discovered by FastAPI at route-registration time rather
# than through a conventional top-level application import. Include both
# modules explicitly so frozen record-upload routes start without attempting an
# installer or failing at first API launch.
hiddenimports = ["sqlite3", "_sqlite3", "mailbox", "multipart", "multipart.multipart", "psutil"]
hiddenimports += [
    "legal.security.privacy_fortress",
    "legal.ops.release_pilot_hardening",
    "legal.pilot.real_matter_operations",
    "legal.pilot.sandbox_operations",
    "legal.pilot.launch_ops",
    "legal.release.release_candidate_operations",
    "legal.release.ga_release",
]
if FULL_DOCUMENT_INTELLIGENCE:
    hiddenimports.append("en_core_web_lg")
# The canonical ``src/maine_family_law_llm`` tree is deliberately bundled as
# source data above. The repository-root package is only a runtime shim that
# points at that tree; asking PyInstaller to collect submodules from the shim
# produces false missing-hidden-import errors and contributes no frozen code.
# Keep dynamic source modules as shipped runtime assets and let normal imports
# resolve them through the shim's explicit ``__path__`` at runtime.
for package_name in ("app", "legal", "fastapi", "starlette", "uvicorn", "httpx", "pydantic", "pypdfium2", "cryptography", "docx", "docx_editor"):
    hiddenimports += collect_runtime_submodules(package_name)
if FULL_DOCUMENT_INTELLIGENCE:
    for package_name in ("docling", "docling_ibm_models", "rapidocr", "presidio_analyzer", "ocrmypdf", "spacy", "sqlite_vec", "qdrant_client", "peft", "accelerate", "safetensors"):
        hiddenimports += collect_runtime_submodules(package_name)
hiddenimports = sorted(set(hiddenimports))

excluded_packages = ["pytest", "tests", "tkinter.test", "unittest.test"]
if not FULL_DOCUMENT_INTELLIGENCE:
    excluded_packages += [
        "torch",
        "torchvision",
        "transformers",
        "docling",
        "docling_core",
        "docling_ibm_models",
        "rapidocr",
        "presidio_analyzer",
        "spacy",
        "qdrant_client",
        "ocrmypdf",
    ]

a = Analysis(
    [str(ROOT / "app" / "store_entrypoint.py")],
    pathex=[str(ROOT / "src"), str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_packages,
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
