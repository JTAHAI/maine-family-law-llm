"""Explicit local low-memory posture with conservative fallback settings."""
from __future__ import annotations
import hashlib,json,os
from datetime import UTC,datetime
from pathlib import Path
from typing import Any
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.model_orchestration.hardware import profile_hardware
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

def _now(): return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _canon(v): return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def _dig(v): return hashlib.sha256(_canon(v)).hexdigest()
class LowMemoryModeStore:
 schema='maine_family_law_llm.low_memory_mode.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None): self.root=Path(root).resolve()/'40_RUNTIME'/'low-memory-mode';self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self): return self.root/'state.json.enc'
 @property
 def lock(self): return self.root/'.state.lock'
 def _load(self):
  if not self.path.exists(): return {'schema':self.schema,'active':False,'events':[],'revision':0}
  try: state=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=1024*1024,require_object=True))
  except Exception as exc: raise IntakeWorkbenchError('low_memory_mode_unavailable',409) from exc
  if state.get('schema')!=self.schema: raise IntakeWorkbenchError('low_memory_mode_unavailable',409)
  prior=''
  for e in state.get('events',[]):
   x=dict(e);actual=x.pop('event_hash','')
   if x.get('previous_event_hash')!=prior or actual!=_dig(x): raise IntakeWorkbenchError('low_memory_mode_history_invalid',409)
   prior=actual
  return state
 def _write(self,s): atomic_write_bytes(self.path,_canon(self.encryptor.encrypt_json(s)),mode=0o600)
 def evaluate(self):
  p=profile_hardware(self.root).as_dict();available=int(p.get('available_memory_bytes') or 0);low=bool(available and available<4*1024**3)
  return {'schema_version':'low_memory_mode_v1','detected_low_memory':low,'hardware':{'available_memory_bytes':available,'recommended_context_limit':int(p.get('recommended_context_limit') or 0)},'fallbacks':{'retrieval':'lexical_only','model':'compact_admitted_only_or_deterministic','max_batch_items':1,'max_context_tokens':2048,'warm_workers':'release'},'review_required':True,'local_only':True,'network_used':False}
 def set_active(self,payload:dict[str,Any]):
  if payload.get('user_confirmed') is not True: raise IntakeWorkbenchError('low_memory_mode_confirmation_required',409)
  desired=bool(payload.get('active',True));evaluation=self.evaluate()
  with exclusive_file_lock(self.lock):
   s=self._load();s['active']=desired;s['updated_at']=_now();event={'event_id':'lowmem_'+hashlib.sha256((_now()+str(desired)).encode()).hexdigest()[:20],'at':_now(),'action':'low_memory_mode_activated' if desired else 'low_memory_mode_deactivated','detail':{'detected_low_memory':evaluation['detected_low_memory'],'fallbacks':evaluation['fallbacks']},'previous_event_hash':str(s['events'][-1].get('event_hash') or '') if s['events'] else '','review_required':True};event['event_hash']=_dig(event);s['events'].append(event);s['revision']=int(s.get('revision') or 0)+1;self._write(s)
  return {**evaluation,'active':desired,'status':'low_memory_mode_active_review_required' if desired else 'normal_mode_review_required','receipt':event}
 def status(self):
  s=self._load();return {**self.evaluate(),'active':bool(s.get('active')),'status':'low_memory_mode_active_review_required' if s.get('active') else 'normal_mode_review_required','recent_events':list(reversed(s.get('events',[])[-12:]))}
