"""Encrypted, non-determinative venue and court-location review workspaces."""
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
def _now()->str:return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _digest(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _id(v:Any,n:str)->str:
 x=str(v or "").strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f"{n}_invalid")
 return x
def _text(v:Any,n:str,limit:int=2000,required:bool=True)->str:
 x=" ".join(str(v or "").replace("\x00","").split())
 if required and not x:raise IntakeWorkbenchError(f"{n}_required")
 if len(x)>limit:raise IntakeWorkbenchError(f"{n}_too_long")
 return x
class VenueLocationNavigatorStore:
 schema="maine_family_law_llm.venue_location_navigator.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"18_PROCEDURE"/"venue-locations"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("venue_location_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self)->Path:return self.root/"workspaces.json.enc"
 @property
 def lock(self)->Path:return self.root/".workspaces.lock"
 def _load(self)->dict[str,Any]:
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"workspaces":[],"ledger":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=16*1024*1024,require_object=True))
  except Exception as exc:raise IntakeWorkbenchError("venue_location_store_unavailable",409) from exc
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope:raise IntakeWorkbenchError("cross_matter_access_denied",404)
  v.setdefault("workspaces",[]);v.setdefault("ledger",[]);v.setdefault("revision",0);return v
 def _save(self,v:dict[str,Any])->None:atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _authority(v:dict[str,Any])->dict[str,Any]:
  digest=str(v.get("source_hash") or "").casefold()
  if not _HASH.fullmatch(digest):raise IntakeWorkbenchError("venue_location_authority_invalid",409)
  return {"authority_id":_id(v.get("authority_id"),"venue_location_authority_id"),"source_id":_text(v.get("source_id"),"venue_location_source_id",240),"source_hash":digest,"citation":_text(v.get("citation"),"venue_location_citation",500),"title":_text(v.get("title"),"venue_location_title",500),"freshness_status":_text(v.get("freshness_status"),"venue_location_freshness",80,False) or "unknown","lane":"official_authority"}
 @staticmethod
 def _public(v:dict[str,Any])->dict[str,Any]:
  r=deepcopy(v);r.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"venue_determined":False,"notice":"This workspace organizes an official source, reviewer-entered public location/contact notes, and unresolved venue facts. It does not decide venue, jurisdiction, court assignment, filing location, or legal effect."});return r
 def create(self,p:dict[str,Any],*,authority:dict[str,Any])->dict[str,Any]:
  if p.get("user_confirmed") is not True:raise IntakeWorkbenchError("venue_location_confirmation_required",409)
  wid=_id(p.get("workspace_id"),"venue_location_workspace_id");unresolved=p.get("unresolved_facts") or []
  if not isinstance(unresolved,list) or len(unresolved)>30:raise IntakeWorkbenchError("venue_location_unresolved_invalid")
  e={"workspace_id":wid,"reviewer_safe_id":_id(p.get("reviewer_safe_id"),"reviewer_safe_id"),"location_label":_text(p.get("location_label"),"venue_location_label",300),"contact_label":_text(p.get("contact_label"),"venue_location_contact",500,False),"unresolved_facts":[_text(x,"venue_location_unresolved",1000) for x in unresolved if _text(x,"venue_location_unresolved",1000,False)],"authority":self._authority(authority),"created_at":_now(),"review_required":True,"filing_ready":False};e["workspace_hash"]=_digest({k:v for k,v in e.items() if k!="created_at"})
  with exclusive_file_lock(self.lock):
   s=self._load()
   if any(x.get("workspace_id")==wid for x in s["workspaces"]):raise IntakeWorkbenchError("venue_location_workspace_id_already_exists",409)
   s["workspaces"].append(e);event={"event_id":f"venue_location_{uuid.uuid4().hex}","at":_now(),"action":"create_venue_location_workspace","workspace_id":wid,"previous_event_hash":str(s["ledger"][-1].get("event_hash") or "") if s["ledger"] else "","review_required":True};event["event_hash"]=_digest(event);s["ledger"].append(event);s["revision"]=int(s.get("revision") or 0)+1;self._save(s)
  return self._public(e)
 def workspaces(self,wid:str="")->dict[str,Any]:
  rows=[self._public(x) for x in self._load()["workspaces"]]
  if wid:
   x=next((x for x in rows if x.get("workspace_id")==_id(wid,"venue_location_workspace_id")),None)
   if x is None:raise IntakeWorkbenchError("venue_location_workspace_not_found",404)
   return {"workspace":x,"review_required":True,"local_only":True}
  return {"workspaces":rows,"review_required":True,"local_only":True}
 def source(self,wid:str)->dict[str,Any]:
  w=self.workspaces(wid)["workspace"];return {"workspace_id":w["workspace_id"],"source":w["authority"],"review_required":True}
