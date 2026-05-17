from legal.data_boundaries import StoreName, all_store_paths, store_path


def test_all_canonical_stores_are_declared(tmp_path):
    stores = all_store_paths(project_root=tmp_path)
    names = {store.name for store in stores}

    assert names == set(StoreName)


def test_matter_and_audit_stores_require_encryption(tmp_path):
    matter = store_path(StoreName.MATTER, project_root=tmp_path)
    audit = store_path(StoreName.AUDIT, project_root=tmp_path)
    official = store_path(StoreName.OFFICIAL_AUTHORITY, project_root=tmp_path)

    assert matter.encrypted_required is True
    assert audit.encrypted_required is True
    assert official.encrypted_required is False
    assert matter.packaged_allowed is False
