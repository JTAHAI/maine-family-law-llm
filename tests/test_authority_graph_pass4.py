from legal.retrieval.authority_graph import AuthorityGraph
from legal.retrieval.authority_ranker import AuthorityRanker


def test_authority_graph_tracks_typed_relations_and_reverse_edges():
    graph = AuthorityGraph()
    graph.add_case_interprets_statute("case-1", "statute-1653")
    graph.add_case_applies_rule("case-1", "rule-52")
    graph.add_form_depends_on_authority("form-fm-002", "rule-100")

    assert graph.related_authorities("case-1") == ["statute-1653", "rule-52"]
    assert graph.outgoing("case-1", relation="interprets")[0].target_source_id == "statute-1653"
    assert graph.incoming("statute-1653", relation="interprets")[0].source_id == "case-1"
    assert graph.to_adjacency()["form-fm-002"][0]["relation"] == "depends_on"


def test_authority_ranker_orders_official_authority_above_mirrors_and_unknowns():
    ranker = AuthorityRanker()
    ranked = ranker.rank(
        [
            {"source_id": "mirror", "authority_status": "verified_public_api"},
            {"source_id": "unknown", "authority_status": "not_found"},
            {"source_id": "official", "authority_status": "verified_official_maine"},
        ]
    )

    assert [item["source_id"] for item in ranked] == ["official", "mirror", "unknown"]
