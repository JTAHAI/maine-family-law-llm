from legal.release.release_manifest import ReleaseManifest

def test_release_manifest():
    manifest = ReleaseManifest().generate()

    assert manifest["contains_private_data"] is False
