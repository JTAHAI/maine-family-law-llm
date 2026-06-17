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
from maine_family_law_llm.case_library import active_case_root, list_registered_case_roots, prune_missing_case_roots, set_active_case_root
from maine_family_law_llm.case_corpus_builder import (
    bootstrap_repository,
    create_sample_case_build,
    export_to_usb,
)

ACTION_SPECS = (
    ("Create New Case Corpus", "create_new_case"),
    ("Open Existing Case Corpus", "open_existing_case"),
    ("Import More Evidence", "import_more_evidence"),
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
    ) -> None:
        super().__init__(parent)
        self.title(title_text)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.result: CorpusBuildPlan | None = None
        self.source_roots: list[Path] = []
        self.case_name_var = tk.StringVar(value=default_case_name)
        self.output_root_var = tk.StringVar(value=str(default_output_root))
        self.confirm_text = confirm_text
        self._build_ui(instructions)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build_ui(self, instructions: str) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=instructions, wraplength=760, justify="left").pack(anchor="w")

        sources_frame = ttk.LabelFrame(frame, text="Source folders", padding=12)
        sources_frame.pack(fill="both", expand=True, pady=(14, 12))
        self.sources_listbox = tk.Listbox(sources_frame, height=8)
        self.sources_listbox.grid(row=0, column=0, rowspan=3, sticky="nsew")
        sources_buttons = ttk.Frame(sources_frame)
        sources_buttons.grid(row=0, column=1, sticky="n", padx=(12, 0))
        ttk.Button(sources_buttons, text="Add folder", command=self._add_source_folder).pack(fill="x")
        ttk.Button(sources_buttons, text="Remove selected", command=self._remove_selected_source).pack(fill="x", pady=(8, 0))
        ttk.Label(
            sources_buttons,
            text="Add every folder you want included.\nThe build stays read-only against the originals.",
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
            messagebox.showwarning("Source folders required", "Add at least one source folder before building.", parent=self)
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
        self.geometry("840x560")
        self.repo_root = REPO_ROOT
        bootstrap_repository(self.repo_root)
        prune_missing_case_roots()
        self.case_root_var = tk.StringVar(value="")
        self.saved_case_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready. Local-first mode is enabled.")
        self.saved_case_lookup: dict[str, Path] = {}
        self._build_ui()
        self._refresh_case_library()
        current_active = active_case_root()
        if current_active is not None:
            self._set_case_root(current_active, "Loaded the last active case corpus for this install.")

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Maine Family Law Full Record Review System", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="Create New Case Corpus, open an existing case root, or build a neutral sample case. Advanced details stay hidden unless you open the output folders.",
            wraplength=700,
        ).pack(anchor="w", pady=(6, 18))
        grid = ttk.Frame(frame)
        grid.pack(fill="x")
        for idx, (label, method_name) in enumerate(ACTION_SPECS):
            ttk.Button(grid, text=label, command=getattr(self, method_name)).grid(row=idx // 2, column=idx % 2, sticky="ew", padx=6, pady=6)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        library_frame = ttk.LabelFrame(frame, text="Installed corpus library", padding=12)
        library_frame.pack(fill="x", pady=(16, 0))
        ttk.Label(
            library_frame,
            text="One install can manage multiple families or client matters. Switch the active corpus here before opening the review portal or asking questions in the local workbench.",
            wraplength=700,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        self.saved_case_combo = ttk.Combobox(library_frame, textvariable=self.saved_case_var, state="readonly")
        self.saved_case_combo.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(library_frame, text="Use selected corpus", command=self.activate_selected_saved_case).grid(row=1, column=1, padx=(10, 0), pady=(10, 0), sticky="ew")
        ttk.Button(library_frame, text="Refresh library", command=self._refresh_case_library).grid(row=1, column=2, padx=(10, 0), pady=(10, 0), sticky="ew")
        library_frame.columnconfigure(0, weight=1)
        ttk.Label(frame, textvariable=self.case_root_var, foreground="#0b5c7d").pack(anchor="w", pady=(18, 8))
        ttk.Label(frame, textvariable=self.status_var, wraplength=700).pack(anchor="w")

    def _set_case_root(self, case_root: Path, status_text: str) -> None:
        self.case_root_var.set(str(case_root))
        set_active_case_root(case_root)
        self._refresh_case_library(selected_case_root=case_root)
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
    ) -> CorpusBuildPlan | None:
        wizard = CorpusBuildWizard(
            self,
            title_text=title_text,
            instructions=instructions,
            confirm_text=confirm_text,
            default_output_root=default_output_root,
            default_case_name=default_case_name,
        )
        self.wait_window(wizard)
        return wizard.result

    def create_new_case(self) -> None:
        plan = self._show_corpus_build_wizard(
            title_text="Create New Case Corpus",
            instructions="Add one or more source folders for the case you want to build. The launcher will hash and inventory the originals read-only, then build a fresh local case workspace from the combined sources.",
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
        self._set_case_root(result.case_root, f"Built case corpus at {result.case_root} from {len(plan.source_roots)} source folder(s).")

    def open_existing_case(self) -> None:
        selected = filedialog.askdirectory(title="Open Existing Case Corpus")
        if selected:
            self._set_case_root(Path(selected), "Case corpus selected and made active for this install.")

    def import_more_evidence(self) -> None:
        case_root = self._require_case_root()
        if case_root is None:
            return
        plan = self._show_corpus_build_wizard(
            title_text="Import More Evidence",
            instructions="Add one or more additional source folders. The launcher will build a new expanded case workspace instead of mutating the existing case in place.",
            confirm_text="Build expanded case",
            default_output_root=case_root.parent,
            default_case_name=f"{case_root.name} expanded",
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
            messagebox.showerror("Import More Evidence", str(exc), parent=self)
            self.status_var.set("Import More Evidence failed.")
            return
        self._set_case_root(
            result.case_root,
            f"Built expanded case corpus at {result.case_root} from {len(plan.source_roots)} additional source folder(s).",
        )

    def build_sample_case(self) -> None:
        result = create_sample_case_build(self.repo_root)
        self._set_case_root(result.case_root, "Built a neutral sample case corpus and refreshed its portal, indexes, and packages.")

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
        self._open_path(case_root / "00_START_HERE" / "search.html", "search and index portal")

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
        self._open_path(case_root / "00_START_HERE" / "START_HERE.html", "review portal")

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
        self.status_var.set("Repository launchers, docs, and sample assets were refreshed.")


def main() -> int:
    app = MaineFamilyLawLauncher()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
