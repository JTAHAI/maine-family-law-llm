from legal.retrieval.authority_graph import AuthorityGraph

def test_authority_graph():
    graph = AuthorityGraph()

    graph.add_authority_relation("source-1", "source-2")

    assert graph.related_authorities("source-1") == ["source-2"]
