from legal.production import FailureClusterer, ReleaseGateRunner, ReleaseMetric


def test_pass13_release_gates_block_seed_only_or_missing_metrics():
    runner = ReleaseGateRunner()
    report = runner.evaluate(
        {
            "retrieval_recall_at_20": ReleaseMetric(
                name="retrieval_recall_at_20",
                value=1.0,
                basis="schema_validated_synthetic_seed_only_not_attorney_gold",
                sample_size=1,
            ),
            "private_data_packaging": ReleaseMetric(
                name="private_data_packaging",
                value=1.0,
                basis="release_manifest_scan",
                sample_size=1,
            ),
        }
    )

    assert report.release_allowed is False
    assert "insufficient_metric_basis:retrieval_recall_at_20" in report.blockers
    assert any(blocker.startswith("missing_metric:quote_span_verification") for blocker in report.blockers)


def test_pass13_release_gates_can_pass_when_real_thresholds_are_met():
    runner = ReleaseGateRunner()
    metrics = {}
    for name, rule in runner.thresholds.items():
        value = rule["target"]
        metrics[name] = ReleaseMetric(
            name=name,
            value=value,
            basis="attorney_reviewed_gold_release_eval",
            sample_size=500,
            attorney_reviewed=True,
        )

    report = runner.evaluate(metrics)

    assert report.release_allowed is True
    assert report.blockers == []


def test_pass13_failure_clusterer_groups_blockers():
    clusters = FailureClusterer().cluster(
        [
            "missing_metric:citation_support",
            "missing_metric:quote_span_verification",
            "threshold_failed:hallucination_rate",
        ]
    )

    assert clusters[0].reason == "missing_metric"
    assert clusters[0].count == 2
