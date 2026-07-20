from __future__ import annotations

import json
import os
import threading
import sys
import tkinter as tk
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app.local_api_service import ensure_local_service, stop_local_service
from app.runtime_support import RuntimeContext, build_runtime_context, configure_runtime_environment, local_about_links, open_path_or_url
from app.wizard_import_corpus import import_additional_corpus
from app.wizard_new_case import default_case_build_root, launch_new_case_wizard, suggest_case_name
from maine_family_law_llm.case_library import active_case_root, list_registered_case_roots, prune_missing_case_roots, set_active_case_root
from maine_family_law_llm.case_corpus_builder import (
    bootstrap_repository,
    create_sample_case_build,
    export_to_usb,
)
from maine_family_law_llm.case_workspace import (
    append_case_ingest_history,
    default_workspace_root,
    inherit_case_ingest_history,
    load_case_summary,
    read_case_ingest_history,
    read_case_source_roots,
)
from maine_family_law_llm.version import APP_DISPLAY_NAME, GITHUB_REPOSITORY_URL, STORE_MISSION_TAGLINE, VERSION

ACTION_SPECS = (
    ("Open Local AI Chat", "open_local_ai_chat"),
    ("Create New Case Corpus", "create_new_case"),
    ("Open Existing Case Corpus", "open_existing_case"),
    ("Reopen Intake / Add More Evidence", "import_more_evidence"),
    ("Build Neutral Sample Corpus", "build_sample_case"),
    ("Open Search / Indexes", "open_search_indexes"),
    ("Open GAL Package", "open_gal_package"),
    ("Open Court Package", "open_court_package"),
    ("Open Lawyer Package", "open_lawyer_package"),
    ("Open ADA / Prosecutor Package", "open_ada_package"),
    ("Open External Legal-Matter Release", "open_external_release"),
    ("Open Private Forensic Master", "open_private_master"),
    ("Verify Hashes / Proof", "verify_hashes"),
    ("Open Review Portal", "open_review_portal"),
    ("Export to USB", "export_usb"),
    ("Stop Local AI Chat", "stop_local_ai_chat"),
    ("About / Help", "show_about_help"),
    ("Repair / Troubleshoot", "repair_repo"),
    ("Exit", "destroy"),
)

SOURCE_GUIDE_SPECS = (
    ("What can I import?", REPO_ROOT / "docs" / "HOW_TO_ADD_YOUR_CORPUS.html"),
    ("Gmail / Workspace", REPO_ROOT / "docs" / "HOW_TO_EXPORT_FROM_GMAIL_AND_GOOGLE_WORKSPACE.html"),
    ("Outlook / Hotmail", REPO_ROOT / "docs" / "HOW_TO_EXPORT_FROM_OUTLOOK_AND_HOTMAIL.html"),
    ("Phone / screenshots", REPO_ROOT / "docs" / "HOW_TO_EXPORT_FROM_IPHONE_AND_ANDROID.html"),
    ("Privacy / hashes", REPO_ROOT / "docs" / "HASH_AND_CHAIN_OF_CUSTODY.html"),
)


@dataclass
class CorpusBuildPlan:
    source_roots: list[Path]
    output_root: Path
    case_name: str


def start_background_task(
    after_callback: Callable[[int, Callable[[], None]], object],
    worker: Callable[[], object],
    on_success: Callable[[object], None],
    on_failure: Callable[[str], None],
) -> threading.Thread:
    def _run() -> None:
        try:
            result = worker()
        except Exception as exc:  # pragma: no cover - callback path exercised through launcher tests
            error_text = f"{exc.__class__.__name__}: {exc}"
            after_callback(0, lambda: on_failure(error_text))
            return
        after_callback(0, lambda: on_success(result))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def build_new_case_from_sources(
    repo_root: Path,
    source_roots: list[Path],
    output_root: Path | None = None,
    case_name: str = "",
):
    return launch_new_case_wizard(
        repo_root=repo_root,
        source_roots=source_roots,
        output_root=output_root,
        case_name=case_name,
    )


def import_case_from_sources(
    repo_root: Path,
    existing_case_root: Path | None,
    source_roots: list[Path],
    output_root: Path | None = None,
    case_name: str = "",
):
    return import_additional_corpus(
        repo_root=repo_root,
        existing_case_root=existing_case_root,
        source_roots=source_roots,
        output_root=output_root,
        case_name=case_name,
    )


