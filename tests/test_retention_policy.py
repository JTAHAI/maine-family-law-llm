from legal.data_boundaries import DataClass, retention_policy_for


def test_matter_data_deletion_policy_exists():
    policy = retention_policy_for(DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA)

    assert policy.delete_on_user_request is True
    assert "delete_source_file" in policy.minimum_action


def test_official_authority_snapshot_policy_is_not_user_deleted():
    policy = retention_policy_for(DataClass.OFFICIAL_PUBLIC_AUTHORITY)

    assert policy.retain == "indefinite_snapshot_history"
    assert policy.delete_on_user_request is False
