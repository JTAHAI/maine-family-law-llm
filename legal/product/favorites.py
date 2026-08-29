"""Encrypted active-matter favorites with explicit local role-filtering."""
from __future__ import annotations
import hashlib,json,os,re
from copy import deepcopy
from datetime import UTC,datetime
from pathlib import Path
from typing import Any
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
_ID=re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{1,119}\Z");_HASH=re.compile(r"[0-9a-f]{64}\Z")
_KINDS=frozenset({'matter','record','official_source','draft','workspace'});_VIS=frozenset({'private','review_team','attorney_only'});_ROLES=frozenset({'attorney','paralegal','advocate','self_represented','other_reviewer','reviewer','viewer'})
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def _dig(v):return hashlib.sha256(_canon(v)).hexdigest()
def _id(v,label):
 x=str(v or '').strip()
 if not _ID.fullmatch(x) or '..' in x or '/' in x or '\\' in x:raise IntakeWorkbenchError(f'favorite_{label}_invalid')
 return x
def _hash(v):
 x=str(v or '').strip().casefold()
 if not _HASH.fullmatch(x):raise IntakeWorkbenchError('favorite_source_hash_invalid')
 return x
def _role(v):
 x=str(v or '').strip().casefold()
 if x not in _ROLES:raise IntakeWorkbenchError('favorite_role_invalid')
 return x
class FavoritesStore:
 schema='maine_family_law_llm.favorites.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):self.root=Path(root).resolve()/'40_RUNTIME'/'favorites';self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'favorites.json.enc'
 @property
 def lock(self):return self.root/'.favorites.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'favorites':{},'events':[],'revision':0}
  try:s=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=2*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('favorites_unavailable',409) from e
  if s.get('schema')!=self.schema:raise IntakeWorkbenchError('favorites_unavailable',409)
  prior=''
  for event in s.get('events',[]):
   cp=dict(event);digest=str(cp.pop('event_hash',''))
   if cp.get('previous_event_hash')!=prior or digest!=_dig(cp):raise IntakeWorkbenchError('favorites_history_invalid',409)
   prior=digest
  return s
 def _write(self,s):atomic_write_bytes(self.path,_canon(self.encryptor.encrypt_json(s)),mode=0o600)
 def _event(self,s,a,f,d):
  e={'event_id':'fav_'+hashlib.sha256((a+f+_now()).encode()).hexdigest()[:24],'at':_now(),'action':a,'favorite_id':f,'detail':deepcopy(d),'previous_event_hash':str(s['events'][-1].get('event_hash') or '') if s['events'] else '','review_required':True};e['event_hash']=_dig(e);s['events'].append(e);s['revision']=int(s.get('revision') or 0)+1;return e
 def _target(self,k,x):
  if not isinstance(x,dict):raise IntakeWorkbenchError('favorite_target_invalid')
  if k=='record':return {'record_id':_id(x.get('record_id'),'record_id'),'source_hash':_hash(x.get('source_hash')),'page':max(0,min(int(x.get('page') or 0),100000))}
  return {'target_id':_id(x.get('target_id'),'target_id')}
 def _visible(self,row,role):return row['visibility']=='review_team' or (row['visibility']=='attorney_only' and role=='attorney') or (row['visibility']=='private' and row['owner_role']==role)
 def _public(self,row):return {k:deepcopy(row.get(k)) for k in ('favorite_id','kind','label','target','visibility','owner_role','created_at','review_required','notice')}
 def create(self,p):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('favorite_confirmation_required',409)
  fid=_id(p.get('favorite_id'),'id');kind=str(p.get('kind') or '').strip().casefold();vis=str(p.get('visibility') or 'private').strip().casefold();label=' '.join(str(p.get('label') or '').split())[:160];role=_role(p.get('owner_role'))
  if kind not in _KINDS or vis not in _VIS or not label or '/' in label or '\\' in label:raise IntakeWorkbenchError('favorite_invalid')
  row={'favorite_id':fid,'kind':kind,'label':label,'target':self._target(kind,p.get('target')),'visibility':vis,'owner_role':role,'created_at':_now(),'review_required':True,'notice':'A favorite is an encrypted local shortcut. Visibility is a local role filter, not a legal access decision or identity proof.'}
  with exclusive_file_lock(self.lock):
   s=self._load()
   if fid in s['favorites']:raise IntakeWorkbenchError('favorite_id_exists',409)
   s['favorites'][fid]=row;e=self._event(s,'favorite_created',fid,{'kind':kind,'visibility':vis,'owner_role':role});self._write(s)
  return {'favorite':self._public(row),'receipt':deepcopy(e),'local_only':True,'network_used':False}
 def list(self,viewer_role):
  role=_role(viewer_role);rows=[self._public(x) for x in self._load()['favorites'].values() if self._visible(x,role)]
  return {'favorites':rows,'viewer_role':role,'role_filtering':'local_presentation_not_identity_proof','review_required':True,'local_only':True,'network_used':False}
 def get(self,fid,viewer_role):
  role=_role(viewer_role);row=self._load()['favorites'].get(_id(fid,'id'))
  if not row or not self._visible(row,role):raise IntakeWorkbenchError('favorite_not_available',404)
  return {'favorite':self._public(row),'target':deepcopy(row['target']),'review_required':True,'local_only':True,'network_used':False}
 def remove(self,fid,owner_role):
  fid=_id(fid,'id');role=_role(owner_role)
  with exclusive_file_lock(self.lock):
   s=self._load();row=s['favorites'].get(fid)
   if not row or row['owner_role']!=role:raise IntakeWorkbenchError('favorite_not_available',404)
   s['favorites'].pop(fid);e=self._event(s,'favorite_removed',fid,{'owner_role':role});self._write(s)
  return {'status':'removed_review_required','receipt':deepcopy(e),'review_required':True,'local_only':True,'network_used':False}
