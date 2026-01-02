from evidence import EvidenceItem
from research_metrics import canonicalize_url, compute_quality_score, compute_retrieval_kpis, hash_snippet


def test_compute_retrieval_kpis_counts_domains_and_dupes():
    evidence = [
        EvidenceItem(provider="a", query="q", url="https://a.com/1", content_hash="x1"),
        EvidenceItem(provider="a", query="q", url="https://a.com/2", content_hash="x2"),
        EvidenceItem(provider="b", query="q", url="https://b.com/3", content_hash="x1"),
    ]
    kpis = compute_retrieval_kpis(evidence)
    assert kpis["unique_domains"] == 2
    assert kpis["duplicates"] == 1
    assert "avg_quality" in kpis


def test_hash_snippet_changes_on_content():
    h1 = hash_snippet("hello")
    h2 = hash_snippet("hello world")
    assert h1 != h2


def test_compute_quality_score_prefers_trusted_domains():
    gov_item = EvidenceItem(provider="web", query="q", url="https://example.gov/news/1")
    blog_item = EvidenceItem(provider="web", query="q", url="https://substack.com/p/post")
    assert compute_quality_score(gov_item) > compute_quality_score(blog_item)
    assert canonicalize_url("https://example.com/path/") == "example.com/path"
