"""Fail-closed recovery report for abandoned local runtime workers."""
from __future__ import annotations
from typing import Any

_SAFE_RESTART_TYPES=frozenset({'local_ocr','batch_inference'})

class RuntimeCrashRecovery:
    def __init__(self,kernel:Any,*,matter_id:str):
        self.kernel=kernel;self.matter_id=str(matter_id or '').strip()
        if not self.matter_id: raise ValueError('crash_recovery_matter_required')
    @staticmethod
    def _public(job:dict[str,Any])->dict[str,Any]:
        return {key:job.get(key) for key in ('job_id','job_type','status','attempt','progress','created_at','updated_at','completed_at','version')}
    def recover(self)->dict[str,Any]:
        """Requeue only expired leased work; never auto-retry a terminal failure."""
        recovered_all=self.kernel.recover_expired()
        recovered=[j for j in recovered_all if str(j.get('matter_id') or '')==self.matter_id]
        jobs=self.kernel.list_jobs(matter_id=self.matter_id,limit=200)
        completed=[];discarded=[];restart=[];failed=[]
        recovered_ids={str(j.get('job_id')) for j in recovered}
        for job in jobs:
            status=str(job.get('status') or '')
            row=self._public(job)
            if status=='completed': completed.append(row)
            elif status=='cancelled': discarded.append({**row,'reason':'cancelled_before_or_during_recovery'})
            elif status=='failed': failed.append({**row,'reason':'terminal_failure_preserved_for_review'})
            elif str(job.get('job_id')) in recovered_ids and str(job.get('job_type')) in _SAFE_RESTART_TYPES:
                restart.append({**row,'restart_status':'requeued_after_expired_lease_review_required'})
            elif status in {'queued','running','cancel_requested'}:
                restart.append({**row,'restart_status':'existing_or_pending_worker_review_required'})
        return {'schema_version':'runtime_crash_recovery_v1','matter_scope':'active_matter_only','status':'recovered_review_required' if recovered else 'no_expired_worker_review_required','restarted_workers':restart,'completed_preserved':completed,'discarded_work':discarded,'terminal_failures_preserved':failed,'recovered_job_ids':sorted(recovered_ids),'automatic_terminal_retry':False,'network_used':False,'review_required':True,'notice':'Only work abandoned by an expired lease is requeued. Completed and cancelled work is preserved; terminal failures are not silently retried.'}
    def job(self,job_id:str)->dict[str,Any]:
        job=self.kernel.get_job(str(job_id or ''))
        if not job or str(job.get('matter_id') or '')!=self.matter_id: raise KeyError(job_id)
        events=self.kernel.events(str(job_id))
        return {'job':self._public(job),'events':[{'event_id':e.get('event_id'),'event_type':e.get('event_type'),'created_at':e.get('created_at')} for e in events[-40:]],'review_required':True,'network_used':False}
