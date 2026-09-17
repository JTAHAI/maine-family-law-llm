"""Consent-bound Windows Ollama setup. No work runs on import or ordinary startup.

This installs general Qwen inference, never grants legal/specialist admission.
Official release/model pins were inspected 2026-09-17. Existing installations
are reused, never upgraded or deleted by this service.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from legal.model_orchestration.hardware import profile_hardware
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from .setup import LocalAiSetupError, LocalAiSetupStore, _canonical, _digest, _now

GIB = 1024**3
MODELS = {
    "qwen3:4b": {"label": "Standard local AI (4B)", "bytes": 2497293444,
                 "sha256": "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7",
                 "ram": 6 * GIB, "vram": 4 * GIB},
    "qwen3:8b": {"label": "More capable local AI (8B)", "bytes": 5225387677,
                 "sha256": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41",
                 "ram": 10 * GIB, "vram": int(5.5 * GIB)},
}
INSTALLER_URL = "https://github.com/ollama/ollama/releases/download/v0.34.1/OllamaSetup.exe"
INSTALLER_BYTES = 1570506608
INSTALLER_SHA256 = "a92986c86ab6854675ffd1b725db7c0350d40755895c95c397c58d61014e14d9"
BASE = "http://127.0.0.1:11434"
TERMINAL = {"ready", "failed", "cancelled", "interrupted"}


class Cancelled(Exception):
    pass


def model_profile(model):
    if model not in MODELS:
        raise LocalAiSetupError("local_ai_model_not_allowed", 400)
    return MODELS[model]


class RedirectPolicy(HTTPRedirectHandler):
    def __init__(self, download=False):
        self.download = download

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if (not self.download or target.scheme != "https" or target.username
                or target.hostname not in {"github.com", "release-assets.githubusercontent.com"}
                or target.port not in {None, 443}):
            raise LocalAiSetupError("local_ai_redirect_forbidden")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def local_request(path, body=None, timeout=4):
    request = Request(BASE + path, data=None if body is None else _canonical(body),
                      headers={"Content-Type": "application/json"})
    return build_opener(ProxyHandler({}), RedirectPolicy()).open(request, timeout=timeout)


def local_json(path, body=None, timeout=4):
    with local_request(path, body, timeout) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise LocalAiSetupError("local_ai_response_too_large")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise LocalAiSetupError("local_ai_response_invalid") from exc
    if not isinstance(value, dict):
        raise LocalAiSetupError("local_ai_response_invalid")
    return value


def signature_valid(path):
    if os.name != "nt":
        return False
    command = ("$s=Get-AuthenticodeSignature -LiteralPath $env:MFL_SIGNATURE_FILE; "
               "@{valid=($s.Status -eq 'Valid');subject=$s.SignerCertificate.Subject} | ConvertTo-Json -Compress")
    env = {**os.environ, "MFL_SIGNATURE_FILE": str(path)}
    ps = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    # A PowerShell 7 parent can otherwise make Windows PowerShell autoload the
    # incompatible Core Security module. Use only the OS-bundled module path.
    for key in list(env):
        if key.casefold() == "psmodulepath":
            del env[key]
    env["PSModulePath"] = str(ps.parent / "Modules")
    try:
        result = subprocess.run([str(ps), "-NoProfile", "-NonInteractive", "-Command", command],
                                env=env, capture_output=True, timeout=30, check=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        signature = json.loads(result.stdout)
        return signature.get("valid") is True and bool(re.search(
            r"(?:^|,\s*)O=Ollama Inc\.(?:,|$)", str(signature.get("subject", ""))))
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def engine_path():
    candidates = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"]
    found = shutil.which("ollama")
    if found:
        candidates.append(Path(found))
    return next((path for path in candidates if path.is_file() and not path.is_symlink()), None)


def model_root():
    configured = os.environ.get("OLLAMA_MODELS", "").strip()
    if os.name == "nt" and not configured:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                configured = winreg.QueryValueEx(key, "OLLAMA_MODELS")[0]
        except OSError:
            pass
    return Path(os.path.expandvars(configured)).expanduser() if configured else Path.home() / ".ollama/models"


def free_bytes(path):
    path = Path(path).resolve()
    while not path.exists() and path != path.parent:
        path = path.parent
    return shutil.disk_usage(path).free


def installed_models():
    try:
        value = local_json("/api/tags")
        rows = value.get("models")
        if not isinstance(rows, list) or len(rows) > 4096:
            raise LocalAiSetupError("local_ai_inventory_invalid")
        return True, {row.get("name"): str(row.get("digest", "")).removeprefix("sha256:")
                      for row in rows if isinstance(row, dict)}
    except (URLError, OSError):
        return False, {}


def inspect_model(model, root):
    spec = model_profile(model)
    running, installed = installed_models()
    path = engine_path()
    digest = installed.get(model)
    # A stopped runtime can still have the requested model. This is only an
    # inventory hint; /api/tags is rechecked after starting the signed engine.
    if not running:
        manifest = model_root() / "manifests/registry.ollama.ai/library/qwen3" / model.split(":")[1]
        if manifest.is_file() and not manifest.is_symlink() and manifest.stat().st_size <= 1024 * 1024:
            raw = manifest.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest == spec["sha256"]:
                # A manifest alone is not an installed model: interrupted pulls
                # may leave it without all of its content-addressed blobs.
                document = json.loads(raw)
                layers = [document.get("config", {}), *document.get("layers", [])]
                for layer in layers:
                    blob_id = str(layer.get("digest", ""))
                    if not re.fullmatch(r"sha256:[a-f0-9]{64}", blob_id):
                        digest = None
                        break
                    blob = model_root() / "blobs" / blob_id.replace(":", "-")
                    if not blob.is_file() or blob.is_symlink() or blob.stat().st_size != layer.get("size"):
                        digest = None
                        break
    hardware = profile_hardware(root).as_dict()
    ram, vram = int(hardware.get("available_memory_bytes") or 0), int(hardware.get("available_vram_bytes") or 0)
    fits = ram >= spec["ram"] or (vram >= spec["vram"] and ram >= 2 * GIB)
    blockers = []
    if platform.system() != "Windows" or platform.machine().lower() not in {"amd64", "x86_64"}:
        blockers.append("windows_x64_required")
    if not fits:
        blockers.append("insufficient_available_memory")
    if digest and digest != spec["sha256"]:
        blockers.append("existing_model_revision_differs_no_overwrite")
    engine_missing = path is None and not running
    model_missing = not digest
    # Count both allocations when they share a volume. Include installer cache,
    # expanded engine and a reserve; Ollama owns its resumable model cache.
    needs = [(Path(root), INSTALLER_BYTES + GIB if engine_missing else 256 * 1024**2),
             (model_root(), spec["bytes"] + 2 * GIB if model_missing else 256 * 1024**2)]
    if engine_missing:
        needs.append((Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama", 5 * GIB))
    volumes = {}
    for destination, amount in needs:
        key = str(destination.resolve().anchor).casefold()
        previous = volumes.get(key, (destination, 0))
        volumes[key] = (destination, previous[1] + amount)
    if any(free_bytes(destination) < amount for destination, amount in volumes.values()):
        blockers.append("insufficient_disk_space")
    return {"model": model, "label": spec["label"], "runtime_running": running,
            "engine_installed": bool(path) or running, "model_installed": digest == spec["sha256"],
            "download_bytes": (INSTALLER_BYTES if engine_missing else 0) + (spec["bytes"] if model_missing else 0),
            "required_disk_bytes": sum(amount for _, amount in volumes.values()),
            "eligible": not blockers, "blockers": blockers, "review_required": True,
            "model_sha256": spec["sha256"], "network_scope": "loopback_inventory_only",
            "legal_quality_certified": False}


def checked_file(path, expected):
    if not path.is_file() or path.is_symlink():
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == expected


class WindowsBackend:
    def inspect(self, model, root):
        return inspect_model(model, root)

    def ensure_engine(self, root, cancel, update):
        running, _ = installed_models()
        if running:
            update("engine_reused", "Ollama is already running. No installation needed.")
            return
        path = engine_path()
        if path is None:
            cache = root / "installer-cache"
            cache.mkdir(parents=True, exist_ok=True)
            if cache.is_symlink() or cache.resolve().parent != root.resolve():
                raise LocalAiSetupError("local_ai_cache_path_invalid")
            installer = cache / "OllamaSetup-0.34.1.exe"
            if not checked_file(installer, INSTALLER_SHA256):
                partial = cache / (secrets.token_hex(12) + ".part")
                update("downloading_engine", "Downloading the official Ollama installer.", 0, INSTALLER_BYTES)
                try:
                    request = Request(INSTALLER_URL, headers={"User-Agent": "MaineFamilyLawLLM-setup/9.0.1"})
                    opener = build_opener(ProxyHandler({}), RedirectPolicy(download=True))
                    digest, received, deadline = hashlib.sha256(), 0, time.monotonic() + 7200
                    with opener.open(request, timeout=30) as response, partial.open("xb") as output:
                        while True:
                            if cancel.is_set():
                                raise Cancelled()
                            if time.monotonic() > deadline:
                                raise LocalAiSetupError("local_ai_download_timeout")
                            block = response.read(1024 * 1024)
                            if not block:
                                break
                            received += len(block)
                            if received > INSTALLER_BYTES or free_bytes(cache) < len(block) + GIB:
                                raise LocalAiSetupError("local_ai_download_size_or_disk_limit")
                            output.write(block)
                            digest.update(block)
                            update("downloading_engine", "Downloading Ollama. Your records are not being sent.", received, INSTALLER_BYTES)
                    if received != INSTALLER_BYTES or digest.hexdigest() != INSTALLER_SHA256:
                        raise LocalAiSetupError("local_ai_installer_hash_mismatch")
                    os.replace(partial, installer)
                finally:
                    partial.unlink(missing_ok=True)  # Only this operation's random temporary file.
            if cancel.is_set():
                raise Cancelled()
            if not signature_valid(installer):
                raise LocalAiSetupError("local_ai_installer_signature_invalid")
            update("installing_engine", "Installing Ollama for your Windows account. Let this step finish before closing.")
            result = subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
                                    timeout=900, capture_output=True,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode != 0:
                raise LocalAiSetupError("local_ai_installer_failed")
            installer.unlink(missing_ok=True)
            path = engine_path()
        else:
            update("engine_reused", "Using the existing Ollama installation without reinstalling it.")
        if cancel.is_set():
            raise Cancelled()
        if installed_models()[0]:
            return
        if path is None or not signature_valid(path):
            raise LocalAiSetupError("local_ai_existing_engine_unverified")
        update("starting_engine", "Starting your local Ollama engine.")
        env = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NO_CLOUD": "1"}
        subprocess.Popen([str(path), "serve"], env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(60):
            if installed_models()[0]:
                return
            if cancel.wait(1):
                raise Cancelled()
        raise LocalAiSetupError("local_ai_engine_start_failed")

    def ensure_model(self, model, cancel, update):
        expected = model_profile(model)["sha256"]
        _, inventory = installed_models()
        if inventory.get(model):
            if inventory[model] != expected:
                raise LocalAiSetupError("existing_model_revision_differs_no_overwrite")
            update("model_reused", "This model is already installed. No model download needed.")
            return
        if free_bytes(model_root()) < model_profile(model)["bytes"] + 2 * GIB:
            raise LocalAiSetupError("insufficient_disk_space")
        update("downloading_model", "Downloading the selected reasoning model. No matter data is sent.")
        deadline = time.monotonic() + 7200
        with local_request("/api/pull", {"model": model, "stream": True}, timeout=30) as response:
            for _ in range(200000):
                if cancel.is_set():
                    raise Cancelled()
                if free_bytes(model_root()) < GIB:
                    raise LocalAiSetupError("insufficient_disk_space")
                if time.monotonic() > deadline:
                    raise LocalAiSetupError("local_ai_download_timeout")
                line = response.readline(65537)
                if not line:
                    break
                if len(line) > 65536:
                    raise LocalAiSetupError("local_ai_progress_invalid")
                item = json.loads(line)
                if not isinstance(item, dict) or item.get("error"):
                    raise LocalAiSetupError("local_ai_model_download_failed")
                update("downloading_model", "Downloading or verifying a model layer.",
                       max(0, int(item.get("completed") or 0)), max(0, int(item.get("total") or 0)))
                if item.get("status") == "success":
                    break
        if installed_models()[1].get(model) != expected:
            raise LocalAiSetupError("local_ai_model_hash_mismatch")

    def smoke(self, model):
        # Exercise the actual source-review contract, not a second template.
        # Fictional transport/quotation smoke only, never legal-quality evidence.
        from legal.agent_runtime.providers import CuratedOllamaReasoningClient
        quote = "The fictional meeting is proposed for Tuesday. No agreement is recorded."
        answer = CuratedOllamaReasoningClient(model_name=model, capability="evidence_review", timeout_seconds=180).generate_response(
            "Review this fictional record. Copy the full record body, preserving its qualification.\n"
            "[1] Record body: " + quote)
        if list(answer.excerpts) != [{"reference": 1, "quote": quote}]:
            raise LocalAiSetupError("local_ai_model_smoke_failed")


class InstallService:
    def __init__(self, backend=None):
        self.backend = backend or WindowsBackend()
        self.lock = threading.RLock()
        self.operation = threading.Lock()
        self.plans = {}
        self.jobs = {}

    def prepare(self, store, model):
        inventory = self.backend.inspect(model, store.root)
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.plans = {k: v for k, v in self.plans.items() if v["expires"] > time.monotonic()}
            if len(self.plans) >= 64:
                raise LocalAiSetupError("local_ai_setup_busy", 429)
            self.plans[token] = {"audience": store.audience, "model": model, "expires": time.monotonic() + 600}
        return {**inventory, "plan_token": token, "expires_in_seconds": 600,
                "consent_text": "Install only missing Ollama/model components; start the local engine and run a fictional test. Downloads contact GitHub and Ollama's model registry/CDN, not your matter records. Existing components are kept. Ollama may run in the background and maintain its own updates. Qwen is general-purpose, not a legally qualified specialist."}

    def _save(self, store, state):
        store.directory.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(store.directory / "install-job.json.enc",
                           _canonical(store.encryptor.encrypt_json(state)), mode=0o600)

    def start(self, store, token, confirmed):
        if confirmed is not True:
            raise LocalAiSetupError("local_ai_setup_confirmation_required", 400)
        with self.lock:
            plan = self.plans.get(token)
            if not plan or plan["audience"] != store.audience or plan["expires"] <= time.monotonic():
                raise LocalAiSetupError("local_ai_install_plan_invalid", 409)
            if not self.operation.acquire(blocking=False):
                raise LocalAiSetupError("local_ai_install_already_running", 409)
            if len(self.jobs) >= 64:
                self.jobs = {k: v for k, v in self.jobs.items() if v[1]["status"] not in TERMINAL}
            del self.plans[token]
            job = secrets.token_hex(16)
            state = {"job_id": job, "model": plan["model"], "status": "queued", "message": "Preparing local AI.",
                     "review_required": True, "completed_bytes": 0, "total_bytes": 0,
                     "events": [], "error_code": None, "legal_quality_certified": False}
            cancel = threading.Event()
            self.jobs[job] = (store.audience, state, cancel)
            try:
                self._save(store, state)
            except Exception:
                self.jobs.pop(job, None)
                self.operation.release()
                raise
            threading.Thread(target=self._run, args=(store, job), daemon=True).start()
            return self.status(store, job)

    def _run(self, store, job):
        _, state, cancel = self.jobs[job]
        def update(stage, message, completed=0, total=0):
            with self.lock:
                changed = state["status"] != stage
                state.update(status=stage, message=message, completed_bytes=completed, total_bytes=total)
                if changed:
                    event = {"stage": stage, "at": _now(), "previous_hash": state["events"][-1]["hash"] if state["events"] else ""}
                    event["hash"] = _digest(event)
                    state["events"].append(event)
                    self._save(store, state)
        try:
            # Cross-process serialization as well as the fast in-process gate.
            store.root.mkdir(parents=True, exist_ok=True)
            with exclusive_file_lock(store.root / ".ollama-install.lock"):
                check = self.backend.inspect(state["model"], store.root)
                if not check["eligible"]:
                    raise LocalAiSetupError(check["blockers"][0])
                if cancel.is_set():
                    raise Cancelled()
                self.backend.ensure_engine(store.root, cancel, update)
                if cancel.is_set():
                    raise Cancelled()
                check = self.backend.inspect(state["model"], store.root)
                if not check["eligible"]:
                    raise LocalAiSetupError(check["blockers"][0])
                self.backend.ensure_model(state["model"], cancel, update)
                if cancel.is_set():
                    raise Cancelled()
                update("testing", "Checking a fictional response. Your matter is not part of this test.")
                self.backend.smoke(state["model"])
                if cancel.is_set():
                    raise Cancelled()
                update("ready", "Local AI is ready on this computer. Choose Use in chat. Every result still needs review.")
        except Cancelled:
            update("cancelled", "Setup stopped. Existing software and models were kept; Ollama may retain partial downloads for retry.")
        except Exception as exc:
            with self.lock:
                state["error_code"] = exc.code if isinstance(exc, LocalAiSetupError) else "local_ai_setup_failed"
            update("failed", "Setup could not finish. Your records and existing models are unchanged. Check your connection or free space, then try again.")
        finally:
            self.operation.release()

    def status(self, store, job):
        if not re.fullmatch(r"[a-f0-9]{32}", job):
            raise LocalAiSetupError("local_ai_job_not_found", 404)
        with self.lock:
            entry = self.jobs.get(job)
            if not entry or entry[0] != store.audience:
                from legal.security.strict_json import strict_json_load_path
                path = store.directory / "install-job.json.enc"
                if not path.is_file():
                    raise LocalAiSetupError("local_ai_job_not_found", 404)
                state = store.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=65536, require_object=True))
                previous = ""
                for event in state.get("events", []):
                    unsigned = {k: v for k, v in event.items() if k != "hash"}
                    if event.get("previous_hash") != previous or event.get("hash") != _digest(unsigned):
                        raise LocalAiSetupError("local_ai_install_history_invalid")
                    previous = event["hash"]
                if state.get("job_id") != job:
                    raise LocalAiSetupError("local_ai_job_not_found", 404)
                if state.get("status") not in TERMINAL:
                    state.update(status="interrupted", message="Setup was interrupted. Check this PC again to reuse completed components.")
                return state
            return json.loads(json.dumps(entry[1]))

    def cancel(self, store, job):
        self.status(store, job)
        with self.lock:
            entry = self.jobs.get(job)
            if entry and entry[0] == store.audience:
                entry[2].set()
        return {"status": "cancel_requested", "message": "Stopping after the current safe step. An installer already running must finish; nothing is uninstalled."}


INSTALLS = InstallService()
