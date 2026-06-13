from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from maine_family_law_llm.case_corpus_builder import (
    bootstrap_repository,
    build_case_corpus,
    create_sample_case_build,
    export_to_usb,
)


class MaineFamilyLawLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Maine Family Law LLM")
        self.geometry("760x520")
        self.repo_root = REPO_ROOT
        bootstrap_repository(self.repo_root)
        self.case_root_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready. Local-first mode is enabled.")
        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Maine Family Law Full Record Review System", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="Create New Case Corpus, open an existing case root, or build a neutral sample case. Advanced details stay hidden unless you open the output folders.",
            wraplength=700,
        ).pack(anchor="w", pady=(6, 18))
        buttons = (
            ("Create New Case Corpus", self.create_new_case),
            ("Open Existing Case Corpus", self.open_existing_case),
            ("Import More Evidence", self.import_more_evidence),
            ("Build / Rebuild Search Index", self.rebuild_index),
            ("Build GAL Package", self.rebuild_index),
            ("Build Court Package", self.rebuild_index),
            ("Build Lawyer Package", self.rebuild_index),
            ("Build ADA / Prosecutor Package", self.rebuild_index),
            ("Build Full External Legal-Matter Release", self.rebuild_index),
            ("Build Private Forensic Master", self.rebuild_index),
            ("Verify Hashes", self.verify_hashes),
            ("Open Review Portal", self.open_existing_case),
            ("Export to USB", self.export_usb),
            ("Repair / Troubleshoot", self.repair_repo),
            ("Exit", self.destroy),
        )
        grid = ttk.Frame(frame)
        grid.pack(fill="x")
        for idx, (label, command) in enumerate(buttons):
            ttk.Button(grid, text=label, command=command).grid(row=idx // 2, column=idx % 2, sticky="ew", padx=6, pady=6)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        ttk.Label(frame, textvariable=self.case_root_var, foreground="#0b5c7d").pack(anchor="w", pady=(18, 8))
        ttk.Label(frame, textvariable=self.status_var, wraplength=700).pack(anchor="w")

    def _select_output_root(self) -> Path | None:
        selected = filedialog.askdirectory(title="Select Output Folder")
        return Path(selected) if selected else None

    def create_new_case(self) -> None:
        source = filedialog.askdirectory(title="Select Source Folder")
        output_root = self._select_output_root()
        if not source or output_root is None:
            return
        result = build_case_corpus(
            repo_root=self.repo_root,
            source_roots=[Path(source)],
            output_root=output_root,
            case_name="Imported Family Matter",
        )
        self.case_root_var.set(str(result.case_root))
        self.status_var.set(f"Built case corpus at {result.case_root}")

    def open_existing_case(self) -> None:
        selected = filedialog.askdirectory(title="Open Existing Case Corpus")
        if selected:
            self.case_root_var.set(selected)
            self.status_var.set("Case corpus selected.")

    def import_more_evidence(self) -> None:
        self.status_var.set("Use Create New Case Corpus with the same output folder to import more evidence safely.")

    def rebuild_index(self) -> None:
        result = create_sample_case_build(self.repo_root)
        self.case_root_var.set(str(result.case_root))
        self.status_var.set("Built a local sample case corpus and refreshed indexes.")

    def verify_hashes(self) -> None:
        messagebox.showinfo("Verify Hashes", "Hash verification is run as part of every build and sample build.")

    def export_usb(self) -> None:
        if not self.case_root_var.get():
            self.status_var.set("Select or build a case corpus first.")
            return
        destination = self._select_output_root()
        if destination is None:
            return
        export = export_to_usb(Path(self.case_root_var.get()), destination / "USB_EXPORT")
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
