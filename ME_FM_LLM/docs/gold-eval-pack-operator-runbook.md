# Pass 27 Gold Eval Pack Operator Runbook

Pass 27 is not a source-only pass. It closes only when attorney-reviewed gold JSONL datasets meet the configured minimums and `audit-gold-eval-pack --require-ready` passes.

## Inputs

- `D:\dev\ME_FM_LLM_data\eval_store\gold_annotation_queue.csv`
- `D:\dev\ME_FM_LLM_data\eval_store\gold_annotation_queue.jsonl`

The queue is not gold. Reviewers must fill the required gold fields, mark rows `attorney_reviewed_final`, and keep `private_data_allowed_for_training` false.

Required gold fields:

- `source_id`
- `source_class`
- `jurisdiction`
- `text_span`
- `label`
- `annotator_or_generation_method`
- `confidence`
- `hash`
- `created_at`
- `review_status`
- `private_data_allowed_for_training`

## Promote reviewed queue rows

```powershell
cd D:\dev\ME_FM_LLM

python .\scripts\promote-reviewed-gold-annotations.py `
  --reviewed-queue D:\dev\ME_FM_LLM_data\eval_store\gold_annotation_queue.reviewed.jsonl `
  --eval-root D:\dev\ME_FM_LLM_data\eval_store `
  --output-report D:\dev\ME_FM_LLM_data\eval_store\gold_promotion_report.json `
  --require-promoted
```

## Build and audit the gold pack

```powershell
python .\scripts\build-gold-eval-pack-manifest.py `
  --eval-root D:\dev\ME_FM_LLM_data\eval_store `
  --output D:\dev\ME_FM_LLM_data\eval_store\gold_eval_pack_manifest.json `
  --require-ready

python .\scripts\audit-gold-eval-pack.py `
  --eval-root D:\dev\ME_FM_LLM_data\eval_store `
  --require-ready > D:\dev\ME_FM_LLM_data\eval_store\gold_eval_pack_audit.json
```

## Pass 27 evidence to upload

```powershell
Compress-Archive `
  -Path D:\dev\ME_FM_LLM_data\eval_store\gold_promotion_report.json, `
        D:\dev\ME_FM_LLM_data\eval_store\gold_eval_pack_manifest.json, `
        D:\dev\ME_FM_LLM_data\eval_store\gold_eval_pack_audit.json `
  -DestinationPath D:\dev\ME_FM_LLM_PASS_27_EVIDENCE.zip `
  -Force
```

Upload `D:\dev\ME_FM_LLM_PASS_27_EVIDENCE.zip` after the audit exits cleanly.
