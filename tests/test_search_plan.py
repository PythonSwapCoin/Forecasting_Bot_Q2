from search_plan import build_search_plan


def test_build_search_plan_produces_queries_and_formalization():
    question = {
        "title": "Will Example Corp IPO by 2026?",
        "resolution_criteria": "Resolves YES if IPO before 2026-12-31",
        "fine_print": "",
    }
    plan = build_search_plan(question)
    assert plan["formalization"]["entities"]
    assert plan["historical_queries"]
    assert plan["current_queries"]
    assert plan["all_queries"]
