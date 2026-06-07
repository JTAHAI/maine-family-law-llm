from legal.conversation import AudienceRouter


def test_audience_router_normalizes_aliases() -> None:
    router = AudienceRouter()
    assert router.normalize_audience("lawyer") == "attorney"
    assert router.normalize_audience("pro-se") == "self_represented"
    assert router.normalize_audience("mystery-role") == "unknown"


def test_audience_router_defaults_unknown_to_safe_plain_language() -> None:
    router = AudienceRouter()
    routed = router.route(user_role="mystery-role", task_type="query")
    assert routed.audience == "unknown"
    assert routed.mode == "self_represented_plain_language"
