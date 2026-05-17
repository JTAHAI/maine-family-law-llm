from pathlib import Path

from legal.release import PostGARepoReviewer

ROOT = Path(__file__).resolve().parents[1]


def test_post_ga_review_separates_source_foundation_from_real_ga_readiness(tmp_path):
    report = PostGARepoReviewer(
        project_root=ROOT,
        data_root=tmp_path / "missing_external_data_root",
        eval_root=ROOT / "eval_data",
    ).review().as_dict()

    assert report["status"] == "pass"
    assert report["numbered_pass_foundations_complete"] is True
    assert report["production_ready"] is False
    assert report["production_status"] == "blocked_real_build_path_required"
    assert report["fixture_evidence_detected"] is True
    assert "fixture_evidence_must_be_replaced_before_real_ga" in report["blockers"]
    assert any(blocker.startswith("authority:") for blocker in report["blockers"])
    assert any(blocker.startswith("release_metric:") for blocker in report["blockers"])
    assert [stage["stage_id"] for stage in report["build_path"]][:3] == ["B1", "B2", "B3"]


def test_post_ga_review_enforces_single_pass_txt_log():
    report = PostGARepoReviewer(project_root=ROOT).review().as_dict()

    assert report["single_pass_log_present"] is True
    assert report["only_one_pass_txt_file"] is True
