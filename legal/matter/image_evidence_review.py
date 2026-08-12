"""Encrypted visual-evidence review metadata; no authenticity or event inference."""
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
def _t(v:Any,n:int=8000)->str:
 x=str(v or '').strip()
 if len(x)>n:raise IntakeWorkbenchError('text_limit_exceeded')
 return x
def _h(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _now()->str:return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
class ImageEvidenceStore:
 schema='maine_family_law_llm.image_evidence_review.v1'
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/'39_IMAGE_EVIDENCE'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('image_store_unavailable',409)
  self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me');self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
 @property
 def path(self):return self.root/'images.json.enc'
 @property
 def lock(self):return self.root/'.images.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'items':[],'history':[],'revision':0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('image_store_unavailable',409) from e
  if v.get('schema')!=self.schema or v.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 def _mut(self,a,ids,fn):
  with exclusive_file_lock(self.lock):
   v=self._load();r=fn(v);e={'event_id':f'image_{uuid.uuid4().hex}','at':_now(),'action':a,'ids':ids,'previous_hash':v['history'][-1]['hash'] if v['history'] else '','review_required':True};e['hash']=_h(e);v['history'].append(e);v['revision']+=1;self._save(v);return r
 def inventory(self):
  v=deepcopy(self._load());v.pop('scope',None);v.update({'status':'review_required','review_required':True,'local_only':True,'originals_immutable':True,'authenticity':'not_determined','event_conclusion':'not_determined'});return v
 def add(self,p):
  rows=p.get('items')
  if not isinstance(rows,list) or not rows:raise IntakeWorkbenchError('image_items_invalid')
  def fn(v):
   for x in rows:v['items'].append({'image_id':_id(x.get('image_id'),'image_id'),'original_hash':_t(x.get('original_hash'),128),'kind':_t(x.get('kind'),128),'source_ref':x.get('source_ref') or {},'metadata_warning':bool(x.get('metadata_warning')),'annotation_derivative_hash':_t(x.get('annotation_derivative_hash'),128),'reviewer_status':'review_required'})
   return self.inventory()
  return self._mut('image_added',[_id(x.get('image_id'),'image_id') for x in rows if isinstance(x,dict)],fn)
 def receipt(self):
  v=self._load();r={'revision':v['revision'],'items_hash':_h(v['items']),'history_hash':_h(v['history']),'review_required':True,'issued_at':_now()};r['receipt_hash']=_h(r);return r
