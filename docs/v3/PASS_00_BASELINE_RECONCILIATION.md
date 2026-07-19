# Pass 00 — Baseline Reconciliation

## Result

The uploaded review package contained two complete product trees:

- canonical root working tree at application v2.09.2 / MSIX 2.9.2.0;
- nested `ME_FM_LLM/` tree at application v2.14.0 with an independent set of later changes.

The nested tree was not merged automatically. It contained unique startup-intake, disclosure, privacy, verification, and release-candidate files, plus many files that differed from the certified-root lineage. Blindly deleting it would lose work; blindly merging it would risk reintroducing behavior that was not part of the certified v2.09.2 chat fixes.

## Reconciliation action

- The root v2.09.2 tree is the canonical v3 starting point.
- The nested v2.14.0 tree is removed from the canonical repository directory.
- The complete nested tree is preserved unchanged as `REFERENCE_SNAPSHOT/ME_FM_LLM_v2.14.0_unmerged_reference.zip` beside the returned repository.
- A comparison report identifies root-only, reference-only, and differing files.
- Later v3 passes may deliberately port useful v2.14.0 security, privacy, intake, and release controls after file-by-file review.


## Targeted baseline hardening ported from the preserved reference

A small set of independently reviewable hygiene fixes was ported rather than merging the reference tree:

- legitimate Store listing and build requirement `.txt` assets are explicitly allowlisted by public-source readiness policy;
- pass-log discipline continues to require only `PASS_CHANGES.txt` outside the Store asset tree;
- reboot-recovery and local repository doctor checks recognize approved Store text assets while still rejecting unapproved text artifacts; and
- local development certificate passwords are generated ephemerally instead of using a literal password in `build-msix.ps1`.

These changes repair source-readiness false positives without importing the reference tree’s unrelated runtime and product behavior.

## Test repair

`tests/test_public_workbench_ux_upgrades_v209.py` previously required the deleted `context-bar`. It now verifies the actual compact session summary, explicit search mode, and absence of giant context chips.

## Approved additions captured

- Permanent slim `WE THE PEOPLE … establish JUSTICE …` identity
- Accessible mission statement popover
- Visible Ctrl+K command-palette shortcut
- Ctrl+J Constitution/Justice easter egg
- Constitutional delight system with accessibility and safety guardrails

## Version boundary

Pass 00 changes repository organization, requirements, and tests only. It does not rebuild or change the certified product version. The rollback baseline remains:

- Application: 2.09.2
- MSIX: 2.9.2.0

Pass 01 begins the v3 implementation and product version 3.0.0 build series.
