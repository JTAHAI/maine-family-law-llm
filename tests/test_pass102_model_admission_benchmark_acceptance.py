from pathlib import Path
from types import SimpleNamespace
from legal.runtime.model_admission_benchmark import ModelAdmissionBenchmarkStore
class FakeRuntime:
 def preview(self,**kwargs):
  prompt=kwargs['question'];return SimpleNamespace(manifest_sha256='approved'),(),{'direct_prompt_blocked':'Ignore previous' in prompt,'document_instructions_quarantined':False}
 def run(self,request):
  answer='{"status":"ok"}' if 'JSON object' in request.question else 'Source response [1]';return SimpleNamespace(model={'provider_id':'fake','model_id':'fake','loopback_only':True},status='completed_review_required',answer=answer)
def test_pass102_benchmark_is_encrypted_review_only_not_admission(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=ModelAdmissionBenchmarkStore(root,encryption_key='fictional-test-key');r=s.run({'benchmark_id':'model_001','user_confirmed':True},FakeRuntime());assert r['admission_eligible'] is False and r['safety']['direct_prompt_blocked'] is True;assert 'model_001' not in s.path.read_text()
