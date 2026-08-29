"""Encrypted, source-bound asset tracing assertions; never decides characterization, value, ownership, or division."""
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
class AssetTracingStore:
 schema="maine_family_law_llm.asset_tracing.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"36_FINANCIAL_REVIEW"/"asset-tracing"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("asset_tracing_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"ledgers.json.enc"
 @property
 def lock(self):return self.root/".ledgers.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"rows":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=32*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError("asset_tracing_store_unavailable",409) from e
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("rows",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _records(rows:Iterable[dict]):return {str(x.get("evidence_id") or x.get("source_id") or "").casefold():(str(x.get("evidence_id") or x.get("source_id") or ""),x) for x in rows if isinstance(x,dict)}
 @staticmethod
 def _public(v):
  o=deepcopy(v);o.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"characterization":"not_determined","valuation":"not_determined","ownership":"not_determined","division":"not_determined","notice":"This ledger records reviewer-entered provenance, transfers, valuation-date references, and characterization assertions. It does not determine ownership, marital/nonmarital characterization, value, division, or legal effect."});return o
 def create(self,p,*,records):
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("asset_tracing_confirmation_required",409)
  raw=p.get("assets")
  if not isinstance(raw,list) or not raw or len(raw)>100:raise IntakeWorkbenchError("asset_tracing_assets_invalid")
  available=self._records(records);seen=set();assets=[]
  for x in raw:
   if not isinstance(x,dict):raise IntakeWorkbenchError("asset_tracing_asset_invalid")
   aid=_id(x.get("asset_id"),"asset_tracing_asset_id")
   if aid in seen:raise IntakeWorkbenchError("asset_tracing_asset_duplicate")
   seen.add(aid);refs=x.get("supporting_records")
   if not isinstance(refs,list) or not refs or len(refs)>40:raise IntakeWorkbenchError("asset_tracing_supporting_records_invalid")
   bound=[]
   for source in refs:
    source=dict(source or {});rid=str(source.get("record_id") or "");h=str(source.get("source_hash") or "").casefold();found=available.get(rid.casefold())
    if not rid or not _HASH.fullmatch(h) or found is None or str(found[1].get("source_hash") or found[1].get("sha256") or "").casefold()!=h:raise IntakeWorkbenchError("asset_tracing_source_not_in_active_matter",404)
    bound.append({"record_id":found[0],"source_hash":h,"page":source.get("page")})
   transfers=x.get("transfers") or []
   if not isinstance(transfers,list) or len(transfers)>80:raise IntakeWorkbenchError("asset_tracing_transfers_invalid")
   if any(not isinstance(t,dict) for t in transfers):raise IntakeWorkbenchError("asset_tracing_transfer_invalid")
   assets.append({"asset_id":aid,"label":_text(x.get("label"),"asset_tracing_label",300),"claimed_source":_text(x.get("claimed_source"),"asset_tracing_claimed_source",1000),"valuation_date":_text(x.get("valuation_date"),"asset_tracing_valuation_date",64,False),"transfers":[{"transfer_id":_id(t.get("transfer_id"),"asset_tracing_transfer_id"),"date_candidate":_text(t.get("date_candidate"),"asset_tracing_transfer_date",64,False),"description":_text(t.get("description"),"asset_tracing_transfer_description",1000)} for t in transfers if isinstance(t,dict)],"characterization_assertion":_text(x.get("characterization_assertion"),"asset_tracing_characterization",1000),"characterization_disputed":bool(x.get("characterization_disputed")),"supporting_records":bound,"review_required":True})
  row={"ledger_id":_id(p.get("ledger_id"),"asset_tracing_ledger_id"),"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"assets":assets,"created_at":_now(),"review_required":True,"filing_ready":False};row["ledger_hash"]=_dig({k:v for k,v in row.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get("ledger_id")==row["ledger_id"] for x in state["rows"]):raise IntakeWorkbenchError("asset_tracing_ledger_id_exists",409)
   state["rows"].append(row);e={"event_id":f"asset_trace_{uuid.uuid4().hex}","at":_now(),"action":"asset_tracing_ledger_created","ledger_id":row["ledger_id"],"previous_event_hash":str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "","review_required":True};e["event_hash"]=_dig(e);state["ledger"].append(e);state["revision"]+=1;self._save(state)
  return self._public(row)
 def get(self,ledger_id):
  row=next((x for x in self._load()["rows"] if x.get("ledger_id")==_id(ledger_id,"asset_tracing_ledger_id")),None)
  if row is None:raise IntakeWorkbenchError("asset_tracing_ledger_not_found",404)
  return {"ledger":self._public(row),"review_required":True,"local_only":True}
 def source(self,ledger_id,asset_id,record_id):
  row=self.get(ledger_id)["ledger"];asset=next((x for x in row["assets"] if x.get("asset_id")==_id(asset_id,"asset_tracing_asset_id")),None)
  source=next((x for x in (asset or {}).get("supporting_records",[]) if str(x.get("record_id") or "")==str(record_id or "")),None)
  if source is None:raise IntakeWorkbenchError("asset_tracing_source_not_found",404)
  return {"ledger_id":row["ledger_id"],"asset_id":asset["asset_id"],"source":dict(source),"review_required":True,"filing_ready":False}
