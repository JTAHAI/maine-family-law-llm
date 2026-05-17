#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import EnterprisePreflightRunner, ReleaseProvenanceBuilder
from legal.release import PublicRepoReadinessAuditor
from legal.resources import OfflineValidationPackBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-GA enterprise hardening evidence bundle.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--data-root", default="/tmp/maine-family-law-llm-post-ga-hardening-data")
    parser.add_argument("--output", default="smoke_evidence_post_ga_enterprise_hardening.json")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    data_root = Path(args.data_root).expanduser().resolve()
    preflight = EnterprisePreflightRunner(repo_root=repo_root, data_root=data_root).run(create_external_dirs=True)
    offline_pack = OfflineValidationPackBuilder(data_root=data_root).build()
    public_release = PublicRepoReadinessAuditor(project_root=repo_root).audit()
    provenance = ReleaseProvenanceBuilder(project_root=repo_root).build()
    status = "pass" if all(
        item == "pass"
        for item in [preflight.status, offline_pack.status, public_release.status, provenance.status]
    ) else "fail"
    evidence = {
        "status": status,
        "preflight": preflight.as_dict(),
        "offline_validation_pack": offline_pack.as_dict(),
        "public_release_readiness": public_release.as_dict(),
        "release_provenance": {
            k: v for k, v in provenance.as_dict().items() if k != "artifacts"
        },
        "interpretation": "Post-GA hardening passes are source/local-readiness controls. Production legal readiness still requires live external data and signoffs.",
    }
    out = Path(args.output)
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
