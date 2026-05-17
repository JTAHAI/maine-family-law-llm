from __future__ import annotations

from legal.connectors import load_official_source_targets
from legal.production import EnterpriseDataProductAuditor, ReleaseGateRunner, ReleaseMetric


def test_pass16_expanded_source_catalog_has_enterprise_coverage():
    targets = load_official_source_targets()
    by_class: dict[str, int] = {}
    for target in targets:
        by_class[target.source_class] = by_class.get(target.source_class, 0) + 1

    assert by_class["statute_title_index"] >= 8
    assert by_class["statute_title_pdf"] >= 8
    assert by_class["court_rules_index"] >= 4
    assert by_class["court_forms_index"] >= 1
    assert by_class["law_court_opinion_index"] >= 7
    assert all("maine.gov" in target.url or "courts.maine.gov" in target.url for target in targets)


def test_pass16_enterprise_data_product_gate_blocks_seed_eval_rows():
    report = EnterpriseDataProductAuditor().run()

    assert report.status == "pass"
    assert report.production_ready is False
    assert any(blocker.startswith("gold_rows_minimum_not_met") for blocker in report.blockers)
    retrieval = next(item for item in report.datasets if item.dataset == "maine_rag_retrieval_gold.jsonl")
    assert retrieval.rows == 1
    assert retrieval.minimum_rows == 500
    assert retrieval.status == "blocked_minimum_rows"


def test_pass16_release_gates_block_real_metrics_without_attorney_review():
    runner = ReleaseGateRunner()
    metrics = {
        name: ReleaseMetric(
            name=name,
            value=0.0 if rule["operator"] in {"<=", "=="} and rule["target"] == 0.0 else rule["target"],
            basis="real_release_eval_file",
            sample_size=max(int(rule.get("minimum_sample_size", 1)), 500),
            attorney_reviewed=False,
        )
        for name, rule in runner.thresholds.items()
    }
    for name, rule in runner.thresholds.items():
        if rule["operator"] == "==" and rule["target"] == 1.0:
            metrics[name] = ReleaseMetric(
                name=name,
                value=1.0,
                basis="real_release_eval_file",
                sample_size=max(int(rule.get("minimum_sample_size", 1)), 500),
                attorney_reviewed=False,
            )

    report = runner.evaluate(metrics)

    assert report.release_allowed is False
    assert "attorney_review_missing:retrieval_recall_at_20" in report.blockers
    assert "attorney_review_missing:citation_support" in report.blockers


def test_pass16_release_gates_block_undersized_real_samples():
    runner = ReleaseGateRunner()
    metric = ReleaseMetric(
        name="retrieval_recall_at_20",
        value=1.0,
        basis="real_release_eval_file",
        sample_size=25,
        attorney_reviewed=True,
    )
    report = runner.evaluate({"retrieval_recall_at_20": metric})

    assert report.release_allowed is False
    assert "minimum_sample_size_not_met:retrieval_recall_at_20" in report.blockers
