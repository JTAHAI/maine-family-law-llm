"""Encrypted reviewer rationales attached to exact local document revisions."""
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
_ID=re.compile(r"[a-z][a-z0-9_-]{2,79}\Z"); _IMPACTS={"not_run","needs_recheck","no_known_verifier_change","introduced_support_gap","introduced_citation_change"}
def _now()->str:return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _sha(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _id(v:Any,n:str)->str:
 x=str(v or '').strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f'{n}_invalid')
 return x
def _text(v:Any,n:str,limit:int=2000)->str:
 x=' '.join(str(v or '').replace('\x00','').split())
 if not x:raise IntakeWorkbenchError(f'{n}_required')
 if len(x)>limit:raise IntakeWorkbenchError(f'{n}_too_long')
 return x
class RevisionRationaleStore:
 schema='maine_family_law_llm.revision_rationale.v1'
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/'19_DRAFTING'/'revision-rationales'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('revision_rationale_store_unavailable',409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self)->Path:return self.root/'rationales.json.enc'
 @property
 def lock(self)->Path:return self.root/'.rationales.lock'
 def _load(self)->dict[str,Any]:
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'rationales':[],'ledger':[],'revision':0}
  try:s=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('revision_rationale_store_unavailable',409) from e
  if s.get('schema')!=self.schema or s.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  s.setdefault('rationales',[]);s.setdefault('ledger',[]);return s
 def _save(self,s:dict[str,Any])->None:atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(s),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _public(row:dict[str,Any])->dict[str,Any]:
  x=deepcopy(row);x.pop('scope',None);x.update({'status':'review_required','review_required':True,'filing_ready':False,'local_only':True,'notice':'A reviewer rationale records why a revision needs review. It does not verify support, decide facts or law, or approve filing.'});return x
 def record(self,payload:dict[str,Any],*,document:dict[str,Any])->dict[str,Any]:
  if payload.get('user_confirmed') is not True:raise IntakeWorkbenchError('revision_rationale_confirmation_required',409)
  doc_id=_text(document.get('document_id'),'document_id',80);rev_id=_text(document.get('current_revision_id'),'revision_id',80);reviewer=_id(payload.get('reviewer_safe_id'),'reviewer_safe_id');reason=_text(payload.get('reason'),'revision_reason',4000);summary=_text(payload.get('change_summary'),'change_summary',2000);impact=str(payload.get('verifier_impact') or 'not_run').strip().casefold()
  if impact not in _IMPACTS:raise IntakeWorkbenchError('verifier_impact_invalid')
  claims=[]
  for raw in list(payload.get('affected_claim_ids') or [])[:100]:
   claim=_text(raw,'affected_claim_id',120)
   if claim not in claims:claims.append(claim)
  rid='rationale_'+_sha({'doc':doc_id,'rev':rev_id,'reason':reason,'summary':summary})[:24]
  with exclusive_file_lock(self.lock):
   s=self._load();s['rationales']=[r for r in s['rationales'] if r.get('rationale_id')!=rid];row={'rationale_id':rid,'document_id':doc_id,'revision_id':rev_id,'document_content_sha256':hashlib.sha256(str(document.get('content') or '').encode()).hexdigest(),'reviewer_safe_id':reviewer,'change_summary':summary,'reason':reason,'affected_claim_ids':claims,'verifier_impact':impact,'created_at':_now(),'review_required':True,'filing_ready':False};s['rationales'].append(row);prior=str(s['ledger'][-1].get('event_hash') or '') if s['ledger'] else '';event={'event_id':f'rationale_{uuid.uuid4().hex}','at':_now(),'action':'record_revision_rationale','rationale_id':rid,'previous_event_hash':prior,'review_required':True};event['event_hash']=_sha(event);s['ledger'].append(event);s['revision']=int(s.get('revision') or 0)+1;self._save(s);return self._public(row)
 def list(self,document_id:str)->dict[str,Any]:return {'rationales':[self._public(r) for r in self._load()['rationales'] if r.get('document_id')==document_id],'review_required':True,'local_only':True}