class CorpusBuildWizard(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        title_text: str,
        instructions: str,
        confirm_text: str,
        default_output_root: Path,
        default_case_name: str,
        existing_source_roots: list[Path] | None = None,
        history_rows: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(title_text)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.result: CorpusBuildPlan | None = None
        self.source_roots: list[Path] = []
        self.existing_source_roots = existing_source_roots or []
        self.history_rows = history_rows or []
        self.case_name_var = tk.StringVar(value=default_case_name)
        self.output_root_var = tk.StringVar(value=str(default_output_root))
        self.confirm_text = confirm_text
        self._build_ui(instructions)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build_ui(self, instructions: str) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=instructions, wraplength=760, justify="left").pack(anchor="w")

        if self.existing_source_roots:
            existing_frame = ttk.LabelFrame(frame, text="Already included in this case", padding=12)
            existing_frame.pack(fill="x", pady=(14, 10))
            self.existing_listbox = tk.Listbox(existing_frame, height=min(6, max(3, len(self.existing_source_roots))), selectmode="extended")
            self.existing_listbox.grid(row=0, column=0, sticky="nsew")
            for path in self.existing_source_roots:
                status = "available" if path.exists() else "missing"
                self.existing_listbox.insert(tk.END, f"{path} [{status}]")
            existing_buttons = ttk.Frame(existing_frame)
            existing_buttons.grid(row=0, column=1, sticky="n", padx=(12, 0))
            ttk.Button(existing_buttons, text="Open selected", command=self._open_selected_existing_source).pack(fill="x")
            ttk.Label(
                existing_frame,
                text=(
                    "These source folders stay included automatically when you add more evidence later. "
                    "You only need to add the new files or folders below."
                ),
                wraplength=720,
                justify="left",
            ).grid(row=1, column=0, sticky="w", pady=(10, 0))
            missing_count = sum(1 for path in self.existing_source_roots if not path.exists())
            if missing_count:
                ttk.Label(
                    existing_frame,
                    text=(
                        f"Warning: {missing_count} remembered source path(s) are missing right now. "
                        "Reconnect a moved drive or folder before rebuilding if you want those files included again."
                    ),
                    foreground="#8a3b12",
                    wraplength=720,
                    justify="left",
                ).grid(row=2, column=0, sticky="w", pady=(8, 0))
            existing_frame.columnconfigure(0, weight=1)

        if self.history_rows:
            recent = self.history_rows[-4:]
            history_lines = []
            for row in reversed(recent):
                when = str(row.get("recorded_at", ""))[:10] or "undated"
                mode = str(row.get("mode", "update")).replace("_", " ")
                added_count = len(row.get("source_roots_added", []) or [])
                cumulative_count = len(row.get("cumulative_source_roots", []) or [])
                history_lines.append(
                    f"{when}: {mode} - added {added_count} path(s), cumulative source roots {cumulative_count}."
                )
            history_frame = ttk.LabelFrame(frame, text="Recent intake history", padding=12)
            history_frame.pack(fill="x", pady=(0, 10))
            ttk.Label(
                history_frame,
                text="\n".join(history_lines),
                wraplength=720,
                justify="left",
            ).pack(anchor="w")

        sources_frame = ttk.LabelFrame(frame, text="Add new source folders or files", padding=12)
        sources_frame.pack(fill="both", expand=True, pady=(14, 12))
        self.sources_listbox = tk.Listbox(sources_frame, height=8, selectmode="extended")
        self.sources_listbox.grid(row=0, column=0, rowspan=6, sticky="nsew")
        sources_buttons = ttk.Frame(sources_frame)
        sources_buttons.grid(row=0, column=1, sticky="n", padx=(12, 0))
        ttk.Button(sources_buttons, text="Add folder", command=self._add_source_folder).pack(fill="x")
        ttk.Button(sources_buttons, text="Add files", command=self._add_source_files).pack(fill="x", pady=(8, 0))
        ttk.Button(sources_buttons, text="Add Documents", command=lambda: self._add_known_folder(Path.home() / "Documents")).pack(fill="x", pady=(8, 0))
        ttk.Button(sources_buttons, text="Add Downloads", command=lambda: self._add_known_folder(Path.home() / "Downloads")).pack(fill="x", pady=(8, 0))
        ttk.Button(sources_buttons, text="Add Desktop", command=lambda: self._add_known_folder(Path.home() / "Desktop")).pack(fill="x", pady=(8, 0))
        ttk.Button(sources_buttons, text="Add Pictures", command=lambda: self._add_known_folder(Path.home() / "Pictures")).pack(fill="x", pady=(8, 0))
        ttk.Button(sources_buttons, text="Open selected", command=self._open_selected_new_source).pack(fill="x", pady=(8, 0))
        ttk.Button(sources_buttons, text="Remove selected", command=self._remove_selected_source).pack(fill="x", pady=(8, 0))
        ttk.Label(
            sources_buttons,
            text=(
                "Supported inputs: folders, PDFs, screenshots, phone exports, email exports, Word files, "
                "spreadsheets, ZIPs, and scanned batches. The build stays read-only against the originals."
            ),
            wraplength=220,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        guide_frame = ttk.LabelFrame(sources_buttons, text="Need help getting records out?", padding=10)
        guide_frame.pack(fill="x", pady=(12, 0))
        for label, guide_path in SOURCE_GUIDE_SPECS:
            ttk.Button(
                guide_frame,
                text=label,
                command=lambda current=guide_path: self._open_guide(current),
            ).pack(fill="x", pady=(0, 6))
        ttk.Label(
            guide_frame,
            text="These guides walk nontechnical users through Gmail, Outlook, Hotmail, Google Workspace, phone screenshots, attachments, and evidence staging.",
            wraplength=220,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        help_frame = ttk.LabelFrame(frame, text="Common source examples", padding=12)
        help_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            help_frame,
            text=(
                "Court PDFs, downloaded attachments, phone screenshot folders, school records, counseling or provider records, "
                "USB copies, and staged exports from Gmail, Outlook, Hotmail, or Workspace."
            ),
            wraplength=720,
            justify="left",
        ).pack(anchor="w")
        sources_frame.columnconfigure(0, weight=1)
        sources_frame.rowconfigure(0, weight=1)

        case_frame = ttk.LabelFrame(frame, text="Build settings", padding=12)
        case_frame.pack(fill="x")
        ttk.Label(case_frame, text="Case name").grid(row=0, column=0, sticky="w")
        ttk.Entry(case_frame, textvariable=self.case_name_var).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 10))
        ttk.Label(case_frame, text="Output folder").grid(row=2, column=0, sticky="w")
        ttk.Entry(case_frame, textvariable=self.output_root_var).grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(case_frame, text="Browse output", command=self._browse_output_root).grid(row=3, column=1, sticky="ew", padx=(10, 0))
        case_frame.columnconfigure(0, weight=1)

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(actions, text=self.confirm_text, command=self._submit).pack(side="right", padx=(0, 10))

    def _refresh_sources(self) -> None:
        self.sources_listbox.delete(0, tk.END)
        for path in self.source_roots:
            self.sources_listbox.insert(tk.END, str(path))
        if self.source_roots and not self.case_name_var.get().strip():
            self.case_name_var.set(suggest_case_name(self.source_roots))

    def _add_source_folder(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="Add Source Folder",
            initialdir=str(Path.home()),
            mustexist=True,
        )
        if not selected:
            return
        candidate = Path(selected)
        if candidate not in self.source_roots:
            self.source_roots.append(candidate)
            self._refresh_sources()

    def _add_source_files(self) -> None:
        selected = filedialog.askopenfilenames(
            parent=self,
            title="Add Source Files",
            initialdir=str(Path.home()),
        )
        if not selected:
            return
        changed = False
        for item in selected:
            candidate = Path(item)
            if candidate not in self.source_roots:
                self.source_roots.append(candidate)
                changed = True
        if changed:
            self._refresh_sources()

    def _add_known_folder(self, candidate: Path) -> None:
        if candidate.exists() and candidate not in self.source_roots:
            self.source_roots.append(candidate)
            self._refresh_sources()

    def _open_selected_existing_source(self) -> None:
        if not hasattr(self, "existing_listbox"):
            return
        selection = list(self.existing_listbox.curselection())
        if not selection:
            return
        path = self.existing_source_roots[selection[0]]
        if path.exists():
            os.startfile(str(path))
        else:
            messagebox.showwarning(
                "Source path unavailable",
                f"This remembered source path is not available right now:\n\n{path}",
                parent=self,
            )

    def _open_selected_new_source(self) -> None:
        selection = list(self.sources_listbox.curselection())
        if not selection:
            return
        path = self.source_roots[selection[0]]
        if path.exists():
            os.startfile(str(path))
        else:
            messagebox.showwarning("Source path unavailable", f"Path not found:\n\n{path}", parent=self)

    def _remove_selected_source(self) -> None:
        selection = list(self.sources_listbox.curselection())
        if not selection:
            return
        indexes = set(selection)
        self.source_roots = [path for idx, path in enumerate(self.source_roots) if idx not in indexes]
        self._refresh_sources()

    def _browse_output_root(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="Select Output Folder",
            initialdir=self.output_root_var.get() or str(default_case_build_root()),
        )
        if selected:
            self.output_root_var.set(selected)

    def _open_guide(self, guide_path: Path) -> None:
        if not guide_path.exists():
            messagebox.showwarning("Guide not found", f"Guide not found at {guide_path}", parent=self)
            return
        os.startfile(str(guide_path))

    def _submit(self) -> None:
        if not self.source_roots:
            messagebox.showwarning(
                "Source paths required",
                "Add at least one new source folder or file before continuing.",
                parent=self,
            )
            return
        output_text = self.output_root_var.get().strip()
        if not output_text:
            messagebox.showwarning("Output folder required", "Choose an output folder for the new build.", parent=self)
            return
        self.result = CorpusBuildPlan(
            source_roots=list(self.source_roots),
            output_root=Path(output_text),
            case_name=self.case_name_var.get().strip() or suggest_case_name(self.source_roots),
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class MaineFamilyLawLauncher(tk.Tk):
    def __init__(self, runtime_context: RuntimeContext | None = None) -> None:
        super().__init__()
        self.runtime = configure_runtime_environment(runtime_context or build_runtime_context())
        self.title(f"{APP_DISPLAY_NAME} v{VERSION}")
        self.geometry("1040x740")
        self.minsize(900, 650)
        self.configure(background="#eee8de")
        self.option_add("*Font", ("Segoe UI", 10))
        self._configure_styles()
        self.repo_root = self.runtime.bundle_root
        self.bootstrap_warning = ""
        self._case_build_in_progress = False
        self._build_progress_dialog: tk.Toplevel | None = None
        self.action_buttons: dict[str, ttk.Button] = {}
        if self.runtime.allows_repo_bootstrap_writes:
            try:
                bootstrap_repository(self.repo_root)
            except Exception as exc:
                self.bootstrap_warning = f"Repository bootstrap refresh did not complete cleanly: {exc}"
        prune_missing_case_roots()
        self.case_root_var = tk.StringVar(value="")
        self.saved_case_var = tk.StringVar(value="")
        self.case_summary_var = tk.StringVar(value="No case corpus selected yet.")
        self.status_var = tk.StringVar(
            value=(
                "Ready. Open Local AI Chat to start the local source-grounded workbench. "
                "The intake wizard stays available, but it does not block startup."
            )
        )
        self.saved_case_lookup: dict[str, Path] = {}
        self._build_ui()
        self._refresh_case_library()
        current_active = active_case_root()
        if current_active is not None:
            self._set_case_root(current_active, "Loaded the last active case corpus for this install.")
        elif self.bootstrap_warning:
            self.status_var.set(self.bootstrap_warning)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        for preferred in ("vista", "clam", "default"):
            try:
                style.theme_use(preferred)
                break
            except tk.TclError:
                continue
        style.configure("App.TFrame", background="#eee8de")
        style.configure("Card.TFrame", background="#fffdf9", relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe", background="#fffdf9", bordercolor="#d7cec0", relief="solid")
        style.configure("Card.TLabelframe.Label", background="#fffdf9", foreground="#24303b", font=("Segoe UI", 10, "bold"))
        style.configure("Body.TLabel", background="#fffdf9", foreground="#24303b")
        style.configure("Muted.TLabel", background="#fffdf9", foreground="#65717b")
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 12))
        style.configure("Action.TButton", padding=(12, 9))
        style.configure("Quiet.TButton", padding=(10, 8))
        style.configure("Status.TLabel", background="#24303b", foreground="#f8fafc", padding=(12, 8))
        style.configure("TNotebook", background="#eee8de", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 9), font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="App.TFrame", padding=12)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        header = tk.Frame(shell, bg="#1f2933", padx=18, pady=12, highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        identity = tk.Frame(header, bg="#1f2933")
        identity.grid(row=0, column=0, sticky="w")
        tk.Label(
            identity,
            text="WE THE PEOPLE",
            bg="#1f2933",
            fg="#75d7e6",
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")
        justice_label = tk.Label(
            identity,
            text="... establish JUSTICE ...",
            bg="#1f2933",
            fg="#ffffff",
            font=("Georgia", 19, "bold"),
            cursor="hand2",
            takefocus=True,
        )
        justice_label.pack(anchor="w")
        mission_popup: tk.Toplevel | None = None

        def hide_mission(_event=None) -> None:
            nonlocal mission_popup
            if mission_popup is not None:
                try:
                    mission_popup.destroy()
                except tk.TclError:
                    pass
                mission_popup = None

        def show_mission(_event=None) -> None:
            nonlocal mission_popup
            if mission_popup is not None and mission_popup.winfo_exists():
                return
            mission_popup = tk.Toplevel(self)
            mission_popup.overrideredirect(True)
            mission_popup.attributes("-topmost", True)
            tk.Label(
                mission_popup,
                text=(
                    "Justice does not belong to one institution or one profession, it belongs to the People "
                    "which these institutions of government are meant to serve; it is Public."
                ),
                bg="#f8f1e5",
                fg="#24303b",
                justify="left",
                wraplength=620,
                padx=12,
                pady=9,
                relief="solid",
                borderwidth=1,
            ).pack()
            mission_popup.update_idletasks()
            x = justice_label.winfo_rootx()
            y = justice_label.winfo_rooty() + justice_label.winfo_height() + 6
            mission_popup.geometry(f"+{x}+{y}")

        def toggle_mission(_event=None) -> str:
            if mission_popup is not None and mission_popup.winfo_exists():
                hide_mission()
            else:
                show_mission()
            return "break"

        justice_label.bind("<Enter>", show_mission)
        justice_label.bind("<Leave>", hide_mission)
        justice_label.bind("<FocusIn>", show_mission)
        justice_label.bind("<FocusOut>", hide_mission)
        justice_label.bind("<Return>", toggle_mission)
        justice_label.bind("<space>", toggle_mission)

        brand = tk.Frame(header, bg="#1f2933")
        brand.grid(row=0, column=1, sticky="e")
        tk.Label(
            brand,
            text=APP_DISPLAY_NAME,
            bg="#1f2933",
            fg="#ffffff",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="e")
        tk.Label(
            brand,
            text=f"v{VERSION} · local-only",
            bg="#1f2933",
            fg="#cbd5df",
            font=("Segoe UI", 9),
        ).pack(anchor="e")

        notebook = ttk.Notebook(shell)
        notebook.grid(row=1, column=0, sticky="nsew")

        start_tab = ttk.Frame(notebook, style="App.TFrame", padding=4)
        review_tab = ttk.Frame(notebook, style="App.TFrame", padding=4)
        support_tab = ttk.Frame(notebook, style="App.TFrame", padding=4)
        notebook.add(start_tab, text="Start here")
        notebook.add(review_tab, text="Review & export")
        notebook.add(support_tab, text="Support & tools")

        for tab in (start_tab, review_tab, support_tab):
            tab.columnconfigure(0, weight=1)

        def action_button(parent: tk.Misc, label: str, method_name: str, *, style_name: str = "Action.TButton") -> ttk.Button:
            button = ttk.Button(parent, text=label, command=getattr(self, method_name), style=style_name)
            self.action_buttons[method_name] = button
            return button

        start_card = ttk.Frame(start_tab, style="Card.TFrame", padding=18)
        start_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        start_card.columnconfigure(0, weight=1)
        ttk.Label(
            start_card,
            text="Start with the conversation",
            style="Body.TLabel",
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            start_card,
            text=(
                "Ask about Maine law, review a private matter, or use both source lanes separately. "
                "You can build or choose a corpus when the records are ready."
            ),
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(5, 12))
        action_button(start_card, "Open Local AI Chat", "open_local_ai_chat", style_name="Primary.TButton").grid(
            row=2, column=0, sticky="ew"
        )

        quick = ttk.LabelFrame(start_tab, text="Matter setup", style="Card.TLabelframe", padding=14)
        quick.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for idx in range(3):
            quick.columnconfigure(idx, weight=1)
        setup_actions = (
            ("Create New Case Corpus", "create_new_case"),
            ("Open Existing Case Corpus", "open_existing_case"),
            ("Reopen Intake / Add More Evidence", "import_more_evidence"),
        )
        for idx, (label, method_name) in enumerate(setup_actions):
            action_button(quick, label, method_name).grid(
                row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 0)
            )
        ttk.Label(
            quick,
            text=(
                "Create a case corpus, reopen it later, and keep adding documents without starting over. "
                "Original source records remain read-only."
            ),
            style="Muted.TLabel",
            wraplength=820,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        library_frame = ttk.LabelFrame(start_tab, text="Installed corpus library", style="Card.TLabelframe", padding=14)
        library_frame.grid(row=2, column=0, sticky="ew")
        library_frame.columnconfigure(0, weight=1)
        ttk.Label(
            library_frame,
            text=(
                "One install can manage multiple families or client matters. Switch the active corpus here before "
                "opening the review portal or asking questions in the local AI chat."
            ),
            style="Muted.TLabel",
            wraplength=820,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        self.saved_case_combo = ttk.Combobox(library_frame, textvariable=self.saved_case_var, state="readonly")
        self.saved_case_combo.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(library_frame, text="Use selected corpus", command=self.activate_selected_saved_case, style="Action.TButton").grid(row=1, column=1, padx=(10, 0), pady=(10, 0), sticky="ew")
        ttk.Button(library_frame, text="Refresh library", command=self._refresh_case_library, style="Quiet.TButton").grid(row=1, column=2, padx=(8, 0), pady=(10, 0), sticky="ew")
        ttk.Button(library_frame, text="Open selected case folder", command=self.open_selected_case_folder, style="Quiet.TButton").grid(row=2, column=1, padx=(10, 0), pady=(8, 0), sticky="ew")
        ttk.Button(library_frame, text="Open workspace folder", command=self._open_workspace_folder, style="Quiet.TButton").grid(row=2, column=2, padx=(8, 0), pady=(8, 0), sticky="ew")
        ttk.Label(library_frame, textvariable=self.case_root_var, style="Muted.TLabel", wraplength=820).grid(row=3, column=0, columnspan=4, sticky="w", pady=(12, 2))
        ttk.Label(library_frame, textvariable=self.case_summary_var, style="Body.TLabel", wraplength=820, justify="left").grid(row=4, column=0, columnspan=4, sticky="w")

        review_intro = ttk.Frame(review_tab, style="Card.TFrame", padding=16)
        review_intro.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(review_intro, text="Review the active matter", style="Body.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(
            review_intro,
            text="These tools use the selected local corpus. Choose the correct matter on Start here before opening a package.",
            style="Muted.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

        review_grid = ttk.LabelFrame(review_tab, text="Review portals and role packages", style="Card.TLabelframe", padding=14)
        review_grid.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for idx in range(2):
            review_grid.columnconfigure(idx, weight=1)
        review_actions = (
            ("Open Review Portal", "open_review_portal"),
            ("Open Search / Indexes", "open_search_indexes"),
            ("Open GAL Package", "open_gal_package"),
            ("Open Court Package", "open_court_package"),
            ("Open Lawyer Package", "open_lawyer_package"),
            ("Open ADA / Prosecutor Package", "open_ada_package"),
            ("Open External Legal-Matter Release", "open_external_release"),
            ("Open Private Forensic Master", "open_private_master"),
        )
        for idx, (label, method_name) in enumerate(review_actions):
            action_button(review_grid, label, method_name).grid(
                row=idx // 2, column=idx % 2, sticky="ew", padx=(0 if idx % 2 == 0 else 8, 0), pady=(0 if idx < 2 else 8, 0)
            )

        proof_grid = ttk.LabelFrame(review_tab, text="Proof and export", style="Card.TLabelframe", padding=14)
        proof_grid.grid(row=2, column=0, sticky="ew")
        for idx in range(3):
            proof_grid.columnconfigure(idx, weight=1)
        for idx, (label, method_name) in enumerate((
            ("Verify Hashes / Proof", "verify_hashes"),
            ("Export to USB", "export_usb"),
            ("Build Neutral Sample Corpus", "build_sample_case"),
        )):
            action_button(proof_grid, label, method_name).grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 8, 0))

        support_card = ttk.LabelFrame(support_tab, text="Support and local runtime", style="Card.TLabelframe", padding=14)
        support_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for idx in range(2):
            support_card.columnconfigure(idx, weight=1)
        support_actions = (
            ("About / Help", "show_about_help"),
            ("Repair / Troubleshoot", "repair_repo"),
            ("Stop Local AI Chat", "stop_local_ai_chat"),
            ("Exit", "destroy"),
        )
        for idx, (label, method_name) in enumerate(support_actions):
            action_button(support_card, label, method_name).grid(
                row=idx // 2, column=idx % 2, sticky="ew", padx=(0 if idx % 2 == 0 else 8, 0), pady=(0 if idx < 2 else 8, 0)
            )
        ttk.Label(
            support_tab,
            text=STORE_MISSION_TAGLINE,
            style="Muted.TLabel",
            wraplength=820,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(4, 0))

        status = ttk.Label(shell, textvariable=self.status_var, style="Status.TLabel", wraplength=980, justify="left")
        status.grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def _set_case_root(self, case_root: Path, status_text: str) -> None:
        self.case_root_var.set(str(case_root))
        set_active_case_root(case_root)
        self._refresh_case_library(selected_case_root=case_root)
        summary = load_case_summary(case_root)
        last_import = str(summary.get("last_import_at", "")).replace("T", " ").replace("Z", " UTC").strip()
        missing_roots = int(summary.get("missing_source_root_count", 0) or 0)
        self.case_summary_var.set(
            " | ".join(
                [
                    f"Case: {summary.get('case_name', case_root.name)}",
                    f"Indexed files: {int(summary.get('total_files_indexed', 0) or 0):,}",
                    f"Legal-matter items: {int(summary.get('legal_matter_items', 0) or 0):,}",
                    f"PDF pages: {int(summary.get('total_pdf_pages', 0) or 0):,}",
                    f"Remembered source roots: {int(summary.get('source_root_count', 0) or 0)}",
                    f"Available now: {int(summary.get('available_source_root_count', 0) or 0)}",
                    f"Missing remembered source paths: {missing_roots}",
                    f"Intake history entries: {int(summary.get('history_count', 0) or 0)}",
                    f"Last intake: {last_import or 'not recorded yet'}",
                ]
            )
        )
        if missing_roots:
            self.status_var.set(f"{status_text} Warning: {missing_roots} remembered source path(s) are currently unavailable.")
        else:
            self.status_var.set(status_text)

    def _refresh_case_library(self, selected_case_root: Path | None = None) -> None:
        entries = list_registered_case_roots()
        self.saved_case_lookup = {}
        display_values: list[str] = []
        for entry in entries:
            label = str(entry["label"])
            counts = []
            if entry.get("indexed_records"):
                counts.append(f"{int(entry['indexed_records']):,} indexed")
            if entry.get("pdf_pages"):
                counts.append(f"{int(entry['pdf_pages']):,} PDF pages")
            suffix = f" ({' | '.join(counts)})" if counts else ""
            display = f"{label}{suffix} - {entry['case_root']}"
            self.saved_case_lookup[display] = Path(str(entry["case_root"]))
            display_values.append(display)
        self.saved_case_combo["values"] = display_values
        if selected_case_root is not None:
            selected = str(selected_case_root.resolve())
            for label, path in self.saved_case_lookup.items():
                if str(path.resolve()) == selected:
                    self.saved_case_var.set(label)
                    break
        elif display_values and not self.saved_case_var.get():
            self.saved_case_var.set(display_values[0])

    def activate_selected_saved_case(self) -> None:
        selected = self.saved_case_var.get().strip()
        if not selected:
            self.status_var.set("No saved corpus is selected yet.")
            return
        case_root = self.saved_case_lookup.get(selected)
        if case_root is None or not case_root.exists():
            self.status_var.set("The selected saved corpus is missing. Refresh the library to prune stale entries.")
            return
        self._set_case_root(case_root, f"Active corpus switched to {case_root}.")

    def open_selected_case_folder(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        os.startfile(str(case_root))
        self.status_var.set(f"Opened selected case folder at {case_root}.")

    def _open_workspace_folder(self) -> None:
        workspace_root = default_workspace_root()
        workspace_root.mkdir(parents=True, exist_ok=True)
        os.startfile(str(workspace_root))
        self.status_var.set(f"Opened workspace folder at {workspace_root}.")

    def _select_output_root(self) -> Path | None:
        selected = filedialog.askdirectory(title="Select Output Folder")
        return Path(selected) if selected else None

    def _show_corpus_build_wizard(
        self,
        *,
        title_text: str,
        instructions: str,
        confirm_text: str,
        default_output_root: Path,
        default_case_name: str,
        existing_source_roots: list[Path] | None = None,
        history_rows: list[dict[str, object]] | None = None,
    ) -> CorpusBuildPlan | None:
        wizard = CorpusBuildWizard(
            self,
            title_text=title_text,
            instructions=instructions,
            confirm_text=confirm_text,
            default_output_root=default_output_root,
            default_case_name=default_case_name,
            existing_source_roots=existing_source_roots,
            history_rows=history_rows,
        )
        self.wait_window(wizard)
        return wizard.result

    def _set_case_build_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for method_name in ("create_new_case", "import_more_evidence"):
            button = self.action_buttons.get(method_name)
            if button is not None:
                button.configure(state=state)

    def _show_background_build_dialog(self, title: str, message: str) -> None:
        self._close_background_build_dialog()
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=message, wraplength=520, justify="left").pack(anchor="w")
        progress = ttk.Progressbar(frame, mode="indeterminate", length=360)
        progress.pack(fill="x", pady=(12, 0))
        progress.start(12)
        ttk.Label(
            frame,
            text="The main window stays open while the build runs in the background.",
            wraplength=520,
            justify="left",
            foreground="#5f6b74",
        ).pack(anchor="w", pady=(10, 0))
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        dialog.update_idletasks()
        x = self.winfo_rootx() + 80
        y = self.winfo_rooty() + 80
        dialog.geometry(f"+{x}+{y}")
        self._build_progress_dialog = dialog

    def _close_background_build_dialog(self) -> None:
        dialog = self._build_progress_dialog
        self._build_progress_dialog = None
        if dialog is not None and dialog.winfo_exists():
            dialog.destroy()

    def _run_case_build_async(
        self,
        *,
        action_label: str,
        progress_message: str,
        worker: Callable[[], object],
        on_success: Callable[[object], None],
    ) -> None:
        if self._case_build_in_progress:
            self.status_var.set("A corpus build is already running. Please wait for it to finish.")
            return
        self._case_build_in_progress = True
        self._set_case_build_controls_enabled(False)
        self.status_var.set(progress_message)
        self._show_background_build_dialog(action_label, progress_message)

        def _finish_success(result: object) -> None:
            self._case_build_in_progress = False
            self._close_background_build_dialog()
            self._set_case_build_controls_enabled(True)
            try:
                on_success(result)
            except Exception as exc:  # pragma: no cover - UI callback safety
                messagebox.showerror(action_label, f"{exc.__class__.__name__}: {exc}", parent=self)
                self.status_var.set(f"{action_label} completed, but follow-up handling failed.")

        def _finish_failure(error_text: str) -> None:
            self._case_build_in_progress = False
            self._close_background_build_dialog()
            self._set_case_build_controls_enabled(True)
            messagebox.showerror(action_label, error_text, parent=self)
            self.status_var.set(f"{action_label} failed.")

        start_background_task(self.after, worker, _finish_success, _finish_failure)

    def create_new_case(self) -> None:
        plan = self._show_corpus_build_wizard(
            title_text="Create New Case Corpus",
            instructions=(
                "Add one or more source folders or files for the case you want to build. "
                "The launcher hashes and inventories the originals read-only, then builds a fresh local case workspace from the combined sources."
            ),
            confirm_text="Build corpus",
            default_output_root=default_case_build_root(),
            default_case_name="",
        )
        if plan is None:
            return

        def _worker() -> object:
            return build_new_case_from_sources(
                repo_root=self.repo_root,
                source_roots=plan.source_roots,
                output_root=plan.output_root,
                case_name=plan.case_name,
            )

        def _on_success(result: object) -> None:
            build_result = result
            append_case_ingest_history(
                build_result.case_root,
                mode="create_new_case",
                case_name=plan.case_name,
                source_roots_added=plan.source_roots,
                cumulative_source_roots=read_case_source_roots(build_result.case_root),
                notes="Initial case build from user-selected source folders and files.",
            )
            self._set_case_root(
                build_result.case_root,
                f"Built case corpus at {build_result.case_root} from {len(plan.source_roots)} source path(s).",
            )

        self._run_case_build_async(
            action_label="Create New Case Corpus",
            progress_message="Building the new case corpus in the background. The launcher will stay responsive.",
            worker=_worker,
            on_success=_on_success,
        )

    def open_existing_case(self) -> None:
        selected = filedialog.askdirectory(title="Open Existing Case Corpus")
        if selected:
            self._set_case_root(Path(selected), "Case corpus selected and made active for this install.")

    def import_more_evidence(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        case_summary = load_case_summary(case_root)
        existing_sources = read_case_source_roots(case_root)
        history_rows = read_case_ingest_history(case_root)
        plan = self._show_corpus_build_wizard(
            title_text="Reopen Intake / Add More Evidence",
            instructions=(
                "Add one or more new source folders or files. The launcher automatically carries forward the source "
                "folders already used for this case, then builds a new expanded case workspace without mutating the older one."
            ),
            confirm_text="Build expanded case",
            default_output_root=case_root.parent,
            default_case_name=f"{case_summary.get('case_name', case_root.name)} expanded",
            existing_source_roots=existing_sources,
            history_rows=history_rows,
        )
        if plan is None:
            return

        def _worker() -> object:
            return import_case_from_sources(
                repo_root=self.repo_root,
                existing_case_root=case_root,
                source_roots=plan.source_roots,
                output_root=plan.output_root,
                case_name=plan.case_name,
            )

        def _on_success(result: object) -> None:
            build_result = result
            cumulative_sources = read_case_source_roots(build_result.case_root)
            inherit_case_ingest_history(
                build_result.case_root,
                existing_case_root=case_root,
                mode="add_more_evidence",
                case_name=plan.case_name,
                source_roots_added=plan.source_roots,
                cumulative_source_roots=cumulative_sources,
                notes="Expanded case build that keeps prior source roots and adds newly selected evidence.",
            )
            self._set_case_root(
                build_result.case_root,
                (
                    f"Built expanded case corpus at {build_result.case_root} from {len(plan.source_roots)} new source path(s). "
                    f"The new case now remembers {len(cumulative_sources)} cumulative source root(s)."
                ),
            )

        self._run_case_build_async(
            action_label="Reopen Intake / Add More Evidence",
            progress_message="Adding the new evidence in the background. The launcher will stay responsive.",
            worker=_worker,
            on_success=_on_success,
        )

    def build_sample_case(self) -> None:
        def _worker() -> object:
            return create_sample_case_build(
                self.repo_root,
                output_root=default_workspace_root() / "sample_cases",
                case_name="Example Family Matter",
            )

        def _on_success(result: object) -> None:
            build_result = result
            append_case_ingest_history(
                build_result.case_root,
                mode="sample_case",
                case_name="Example Family Matter",
                source_roots_added=read_case_source_roots(build_result.case_root),
                cumulative_source_roots=read_case_source_roots(build_result.case_root),
                notes="Neutral sample case for orientation and testing.",
            )
            self._set_case_root(
                build_result.case_root,
                "Built a neutral sample case corpus and refreshed its portal, indexes, and packages.",
            )

        self._run_case_build_async(
            action_label="Build Neutral Sample Corpus",
            progress_message="Building the neutral sample corpus in the background. The launcher will stay responsive.",
            worker=_worker,
            on_success=_on_success,
        )

    def _current_case_root(self) -> Path | None:
        value = self.case_root_var.get().strip()
        return Path(value) if value else None

    def _require_case_root(self) -> Path | None:
        case_root = self._current_case_root()
        if case_root is None or not case_root.exists():
            self.status_var.set("Select or build a case corpus first.")
            return None
        return case_root

    def _open_path(self, path: Path, description: str) -> None:
        if not path.exists():
            self.status_var.set(f"{description} is not available yet at {path}.")
            return
        open_path_or_url(path)
        self.status_var.set(f"Opened {description}.")

    def open_local_ai_chat(self) -> None:
        try:
            service = ensure_local_service(self.runtime)
        except Exception as exc:
            messagebox.showerror(
                "Open Local AI Chat",
                (
                    "The local chat service could not start.\n\n"
                    f"{exc.__class__.__name__}: {exc}\n\n"
                    "Use Repair / Troubleshoot if this repeats, then review the local runtime logs."
                ),
                parent=self,
            )
            self.status_var.set("Local AI chat start failed.")
            return
        open_path_or_url(service.url)
        active = self._current_case_root()
        if active is not None and active.exists():
            self.status_var.set(
                f"Opened Local AI Chat at {service.url} using the active corpus {active.name}."
            )
        else:
            self.status_var.set(
                f"Opened Local AI Chat at {service.url}. No active corpus is selected yet, so sample and general local review tools remain available."
            )

    def stop_local_ai_chat(self) -> None:
        stopped = stop_local_service(self.runtime)
        if stopped:
            self.status_var.set("Stopped the local AI chat service.")
        else:
            self.status_var.set("No running local AI chat service was found for this install.")

    def show_about_help(self) -> None:
        docs_root = self.repo_root / "docs"
        nontechnical_readme = docs_root / "README_FOR_NONTECHNICAL_USERS.html"
        links = local_about_links(self.runtime)
        dialog = tk.Toplevel(self)
        dialog.title("About / Help")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{APP_DISPLAY_NAME} v{VERSION}", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Not legal advice. Review required.\n"
                "This workbench stays local-first, keeps original source records read-only, and is not affiliated with the Maine Judicial Branch, any Maine court, or any government body."
            ),
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(8, 10))
        ttk.Label(
            frame,
            text=(
                "Built for Maine families. Open-sourced so every state can build its own verified, source-grounded edition.\n\n"
                "Forks for other states must replace and validate statutes, rules, forms, case law, citation standards, ontology, freshness checks, evaluation data, and human-review policies."
            ),
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            frame,
            text="\n".join(
                [
                    f"Runtime mode: {self.runtime.mode}",
                    f"Bundle root: {self.runtime.bundle_root}",
                    f"Writable data root: {self.runtime.writable_root}",
                    f"Case library: {self.runtime.case_library_path}",
                    f"Logs: {self.runtime.logs_root}",
                    f"Source code: {GITHUB_REPOSITORY_URL}",
                ]
            ),
            wraplength=560,
            justify="left",
            foreground="#5f6b74",
        ).pack(anchor="w", pady=(0, 12))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Open source code", command=lambda: open_path_or_url(GITHUB_REPOSITORY_URL)).grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="ew")
        ttk.Button(buttons, text="Fork for your state", command=lambda: open_path_or_url(links["fork_guide"])).grid(row=0, column=1, padx=(0, 8), pady=(0, 8), sticky="ew")
        ttk.Button(buttons, text="Privacy policy", command=lambda: open_path_or_url(links["privacy_policy"])).grid(row=0, column=2, pady=(0, 8), sticky="ew")
        ttk.Button(buttons, text="Nontechnical guide", command=lambda: open_path_or_url(nontechnical_readme)).grid(row=1, column=0, padx=(0, 8), sticky="ew")
        ttk.Button(buttons, text="Troubleshooting", command=lambda: open_path_or_url(docs_root / "TROUBLESHOOTING.html")).grid(row=1, column=1, padx=(0, 8), sticky="ew")
        ttk.Button(buttons, text="Close", command=dialog.destroy).grid(row=1, column=2, sticky="e")
        for idx in range(3):
            buttons.columnconfigure(idx, weight=1)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.wait_window(dialog)
        self.status_var.set("Opened About / Help with source, privacy, and state-fork guidance.")

    def open_search_indexes(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        preferred = case_root / "00_START_HERE" / "index.html"
        fallback = case_root / "00_START_HERE" / "search.html"
        self._open_path(preferred if preferred.exists() else fallback, "search and index portal")

    def _open_role_package(self, folder_name: str, description: str) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        self._open_path(case_root / "03_ROLE_PACKAGES" / folder_name / "index.html", description)

    def open_gal_package(self) -> None:
        self._open_role_package("01_GAL_REVIEW_USB", "GAL package")

    def open_court_package(self) -> None:
        self._open_role_package("02_COURT_REVIEW_USB", "court package")

    def open_lawyer_package(self) -> None:
        self._open_role_package("03_LAWYER_INTAKE_USB", "lawyer package")

    def open_ada_package(self) -> None:
        self._open_role_package("04_ADA_PROSECUTOR_CONTEXT_USB", "ADA / prosecutor package")

    def open_external_release(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        self._open_path(case_root / "02_EXTERNAL_LEGAL_MATTER_RELEASE" / "index.html", "external legal-matter release")

    def open_private_master(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        self._open_path(case_root / "01_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY", "private forensic master")

    def open_review_portal(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        preferred = case_root / "00_START_HERE" / "index.html"
        fallback = case_root / "00_START_HERE" / "START_HERE.html"
        self._open_path(preferred if preferred.exists() else fallback, "review portal")

    def verify_hashes(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        proof_path = case_root / "15_PROOF_VALIDATION" / "CASE_BUILD_PROOF.json"
        if not proof_path.exists():
            messagebox.showwarning("Verify Hashes", f"Proof file not found at {proof_path}")
            return
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        messagebox.showinfo(
            "Verify Hashes",
            "\n".join(
                [
                    f"Result: {proof.get('result', 'UNKNOWN')}",
                    f"Source files hashed: {proof.get('source_files_hashed', 0)}",
                    f"Hash verification pass: {proof.get('hash_verification_pass', False)}",
                    f"Source mutation pass: {proof.get('source_mutation_pass', False)}",
                    f"Privacy scan pass: {proof.get('privacy_scan_pass', False)}",
                ]
            ),
        )

    def export_usb(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        destination = self._select_output_root()
        if destination is None:
            return
        export = export_to_usb(case_root, destination / "USB_EXPORT")
        self.status_var.set(f"USB export created at {export['export_root']}")

    def repair_repo(self) -> None:
        if self.runtime.allows_repo_bootstrap_writes:
            bootstrap_repository(self.repo_root)
            self._refresh_case_library()
            self.status_var.set("Repository launchers, docs, and sample assets were refreshed.")
            return
        self.runtime.writable_root.mkdir(parents=True, exist_ok=True)
        self.runtime.logs_root.mkdir(parents=True, exist_ok=True)
        self._refresh_case_library()
        self.status_var.set(
            "Store runtime writable folders and corpus library were refreshed. Installed app files were left untouched."
        )


def main(runtime_context: RuntimeContext | None = None) -> int:
    app = MaineFamilyLawLauncher(runtime_context=runtime_context)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
