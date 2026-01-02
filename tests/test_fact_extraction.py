from evidence import EvidenceItem
from fact_extraction import extract_fact_candidates


def test_extract_fact_candidates_returns_numeric_facts():
    evidence = [
        EvidenceItem(
            provider="test",
            query="revenue",
            snippet="Revenue reached 10 million USD in 2024 according to filings.",
            url="http://example.com/article",
        )
    ]
    facts = extract_fact_candidates(evidence, max_facts=5)
    assert facts, "no facts extracted"
    assert facts[0]["value_text"] == "10"
    assert facts[0]["unit"].lower().startswith("million")
