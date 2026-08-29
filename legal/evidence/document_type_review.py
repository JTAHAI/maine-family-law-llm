"""Explainable review-only document type candidates."""
from __future__ import annotations
from typing import Any
_RULES={'order':('ordered','judgment','decree'),'pleading':('complaint','motion','petition'),'affidavit':('affidavit','sworn'),'correspondence':('dear ','sincerely','email'),'financial_record':('account','balance','statement'),'form':('form ','worksheet'),'exhibit':('exhibit',)}
def classify_document(*,source_hash:str,text_excerpt:str)->dict[str,Any]:
 h=str(source_hash).lower()
 if len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('document_type_source_hash_required')
 t=str(text_excerpt or '').casefold(); hits=[k for k,v in _RULES.items() if any(x in t for x in v)]
 return {'status':'pass','source_hash':h,'candidate_types':hits or ['unknown'],'signals':hits,'notice':'Type labels are review candidates based on visible text signals. They do not alter record metadata, establish authenticity, or determine legal effect.','review_required':True}
