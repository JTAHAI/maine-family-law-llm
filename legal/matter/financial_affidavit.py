"""Encrypted source-bound financial-affidavit preparation; never creates sworn conclusions or calculations."""
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
_ID=re.compile(r"[a-z][a-z0-9_-]{2,79}\Z");_HASH=re.compile(r"[a-f0-9]{64}\Z");_CATS={"income","expense","asset","debt","unknown"}
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def _id(v,n):
 x=str(v or "").strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f"{n}_invalid")
 return x
def _text(v,n,l=4000,required=True):
 x=" ".join(str(v or "").replace("\x00","").split())
 if required and not x:raise IntakeWorkbenchError(f"{n}_required")
 if len(x)>l:raise IntakeWorkbenchError(f"{n}_too_long")
 return x
class FinancialAffidavitStore:
 schema="maine_family_law_llm.financial_affidavit.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"36_FINANCIAL_REVIEW"/"affidavit-workspaces"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("financial_affidavit_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"workspaces.json.enc"
 @property
 def lock(self):return self.root/".workspaces.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"rows":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=32*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError("financial_affidavit_store_unavailable",409) from e
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("rows",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _records(rows:Iterable[dict]):return {str(x.get("evidence_id") or x.get("source_id") or "").casefold():(str(x.get("evidence_id") or x.get("source_id") or ""),x) for x in rows if isinstance(x,dict)}
 @staticmethod
 def _public(v):
  o=deepcopy(v);o.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"affidavit_completion":"not_available","totals":"not_calculated","notice":"This organizes source-bound financial rows and flags reviewer-visible mismatches. It does not calculate totals, determine income or value, reconcile a debt, create an affidavit, or make a sworn or filing-ready conclusion."});return o
 def create(self,p,*,records):
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("financial_affidavit_confirmation_required",409)
  raw=p.get("entries")
  if not isinstance(raw,list) or not raw or len(raw)>150:raise IntakeWorkbenchError("financial_affidavit_entries_invalid")
  available=self._records(records);seen=set();entries=[]
  for x in raw:
   if not isinstance(x,dict):raise IntakeWorkbenchError("financial_affidavit_entry_invalid")
   eid=_id(x.get("entry_id"),"financial_affidavit_entry_id");cat=str(x.get("category") or "unknown").casefold();key=_id(x.get("reconciliation_key"),"financial_affidavit_reconciliation_key")
   if eid in seen or cat not in _CATS:raise IntakeWorkbenchError("financial_affidavit_entry_id_or_category_invalid")
   seen.add(eid);source=dict(x.get("source_ref") or {});rid=str(source.get("record_id") or "");h=str(source.get("source_hash") or "").casefold();found=available.get(rid.casefold())
   if not rid or not _HASH.fullmatch(h) or found is None or str(found[1].get("source_hash") or found[1].get("sha256") or "").casefold()!=h:raise IntakeWorkbenchError("financial_affidavit_source_not_in_active_matter",404)
   entries.append({"entry_id":eid,"category":cat,"label":_text(x.get("label"),"financial_affidavit_label",300),"reported_value":_text(x.get("reported_value"),"financial_affidavit_reported_value",500,False),"reconciliation_key":key,"source_ref":{"record_id":found[0],"source_hash":h,"page":source.get("page")},"state":"source_bound_review_required"})
  groups={}
  for entry in entries:groups.setdefault(entry["reconciliation_key"],[]).append(entry)
  mismatches=[{"reconciliation_key":k,"entry_ids":[x["entry_id"] for x in rows],"reported_values":sorted({x["reported_value"] for x in rows}),"status":"review_required"} for k,rows in groups.items() if len({x["reported_value"] for x in rows})>1]
  unknowns=p.get("unknowns") or []
  if not isinstance(unknowns,list) or len(unknowns)>60:raise IntakeWorkbenchError("financial_affidavit_unknowns_invalid")
  row={"workspace_id":_id(p.get("workspace_id"),"financial_affidavit_workspace_id"),"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"entries":entries,"reconciliation_mismatches":mismatches,"unknowns":[_text(x,"financial_affidavit_unknown",500) for x in unknowns],"created_at":_now(),"review_required":True,"filing_ready":False};row["workspace_hash"]=_dig({k:v for k,v in row.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get("workspace_id")==row["workspace_id"] for x in state["rows"]):raise IntakeWorkbenchError("financial_affidavit_workspace_id_exists",409)
   state["rows"].append(row);e={"event_id":f"financial_affidavit_{uuid.uuid4().hex}","at":_now(),"action":"financial_affidavit_workspace_created","workspace_id":row["workspace_id"],"previous_event_hash":str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "","review_required":True};e["event_hash"]=_dig(e);state["ledger"].append(e);state["revision"]+=1;self._save(state)
  return self._public(row)
 def get(self,workspace_id):
  row=next((x for x in self._load()["rows"] if x.get("workspace_id")==_id(workspace_id,"financial_affidavit_workspace_id")),None)
  if row is None:raise IntakeWorkbenchError("financial_affidavit_workspace_not_found",404)
  return {"workspace":self._public(row),"review_required":True,"local_only":True}
 def source(self,workspace_id,entry_id):
  row=self.get(workspace_id)["workspace"];entry=next((x for x in row["entries"] if x.get("entry_id")==_id(entry_id,"financial_affidavit_entry_id")),None)
  if entry is None:raise IntakeWorkbenchError("financial_affidavit_entry_not_found",404)
  return {"workspace_id":row["workspace_id"],"entry_id":entry["entry_id"],"source":dict(entry["source_ref"]),"review_required":True,"filing_ready":False}
