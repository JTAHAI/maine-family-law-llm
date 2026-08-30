# Local r7 release-candidate status

The preserved candidate is available inside this repository at
`dist/release/v8.0.0/r7/msix/MaineFamilyLawLLM_8.0.0.0_x64.msix`.
Its SHA-256 is `bf2053b680827f87c10a413ef3ccd6e7765410a6ef149f023e17fe8714146a19`.

This is a package candidate, not an assertion of Microsoft Store or Enterprise readiness. The
exact archive and its contents passed sealed-payload, archive-diff, private-data, and bundled
engine audits. Frozen-r7 fictional checks passed for offline core workflows, durable restart,
privacy/security, backup/transfer, runtime management, and cancellation. The frozen production
UI endpoint also served the fictional fixture over loopback.

The candidate remains blocked for Store upload because the required isolated installation and
upgrade lifecycle, OS-level outbound-network proof, and WACK run have not
been completed. Microsoft Store signs submitted MSIX packages; the absence of a local
production signature is not itself a Store-upload blocker. The complete post-repair
Python regression passed: 2,283 passed and 22 skipped.
A Store update also needs a version greater than an already-published `8.0.0.0` package. WACK is
installed on this host but needs elevation.

The separate fast-interchange adapter pack is not bundled or admitted: it consists of
development protocol/safety adapters and is not represented as a substantive Maine-law model.

The full machine-readable evidence is in
`dist/ga_today/evidence/08_r7_release_candidate_summary.json`.
