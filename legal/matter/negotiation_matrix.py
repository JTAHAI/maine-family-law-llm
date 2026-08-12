"""Encrypted local proposal comparison; never sends, accepts, or certifies agreements."""
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
_ID=re.compile(r'[a-z][a-z0-9_-]{2,79}\Z')
def _id(v:Any,n:str)->str:
 x=str(v or '').strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f'{n}_invalid')
 return x
def _t(v:Any,n:int=12000)->str:
 x=str(v or '').strip()
 if len(x)>n:raise IntakeWorkbenchError('text_limit_exceeded')
 return x
def _h(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _now()->str:return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
class NegotiationMatrixStore:
 schema='maine_family_law_llm.negotiation_matrix.v1'
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/'34_NEGOTIATION_MATRIX'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('negotiation_store_unavailable',409)
  self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me');self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
 @property
 def path(self):return self.root/'proposals.json.enc'
 @property
 def lock(self):return self.root/'.proposals.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'proposals':[],'history':[],'revision':0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('negotiation_store_unavailable',409) from e
  if v.get('schema')!=self.schema or v.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 def _mut(self,a,ids,fn):
  with exclusive_file_lock(self.lock):
   v=self._load();r=fn(v);e={'event_id':f'proposal_{uuid.uuid4().hex}','at':_now(),'action':a,'ids':ids,'previous_hash':v['history'][-1]['hash'] if v['history'] else '','review_required':True};e['hash']=_h(e);v['history'].append(e);v['revision']+=1;self._save(v);return r
 def inventory(self):
  v=deepcopy(self._load());v.pop('scope',None);v.update({'status':'review_required','review_required':True,'local_only':True,'automatic_communication':False,'agreement_validity':'not_determined','negotiation_recommendation':'not_available'});return v
 def add(self,p):
  rows=p.get('proposals')
  if not isinstance(rows,list) or not rows:raise IntakeWorkbenchError('proposals_invalid')
  def fn(v):
   for x in rows:
    src=x.get('source_ref') or {};v['proposals'].append({'proposal_id':_id(x.get('proposal_id'),'proposal_id'),'author_role':_t(x.get('author_role'),128),'date_candidate':_t(x.get('date_candidate'),64),'topics':x.get('topics',[]),'exact_text':_t(x.get('exact_text')),'source_ref':{'record_id':_id(src.get('record_id'),'record_id'),'span':_t(src.get('span'),128)},'status':'review_required'})
   return self.inventory()
  return self._mut('proposal_added',[_id(x.get('proposal_id'),'proposal_id') for x in rows if isinstance(x,dict)],fn)
 def compare(self,left,right):
  v=self._load();a=next((x for x in v['proposals'] if x['proposal_id']==_id(left,'proposal_id')),None);b=next((x for x in v['proposals'] if x['proposal_id']==_id(right,'proposal_id')),None)
  if not a or not b:raise IntakeWorkbenchError('proposal_not_found',404)
  return {'status':'review_required','left':a,'right':b,'shared_topics':sorted(set(a['topics'])&set(b['topics'])),'agreement':'not_determined','recommendation':'not_available'}
 def receipt(self):
  v=self._load();r={'revision':v['revision'],'proposals_hash':_h(v['proposals']),'history_hash':_h(v['history']),'review_required':True,'issued_at':_now()};r['receipt_hash']=_h(r);return r
