# v5.19.0 GA Shipment Readiness

v5.19.0 implements the software-side operations for planned Pass 51. It binds a frozen Pass 50 candidate to the final GA artifact inventory, ten GA-definition controls, a qualified release channel, rollback evidence, blocker closure, and immutable shipment-readiness packets.

## Boundary

The application never sets `pass51_complete` to true. A software-side pass means only that the recorded inventory and controls are structurally complete and ready for independent external shipment verification. It does not prove Store approval, production deployment, attorney/legal approval, or that GA shipped.

## External root

Set `MAINE_FAMILY_LAW_RELEASE_ROOT` to a directory outside the source repository. The shipment ledger and evidence packets are written only there.

## Required artifacts

The workflow records the fourteen artifact classes defined by `GAShipmentAuditor`, including clean source, external legal data, parsed authority, retrieval indexes, attorney-reviewed gold data, metrics, security/governance, guides, and maintenance runbooks.

## Required controls

All ten GA-definition controls require explicit evidence hashes. Missing or false controls block readiness.

## Release channel

A shipment selects exactly one channel: source release, Microsoft Store, or enterprise managed. Qualification, rollback, distribution reference, package hash, and receipt hashes are recorded without being independently certified by the application.
