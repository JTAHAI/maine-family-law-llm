"""Review-only scanner profile planning; transformations require later approval."""
from __future__ import annotations
import hashlib
from typing import Any

def scanner_review_plan(*, original_sha256: str, page_count: int, duplex: bool=False, blank_pages: list[int]|None=None, rotations: dict[int,int]|None=None) -> dict[str,Any]:
    digest=str(original_sha256).lower()
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest): raise ValueError('scanner_original_hash_required')
    pages=max(0,int(page_count)); blanks=sorted({int(x) for x in (blank_pages or []) if 1<=int(x)<=pages}); turns={str(int(k)):int(v) for k,v in (rotations or {}).items() if 1<=int(k)<=pages and int(v) in {90,180,270}}
    return {'status':'pass','original_sha256':digest,'page_count':pages,'profile':{'duplex':bool(duplex),'blank_page_candidates':blanks,'rotation_candidates':turns},'derivative_id':'scan-'+hashlib.sha256((digest+str(pages)).encode()).hexdigest()[:16],'notice':'This is a review proposal. The original scan remains immutable; blank-page removal, rotation, cleanup, and OCR require explicit later approval.','review_required':True}
