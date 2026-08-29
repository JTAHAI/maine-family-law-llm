"""Encrypted preparation workspace for current child-support worksheet review; never calculates support."""
from __future__ import annotations
import hashlib,json,os,re,uuid
from copy import deepcopy
from datetime import UTC,datetime
from pathlib import Path
from typing import Any
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
_ID=re.compile(r"[a-z][a-z0-9_-]{2,79}\Z");_HASH=re.compile(r"[a-f0-9]{64}\Z")
_FIELDS={"gross_income","health_insurance","child_care","support_paid","children","overnights","other"}
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
class ChildSupportWorksheetStore:
 schema="maine_family_law_llm.child_support_worksheet.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"36_FINANCIAL_REVIEW"/"child-support-worksheets"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("child_support_worksheet_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"workspaces.json.enc"
 @property
 def lock(self):return self.root/".workspaces.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"rows":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=16*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError("child_support_worksheet_store_unavailable",409) from e
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("rows",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _authority(v):
  h=str(v.get("source_hash") or "").casefold();fresh=str(v.get("freshness_status") or "unknown").casefold()
  if not _HASH.fullmatch(h):raise IntakeWorkbenchError("child_support_authority_invalid",409)
  if fresh not in {"fresh","current"}:raise IntakeWorkbenchError("child_support_current_authority_required",409)
  return {"authority_id":_id(v.get("authority_id"),"child_support_authority_id"),"source_id":_text(v.get("source_id"),"child_support_source_id",240),"source_hash":h,"citation":_text(v.get("citation"),"child_support_citation",500),"title":_text(v.get("title"),"child_support_title",500),"exact_span":_text(v.get("exact_span") or v.get("source_span_preview"),"child_support_span",4000,False),"freshness_status":fresh,"lane":"official_authority"}
 @staticmethod
 def _inputs(v):
  if not isinstance(v,list) or not v or len(v)>60:raise IntakeWorkbenchError("child_support_inputs_invalid")
  seen=set();rows=[]
  for x in v:
   if not isinstance(x,dict):raise IntakeWorkbenchError("child_support_input_invalid")
   field=str(x.get("field_id") or "").strip().casefold();iid=_id(x.get("input_id"),"child_support_input_id")
   if field not in _FIELDS or iid in seen:raise IntakeWorkbenchError("child_support_input_field_or_id_invalid")
   seen.add(iid);state=str(x.get("state") or "user_entered_unverified")
   if state not in {"user_entered_unverified","unknown","missing"}:raise IntakeWorkbenchError("child_support_input_state_invalid")
   rows.append({"input_id":iid,"field_id":field,"label":_text(x.get("label"),"child_support_input_label",300),"value":_text(x.get("value"),"child_support_input_value",4000,False),"state":state})
  return rows
 @staticmethod
 def _public(v):
  out=deepcopy(v);out.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"calculation":"not_available","worksheet_completion":"not_available","notice":"This organizes user-entered worksheet inputs and missing facts against a selected current official source. It does not calculate child support, determine income, deviations, eligibility, legal effect, or complete a worksheet."});return out
 def create(self,p,*,authority):
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("child_support_worksheet_confirmation_required",409)
  missing=p.get("missing_facts") or []
  if not isinstance(missing,list) or len(missing)>60:raise IntakeWorkbenchError("child_support_missing_facts_invalid")
  row={"workspace_id":_id(p.get("workspace_id"),"child_support_workspace_id"),"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"authority":self._authority(authority),"inputs":self._inputs(p.get("inputs")),"missing_facts":[_text(x,"child_support_missing_fact",500) for x in missing],"created_at":_now(),"review_required":True,"filing_ready":False};row["workspace_hash"]=_dig({k:v for k,v in row.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get("workspace_id")==row["workspace_id"] for x in state["rows"]):raise IntakeWorkbenchError("child_support_workspace_id_exists",409)
   state["rows"].append(row);e={"event_id":f"child_support_{uuid.uuid4().hex}","at":_now(),"action":"child_support_worksheet_prepared","workspace_id":row["workspace_id"],"previous_event_hash":str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "","review_required":True};e["event_hash"]=_dig(e);state["ledger"].append(e);state["revision"]+=1;self._save(state)
  return self._public(row)
 def get(self,workspace_id):
  row=next((x for x in self._load()["rows"] if x.get("workspace_id")==_id(workspace_id,"child_support_workspace_id")),None)
  if row is None:raise IntakeWorkbenchError("child_support_workspace_not_found",404)
  return {"workspace":self._public(row),"review_required":True,"local_only":True}
 def authority_source(self,workspace_id):
  row=self.get(workspace_id)["workspace"]
  return {"workspace_id":row["workspace_id"],"source":row["authority"],"review_required":True,"filing_ready":False}
