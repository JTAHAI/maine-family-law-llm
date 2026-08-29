"""Encrypted matter labels with collision-safe migration and audit history."""
from __future__ import annotations
import hashlib,json,os,re,unicodedata
from copy import deepcopy
from datetime import UTC,datetime
from pathlib import Path
from typing import Any
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
_ID=re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{1,119}\Z");_HASH=re.compile(r"[0-9a-f]{64}\Z");_COLOR=re.compile(r"#[0-9a-fA-F]{6}\Z")
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def _dig(v):return hashlib.sha256(_canon(v)).hexdigest()
def _id(v,label):
 x=str(v or '').strip()
 if not _ID.fullmatch(x) or '..' in x or '/' in x or '\\' in x:raise IntakeWorkbenchError(f'user_label_{label}_invalid')
 return x
def _hash(v):
 x=str(v or '').strip().casefold()
 if not _HASH.fullmatch(x):raise IntakeWorkbenchError('user_label_source_hash_invalid')
 return x
def _name(v):
 x=' '.join(unicodedata.normalize('NFKC',str(v or '')).split())[:80]
 if not x or '/' in x or '\\' in x:raise IntakeWorkbenchError('user_label_name_invalid')
 return x
def _key(name):return unicodedata.normalize('NFKC',name).casefold()
class UserLabelsStore:
 schema='maine_family_law_llm.user_labels.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):self.root=Path(root).resolve()/'40_RUNTIME'/'user-labels';self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'labels.json.enc'
 @property
 def lock(self):return self.root/'.labels.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'labels':{},'assignments':{},'events':[],'revision':0}
  try:s=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=4*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('user_labels_unavailable',409) from e
  if s.get('schema')!=self.schema:raise IntakeWorkbenchError('user_labels_unavailable',409)
  prior=''
  for event in s.get('events',[]):
   cp=dict(event);d=str(cp.pop('event_hash',''))
   if cp.get('previous_event_hash')!=prior or d!=_dig(cp):raise IntakeWorkbenchError('user_labels_history_invalid',409)
   prior=d
  return s
 def _write(self,s):atomic_write_bytes(self.path,_canon(self.encryptor.encrypt_json(s)),mode=0o600)
 def _event(self,s,a,label_id,detail):
  e={'event_id':'label_'+hashlib.sha256((a+label_id+_now()).encode()).hexdigest()[:24],'at':_now(),'action':a,'label_id':label_id,'detail':deepcopy(detail),'previous_event_hash':str(s['events'][-1].get('event_hash') or '') if s['events'] else '','review_required':True};e['event_hash']=_dig(e);s['events'].append(e);s['revision']=int(s.get('revision') or 0)+1;return e
 def _public_label(self,x):return {k:deepcopy(x.get(k)) for k in ('label_id','name','color','created_at','review_required')}
 def create(self,p):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('user_label_confirmation_required',409)
  lid=_id(p.get('label_id'),'id');name=_name(p.get('name'));color=str(p.get('color') or '#1f7a8c').strip()
  if not _COLOR.fullmatch(color):raise IntakeWorkbenchError('user_label_color_invalid')
  with exclusive_file_lock(self.lock):
   s=self._load()
   if lid in s['labels'] or any(_key(x.get('name',''))==_key(name) for x in s['labels'].values()):raise IntakeWorkbenchError('user_label_collision',409)
   row={'label_id':lid,'name':name,'color':color.lower(),'created_at':_now(),'review_required':True};s['labels'][lid]=row;e=self._event(s,'label_created',lid,{'name_key':_key(name)});self._write(s)
  return {'label':self._public_label(row),'receipt':deepcopy(e),'local_only':True,'network_used':False}
 def assign(self,label_id,p):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('user_label_assignment_confirmation_required',409)
  lid=_id(label_id,'id');record_id=_id(p.get('record_id'),'record_id');source_hash=_hash(p.get('source_hash'));key=f'{lid}:{record_id}:{source_hash}'
  with exclusive_file_lock(self.lock):
   s=self._load()
   if lid not in s['labels']:raise IntakeWorkbenchError('user_label_not_found',404)
   row={'label_id':lid,'record_id':record_id,'source_hash':source_hash,'assigned_at':_now(),'review_required':True};s['assignments'][key]=row;e=self._event(s,'label_assigned',lid,{'record_id':record_id,'source_hash':source_hash});self._write(s)
  return {'assignment':deepcopy(row),'receipt':deepcopy(e),'local_only':True,'network_used':False}
 def list(self):
  s=self._load();return {'labels':[self._public_label(x) for x in s['labels'].values()],'assignments':[deepcopy(x) for x in s['assignments'].values()],'review_required':True,'local_only':True,'network_used':False}
 def export(self,p):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('user_label_export_confirmation_required',409)
  s=self._load();payload={'schema':'maine_family_law_llm.user_labels_export.v1','labels':[self._public_label(x) for x in s['labels'].values()],'assignments':[deepcopy(x) for x in s['assignments'].values()]};payload['sha256']=_dig(payload);return {'export':payload,'review_required':True,'local_only':True,'network_used':False}
 def import_export(self,p):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('user_label_import_confirmation_required',409)
  exp=p.get('export');strategy=str(p.get('collision_strategy') or 'rename').casefold()
  if not isinstance(exp,dict) or exp.get('schema')!='maine_family_law_llm.user_labels_export.v1' or strategy not in {'rename','skip'}:raise IntakeWorkbenchError('user_label_import_invalid')
  labels=exp.get('labels');assignments=exp.get('assignments')
  if not isinstance(labels,list) or not isinstance(assignments,list) or len(labels)>200 or len(assignments)>5000:raise IntakeWorkbenchError('user_label_import_invalid')
  imported=[];skipped=[]
  with exclusive_file_lock(self.lock):
   s=self._load();existing={_key(x.get('name','')) for x in s['labels'].values()};mapping={}
   for raw in labels:
    try:old=_id(raw.get('label_id'),'id');name=_name(raw.get('name'));color=str(raw.get('color') or '#1f7a8c');
    except IntakeWorkbenchError:skipped.append(str(raw.get('label_id') or 'invalid'));continue
    lid=old;count=1
    while lid in s['labels'] or _key(name) in existing:
     if strategy=='skip':skipped.append(old);lid='';break
     count+=1;lid=f'{old}_{count}';name=f'{name} ({count})'
    if not lid:continue
    row={'label_id':lid,'name':name,'color':color if _COLOR.fullmatch(color) else '#1f7a8c','created_at':_now(),'review_required':True};s['labels'][lid]=row;existing.add(_key(name));mapping[old]=lid;imported.append(lid);self._event(s,'label_imported',lid,{'source_label_id':old,'strategy':strategy})
   for raw in assignments:
    if not isinstance(raw,dict) or str(raw.get('label_id') or '') not in mapping:continue
    try:lid=mapping[str(raw['label_id'])];rid=_id(raw.get('record_id'),'record_id');h=_hash(raw.get('source_hash'))
    except IntakeWorkbenchError:continue
    s['assignments'][f'{lid}:{rid}:{h}']={'label_id':lid,'record_id':rid,'source_hash':h,'assigned_at':_now(),'review_required':True}
   self._write(s)
  return {'imported_label_ids':imported,'skipped_label_ids':skipped,'collision_strategy':strategy,'review_required':True,'local_only':True,'network_used':False}
