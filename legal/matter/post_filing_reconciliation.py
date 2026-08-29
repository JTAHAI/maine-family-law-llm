"""Encrypted, review-only reconciliation of a user-provided filing receipt."""
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
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _id(v,n):
 x=str(v or "").strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f"{n}_invalid")
 return x
def _text(v,n,l=1000):
 x=" ".join(str(v or "").replace("\x00","").split())
 if not x:raise IntakeWorkbenchError(f"{n}_required")
 if len(x)>l:raise IntakeWorkbenchError(f"{n}_too_long")
 return x
class PostFilingReconciliationStore:
 schema="maine_family_law_llm.post_filing_reconciliation.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"23_DOCKET_RECONCILIATION"/"post-filing"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("post_filing_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"reconciliations.json.enc"
 @property
 def lock(self):return self.root/".reconciliations.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"rows":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=16*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError("post_filing_store_unavailable",409) from e
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("rows",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _records(rows:Iterable[dict])->dict:
  return {str(r.get("evidence_id") or r.get("source_id") or ""):r for r in rows if isinstance(r,dict) and _HASH.fullmatch(str(r.get("source_hash") or r.get("sha256") or "").casefold())}
 @staticmethod
 def _pub(v):
  r=deepcopy(v);r.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"court_receipt_confirmed":False,"notice":"This compares a user-provided receipt and local records. It does not confirm court acceptance, docket entry, submission, or filing readiness."});return r
 def create(self,p:dict,*,records:Iterable[dict]):
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("post_filing_confirmation_required",409)
  rid=_id(p.get("reconciliation_id"),"post_filing_reconciliation_id");rs=self._records(records);receipt=p.get("receipt_source") or {};receipt_id=_text(receipt.get("record_id"),"post_filing_receipt_record_id",160);receipt_hash=str(receipt.get("source_hash") or "").casefold()
  if not _HASH.fullmatch(receipt_hash) or receipt_id not in rs or str(rs[receipt_id].get("source_hash") or rs[receipt_id].get("sha256") or "").casefold()!=receipt_hash:raise IntakeWorkbenchError("post_filing_receipt_not_in_active_matter",404)
  raw_items=p.get("submitted_items");raw_expect=p.get("docket_expectations")
  if not isinstance(raw_items,list) or not raw_items or len(raw_items)>100 or not isinstance(raw_expect,list) or len(raw_expect)>100:raise IntakeWorkbenchError("post_filing_rows_invalid")
  items=[]
  for x in raw_items:
   record_id=_text(x.get("record_id"),"post_filing_item_record_id",160);h=str(x.get("source_hash") or "").casefold()
   if record_id not in rs or not _HASH.fullmatch(h) or str(rs[record_id].get("source_hash") or rs[record_id].get("sha256") or "").casefold()!=h:raise IntakeWorkbenchError("post_filing_item_not_in_active_matter",404)
   items.append({"record_id":record_id,"source_hash":h,"submitted_filename":_text(x.get("submitted_filename"),"post_filing_filename",300),"lane":"private_matter_record"})
  ex=[{"expectation_id":_id(x.get("expectation_id"),"post_filing_expectation_id"),"expected_filename":_text(x.get("expected_filename"),"post_filing_expected_filename",300),"expected_hash":str(x.get("expected_hash") or "").casefold()} for x in raw_expect]
  decisions=[]
  for item in items:
   best=next((x for x in ex if x["expected_hash"] and x["expected_hash"]==item["source_hash"]),None) or next((x for x in ex if x["expected_filename"].casefold()==item["submitted_filename"].casefold()),None)
   decisions.append({"record_id":item["record_id"],"expectation_id":str((best or {}).get("expectation_id") or ""),"status":"exact_match" if best and best["expected_hash"]==item["source_hash"] and best["expected_filename"].casefold()==item["submitted_filename"].casefold() else ("partial_match" if best else "unmatched"),"review_required":True})
  e={"reconciliation_id":rid,"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"receipt_source":{"record_id":receipt_id,"source_hash":receipt_hash,"lane":"private_matter_record"},"submitted_items":items,"docket_expectations":ex,"decisions":decisions,"created_at":_now(),"review_required":True,"filing_ready":False};e["receipt_hash"]=_dig({k:v for k,v in e.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   s=self._load()
   if any(x.get("reconciliation_id")==rid for x in s["rows"]):raise IntakeWorkbenchError("post_filing_reconciliation_id_already_exists",409)
   s["rows"].append(e);event={"event_id":f"post_filing_{uuid.uuid4().hex}","at":_now(),"action":"create_post_filing_reconciliation","reconciliation_id":rid,"previous_event_hash":str(s["ledger"][-1].get("event_hash") or "") if s["ledger"] else "","review_required":True};event["event_hash"]=_dig(event);s["ledger"].append(event);s["revision"]=int(s.get("revision") or 0)+1;self._save(s)
  return self._pub(e)
 def get(self,rid):
  x=next((self._pub(x) for x in self._load()["rows"] if x.get("reconciliation_id")==_id(rid,"post_filing_reconciliation_id")),None)
  if x is None:raise IntakeWorkbenchError("post_filing_reconciliation_not_found",404)
  return {"reconciliation":x,"review_required":True,"local_only":True}
 def source(self,rid,record_id):
  row=self.get(rid)["reconciliation"];record_id=_text(record_id,"post_filing_source_record_id",160)
  source=row["receipt_source"] if row["receipt_source"].get("record_id")==record_id else next((x for x in row["submitted_items"] if x.get("record_id")==record_id),None)
  if source is None:raise IntakeWorkbenchError("post_filing_source_not_found",404)
  return {"reconciliation_id":row["reconciliation_id"],"source":source,"review_required":True}
