"""Source-bound table-cell lineage for human review."""
from __future__ import annotations
from typing import Any
def table_lineage(*,source_hash:str,cells:list[dict[str,Any]])->dict[str,Any]:
 h=str(source_hash).lower()
 if len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('table_lineage_source_hash_required')
 rows=[]
 for n,c in enumerate(cells[:5000],1):
  if int(c.get('page_number') or 0)<1:raise ValueError('table_lineage_page_required')
  rows.append({'cell_id':str(c.get('cell_id') or f'cell-{n}'),'value':str(c.get('value') or '')[:2000],'page_number':int(c['page_number']),'coordinates':dict(c.get('coordinates') or {}),'ocr_text':str(c.get('ocr_text') or '')[:2000],'review_required':True})
 return {'status':'pass','source_hash':h,'cells':rows,'notice':'Each cell is an extracted, source-bound review item. Corrections must be recorded separately and do not overwrite the original extraction.','review_required':True}
