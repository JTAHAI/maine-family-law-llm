"""Page-quality review from admitted scanner/parser metrics only."""
from __future__ import annotations
from typing import Any
def page_quality_map(*,source_hash:str,pages:list[dict[str,Any]])->dict[str,Any]:
 h=str(source_hash).lower()
 if len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('page_quality_source_hash_required')
 rows=[]
 for n,row in enumerate(pages[:1000],1):
  conf=row.get('ocr_confidence');conf=None if conf is None else max(0.0,min(1.0,float(conf))); flags=[x for x in ('skew','blur','missing_text','parser_fallback') if bool(row.get(x))]
  if conf is not None and conf<.85:flags.append('low_ocr_confidence')
  rows.append({'page_number':int(row.get('page_number') or n),'ocr_confidence':conf,'flags':flags,'review_required':bool(flags)})
 return {'status':'pass','source_hash':h,'pages':rows,'review_page_count':sum(x['review_required'] for x in rows),'notice':'Quality flags reflect supplied parser/OCR/scanner metrics only; they do not replace page-image review or establish document completeness.','review_required':True}
