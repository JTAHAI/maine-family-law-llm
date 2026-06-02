# v1.84 chat appeals routing and runtime diagnostics pass

This pass fixes a live usability defect found during local testing: the question `What court handles appeals?` was incorrectly routed to a parenting/contact schedule answer. The workbench now has a source-backed appeals-routing library item and regression tests for that exact question.

## Changes

- Added `parent_appeals_court_routing` to the deterministic chat library.
- Added local fixture source entries for:
  - Maine Judicial Branch Appeals page.
  - Maine Rules of Appellate Procedure.
- Added an appeals starter prompt to the local browser UI.
- Added `/api/runtime-diagnostics` to prove which package/UI version is actually running.
- Added visible runtime diagnostics panel in the workbench.
- Updated UI version marker to `1.84.0-appeals-routing-runtime-diagnostics`.
- Added tests in `tests/test_appeals_routing_runtime_v184.py`.

## Safety notes

- Appeal questions are time-sensitive and require qualified review.
- The answer is legal information only, not legal advice.
- No attorney review, legal signoff, production GA, real-matter pilot, or filing-ready status is claimed.
