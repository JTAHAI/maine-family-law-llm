"""Encrypted, review-only local calendar candidates from confirmed exact order terms."""
from __future__ import annotations

import hashlib,json,os,re,uuid
from copy import deepcopy
from datetime import UTC,datetime
from pathlib import Path
from typing import Any,Iterable

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID=re.compile(r"[a-z][a-z0-9_-]{2,79}\Z");_HASH=re.compile(r"[a-f0-9]{64}\Z")
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def _id(v,n):
 x=str(v or "").strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f"{n}_invalid")
 return x
def _text(v,n,l=1000):
 x=" ".join(str(v or "").replace("\x00","").split())
 if not x:raise IntakeWorkbenchError(f"{n}_required")
 if len(x)>l:raise IntakeWorkbenchError(f"{n}_too_long")
 return x

class OrderCalendarExtractionStore:
 schema="maine_family_law_llm.order_calendar_extraction.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"22_CALENDAR_REVIEW"/"order-term-extractions"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("order_calendar_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"extractions.json.enc"
 @property
 def lock(self):return self.root/".extractions.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"rows":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError("order_calendar_store_unavailable",409) from e
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("rows",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _records(rows:Iterable[dict])->dict:
  return {str(x.get("evidence_id") or x.get("source_id") or "").casefold():(str(x.get("evidence_id") or x.get("source_id") or ""),x) for x in rows if isinstance(x,dict)}
 @staticmethod
 def _public(row):
  out=deepcopy(row);out.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"calendar_account_write":False,"notice":"This is a reviewer-confirmed local calendar candidate from an exact order term. It does not decide that the order governs, interpret the term, notify anyone, or write an external calendar."});return out
 def create(self,p:dict,*,terms:Iterable[dict],records:Iterable[dict]):
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("order_calendar_confirmation_required",409)
  extraction_id=_id(p.get("extraction_id"),"order_calendar_extraction_id");term_id=_id(p.get("term_id"),"term_id")
  term=next((dict(x) for x in terms if isinstance(x,dict) and str(x.get("term_id") or "")==term_id),None)
  if term is None:raise IntakeWorkbenchError("order_calendar_term_not_found",404)
  review=dict(term.get("operative_candidate_review") or {})
  if review.get("confirmed") is not True or review.get("status")!="reviewer_confirmed_candidate":raise IntakeWorkbenchError("order_calendar_confirmed_term_required",409)
  source=dict(term.get("source_ref") or {});record_id=str(source.get("record_id") or "");source_hash=str(source.get("source_hash") or "").casefold();found=self._records(records).get(record_id.casefold())
  if not record_id or not _HASH.fullmatch(source_hash) or found is None or str(found[1].get("source_hash") or found[1].get("sha256") or "").casefold()!=source_hash:raise IntakeWorkbenchError("order_calendar_source_not_in_active_matter",404)
  canonical_record_id,record=found
  row={"extraction_id":extraction_id,"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"term_id":term_id,"order_id":_id(term.get("order_id"),"order_id"),"exact_language":_text(term.get("exact_language"),"order_calendar_exact_language",20000),"subject":str(term.get("subject") or "other"),"source_ref":{"record_id":canonical_record_id,"source_hash":source_hash,"page":source.get("page")},"candidate_event":{"event_id":f"order_term_{uuid.uuid4().hex}","date_candidate":_text(p.get("date_candidate"),"order_calendar_date",64),"label":_text(p.get("label"),"order_calendar_label",300),"kind":"court_ordered_date","calendar_account_write":False,"review_required":True},"term_reviewer_confirmation":{"reviewer_safe_id":str(review.get("reviewer_safe_id") or ""),"reviewed_at":str(review.get("reviewed_at") or "")},"created_at":_now(),"review_required":True,"filing_ready":False}
  row["extraction_hash"]=_dig({k:v for k,v in row.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get("extraction_id")==extraction_id for x in state["rows"]):raise IntakeWorkbenchError("order_calendar_extraction_id_exists",409)
   state["rows"].append(row);event={"event_id":f"order_calendar_{uuid.uuid4().hex}","at":_now(),"action":"order_term_calendar_candidate_created","extraction_id":extraction_id,"term_id":term_id,"previous_event_hash":str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "","review_required":True};event["event_hash"]=_dig(event);state["ledger"].append(event);state["revision"]+=1;self._save(state)
  return self._public(row)
 def get(self,extraction_id):
  row=next((x for x in self._load()["rows"] if x.get("extraction_id")==_id(extraction_id,"order_calendar_extraction_id")),None)
  if row is None:raise IntakeWorkbenchError("order_calendar_extraction_not_found",404)
  return {"extraction":self._public(row),"review_required":True,"local_only":True}
 def source(self,extraction_id):
  row=self.get(extraction_id)["extraction"]
  return {"extraction_id":row["extraction_id"],"source":dict(row["source_ref"]),"review_required":True,"filing_ready":False}
