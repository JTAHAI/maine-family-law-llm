"""Opt-in, one-shot local candidate discovery; never a background importer."""
from __future__ import annotations
from pathlib import Path
from typing import Any

def scan_candidates(folder: Path | str, *, limit: int = 200) -> dict[str, Any]:
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("watch_folder_unavailable")
    rows=[]
    for path in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if len(rows) >= max(1, min(int(limit), 500)): break
        if path.is_file():
            stat=path.stat()
            rows.append({"candidate_id":f"candidate-{len(rows)+1}","display_name":path.name[:240],"extension":path.suffix.casefold()[:20],"size_bytes":stat.st_size,"modified_at":int(stat.st_mtime),"review_required":True})
    return {"status":"pass","candidates":rows,"count":len(rows),"notice":"This is a one-shot local candidate scan. It does not watch in the background, read file contents, copy files, or import records.","review_required":True}
