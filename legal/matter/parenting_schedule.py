"""Local, neutral schedule scenarios from source-bound terms; never determines legal effect."""
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
_SIMULATION_CATEGORIES={'parenting_time','travel','holiday','school','exchange','other'}
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
class ParentingScheduleStore:
 schema='maine_family_law_llm.parenting_schedule.v1'
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/'33_PARENTING_SCHEDULE'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('schedule_store_unavailable',409)
  self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me');self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
 @property
 def path(self):return self.root/'schedule.json.enc'
 @property
 def lock(self):return self.root/'.schedule.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'terms':[],'scenarios':[],'simulations_v2':[],'history':[],'revision':0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('schedule_store_unavailable',409) from e
  if v.get('schema')!=self.schema or v.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  v.setdefault('simulations_v2',[])
  return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 def _mut(self,a,ids,fn):
  with exclusive_file_lock(self.lock):
   v=self._load();r=fn(v);e={'event_id':f'schedule_{uuid.uuid4().hex}','at':_now(),'action':a,'ids':ids,'previous_hash':v['history'][-1]['hash'] if v['history'] else '','review_required':True};e['hash']=_h(e);v['history'].append(e);v['revision']+=1;self._save(v);return r
 def inventory(self):
  v=deepcopy(self._load());v.pop('scope',None);v.update({'status':'review_required','review_required':True,'local_only':True,'operative_interpretation':'not_determined','legal_advice':'not_available','automatic_calendar_write':False});return v
 def add_terms(self,p):
  rows=p.get('terms')
  if not isinstance(rows,list) or not rows:raise IntakeWorkbenchError('schedule_terms_invalid')
  def fn(v):
   for x in rows:
    src=x.get('source_ref') or {};v['terms'].append({'term_id':_id(x.get('term_id'),'term_id'),'exact_language':_t(x.get('exact_language')),'topic':_t(x.get('topic'),128),'source_ref':{'record_id':_id(src.get('record_id'),'record_id'),'span':_t(src.get('span'),128)},'reviewer_status':'review_required'})
   return self.inventory()
  return self._mut('terms_added',[_id(x.get('term_id'),'term_id') for x in rows if isinstance(x,dict)],fn)
 def scenario(self,p):
  sid=_id(p.get('scenario_id'),'scenario_id');terms=[_id(i,'term_id') for i in p.get('term_ids',[])];events=p.get('events',[])
  def fn(v):
   if any(x['scenario_id']==sid for x in v['scenarios']):raise IntakeWorkbenchError('duplicate_scenario_id',409)
   if not set(terms)<={x['term_id'] for x in v['terms']}:raise IntakeWorkbenchError('term_not_found',404)
   r={'scenario_id':sid,'term_ids':terms,'events':events,'holiday_conflicts':'review_required','transportation':'review_required','calendar_write':False,'review_required':True};r['scenario_hash']=_h(r);v['scenarios'].append(r);return deepcopy(r)
  return self._mut('scenario_added',[sid,*terms],fn)
 def simulate_v2(self,p,*,records):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('schedule_simulation_confirmation_required',409)
  sid=_id(p.get('simulation_id'),'simulation_id');rows=p.get('scenarios')
  if not isinstance(rows,list) or len(rows)<2 or len(rows)>5:raise IntakeWorkbenchError('schedule_simulation_scenarios_invalid')
  available={str(x.get('evidence_id') or x.get('source_id') or ''):x for x in records if isinstance(x,dict)}
  scenarios=[]
  for raw in rows:
   events=raw.get('events') if isinstance(raw,dict) else None
   if not isinstance(events,list) or not events or len(events)>100:raise IntakeWorkbenchError('schedule_simulation_events_invalid')
   clean=[]
   for event in events:
    source=(event or {}).get('source_ref') or {};rid=str(source.get('record_id') or '');digest=str(source.get('source_hash') or '').casefold();record=available.get(rid)
    if not rid or not re.fullmatch(r'[a-f0-9]{64}',digest) or record is None or str(record.get('source_hash') or record.get('sha256') or '').casefold()!=digest:raise IntakeWorkbenchError('schedule_simulation_source_not_in_active_matter',404)
    category=str(event.get('category') or 'other').strip().casefold()
    if category not in _SIMULATION_CATEGORIES:raise IntakeWorkbenchError('schedule_simulation_category_invalid')
    clean.append({'date_candidate':_t(event.get('date_candidate'),64),'label':_t(event.get('label'),300),'category':category,'source_ref':{'record_id':rid,'source_hash':digest},'review_required':True})
   scenarios.append({'scenario_id':_id(raw.get('scenario_id'),'schedule_scenario_id'),'label':_t(raw.get('label'),300),'events':clean})
  dates={}
  for sc in scenarios:
   for e in sc['events']:dates.setdefault(e['date_candidate'],[]).append(sc['scenario_id'])
  result={'simulation_id':sid,'reviewer_safe_id':_id(p.get('reviewer_safe_id'),'reviewer_safe_id'),'scenarios':scenarios,'date_overlaps':[{'date_candidate':d,'scenario_ids':x,'status':'review_required'} for d,x in dates.items() if len(set(x))>1],'recommendation':'not_available','created_at':_now(),'review_required':True,'filing_ready':False};result['simulation_hash']=_h({k:v for k,v in result.items() if k!='created_at'})
  def fn(v):
   if any(x['simulation_id']==sid for x in v['simulations_v2']):raise IntakeWorkbenchError('duplicate_simulation_id',409)
   v['simulations_v2'].append(result);return deepcopy(result)
  return self._mut('schedule_simulation_v2_added',[sid],fn)
 def simulation_v2(self,sid):
  row=next((deepcopy(x) for x in self._load()['simulations_v2'] if x.get('simulation_id')==_id(sid,'simulation_id')),None)
  if row is None:raise IntakeWorkbenchError('schedule_simulation_not_found',404)
  row.update({'status':'review_required','review_required':True,'filing_ready':False,'local_only':True,'recommendation':'not_available','notice':'This neutral schedule comparison does not recommend custody, determine legal effect, or write a calendar.'});return row
 def simulation_v2_source(self,sid,record_id):
  row=self.simulation_v2(sid);rid=str(record_id or '').strip()
  source=next((dict(event.get('source_ref') or {}) for scenario in row['scenarios'] for event in scenario.get('events',[]) if str((event.get('source_ref') or {}).get('record_id') or '')==rid),None)
  if source is None:raise IntakeWorkbenchError('schedule_simulation_source_not_found',404)
  return {'simulation_id':row['simulation_id'],'source':source,'review_required':True,'filing_ready':False}
 def receipt(self):
  v=self._load();r={'revision':v['revision'],'terms_hash':_h(v['terms']),'scenarios_hash':_h(v['scenarios']),'history_hash':_h(v['history']),'review_required':True,'issued_at':_now()};r['receipt_hash']=_h(r);return r
