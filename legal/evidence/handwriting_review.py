"""Conservative handwriting routing; never transcribes or invents text."""
from __future__ import annotations
from typing import Any
def review_handwriting(*, source_hash:str, ocr_confidence:float|None=None, handwriting_signal:bool=False)->dict[str,Any]:
 h=str(source_hash).lower()
 if len(h)!=64 or any(c not in '0123456789abcdef' for c in h): raise ValueError('handwriting_source_hash_required')
 confidence=None if ocr_confidence is None else max(0.0,min(1.0,float(ocr_confidence)))
 needs=bool(handwriting_signal or confidence is None or confidence<0.85)
 return {'status':'pass','source_hash':h,'ocr_confidence':confidence,'handwriting_signal':bool(handwriting_signal),'transcription_status':'human_transcription_required' if needs else 'review_required','notice':'This lane flags possible handwriting or uncertain OCR for human transcription review. It does not recognize handwriting, create a transcript, or substitute derived text for the original.','review_required':True}
