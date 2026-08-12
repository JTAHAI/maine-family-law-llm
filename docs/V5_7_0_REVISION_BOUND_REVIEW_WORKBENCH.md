# v5.7.0 Revision-Bound Review Workbench

The review workbench binds four things into one packet: the current document revision, deterministic authority verification, indexed private-record fact matches, and filing-gate blockers.

## Trust model

The host—not the model—builds the packet. The reviewer receives a one-use confirmation capability. On commit, the host verifies that the document revision has not changed, recomputes the filing gate with human review recorded, and appends a hash-chained decision. An approval can complete human review but cannot turn a failed legal or evidentiary gate into a pass.

## Local API

- `POST /api/document-workspace/documents/{document_id}/review/prepare`
- `POST /api/document-workspace/documents/{document_id}/review/commit`
- `GET /api/document-workspace/documents/{document_id}/reviews`
- `GET /api/document-workspace/documents/{document_id}/reviews/verify`
