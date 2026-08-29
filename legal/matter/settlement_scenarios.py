"""Encrypted, source-bound comparison of user-entered settlement scenarios; never recommends, approves, or predicts outcomes."""
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
_ID=re.compile(r"[a-z][a-z0-9_-]{2,79}\Z");_HASH=re.compile(r"[a-f0-9]{64}\Z");_AREAS=("schedules","property","support","implementation","unresolved_terms")
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def _id(v,n):
 x=str(v or "").strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f"{n}_invalid")
 return x
def _txt(v,n,l=2000):
 x=" ".join(str(v or "").replace("\x00","").split())
 if not x:raise IntakeWorkbenchError(f"{n}_required")
 if len(x)>l:raise IntakeWorkbenchError(f"{n}_too_long")
 return x
class SettlementScenarioStore:
 schema="maine_family_law_llm.settlement_scenarios.v1"
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(root).resolve();self.root=self.case_root/"35_NEGOTIATION"/"settlement-scenarios"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("settlement_scenario_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"comparisons.json.enc"
 @property
 def lock(self):return self.root/".comparisons.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"rows":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=16*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError("settlement_scenario_store_unavailable",409) from e
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("rows",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _records(rows:Iterable[dict]):return {str(x.get("evidence_id") or x.get("source_id") or "").casefold():(str(x.get("evidence_id") or x.get("source_id") or ""),x) for x in rows if isinstance(x,dict)}
 @staticmethod
 def _pub(v):
  o=deepcopy(v);o.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"recommendation":"not_available","agreement_approval":"not_available","notice":"This compares user-entered scenarios and unresolved terms. It does not recommend, approve, interpret, enforce, or predict any agreement or outcome."});return o
 def create(self,p,*,records):
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("settlement_scenario_confirmation_required",409)
  raw=p.get("scenarios")
  if not isinstance(raw,list) or len(raw)!=2:raise IntakeWorkbenchError("settlement_scenarios_exactly_two_required")
  available=self._records(records);scenarios=[];seen=set()
  for x in raw:
   if not isinstance(x,dict):raise IntakeWorkbenchError("settlement_scenario_invalid")
   sid=_id(x.get("scenario_id"),"settlement_scenario_id")
   if sid in seen:raise IntakeWorkbenchError("settlement_scenario_duplicate")
   seen.add(sid);source=dict(x.get("source_ref") or {});rid=str(source.get("record_id") or "");h=str(source.get("source_hash") or "").casefold();found=available.get(rid.casefold())
   if not rid or not _HASH.fullmatch(h) or found is None or str(found[1].get("source_hash") or found[1].get("sha256") or "").casefold()!=h:raise IntakeWorkbenchError("settlement_scenario_source_not_in_active_matter",404)
   areas={}
   for area in _AREAS:
    rows=x.get(area) or []
    if not isinstance(rows,list) or len(rows)>40:raise IntakeWorkbenchError("settlement_scenario_area_invalid")
    areas[area]=[_txt(row,"settlement_scenario_term",1000) for row in rows]
   scenarios.append({"scenario_id":sid,"label":_txt(x.get("label"),"settlement_scenario_label",300),**areas,"source_ref":{"record_id":found[0],"source_hash":h,"page":source.get("page")}})
  differing=[area for area in _AREAS if scenarios[0][area]!=scenarios[1][area]]
  row={"comparison_id":_id(p.get("comparison_id"),"settlement_comparison_id"),"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"scenarios":scenarios,"different_areas":differing,"unresolved_terms":sorted(set(scenarios[0]["unresolved_terms"]+scenarios[1]["unresolved_terms"])),"created_at":_now(),"review_required":True,"filing_ready":False};row["comparison_hash"]=_dig({k:v for k,v in row.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get("comparison_id")==row["comparison_id"] for x in state["rows"]):raise IntakeWorkbenchError("settlement_comparison_id_exists",409)
   state["rows"].append(row);e={"event_id":f"settlement_{uuid.uuid4().hex}","at":_now(),"action":"settlement_scenario_comparison_created","comparison_id":row["comparison_id"],"previous_event_hash":str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "","review_required":True};e["event_hash"]=_dig(e);state["ledger"].append(e);state["revision"]+=1;self._save(state)
  return self._pub(row)
 def get(self,cid):
  row=next((x for x in self._load()["rows"] if x.get("comparison_id")==_id(cid,"settlement_comparison_id")),None)
  if row is None:raise IntakeWorkbenchError("settlement_comparison_not_found",404)
  return {"comparison":self._pub(row),"review_required":True,"local_only":True}
 def source(self,cid,sid):
  row=self.get(cid)["comparison"];scenario=next((x for x in row["scenarios"] if x.get("scenario_id")==_id(sid,"settlement_scenario_id")),None)
  if scenario is None:raise IntakeWorkbenchError("settlement_scenario_not_found",404)
  return {"comparison_id":row["comparison_id"],"scenario_id":scenario["scenario_id"],"source":dict(scenario["source_ref"]),"review_required":True,"filing_ready":False}
