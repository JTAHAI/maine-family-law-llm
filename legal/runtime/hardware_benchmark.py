"""Local-only bounded hardware measurement with explicit no-model-throughput fallback."""
from __future__ import annotations
import hashlib,json,os,platform,shutil,time
from datetime import UTC,datetime
from pathlib import Path
from typing import Any
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _id(v):
 x=str(v or '').strip().casefold()
 if not x or len(x)>80 or not all(c.isalnum() or c in '_-' for c in x):raise IntakeWorkbenchError('hardware_benchmark_id_invalid')
 return x
class HardwareBenchmarkStore:
 schema='maine_family_law_llm.hardware_benchmark.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):
  self.root=Path(root).resolve()/'40_RUNTIME'/'hardware-benchmarks';self.key=encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me';self.encryptor=LocalEnvelopeEncryptor(self.key)
 @property
 def path(self):return self.root/'benchmarks.json.enc'
 @property
 def lock(self):return self.root/'.benchmarks.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'rows':[],'revision':0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=2*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('hardware_benchmark_store_unavailable',409) from e
  if v.get('schema')!=self.schema:raise IntakeWorkbenchError('hardware_benchmark_store_unavailable',409)
  return v
 def run(self,p:dict[str,Any]):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('hardware_benchmark_confirmation_required',409)
  bench_id=_id(p.get('benchmark_id'));start=time.perf_counter();payload=b'local-hardware-probe';count=0
  while time.perf_counter()-start<0.025:payload=hashlib.sha256(payload).digest();count+=1
  total=shutil.disk_usage(Path.cwd().anchor or Path.cwd());ram={}
  try:
   import psutil # type: ignore
   memory=psutil.virtual_memory();ram={'total_bytes':int(memory.total),'available_bytes':int(memory.available)}
  except Exception:ram={'status':'unavailable'}
  cpu=os.cpu_count() or 1;free=int(total.free);setting={'max_parallel_workers':1 if cpu<4 else min(4,cpu//2),'low_memory_mode_recommended':bool(isinstance(ram.get('available_bytes'),int) and ram['available_bytes']<4*1024**3),'retrieval_batch_size':8 if cpu<4 else 32}
  row={'benchmark_id':bench_id,'at':_now(),'system':{'platform':platform.platform(aliased=True,terse=True),'machine':platform.machine(),'processor':platform.processor(),'cpu_logical_cores':cpu,'ram':ram,'storage':{'free_bytes':free,'total_bytes':int(total.total)}},'cpu_hash_probe_per_second':round(count/max(time.perf_counter()-start,0.001),2),'gpu':{'status':'not_measured','reason':'no admitted local GPU probe configured'},'model_throughput':{'status':'not_measured','reason':'no admitted model runtime was invoked'},'bounded_recommendation':setting,'review_required':True,'local_only':True,'network_used':False};row['receipt_hash']=_dig(row)
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get('benchmark_id')==bench_id for x in state['rows']):raise IntakeWorkbenchError('hardware_benchmark_id_exists',409)
   state['rows'].append(row);state['revision']=int(state.get('revision') or 0)+1;atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(state),sort_keys=True).encode(),mode=0o600)
  return row
 def get(self,bid):
  row=next((x for x in self._load()['rows'] if x.get('benchmark_id')==_id(bid)),None)
  if row is None:raise IntakeWorkbenchError('hardware_benchmark_not_found',404)
  return row
