"""Encrypted, source-bound neutral communication protocol drafts; never approves an agreement or assesses safety."""
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
_ID=re.compile(r'[a-z][a-z0-9_-]{2,79}\Z');_HASH=re.compile(r'[a-f0-9]{64}\Z')
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _id(v,n):
 x=str(v or '').strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f'{n}_invalid')
 return x
def _txt(v,n,l=2000):
 x=' '.join(str(v or '').replace('\x00','').split())
 if not x:raise IntakeWorkbenchError(f'{n}_required')
 if len(x)>l:raise IntakeWorkbenchError(f'{n}_too_long')
 return x
class CommunicationPlanStore:
 schema='maine_family_law_llm.communication_plan.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(root).resolve();self.root=self.case_root/'35_NEGOTIATION'/'communication-plans'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('communication_plan_store_unavailable',409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'plans.json.enc'
 @property
 def lock(self):return self.root/'.plans.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'rows':[],'ledger':[],'revision':0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=16*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('communication_plan_store_unavailable',409) from e
  if v.get('schema')!=self.schema or v.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  v.setdefault('rows',[]);v.setdefault('ledger',[]);v.setdefault('revision',0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _pub(v):
  o=deepcopy(v);o.update({'status':'review_required','review_required':True,'filing_ready':False,'local_only':True,'agreement_status':'not_determined','safety_status':'not_determined','notice':'This is a neutral reviewer draft from selected terms. It does not determine safety, consent, legal effect, an agreement, or an enforceable communication or exchange protocol.'});return o
 def create(self,p,*,records:Iterable[dict]):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('communication_plan_confirmation_required',409)
  refs=p.get('source_refs')
  if not isinstance(refs,list) or not refs or len(refs)>20:raise IntakeWorkbenchError('communication_plan_sources_invalid')
  available={str(x.get('evidence_id') or x.get('source_id') or '').casefold():(str(x.get('evidence_id') or x.get('source_id') or ''),x) for x in records if isinstance(x,dict)};bound=[]
  for ref in refs:
   ref=dict(ref or {});rid=str(ref.get('record_id') or '');h=str(ref.get('source_hash') or '').casefold();found=available.get(rid.casefold())
   if not rid or not _HASH.fullmatch(h) or found is None or str(found[1].get('source_hash') or found[1].get('sha256') or '').casefold()!=h:raise IntakeWorkbenchError('communication_plan_source_not_in_active_matter',404)
   bound.append({'record_id':found[0],'source_hash':h,'page':ref.get('page')})
  terms=p.get('terms')
  if not isinstance(terms,list) or not terms or len(terms)>40:raise IntakeWorkbenchError('communication_plan_terms_invalid')
  clean=[{'term_id':_id(x.get('term_id'),'communication_plan_term_id'),'topic':_id(x.get('topic'),'communication_plan_topic'),'text':_txt(x.get('text'),'communication_plan_text'),'state':'reviewer_selected'} for x in terms if isinstance(x,dict)]
  if len(clean)!=len(terms):raise IntakeWorkbenchError('communication_plan_term_invalid')
  row={'plan_id':_id(p.get('plan_id'),'communication_plan_id'),'reviewer_safe_id':_id(p.get('reviewer_safe_id'),'reviewer_safe_id'),'terms':clean,'source_refs':bound,'created_at':_now(),'review_required':True,'filing_ready':False};row['plan_hash']=_dig({k:v for k,v in row.items() if k!='created_at'})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get('plan_id')==row['plan_id'] for x in state['rows']):raise IntakeWorkbenchError('communication_plan_id_exists',409)
   state['rows'].append(row);e={'event_id':f'communication_{uuid.uuid4().hex}','at':_now(),'action':'communication_plan_created','plan_id':row['plan_id'],'previous_event_hash':str(state['ledger'][-1].get('event_hash') or '') if state['ledger'] else '','review_required':True};e['event_hash']=_dig(e);state['ledger'].append(e);state['revision']+=1;self._save(state)
  return self._pub(row)
 def get(self,pid):
  row=next((x for x in self._load()['rows'] if x.get('plan_id')==_id(pid,'communication_plan_id')),None)
  if row is None:raise IntakeWorkbenchError('communication_plan_not_found',404)
  return {'plan':self._pub(row),'review_required':True,'local_only':True}
 def source(self,pid,record_id):
  row=self.get(pid)['plan'];ref=next((x for x in row['source_refs'] if str(x.get('record_id') or '')==str(record_id or '')),None)
  if ref is None:raise IntakeWorkbenchError('communication_plan_source_not_found',404)
  return {'plan_id':row['plan_id'],'source':dict(ref),'review_required':True}
