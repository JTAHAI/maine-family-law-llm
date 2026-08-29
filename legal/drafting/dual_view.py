"""Encrypted legal-review and plain-language document view pairs."""
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
def now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def ident(v,n):
 x=str(v or '').strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f'{n}_invalid')
 return x
def text(v,n,l=1500000):
 x=str(v or '').replace('\x00','').strip()
 if not x:raise IntakeWorkbenchError(f'{n}_required')
 if len(x)>l:raise IntakeWorkbenchError(f'{n}_too_long')
 return x
class DualViewStore:
 schema='maine_family_law_llm.dual_view.v1'
 def __init__(self,case_root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(case_root).resolve();self.root=self.case_root/'19_DRAFTING'/'dual-views'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('dual_view_store_unavailable',409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.enc=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'views.json.enc'
 @property
 def lock(self):return self.root/'.views.lock'
 def load(self):
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'views':[],'ledger':[]}
  try:s=self.enc.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('dual_view_store_unavailable',409) from e
  if s.get('schema')!=self.schema or s.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  s.setdefault('views',[]);s.setdefault('ledger',[]);return s
 def save(self,s):atomic_write_bytes(self.path,json.dumps(self.enc.encrypt_json(s),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def public(v):
  x=deepcopy(v);x.pop('scope',None);x.update({'review_required':True,'filing_ready':False,'local_only':True,'notice':'The plain-language view is a reviewer working copy, not a certified translation, legal conclusion, or filing-ready document.'});return x
 def create(self,p,document):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('dual_view_confirmation_required',409)
  vid=ident(p.get('view_id'),'view_id');reviewer=ident(p.get('reviewer_safe_id'),'reviewer_safe_id');plain=text(p.get('plain_language_text'),'plain_language_text');docid=text(document.get('document_id'),'document_id',80);rev=text(document.get('current_revision_id'),'revision_id',80);legal=text(document.get('content'),'document_content')
  refs=[deepcopy(x) for x in list(document.get('source_refs') or [])[:64] if isinstance(x,dict)]
  with exclusive_file_lock(self.lock):
   s=self.load();s['views']=[x for x in s['views'] if x.get('view_id')!=vid];v={'view_id':vid,'document_id':docid,'revision_id':rev,'legal_review_text':legal,'legal_review_sha256':hashlib.sha256(legal.encode()).hexdigest(),'plain_language_text':plain,'plain_language_sha256':hashlib.sha256(plain.encode()).hexdigest(),'source_refs':refs,'source_refs_sha256':sha(refs),'source_ref_count':len(refs),'reviewer_safe_id':reviewer,'created_at':now(),'review_required':True,'filing_ready':False};s['views'].append(v);e={'event_id':f'dual_{uuid.uuid4().hex}','at':now(),'action':'create_dual_view','view_id':vid,'revision_id':rev,'source_refs_sha256':v['source_refs_sha256'],'previous_hash':s['ledger'][-1]['hash'] if s['ledger'] else '','review_required':True};e['hash']=sha(e);s['ledger'].append(e);self.save(s);return self.public(v)
 def get(self,docid,vid,current_rev=''):
  v=next((x for x in self.load()['views'] if x.get('document_id')==docid and x.get('view_id')==vid),None)
  if not v:raise IntakeWorkbenchError('dual_view_not_found',404)
  x=self.public(v);x['current_revision_match']=x['revision_id']==current_rev;x['stale_for_current_document']=not x['current_revision_match'];return x
