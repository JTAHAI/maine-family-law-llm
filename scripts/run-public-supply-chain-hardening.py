#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import SupplyChainAuditor
from legal.release import AttributionKitBuilder, PublicRepoReadinessAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run public/GitHub supply-chain and attribution hardening checks.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "smoke_evidence_public_supply_chain_hardening.json"))
    parser.add_argument("--sbom-output", default=str(ROOT / "docs" / "sample-evidence" / "source_sbom.json"))
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    attribution = AttributionKitBuilder(project_root=project_root).build(write=True)
    supply_chain = SupplyChainAuditor(project_root=project_root).audit(write_sbom=True, output_path=args.sbom_output)
    public_readiness = PublicRepoReadinessAuditor(project_root=project_root).audit()
    status = "pass" if all(item == "pass" for item in [attribution.status, supply_chain.status, public_readiness.status]) else "fail"
    evidence = {
        "status": status,
        "attribution_kit": attribution.as_dict(),
        "supply_chain": {k: v for k, v in supply_chain.as_dict().items() if k != "sbom"},
        "public_repo_readiness": public_readiness.as_dict(),
        "interpretation": "Public source, attribution, and supply-chain hardening only. Legal production readiness still requires external live authority/evals/signoffs.",
    }
    out = Path(args.output)
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
