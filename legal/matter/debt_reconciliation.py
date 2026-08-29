"""Encrypted source-bound debt statement reconciliation; never decides a debt, balance, responsibility, or payment."""
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
def _text(v,n,l=2000,required=True):
 x=" ".join(str(v or "").replace("\x00","").split())
 if required and not x:raise IntakeWorkbenchError(f"{n}_required")
 if len(x)>l:raise IntakeWorkbenchError(f"{n}_too_long")
 return x
class DebtReconciliationStore:
 schema="maine_family_law_llm.debt_reconciliation.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"36_FINANCIAL_REVIEW"/"debt-reconciliation"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("debt_reconciliation_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"workspaces.json.enc"
 @property
 def lock(self):return self.root/".workspaces.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"rows":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=24*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError("debt_reconciliation_store_unavailable",409) from e
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("rows",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _records(rows:Iterable[dict]):return {str(x.get("evidence_id") or x.get("source_id") or "").casefold():(str(x.get("evidence_id") or x.get("source_id") or ""),x) for x in rows if isinstance(x,dict)}
 @staticmethod
 def _public(v):
  o=deepcopy(v);o.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"balance":"not_determined","responsibility":"not_determined","payment_status":"not_determined","notice":"This compares reviewer-entered statement, balance, responsibility, payment, and missing-period information. It does not determine that a debt exists, a balance, responsibility, payment, validity, or legal effect."});return o
 def create(self,p,*,records):
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("debt_reconciliation_confirmation_required",409)
  raw=p.get("statements")
  if not isinstance(raw,list) or not raw or len(raw)>120:raise IntakeWorkbenchError("debt_reconciliation_statements_invalid")
  available=self._records(records);seen=set();rows=[]
  for x in raw:
   if not isinstance(x,dict):raise IntakeWorkbenchError("debt_reconciliation_statement_invalid")
   sid=_id(x.get("statement_id"),"debt_reconciliation_statement_id");account=_id(x.get("account_key"),"debt_reconciliation_account_key")
   if sid in seen:raise IntakeWorkbenchError("debt_reconciliation_statement_duplicate")
   seen.add(sid);source=dict(x.get("source_ref") or {});rid=str(source.get("record_id") or "");h=str(source.get("source_hash") or "").casefold();found=available.get(rid.casefold())
   if not rid or not _HASH.fullmatch(h) or found is None or str(found[1].get("source_hash") or found[1].get("sha256") or "").casefold()!=h:raise IntakeWorkbenchError("debt_reconciliation_source_not_in_active_matter",404)
   rows.append({"statement_id":sid,"account_key":account,"creditor_label":_text(x.get("creditor_label"),"debt_reconciliation_creditor",300),"period_label":_text(x.get("period_label"),"debt_reconciliation_period",128),"reported_balance":_text(x.get("reported_balance"),"debt_reconciliation_balance",500,False),"responsibility_assertion":_text(x.get("responsibility_assertion"),"debt_reconciliation_responsibility",1000,False),"payment_note":_text(x.get("payment_note"),"debt_reconciliation_payment",1000,False),"missing_period":bool(x.get("missing_period")),"source_ref":{"record_id":found[0],"source_hash":h,"page":source.get("page")},"review_required":True})
  by={}
  for row in rows:by.setdefault(row["account_key"],[]).append(row)
  conflicts=[{"account_key":key,"statement_ids":[x["statement_id"] for x in group],"reported_balances":sorted({x["reported_balance"] for x in group}),"missing_period":any(x["missing_period"] for x in group),"status":"review_required"} for key,group in by.items() if len({x["reported_balance"] for x in group})>1 or any(x["missing_period"] for x in group)]
  row={"workspace_id":_id(p.get("workspace_id"),"debt_reconciliation_workspace_id"),"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"statements":rows,"conflicts_or_gaps":conflicts,"created_at":_now(),"review_required":True,"filing_ready":False};row["workspace_hash"]=_dig({k:v for k,v in row.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get("workspace_id")==row["workspace_id"] for x in state["rows"]):raise IntakeWorkbenchError("debt_reconciliation_workspace_id_exists",409)
   state["rows"].append(row);e={"event_id":f"debt_reconciliation_{uuid.uuid4().hex}","at":_now(),"action":"debt_reconciliation_workspace_created","workspace_id":row["workspace_id"],"previous_event_hash":str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "","review_required":True};e["event_hash"]=_dig(e);state["ledger"].append(e);state["revision"]+=1;self._save(state)
  return self._public(row)
 def get(self,workspace_id):
  row=next((x for x in self._load()["rows"] if x.get("workspace_id")==_id(workspace_id,"debt_reconciliation_workspace_id")),None)
  if row is None:raise IntakeWorkbenchError("debt_reconciliation_workspace_not_found",404)
  return {"workspace":self._public(row),"review_required":True,"local_only":True}
 def source(self,workspace_id,statement_id):
  row=self.get(workspace_id)["workspace"];item=next((x for x in row["statements"] if x.get("statement_id")==_id(statement_id,"debt_reconciliation_statement_id")),None)
  if item is None:raise IntakeWorkbenchError("debt_reconciliation_statement_not_found",404)
  return {"workspace_id":row["workspace_id"],"statement_id":item["statement_id"],"source":dict(item["source_ref"]),"review_required":True,"filing_ready":False}
