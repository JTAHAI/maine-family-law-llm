from datetime import UTC, datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from legal.runtime.crash_recovery import RuntimeCrashRecovery
from maine_family_law_llm.runtime_kernel import DurableJobKernel
from maine_family_law_llm import api as api_module

class ExpiringKernel:
 def __init__(self,k):self.k=k
 def recover_expired(self):return self.k.recover_expired(now=datetime.now(UTC)+timedelta(minutes=20))
 def list_jobs(self,**kw):return self.k.list_jobs(**kw)
 def get_job(self,*a):return self.k.get_job(*a)
 def events(self,*a):return self.k.events(*a)

def test_pass110_requeues_expired_worker_preserves_completed_cancelled_and_failed(tmp_path:Path):
 kernel=DurableJobKernel(tmp_path/'kernel.sqlite3');matter='fictional_matter'
 expired=kernel.create_job('batch_inference',{'safe':'metadata'},matter_id=matter);kernel.claim_job(expired['job_id'],'worker',lease_seconds=15)
 completed=kernel.create_job('batch_inference',{'safe':'metadata'},matter_id=matter);kernel.claim_job(completed['job_id'],'worker2');kernel.finish_job(completed['job_id'],'worker2',result={'status':'complete'})
 cancelled=kernel.create_job('batch_inference',{'safe':'metadata'},matter_id=matter);kernel.request_cancel(cancelled['job_id'])
 failed=kernel.create_job('batch_inference',{'safe':'metadata'},matter_id=matter);kernel.claim_job(failed['job_id'],'worker3');kernel.finish_job(failed['job_id'],'worker3',error={'code':'fictional_failure'})
 report=RuntimeCrashRecovery(ExpiringKernel(kernel),matter_id=matter).recover()
 assert expired['job_id'] in report['recovered_job_ids']
 assert any(x['job_id']==completed['job_id'] for x in report['completed_preserved'])
 assert any(x['job_id']==cancelled['job_id'] for x in report['discarded_work'])
 assert any(x['job_id']==failed['job_id'] for x in report['terminal_failures_preserved'])
 assert RuntimeCrashRecovery(ExpiringKernel(kernel),matter_id=matter).job(expired['job_id'])['job']['status']=='queued'

def test_pass110_api_is_matter_scoped_and_ui_is_shipped(monkeypatch,tmp_path:Path):
 a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir();active={'root':a};kernel=DurableJobKernel(tmp_path/'kernel.sqlite3')
 monkeypatch.setattr(api_module,'active_case_root',lambda:active['root']);monkeypatch.setattr(api_module,'get_runtime_kernel',lambda:kernel);c=TestClient(api_module.app)
 assert c.post('/api/runtime/crash-recovery').status_code==200
 active['root']=b;assert c.post('/api/runtime/crash-recovery').json()['matter_scope']=='active_matter_only'
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert 'Runtime crash recovery' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
