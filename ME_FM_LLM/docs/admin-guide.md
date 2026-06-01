# Admin Guide

Use the admin role to manage tenants, users, RBAC, source-update status, release evidence, audit logs, and blocked exports. Admins must not override legal verifier failures into filing-ready output. Attorney override events are audit-only and never convert a failed gate into a pass.

Before any production deployment, confirm the release manifest, external data product manifest, parsed authority manifest, retrieval index manifest, gold eval manifest, release metrics, security/governance packet, pilot evidence packet, and rollback package all reference the same immutable version.
