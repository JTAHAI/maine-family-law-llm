from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app.wizard_import_corpus import import_additional_corpus
from app.wizard_new_case import default_case_build_root, launch_new_case_wizard, suggest_case_name
from maine_family_law_llm.case_corpus_builder import (
    bootstrap_repository,
    create_sample_case_build,
    export_to_usb,
)
from maine_family_law_llm.case_workspace import (
    append_case_ingest_history,
    default_workspace_root,
    discover_case_roots,
    inherit_case_ingest_history,
    load_active_case,
    load_case_summary,
    read_case_ingest_history,
    read_case_source_roots,
    remember_active_case,
)

ACTION_SPECS = (
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
    ("Repair / Troubleshoot", "repair_repo"),
    ("Exit", "destroy"),
)


@dataclass
class CorpusBuildPlan:
    source_roots: list[Path]
    output_root: Path
    case_name: str


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
        self.import_guide_path = REPO_ROOT / "docs" / "HOW_TO_ADD_YOUR_CORPUS.html"
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
                        "If a drive or folder was moved, reconnect it before rebuilding if you want those files included again."
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
        self.sources_listbox.grid(row=0, column=0, rowspan=5, sticky="nsew")
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
        ttk.Button(sources_buttons, text="Open import guide", command=self._open_import_guide).pack(fill="x", pady=(8, 0))
        ttk.Label(
            sources_buttons,
            text=(
                "Supported inputs: folders, PDFs, screenshots, phone exports, email exports, Word files, "
                "spreadsheets, ZIPs, and scanned batches. The build stays read-only against the originals."
            ),
            wraplength=220,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        sources_frame.columnconfigure(0, weight=1)
        sources_frame.rowconfigure(0, weight=1)

        help_frame = ttk.LabelFrame(frame, text="Common source examples", padding=12)
        help_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            help_frame,
            text=(
                "Gmail or Outlook export folders, downloaded PDF filings, phone photo or screenshot folders, "
                "scanned exhibits, court notices, school records, therapy records, and USB or cloud-export folders "
                "you copied to this computer. If you are starting from email or phone data, use the import guide for "
                "plain-language steps before you build."
            ),
            wraplength=720,
            justify="left",
        ).pack(anchor="w")

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

    def _open_import_guide(self) -> None:
        if self.import_guide_path.exists():
            os.startfile(str(self.import_guide_path))
        else:
            messagebox.showinfo(
                "Import guide unavailable",
                f"Import guide not found at {self.import_guide_path}.",
                parent=self,
            )

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
    def __init__(self) -> None:
        super().__init__()
        self.title("Maine Family Law LLM")
        self.geometry("980x680")
        self.repo_root = REPO_ROOT
        bootstrap_repository(self.repo_root)
        self.case_options: dict[str, Path] = {}
        self.case_selector_var = tk.StringVar(value="")
        self.case_root_var = tk.StringVar(value="")
        self.case_summary_var = tk.StringVar(value="No case corpus selected yet.")
        self.status_var = tk.StringVar(value="Ready. Local-first mode is enabled.")
        self._build_ui()
        self._refresh_known_cases(initial=True)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Maine Family Law Full Record Review System", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Create a case corpus, reopen it later, and keep adding new documents over time. "
                "The launcher remembers prior source folders so users do not have to start over each time."
            ),
            wraplength=860,
        ).pack(anchor="w", pady=(6, 18))

        workspace_frame = ttk.LabelFrame(frame, text="Case workspace", padding=12)
        workspace_frame.pack(fill="x", pady=(0, 18))
        ttk.Label(
            workspace_frame,
            text=(
                "Choose an existing case to reopen the intake wizard later. When you add more evidence, "
                "the build keeps the earlier source folders automatically and adds the new ones on top."
            ),
            wraplength=820,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(workspace_frame, text="Known case corpora").grid(row=1, column=0, sticky="w", pady=(10, 4))
        self.case_selector = ttk.Combobox(workspace_frame, textvariable=self.case_selector_var, state="readonly")
        self.case_selector.grid(row=2, column=0, sticky="ew")
        self.case_selector.bind("<<ComboboxSelected>>", lambda _event: self._activate_selected_case())
        ttk.Button(workspace_frame, text="Use selected case", command=self._activate_selected_case).grid(row=2, column=1, sticky="ew", padx=(10, 0))
        ttk.Button(workspace_frame, text="Refresh case list", command=self._refresh_known_cases).grid(row=2, column=2, sticky="ew", padx=(10, 0))
        ttk.Button(workspace_frame, text="Open workspace folder", command=self._open_workspace_folder).grid(row=2, column=3, sticky="ew", padx=(10, 0))
        ttk.Button(workspace_frame, text="Open selected case folder", command=self._open_selected_case_folder).grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=(10, 0))
        ttk.Button(workspace_frame, text="Open intake guide", command=self._open_import_guide).grid(row=3, column=2, sticky="ew", padx=(10, 0), pady=(10, 0))
        for idx in range(4):
            workspace_frame.columnconfigure(idx, weight=1 if idx == 0 else 0)

        grid = ttk.Frame(frame)
        grid.pack(fill="x")
        for idx, (label, method_name) in enumerate(ACTION_SPECS):
            ttk.Button(grid, text=label, command=getattr(self, method_name)).grid(row=idx // 2, column=idx % 2, sticky="ew", padx=6, pady=6)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        ttk.Label(frame, textvariable=self.case_root_var, foreground="#0b5c7d", wraplength=860).pack(anchor="w", pady=(18, 6))
        ttk.Label(frame, textvariable=self.case_summary_var, wraplength=860, justify="left").pack(anchor="w", pady=(0, 6))
        ttk.Label(frame, textvariable=self.status_var, wraplength=860, justify="left").pack(anchor="w")

    def _format_case_option(self, case_root: Path) -> str:
        summary = load_case_summary(case_root)
        case_name = str(summary.get("case_name", case_root.name))
        legal_items = int(summary.get("legal_matter_items", 0) or 0)
        source_root_count = int(summary.get("source_root_count", 0) or 0)
        return f"{case_name} - {legal_items:,} legal-matter items - {source_root_count} source root(s)"

    def _refresh_known_cases(self, initial: bool = False) -> None:
        discovered = discover_case_roots()
        remembered = load_active_case()
        if remembered and remembered.exists() and remembered not in discovered:
            discovered = [remembered, *discovered]
        self.case_options = {self._format_case_option(path): path for path in discovered}
        values = list(self.case_options.keys())
        self.case_selector["values"] = values
        current = self._current_case_root()
        target = remembered if initial and remembered else current
        if target and target.exists():
            for label, path in self.case_options.items():
                if path == target:
                    self.case_selector_var.set(label)
                    self._activate_case(path, status_message="Case corpus ready.")
                    return
        if values:
            self.case_selector_var.set(values[0])
            if initial:
                self._activate_selected_case(status_message="Loaded first discovered case corpus.")
        elif initial:
            self.case_selector_var.set("")
            self.case_summary_var.set("No case corpora discovered yet. Create one, or open an existing case folder.")

    def _activate_selected_case(self, status_message: str = "Case corpus selected.") -> None:
        label = self.case_selector_var.get().strip()
        case_root = self.case_options.get(label)
        if case_root is not None:
            self._activate_case(case_root, status_message=status_message)

    def _activate_case(self, case_root: Path, *, status_message: str) -> None:
        self.case_root_var.set(str(case_root))
        summary = load_case_summary(case_root)
        last_import = str(summary.get("last_import_at", "")).replace("T", " ").replace("Z", " UTC").strip()
        missing_roots = int(summary.get("missing_source_root_count", 0) or 0)
        self.case_summary_var.set(
            " | ".join(
                [
                    f"Case: {summary.get('case_name', case_root.name)}",
                    f"Indexed files: {int(summary.get('total_files_indexed', 0) or 0):,}",
                    f"Legal-matter items: {int(summary.get('legal_matter_items', 0) or 0):,}",
                    f"Source roots remembered: {int(summary.get('source_root_count', 0) or 0)}",
                    f"Available now: {int(summary.get('available_source_root_count', 0) or 0)}",
                    f"Missing remembered source paths: {missing_roots}",
                    f"Intake history entries: {int(summary.get('history_count', 0) or 0)}",
                    f"Last intake: {last_import or 'not recorded yet'}",
                ]
            )
        )
        remember_active_case(case_root)
        if missing_roots:
            self.status_var.set(
                f"{status_message} Warning: {missing_roots} remembered source path(s) are currently unavailable."
            )
        else:
            self.status_var.set(status_message)

    def _open_workspace_folder(self) -> None:
        workspace_root = default_workspace_root()
        workspace_root.mkdir(parents=True, exist_ok=True)
        os.startfile(str(workspace_root))
        self.status_var.set(f"Opened workspace folder at {workspace_root}.")

    def _open_selected_case_folder(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        os.startfile(str(case_root))
        self.status_var.set(f"Opened selected case folder at {case_root}.")

    def _open_import_guide(self) -> None:
        guide_path = self.repo_root / "docs" / "HOW_TO_ADD_YOUR_CORPUS.html"
        if not guide_path.exists():
            bootstrap_repository(self.repo_root)
        if guide_path.exists():
            os.startfile(str(guide_path))
            self.status_var.set("Opened the corpus intake guide.")
        else:
            self.status_var.set(f"Import guide not available at {guide_path}.")

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

    def create_new_case(self) -> None:
        plan = self._show_corpus_build_wizard(
            title_text="Create New Case Corpus",
            instructions=(
                "Add one or more source folders or files for the case you want to build. "
                "The launcher will hash and inventory the originals read-only, then build a fresh local case workspace "
                "from the combined sources."
            ),
            confirm_text="Build corpus",
            default_output_root=default_case_build_root(),
            default_case_name="",
        )
        if plan is None:
            return
        try:
            result = build_new_case_from_sources(
                repo_root=self.repo_root,
                source_roots=plan.source_roots,
                output_root=plan.output_root,
                case_name=plan.case_name,
            )
        except Exception as exc:
            messagebox.showerror("Create New Case Corpus", str(exc), parent=self)
            self.status_var.set("Create New Case Corpus failed.")
            return
        append_case_ingest_history(
            result.case_root,
            mode="create_new_case",
            case_name=plan.case_name,
            source_roots_added=plan.source_roots,
            cumulative_source_roots=read_case_source_roots(result.case_root),
            notes="Initial case build from user-selected source folders and files.",
        )
        self._refresh_known_cases()
        self._activate_case(
            result.case_root,
            status_message=(
                f"Built case corpus at {result.case_root} from {len(plan.source_roots)} new source path(s). "
                "You can reopen the intake wizard later to add more evidence."
            ),
        )

    def open_existing_case(self) -> None:
        selected = filedialog.askdirectory(title="Open Existing Case Corpus")
        if selected:
            self._activate_case(Path(selected), status_message="Existing case corpus selected.")
            self._refresh_known_cases()

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
        try:
            result = import_case_from_sources(
                repo_root=self.repo_root,
                existing_case_root=case_root,
                source_roots=plan.source_roots,
                output_root=plan.output_root,
                case_name=plan.case_name,
            )
        except Exception as exc:
            messagebox.showerror("Reopen Intake / Add More Evidence", str(exc), parent=self)
            self.status_var.set("Reopen Intake / Add More Evidence failed.")
            return
        cumulative_sources = read_case_source_roots(result.case_root)
        inherit_case_ingest_history(
            result.case_root,
            existing_case_root=case_root,
            mode="add_more_evidence",
            case_name=plan.case_name,
            source_roots_added=plan.source_roots,
            cumulative_source_roots=cumulative_sources,
            notes="Expanded case build that keeps prior source roots and adds newly selected evidence.",
        )
        self._refresh_known_cases()
        self._activate_case(
            result.case_root,
            status_message=(
                f"Built expanded case corpus at {result.case_root} from {len(plan.source_roots)} new source path(s). "
                f"The new case now remembers {len(cumulative_sources)} cumulative source root(s)."
            ),
        )

    def build_sample_case(self) -> None:
        result = create_sample_case_build(self.repo_root)
        append_case_ingest_history(
            result.case_root,
            mode="sample_case",
            case_name="Example Family Matter",
            source_roots_added=read_case_source_roots(result.case_root),
            cumulative_source_roots=read_case_source_roots(result.case_root),
            notes="Neutral sample case for orientation and testing.",
        )
        self._refresh_known_cases()
        self._activate_case(
            result.case_root,
            status_message="Built a neutral sample case corpus and refreshed its portal, indexes, and packages.",
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
        os.startfile(str(path))
        self.status_var.set(f"Opened {description}.")

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
        bootstrap_repository(self.repo_root)
        self._refresh_known_cases()
        self.status_var.set("Repository launchers, docs, and sample assets were refreshed.")


def main() -> int:
    app = MaineFamilyLawLauncher()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
