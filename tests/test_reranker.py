from legal.retrieval.reranker import MaineAuthorityReranker

def test_official_authority_ranks_first():
    reranker = MaineAuthorityReranker()

    results = [
        {"authority_status": "unverified"},
        {"authority_status": "verified_official_maine"},
    ]

    reranked = reranker.rerank(results)

    assert reranked[0]["authority_status"] == "verified_official_maine"