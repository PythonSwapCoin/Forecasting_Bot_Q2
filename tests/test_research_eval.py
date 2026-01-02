from research_eval import score_retrieval


def test_score_retrieval_computes_recall():
    report = {"evidence": [{"snippet": "binary benchmark question"}], "formatted": ""}
    key_facts = ["binary benchmark question", "missing fact"]
    scores = score_retrieval(report, key_facts)
    assert scores["recall"] == 0.5
    assert len(scores["found"]) == 1
