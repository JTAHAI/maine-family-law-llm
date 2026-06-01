# Release metrics measurement workbench

Pass 28 is blocked until task-specific evaluators measure GA metrics over attorney-reviewed gold JSONL rows. This workbench gives operators a fail-closed measurement template and audit command.

Build the external measurement template:

```powershell
python .\scripts\build-release-metric-measurement-template.py --output D:\dev\ME_FM_LLM_data\eval_store\release_metric_measurements.json
```

After evaluators fill numeric values, sample sizes, reviewer status, basis, and source dataset fields, audit it:

```powershell
python .\scripts\audit-release-metric-measurements.py --measurement-path D:\dev\ME_FM_LLM_data\eval_store\release_metric_measurements.json --output D:\dev\ME_FM_LLM_data\eval_store\release_metric_measurement_audit.json --require-ready
```

Then build release evidence:

```powershell
python .\scripts\run-release-metrics-evidence.py --eval-root D:\dev\ME_FM_LLM_data\eval_store --output D:\dev\ME_FM_LLM_data\release_metrics_evidence.json --require-ready
```

The audit rejects repo-local, seed, synthetic, fixture, smoke, source-derived, undersized, missing-review, and wrong-dataset measurements. It does not fabricate any metric values.
