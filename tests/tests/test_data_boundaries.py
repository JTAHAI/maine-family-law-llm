from legal.data_boundaries import (
    DataClass,
    StoreName,
    can_package_by_default,
    can_store,
    can_train_by_default,
    is_private_or_sensitive,
)


def test_matter_data_is_isolated_from_authority_and_training():
    assert can_store(DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA, StoreName.MATTER).allowed
    assert not can_store(
        DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA, StoreName.OFFICIAL_AUTHORITY
    ).allowed
    assert not can_train_by_default(DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA).allowed
    assert not can_package_by_default(DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA).allowed
    assert is_private_or_sensitive(DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA)


def test_official_authority_does_not_enter_matter_store():
    assert can_store(DataClass.OFFICIAL_PUBLIC_AUTHORITY, StoreName.OFFICIAL_AUTHORITY).allowed
    assert can_store(DataClass.OFFICIAL_PUBLIC_AUTHORITY, StoreName.PARSED_AUTHORITY).allowed
    assert not can_store(DataClass.OFFICIAL_PUBLIC_AUTHORITY, StoreName.MATTER).allowed
