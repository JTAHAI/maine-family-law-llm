"""Fail-closed local merge planning for independently reviewed bundle manifests."""
from __future__ import annotations

import hashlib, json, os, re, uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID=re.compile(r"[a-z][a-z0-9_-]{2,79}\Z"); _HASH=re.compile(r"[a-f0-9]{64}\Z")
def _now(): return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")
def _digest(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def _id(v:Any,f:str)->str:
 t=str(v or "").strip().casefold()
 if not _ID.fullmatch(t):raise IntakeWorkbenchError(f"{f}_invalid")
 return t
def _hash(v:Any,f:str)->str:
 t=str(v or "").strip().casefold()
 if not _HASH.fullmatch(t):raise IntakeWorkbenchError(f"{f}_invalid")
 return t
def _bundle(v:Any,label:str)->dict[str,Any]:
 if not isinstance(v,dict):raise IntakeWorkbenchError(f"{label}_bundle_invalid")
 bid=_id(v.get("bundle_id"),f"{label}_bundle_id"); bh=_hash(v.get("bundle_hash"),f"{label}_bundle_hash"); rows=v.get("items")
 if not isinstance(rows,list) or len(rows)>500:raise IntakeWorkbenchError(f"{label}_bundle_items_invalid")
 items=[]
 for row in rows:
  if not isinstance(row,dict):raise IntakeWorkbenchError(f"{label}_bundle_item_invalid")
  items.append({"item_id":_id(row.get("item_id"),"bundle_item_id"),"kind":str(row.get("kind") or "artifact").strip()[:80],"base_hash":_hash(row.get("base_hash"),"bundle_item_base_hash"),"value_hash":_hash(row.get("value_hash"),"bundle_item_value_hash")})
 if len({r['item_id'] for r in items})!=len(items):raise IntakeWorkbenchError(f"{label}_bundle_item_duplicate")
 return {"bundle_id":bid,"bundle_hash":bh,"items":items}

class BundleMergeStore:
 schema="maine_family_law_llm.bundle_merge.v1"
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/"47_BUNDLE_MERGES"
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError("bundle_merge_store_unavailable",409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
 @property
 def path(self):return self.root/"merges.json.enc"
 @property
 def lock(self):return self.root/".merges.lock"
 def _load(self):
  if not self.path.exists():return {"schema":self.schema,"scope":self.scope,"plans":[],"history":[],"revision":0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
  except Exception as exc:raise IntakeWorkbenchError("bundle_merge_store_unavailable",409) from exc
  if v.get("schema")!=self.schema or v.get("scope")!=self.scope or not isinstance(v.get("plans"),list) or not isinstance(v.get("history"),list):raise IntakeWorkbenchError("cross_matter_access_denied",404)
  return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 def _mutate(self,action:str,ids:list[str],op:Callable[[dict[str,Any]],Any]):
  with exclusive_file_lock(self.lock):
   v=self._load();result=op(v);e={"event_id":f"bundle_merge_{uuid.uuid4().hex}","at":_now(),"action":action,"ids":ids,"previous_hash":v["history"][-1]["hash"] if v["history"] else "","review_required":True};e["hash"]=_digest(e);v["history"].append(e);v["revision"]+=1;self._save(v);return result
 @staticmethod
 def _plan(v,mid):
  for p in v["plans"]:
   if p.get("merge_id")==mid:return p
  raise IntakeWorkbenchError("bundle_merge_not_found",404)
 @staticmethod
 def _public(p):
  r=deepcopy(p);r.update({"review_required":True,"local_only":True,"automatic_merge":False,"source_bundles_modified":False,"matter_modified":False});return r
 def create(self,payload):
  mid=_id(payload.get("merge_id"),"merge_id");left=_bundle(payload.get("left_bundle"),"left");right=_bundle(payload.get("right_bundle"),"right")
  if left["bundle_id"]==right["bundle_id"] or left["bundle_hash"]==right["bundle_hash"]:raise IntakeWorkbenchError("bundle_merge_independent_bundles_required",409)
  def op(v):
   if any(x.get("merge_id")==mid for x in v["plans"]):raise IntakeWorkbenchError("duplicate_bundle_merge_id",409)
   li={x["item_id"]:x for x in left["items"]};ri={x["item_id"]:x for x in right["items"]};ids=sorted(set(li)|set(ri));conflicts=[];candidates=[]
   for item in ids:
    a,b=li.get(item),ri.get(item)
    if a and b and a["value_hash"]!=b["value_hash"]:conflicts.append({"conflict_id":f"conflict_{item}","item_id":item,"left_value_hash":a["value_hash"],"right_value_hash":b["value_hash"],"state":"unresolved_review_required"})
    else:candidates.append({"item_id":item,"selected_from":"both" if a and b else ("left" if a else "right"),"value_hash":(a or b)["value_hash"],"review_required":True})
   plan={"merge_id":mid,"left_bundle":left,"right_bundle":right,"candidates":candidates,"conflicts":conflicts,"status":"conflicts_review_required" if conflicts else "merge_review_required","created_at":_now(),"review_required":True};plan["plan_hash"]=_digest(plan);v["plans"].append(plan);return deepcopy(plan)
  return self._public(self._mutate("bundle_merge_plan_created",[mid,left["bundle_id"],right["bundle_id"]],op))
 def resolve(self,merge_id,payload):
  mid=_id(merge_id,"merge_id");cid=_id(payload.get("conflict_id"),"conflict_id");choice=str(payload.get("choice") or "").strip().casefold();resolver=_id(payload.get("resolver_safe_id"),"resolver_safe_id")
  if choice not in {"left","right","defer"}:raise IntakeWorkbenchError("bundle_merge_choice_invalid")
  def op(v):
   p=self._plan(v,mid)
   if p.get("status") in {"merged_review_required","blocked"}:raise IntakeWorkbenchError("bundle_merge_not_resolvable",409)
   c=next((x for x in p["conflicts"] if x["conflict_id"]==cid),None)
   if not c:raise IntakeWorkbenchError("bundle_merge_conflict_not_found",404)
   if c["state"]!="unresolved_review_required":raise IntakeWorkbenchError("bundle_merge_conflict_already_resolved",409)
   c.update({"state":"resolved_review_required" if choice in {"left","right"} else "deferred_review_required","choice":choice,"resolver_safe_id":resolver,"resolved_at":_now()});p["status"]="blocked" if any(x["state"]=="deferred_review_required" for x in p["conflicts"]) else ("ready_to_merge_review_required" if all(x["state"]=="resolved_review_required" for x in p["conflicts"]) else "conflicts_review_required");p["plan_hash"]=_digest({k:x for k,x in p.items() if k!="plan_hash"});return deepcopy(p)
  return self._public(self._mutate("bundle_merge_conflict_resolved",[mid,cid,resolver],op))
 def finalize(self,merge_id,payload):
  mid=_id(merge_id,"merge_id");reviewer=_id(payload.get("reviewer_safe_id"),"reviewer_safe_id")
  if payload.get("confirmed") is not True:raise IntakeWorkbenchError("bundle_merge_confirmation_required")
  def op(v):
   p=self._plan(v,mid)
   if p.get("status")!="ready_to_merge_review_required":raise IntakeWorkbenchError("bundle_merge_conflicts_unresolved",409)
   selected=list(p["candidates"])
   for c in p["conflicts"]:selected.append({"item_id":c["item_id"],"selected_from":c["choice"],"value_hash":c[f"{c['choice']}_value_hash"],"review_required":True})
   merged={"schema":"maine_family_law_llm.merged_reviewer_bundle.v1","merge_id":mid,"lineage":{"left_bundle_hash":p["left_bundle"]["bundle_hash"],"right_bundle_hash":p["right_bundle"]["bundle_hash"],"plan_hash":p["plan_hash"]},"items":sorted(selected,key=lambda x:x["item_id"]),"review_required":True,"local_only":True,"automatic_apply":False,"created_at":_now()};merged["bundle_hash"]=_digest(merged);p.update({"status":"merged_review_required","merged_bundle":merged,"finalized_by_safe_id":reviewer,"finalized_at":_now()});p["plan_hash"]=_digest({k:x for k,x in p.items() if k!="plan_hash"});return deepcopy(p)
  return self._public(self._mutate("bundle_merge_finalized",[mid,reviewer],op))
 def get(self,merge_id):return self._public(self._plan(self._load(),_id(merge_id,"merge_id")))
 def inventory(self):
  v=self._load();return {"schema":self.schema,"plans":[self._public(p) for p in v["plans"]],"history_hash":_digest(v["history"]),"revision":v["revision"],"review_required":True,"local_only":True,"automatic_merge":False}
