"""Local clock-skew detection for time-sensitive review work.

No network time source is contacted.  The monitor compares UTC wall-clock
advance to monotonic-clock advance within one process session.  A material
difference flags audit ordering, deadline candidates, freshness, and timestamp
certificates for human review; it never rewrites their historical times.
"""
from __future__ import annotations
import hashlib, json, os, secrets, time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_MAX_STATE=512*1024; _MAX_RECEIPTS=80; _PROCESS_SESSION=secrets.token_hex(16)
class ClockSkewError(RuntimeError):
 def __init__(self,code:str,*,status_code:int=409)->None: super().__init__(code); self.code=code; self.status_code=status_code
def _now()->str:return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _canon(value:Any)->bytes:return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def _hash(value:Any)->str:return hashlib.sha256(value if isinstance(value,bytes) else _canon(value)).hexdigest()

class ClockSkewMonitor:
 schema_version='runtime_clock_skew_v1'
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None,session_id:str|None=None,wall_clock:Callable[[],float]|None=None,monotonic_clock:Callable[[],float]|None=None)->None:
  self.root=Path(case_root).resolve()/'40_RUNTIME'/'clock-skew'; self.path=self.root/'state.json.enc'; self.lock_path=self.root/'.state.lock'; self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me'); self.session_id=session_id or _PROCESS_SESSION; self.wall=wall_clock or time.time; self.mono=monotonic_clock or time.monotonic
 def _empty(self)->dict[str,Any]:return {'schema_version':self.schema_version,'tenant_id':'','baseline':None,'receipts':[],'audit':[]}
 def _load(self)->dict[str,Any]:
  if not self.path.exists():return self._empty()
  try:s=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=_MAX_STATE,require_object=True))
  except Exception as exc:raise ClockSkewError('clock_skew_store_unavailable') from exc
  if not isinstance(s,dict) or s.get('schema_version')!=self.schema_version:raise ClockSkewError('clock_skew_store_unavailable')
  return s
 def _save(self,s:dict[str,Any])->None:
  try:atomic_write_bytes(self.path,_canon(self.encryptor.encrypt_json(s)),mode=0o600)
  except Exception as exc:raise ClockSkewError('clock_skew_store_write_failed') from exc
 def check(self,*,actor_role:str,tenant_id:str,threshold_seconds:float=300.0)->dict[str,Any]:
  threshold=max(30.0,min(float(threshold_seconds),24*3600)); wall=float(self.wall()); mono=float(self.mono())
  with exclusive_file_lock(self.lock_path):
   s=self._load(); old_tenant=str(s.get('tenant_id') or '')
   if old_tenant and old_tenant!=tenant_id:raise ClockSkewError('clock_skew_tenant_mismatch',status_code=403)
   s['tenant_id']=tenant_id; baseline=s.get('baseline') if isinstance(s.get('baseline'),dict) else None; status='baseline_established'; skew=None
   if baseline and baseline.get('session_id')==self.session_id:
    expected=float(baseline['wall_epoch'])+(mono-float(baseline['monotonic_epoch'])); skew=wall-expected; status='material_skew_detected' if abs(skew)>=threshold else 'within_tolerance'
   elif baseline: status='baseline_restarted'
   if status!='material_skew_detected': s['baseline']={'session_id':self.session_id,'wall_epoch':wall,'monotonic_epoch':mono,'recorded_at':_now()}
   report={'schema_version':self.schema_version,'status':status,'material_skew_detected':status=='material_skew_detected','skew_seconds':round(skew,3) if skew is not None else None,'threshold_seconds':threshold,'affected_review_domains':['audit_ordering','deadline_candidates','authority_freshness','timestamp_certificates'] if status=='material_skew_detected' else [],'network_time_checked':False,'timestamps_rewritten':False,'private_paths_included':False,'review_required':True}
   prev=str((s.get('audit') or [{}])[-1].get('event_hash') or ''); basis={'event_type':'clock_skew_checked','recorded_at':_now(),'report_hash':_hash(report),'previous_hash':prev,'actor_role':actor_role[:40],'tenant_id':tenant_id}; audit={**basis,'event_hash':_hash(basis)}; receipt={'clock_check_id':f"clock_{audit['event_hash'][:24]}",'recorded_at':basis['recorded_at'],'report_hash':basis['report_hash'],'status':status,'review_required':True}; s['receipts']=[*list(s.get('receipts') or []),receipt][-_MAX_RECEIPTS:];s['audit']=[*list(s.get('audit') or []),audit][-_MAX_RECEIPTS:];self._save(s)
  return {**report,'audit_receipt':receipt,'audit_chain_head':audit['event_hash']}
 def verify(self)->dict[str,Any]:
  s=self._load();prev='';valid=True
  for r in s.get('audit') or []:
   b={k:r.get(k) for k in ('event_type','recorded_at','report_hash','previous_hash','actor_role','tenant_id')}
   if r.get('previous_hash')!=prev or r.get('event_hash')!=_hash(b):valid=False;break
   prev=str(r.get('event_hash') or '')
  return {'status':'pass' if valid else 'blocked','receipt_count':len(s.get('receipts') or []),'audit_chain_valid':valid,'review_required':True}
__all__=['ClockSkewError','ClockSkewMonitor']
