from legal.release.release_manifest import ReleaseManifest


def test_release_manifest_blocks_canonical_store_inside_repo(tmp_path):
    (tmp_path / "matter_store").mkdir()
    (tmp_path / "matter_store" / "client.txt").write_text("private", encoding="utf-8")

    manifest = ReleaseManifest(project_root=tmp_path).generate()

    assert manifest["contains_private_data"] is True
    assert manifest["data_boundary_status"] == "fail"


def test_release_manifest_reports_pass_without_runtime_stores(tmp_path):
    (tmp_path / "README.md").write_text("ok", encoding="utf-8")

    manifest = ReleaseManifest(project_root=tmp_path).generate()

    assert manifest["contains_private_data"] is False
    assert manifest["data_boundary_status"] == "pass"
