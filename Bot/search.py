import asyncio
from typing import List, Dict
import sys
import os

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from FastContentExtractor import FastContentExtractor
from research_config import (
    DEFAULT_RESEARCH_SOURCE,
    ENABLE_ASKNEWS,
    ENABLE_BRIGHT_DATA,
    ENABLE_PERPLEXITY,
    ENABLE_SERPER,
    FALLBACK_TO_PERPLEXITY,
    PERPLEXITY_CALL_LIMIT,
    get_research_provider_status,
    prefer_perplexity,
)
from prompts import (
    ARTICLE_SUMMARY_PROMPT,
    context,
    CONTINUATION_SEARCH_PROMPT,
    INITIAL_SEARCH_PROMPT,
    PERPLEXITY_DEEP_RESEARCH_SYSTEM_PROMPT,
    PERPLEXITY_DEEP_RESEARCH_USER_SUFFIX,
)
import dateparser
from dotenv import load_dotenv
import json
import os
from aiohttp import ClientSession, ClientTimeout
from asknews_sdk import AskNewsSDK
from dotenv import load_dotenv
import aiohttp
import re
import random
import time
import traceback
from llm_calls import call_openrouter_gpt
from logging_utils import get_current_logger
from evidence import EvidenceItem, ResearchResult
from evidence_store import persist_research_report, persist_research_result
from replay import make_replay_key, maybe_replay_search, record_search_result
from research_metrics import canonicalize_url, compute_quality_score, compute_retrieval_kpis, hash_snippet
from fact_extraction import extract_fact_candidates
from datetime import datetime, timezone
from search_plan import build_search_plan, formalize_question
load_dotenv()

SERPER_KEY = os.getenv("SERPER_KEY")
ASKNEWS_CLIENT_ID = os.getenv("ASKNEWS_CLIENT_ID")
ASKNEWS_SECRET = os.getenv("ASKNEWS_SECRET")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")  # legacy, not required for OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
PERPLEXITY_AVAILABLE = bool(OPENROUTER_API_KEY) and ENABLE_PERPLEXITY

_perplexity_budget = {"historical": 0, "current": 0, "shared": 0}
_provider_status_logged = False


def reset_perplexity_budget(pairs: int | None = None) -> None:
    """
    Reset Perplexity call counters. By default, split an even budget into
    historical/current pairs (at least 1 each), leaving shared=0.
    """
    global _perplexity_budget
    total_limit = PERPLEXITY_CALL_LIMIT if PERPLEXITY_CALL_LIMIT > 0 else 2
    if total_limit % 2 != 0:
        total_limit -= 1
    if total_limit < 2:
        total_limit = 2
    pair_count = pairs if pairs is not None else total_limit // 2
    pair_count = max(1, pair_count)
    _perplexity_budget = {"historical": pair_count, "current": pair_count, "shared": 0}


def set_perplexity_budget(historical: int, current: int, shared: int = 0) -> None:
    """Explicitly set Perplexity budgets."""
    global _perplexity_budget
    _perplexity_budget = {
        "historical": max(0, historical),
        "current": max(0, current),
        "shared": max(0, shared),
    }


def _consume_perplexity_budget(bucket: str | None) -> bool:
    """Return True if a Perplexity call is allowed from the given bucket."""
    global _perplexity_budget
    use_bucket = bucket if bucket in _perplexity_budget else "shared"
    if _perplexity_budget.get(use_bucket, 0) <= 0:
        return False
    _perplexity_budget[use_bucket] -= 1
    return True


def _log_provider_status_once() -> None:
    """Log provider availability once per process to aid debugging."""
    global _provider_status_logged
    if _provider_status_logged:
        return
    status = get_research_provider_status()
    log(f"[provider_status] {status}", level="info")
    _provider_status_logged = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s>\"']+", text or "")
    return match.group(0) if match else None


def _make_evidence_item(
    provider: str,
    query: str,
    snippet: str | None,
    *,
    query_intent: str | None = None,
    url: str | None = None,
    title: str | None = None,
    published_at: str | None = None,
    metadata: dict | None = None,
) -> EvidenceItem:
    item = EvidenceItem(
        provider=provider,
        query=query,
        query_intent=query_intent,
        url=url,
        title=title or (snippet.splitlines()[0][:120] if snippet else query),
        snippet=snippet,
        published_at=published_at,
        retrieved_at=_now_iso(),
        content_hash=hash_snippet(snippet) or hash_snippet(url or query),
        metadata=metadata or {},
    )
    item.quality_score = compute_quality_score(item)
    return item


def _dedup_evidence_items(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    seen_hash: set[str] = set()
    seen_url: set[str] = set()
    deduped: list[EvidenceItem] = []
    for item in evidence:
        canon = canonicalize_url(item.url)
        if item.content_hash and item.content_hash in seen_hash:
            continue
        if canon and canon in seen_url:
            continue
        if item.content_hash:
            seen_hash.add(item.content_hash)
        if canon:
            seen_url.add(canon)
        deduped.append(item)
    return deduped


def _summarize_evidence_items(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "No evidence collected."
    lines = []
    for ev in evidence[:8]:
        parts = [
            ev.title or ev.query,
            ev.url or "no-url",
            f"provider={ev.provider}",
        ]
        lines.append("- " + " | ".join(parts))
    return "Evidence summary:\n" + "\n".join(lines)

def log(message: str, level: str = "info") -> None:
    logger = get_current_logger()
    logger.log(message, level=level)

def parse_date(date_str: str) -> str:
    parsed_date = dateparser.parse(date_str, settings={'STRICT_PARSING': False})
    if parsed_date:
        return parsed_date.strftime("%b %d, %Y")
    return "Unknown"

def validate_time(before_date_str, source_date_str):
    if source_date_str == "Unknown":
        return False
    before_date = dateparser.parse(before_date_str)
    source_date = dateparser.parse(source_date_str)
    return source_date <= before_date

# new helper: takes raw article text + the question_details dict
async def summarize_article(article: str, question_details: dict) -> str:
    prompt = ARTICLE_SUMMARY_PROMPT.format(
        title=question_details["title"],
        resolution_criteria=question_details["resolution_criteria"],
        fine_print=question_details["fine_print"],
        background=question_details["description"],
        article=article
    )
    return await call_gpt(prompt)


async def call_asknews(question: str) -> str:
    """
    Use the AskNews `news` endpoint to get news context for your query.
    The full API reference can be found here: https://docs.asknews.app/en/reference#get-/v1/news/search
    """
    if not ENABLE_ASKNEWS:
        return {"formatted": "AskNews disabled by config.", "evidence": []}
    if not ASKNEWS_CLIENT_ID or not ASKNEWS_SECRET:
        return {"formatted": "AskNews disabled (no credentials provided).", "evidence": []}
    try:
        ask = AskNewsSDK(
            client_id=ASKNEWS_CLIENT_ID, client_secret=ASKNEWS_SECRET, scopes=set(["news"])
        )

        async with aiohttp.ClientSession() as session:
            # Create tasks for both API calls
            hot_task = asyncio.create_task(asyncio.to_thread(ask.news.search_news,
                query=question,
                n_articles=8,
                return_type="both",
                strategy="latest news"
            ))
            historical_task = asyncio.create_task(asyncio.to_thread(ask.news.search_news,
                query=question,
                n_articles=8,
                return_type="both",
                strategy="news knowledge"
            ))

            # Wait for both tasks to complete
            hot_response, historical_response = await asyncio.gather(hot_task, historical_task)

        hot_articles = hot_response.as_dicts
        historical_articles = historical_response.as_dicts
        formatted_articles = "Here are the relevant news articles:\n\n"
        evidence_items: list[EvidenceItem] = []

        if hot_articles:
            hot_articles = [article.__dict__ for article in hot_articles]
            hot_articles = sorted(hot_articles, key=lambda x: x["pub_date"], reverse=True)

            for article in hot_articles:
                pub_date = article["pub_date"].strftime("%B %d, %Y %I:%M %p")
                formatted_articles += f"**{article['eng_title']}**\n{article['summary']}\nOriginal language: {article['language']}\nPublish date: {pub_date}\nSource:[{article['source_id']}]({article['article_url']})\n\n"
                evidence_items.append(
                    _make_evidence_item(
                        provider="asknews",
                        query=question,
                        snippet=article["summary"],
                        url=article["article_url"],
                        title=article["eng_title"],
                        published_at=article["pub_date"].isoformat() if article.get("pub_date") else None,
                        metadata={"language": article["language"], "source_id": article["source_id"]},
                    )
                )

        if historical_articles:
            historical_articles = [article.__dict__ for article in historical_articles]
            historical_articles = sorted(
                historical_articles, key=lambda x: x["pub_date"], reverse=True
            )

            for article in historical_articles:
                pub_date = article["pub_date"].strftime("%B %d, %Y %I:%M %p")
                formatted_articles += f"**{article['eng_title']}**\n{article['summary']}\nOriginal language: {article['language']}\nPublish date: {pub_date}\nSource:[{article['source_id']}]({article['article_url']})\n\n"
                evidence_items.append(
                    _make_evidence_item(
                        provider="asknews",
                        query=question,
                        snippet=article["summary"],
                        url=article["article_url"],
                        title=article["eng_title"],
                        published_at=article["pub_date"].isoformat() if article.get("pub_date") else None,
                        metadata={"language": article["language"], "source_id": article["source_id"]},
                    )
                )

        if not hot_articles and not historical_articles:
            formatted_articles += "No articles were found.\n\n"
            return {"formatted": formatted_articles, "evidence": evidence_items}

        return {"formatted": formatted_articles, "evidence": evidence_items}
    except Exception as e:
        log(f"[call_asknews] Error: {str(e)}", level="error")
        return {"formatted": f"Error retrieving news articles: {str(e)}", "evidence": []}
    

async def agentic_search(query: str, perplexity_bucket: str | None = None) -> str:
    """
    Performs agentic search using GPT to iteratively research and analyze a query.
    
    Args:
        query: The search query to research
        
    Returns:
        The final comprehensive analysis
    """
    log(f"[agentic_search] Starting research for query: {query}")
    
    max_steps = 7
    current_analysis = ""
    all_search_queries = []  # Track all queries used
    
    # Cost tracking variables
    total_input_tokens = 0
    total_output_tokens = 0

    async def _return_immediate(val: str) -> str:
        return val
    
    def estimate_tokens(text: str) -> int:
        """Estimate token count using ~4 characters per token rule for GPT models"""
        return max(1, len(text) // 4)
    
    def calculate_cost(input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage"""
        input_cost = (input_tokens / 1_000_000) * 1.100  # $1.100 per 1M input tokens
        output_cost = (output_tokens / 1_000_000) * 4.400  # $4.400 per 1M output tokens
        return input_cost + output_cost
    
    for step in range(max_steps):
        try:
            # Prepare the prompt
            if step == 0:
                prompt = INITIAL_SEARCH_PROMPT.format(query=query)
            else:
                # Build previous section
                if current_analysis:
                    previous_section = f"Your previous analysis:\n{current_analysis}\n\nPrevious search queries used: {', '.join(all_search_queries)}\n"
                else:
                    previous_section = f"Previous search queries used: {', '.join(all_search_queries)}\n"
                
                prompt = CONTINUATION_SEARCH_PROMPT.format(
                    query=query,
                    previous_section=previous_section,
                    search_results=search_results
                )
            
            # Track input tokens
            prompt_tokens = estimate_tokens(prompt)
            total_input_tokens += prompt_tokens
            
            # Call GPT for analysis and search queries
            log(f"[agentic_search] Step {step + 1}: Calling GPT")
            response = await call_gpt(prompt, step)
            
            # Track output tokens
            response_tokens = estimate_tokens(response)
            total_output_tokens += response_tokens
            
            # Parse the response
            analysis_match = re.search(r'Analysis:\s*(.*?)(?=Search queries:|$)', response, re.DOTALL)
            if not analysis_match:
                log(f"[agentic_search] Error: Could not parse analysis from response", level="error")
                return f"Error: Failed to parse analysis at step {step + 1}"
            
            # Only update current_analysis after the first search (step > 0)
            if step > 0:
                current_analysis = analysis_match.group(1).strip()
                log(f"[agentic_search] Step {step + 1}: Analysis updated ({len(current_analysis)} chars)")
            else:
                log(f"[agentic_search] Step 1: Initial query understanding complete")
            
            # Check for search queries
            search_queries_match = re.search(r'Search queries:\s*(.*)', response, re.DOTALL)
            
            # For the initial step, we expect search queries
            if step == 0 and not search_queries_match:
                log(f"[agentic_search] Error: No search queries in initial response", level="error")
                return "Error: Failed to generate initial search queries"
            
            if not search_queries_match or step == max_steps - 1:
                # No more searches needed or reached max steps
                if step > 0:  # Only break if we have an analysis
                    log(f"[agentic_search] Research complete at step {step + 1}")
                    break
            
            # Extract search queries with sources
            queries_text = search_queries_match.group(1).strip()
            # Parse format: X. [Query] (Source)
            search_queries_with_source = re.findall(r'\d+\.\s*([^(]+?)\s*\((Google|Google News|Perplexity)\)', queries_text)
            
            if not search_queries_with_source:
                if step == 0:
                    log(f"[agentic_search] Error: No valid search queries in initial response", level="error")
                    return "Error: Failed to parse initial search queries"
                else:
                    log(f"[agentic_search] No new search queries, completing research")
                    break
            
            # Limit to 5 queries and clean them up
            search_queries_with_source = [(q.strip(), source) for q, source in search_queries_with_source[:5]]
            
            log(f"[agentic_search] Step {step + 1}: Found {len(search_queries_with_source)} search queries")
            # Track just the queries for deduplication
            all_search_queries.extend([q for q, _ in search_queries_with_source])
            
            # Execute searches in parallel
            search_tasks = []
            task_sources = []
            for sq, source in search_queries_with_source:
                effective_source = "Perplexity" if prefer_perplexity() else source
                log(f"[agentic_search] Searching: {sq} (Source: {effective_source})")

                if effective_source in ("Google", "Google News"):
                    if ENABLE_SERPER and ENABLE_BRIGHT_DATA:
                        search_tasks.append(
                            google_search_agentic(
                                sq,
                                is_news=(effective_source == "Google News")
                            )
                        )
                        task_sources.append((sq, effective_source))
                    elif FALLBACK_TO_PERPLEXITY and PERPLEXITY_AVAILABLE:
                        log(f"[agentic_search] Falling back to Perplexity for query '{sq}'")
                        search_tasks.append(call_perplexity(sq, bucket=perplexity_bucket))
                        task_sources.append((sq, "Perplexity"))
                    else:
                        msg = f"<RawContent query=\"{sq}\">Search disabled by config.</RawContent>\n"
                        search_tasks.append(_return_immediate(msg))
                        task_sources.append((sq, effective_source))
                elif effective_source == "Perplexity":
                    search_tasks.append(call_perplexity(sq, bucket=perplexity_bucket))
                    task_sources.append((sq, "Perplexity"))
                elif effective_source == "Assistant":
                    search_tasks.append(call_asknews(sq))
                    task_sources.append((sq, "Assistant"))
                else:
                    msg = f"<RawContent query=\"{sq}\">Unknown source '{effective_source}'.</RawContent>\n"
                    search_tasks.append(_return_immediate(msg))
                    task_sources.append((sq, effective_source))
            
            # Gather search results
            search_results_list = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Format search results
            search_results = ""
            for (sq, source), result in zip(task_sources, search_results_list):
                if isinstance(result, Exception):
                    search_results += f"\nSearch query: {sq} (Source: {source})\nError: {str(result)}\n"
                else:
                    formatted = result.get("formatted") if isinstance(result, dict) else result
                    search_results += f"\nSearch query: {sq} (Source: {source})\n{formatted}\n"
            
            log(f"[agentic_search] Step {step + 1}: Search complete, {len(search_results)} chars of results")
            
        except Exception as e:
            log(f"[agentic_search] Error at step {step + 1}: {str(e)}", level="error")
            if current_analysis:
                # Return what we have so far
                break
            else:
                return f"Error during agentic search: {str(e)}"
    
    # Print summary statistics
    steps_used = step + 1
    total_cost = calculate_cost(total_input_tokens, total_output_tokens)
    
    log(f"[agentic_search] Summary: steps={steps_used}, tokens={total_input_tokens + total_output_tokens:,} "
        f"({total_input_tokens:,} input + {total_output_tokens:,} output), estimated_cost=${total_cost:.4f}")
    
    # Ensure we have an analysis to return
    if not current_analysis:
        return "Error: No analysis was generated during the research process"
    
    return current_analysis


async def call_perplexity(prompt: str, bucket: str | None = None) -> str:
    """
    Async function to call Perplexity Sonar Deep Research via OpenRouter.
    """
    if not PERPLEXITY_AVAILABLE:
        return "Error: Perplexity disabled or missing API key."
    if not _consume_perplexity_budget(bucket):
        return "Error: Perplexity call limit reached for this run."
    try:
        return await call_openrouter_gpt(
            prompt + PERPLEXITY_DEEP_RESEARCH_USER_SUFFIX,
            model="perplexity/sonar-deep-research",
            max_tokens=8000,
        )
    except Exception as e:
        log(f"[Perplexity API] [ERROR] {e}", level="error")
        return f"Error: Perplexity API via OpenRouter failed: {e}"

async def google_search(query, is_news=False, date_before=None):
    original_query = query
    query = query.replace('"', '').replace("'", '').strip()
    log(f"[google_search] Cleaned query: '{query}' (original: '{original_query}') | is_news={is_news}, date_before={date_before}")
    
    if not ENABLE_SERPER:
        log("[google_search] [WARN] Serper/Google search disabled by config")
        return []
    if not SERPER_KEY:
        log("[google_search] [ERROR] SERPER_KEY not set; skipping search", level="error")
        return []
    
    search_type = "news" if is_news else "search"
    url = f"https://google.serper.dev/{search_type}"
    headers = {
        'X-API-KEY': SERPER_KEY,
        'Content-Type': 'application/json'
    }
    payload = json.dumps({
        "q": query,
        "num": 20
    })
    timeout = ClientTimeout(total=70)

    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, data=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('news' if is_news else 'organic', [])
                    log(f"[google_search] Found {len(items)} raw results")

                    filtered_items = []
                    for item in items:
                        item_url = item.get('link')
                        item_date_str = item.get('date', '')
                        item_date = parse_date(item_date_str)
                        keep = True
                        if date_before:
                            keep = item_date != "Unknown" and validate_time(date_before, item_date)
                        if keep:
                            log(f"[google_search] [OK] Keeping: {item_url} (date: {item_date})")
                            filtered_items.append(
                                {
                                    "url": item_url,
                                    "title": item.get("title") or item.get("snippet") or item_url,
                                    "snippet": item.get("snippet", ""),
                                    "published_at": item_date if item_date != "Unknown" else None,
                                    "source": item.get("source") or ("news" if is_news else "web"),
                                }
                            )
                        else:
                            log(f"[google_search] [SKIP] Dropped by date: {item_url} (date: {item_date})")
                        if len(filtered_items) >= 12:
                            break

                    log(f"[google_search] Returning {len(filtered_items)} results")
                    return filtered_items
                else:
                    log(f"[google_search] Error in Serper API response: Status {response.status}")
                    response.raise_for_status()
    except Exception as e:
        log(f"[google_search] Exception: {str(e)}")
        raise


async def call_gpt(prompt, step=1):
    """
    Convenience wrapper around OpenRouter GPT models for research prompts.
    """
    try:
        return await call_openrouter_gpt(prompt, model="openai/o3-mini", max_tokens=8000)
    except Exception as e:
        log(f"[call_gpt] Error: {str(e)}")
        return f"Error calling OpenRouter API: {str(e)}"


async def google_search_and_scrape(query, is_news, question_details, date_before=None):
    log(f"[google_search_and_scrape] Called with query='{query}', is_news={is_news}, date_before={date_before}")
    try:
        if not ENABLE_BRIGHT_DATA:
            log("[google_search_and_scrape] [WARN] Bright Data scraping disabled by config")
            return {"formatted": f"<Summary query=\"{query}\">Scraping disabled by config.</Summary>\n", "evidence": []}

        search_results = await google_search(query, is_news, date_before)

        if not search_results:
            log(f"[google_search_and_scrape] [ERROR] No URLs returned for query: '{query}'")
            return {"formatted": f"<Summary query=\"{query}\">No URLs returned from Google.</Summary>\n", "evidence": []}
        # track attempted urls for serper stats
        logger = get_current_logger()
        logger.log(f"[serper_urls] attempted={len(search_results)} success=0")

        urls = [item.get("url") for item in search_results if item.get("url")]
        async with FastContentExtractor() as extractor:
            log(f"[google_search_and_scrape] [INFO] Starting content extraction for {len(urls)} URLs")
            results = await extractor.extract_content(urls)
            log(f"[google_search_and_scrape] [OK] Finished content extraction")

        summarize_tasks: list[asyncio.Task] = []
        no_results = 3
        valid_urls = []
        evidences: list[EvidenceItem] = []

        for url, data in results.items():
            if len(summarize_tasks) >= no_results:
                break
            content = (data.get("content") or "").strip()
            if len(content.split()) < 100:
                log(f"[google_search_and_scrape] [WARN] Skipping low-content article: {url}")
                continue
            truncated = content[:8000]
            log(f"[google_search_and_scrape] [TRUNC] Truncated content for summarization: {len(truncated)} chars from {url}")
            summarize_tasks.append(asyncio.create_task(summarize_article(truncated, question_details)))
            valid_urls.append(url)

        if not summarize_tasks:
            log("[google_search_and_scrape] [WARN] Warning: No content to summarize")
            return {"formatted": f"<Summary query=\"{query}\">No usable content extracted from any URL.</Summary>\n", "evidence": []}

        summaries = await asyncio.gather(*summarize_tasks, return_exceptions=True)

        output = ""
        success_count = 0
        for url, summary in zip(valid_urls, summaries):
            meta = next((m for m in search_results if m.get("url") == url), {})
            snippet_text = summary if not isinstance(summary, Exception) else str(summary)
            evidence_item = _make_evidence_item(
                provider="google_news" if is_news else "google",
                query=query,
                snippet=snippet_text if isinstance(snippet_text, str) else str(snippet_text),
                url=url,
                title=meta.get("title") or query,
                published_at=meta.get("published_at"),
                metadata={"source": meta.get("source", "web")},
            )
            evidences.append(evidence_item)
            if isinstance(summary, Exception):
                log(f"[google_search_and_scrape] [ERROR] Error summarizing {url}: {summary}")
                output += f"\n<Summary source=\"{url}\">\nError summarizing content: {str(summary)}\n</Summary>\n"
            else:
                success_count += 1
                output += f"\n<Summary source=\"{url}\">\n{summary}\n</Summary>\n"

        logger.log(f"[serper_urls] attempted=0 success={success_count}")

        return {"formatted": output, "evidence": evidences}
    except Exception as e:
        log(f"[google_search_and_scrape] Error: {str(e)}")
        traceback_str = traceback.format_exc()
        log(f"Traceback: {traceback_str}")
        return {"formatted": f"<Summary query=\"{query}\">Error during search and scrape: {str(e)}</Summary>\n", "evidence": []}
    

async def google_search_agentic(query, is_news=False):
    """
    Performs Google search and returns raw article content without summarization.
    Used for agentic search where the agent will analyze the raw content.
    
    Args:
        query: Search query string
        is_news: Whether to search Google News (True) or regular Google (False)
        
    Returns:
        Formatted string with raw article contents
    """
    log(f"[google_search_agentic] Called with query='{query}', is_news={is_news}")
    try:
        if not ENABLE_BRIGHT_DATA:
            log("[google_search_agentic] [WARN] Bright Data scraping disabled by config")
            return {"formatted": f"<RawContent query=\"{query}\">Scraping disabled by config.</RawContent>\n", "evidence": []}

        search_results = await google_search(query, is_news)

        if not search_results:
            log(f"[google_search_agentic] [ERROR] No URLs returned for query: '{query}'")
            return {"formatted": f"<RawContent query=\"{query}\">No URLs returned from Google.</RawContent>\n", "evidence": []}

        urls = [item.get("url") for item in search_results if item.get("url")]
        async with FastContentExtractor() as extractor:
            log(f"[google_search_agentic] [INFO] Starting content extraction for {len(urls)} URLs")
            results = await extractor.extract_content(urls)
            log(f"[google_search_agentic] [OK] Finished content extraction")

        output = ""
        no_results = 3
        results_count = 0
        evidences: list[EvidenceItem] = []
        
        for url, data in results.items():
            if results_count >= no_results:
                break
                
            content = (data.get('content') or '').strip()
            if len(content.split()) < 100:
                log(f"[google_search_agentic] [WARN] Skipping low-content article: {url}")
                continue
                
            if content:
                truncated = content[:8000]
                log(f"[google_search_agentic] [TRUNC] Including content: {len(truncated)} chars from {url}")
                output += f"\n<RawContent source=\"{url}\">\n{truncated}\n</RawContent>\n"
                results_count += 1
                evidences.append(
                    _make_evidence_item(
                        provider="google_agentic",
                        query=query,
                        snippet=truncated,
                        url=url,
                        title=next((m.get("title") for m in search_results if m.get("url") == url), query),
                        published_at=next((m.get("published_at") for m in search_results if m.get("url") == url), None),
                        metadata={"source": "agentic"},
                    )
                )
            else:
                log(f"[google_search_agentic] [WARN] No content for {url}, skipping.")

        if not output:
            log("[google_search_agentic] [WARN] Warning: No usable content found")
            return {"formatted": f"<RawContent query=\"{query}\">No usable content extracted from any URL.</RawContent>\n", "evidence": []}

        return {"formatted": output, "evidence": evidences}
        
    except Exception as e:
        log(f"[google_search_agentic] Error: {str(e)}")
        import traceback
        traceback_str = traceback.format_exc()
        log(f"Traceback: {traceback_str}")
        return {"formatted": f"<RawContent query=\"{query}\">Error during search: {str(e)}</RawContent>\n", "evidence": []}





async def process_search_queries(
    response: str,
    forecaster_id: str,
    question_details: dict,
    perplexity_bucket: str | None = None,
    replay_key: str | None = None,
    max_queries: int | None = None,
) -> ResearchResult:
    """
    Parse search queries from the forecaster output, execute providers, and
    return structured evidence plus prompt-ready text.
    """
    _log_provider_status_once()
    search_plan = build_search_plan(question_details)
    question_details["formalization"] = search_plan.get("formalization")

    cached = maybe_replay_search(replay_key)
    if cached:
        log(f"[process_search_queries] Using replay fixture for key={replay_key}", level="info")
        slug = question_details.get("slug") or question_details.get("title", "question")
        replay_report = {
            "bucket": perplexity_bucket or "research",
            "kpis": compute_retrieval_kpis(cached.evidence),
            "search_plan": search_plan,
            "queries": cached.queries,
            "formatted": cached.formatted,
            "evidence": [e.to_dict() for e in cached.evidence],
            "diagnostics": {"source": "replay_cache"},
        }
        question_details.setdefault("research_reports", []).append(replay_report)
        question_details["research"] = {"evidence": [e.to_dict() for e in cached.evidence]}
        persist_research_report(slug, perplexity_bucket or "research", replay_report)
        return cached

    evidence_items: List[EvidenceItem] = []
    diagnostics: dict = {}
    formatted_results = ""
    queries_seen: List[str] = []
    followup_ran = False

    def _normalize_result(query: str, source: str, result: object) -> tuple[str, list[EvidenceItem]]:
        if isinstance(result, Exception):
            return "", []
        formatted = ""
        evidence: list[EvidenceItem] = []
        if isinstance(result, dict) and "formatted" in result:
            formatted = result.get("formatted", "")
            raw_evidence = result.get("evidence") or []
            for raw in raw_evidence:
                if isinstance(raw, EvidenceItem):
                    evidence.append(raw)
                elif isinstance(raw, dict):
                    evidence.append(EvidenceItem.from_dict(raw))
        else:
            formatted = str(result)
        if not evidence:
            url = _extract_first_url(formatted)
            evidence.append(
                _make_evidence_item(
                    source.lower(),
                    query,
                    formatted,
                    query_intent=perplexity_bucket,
                    url=url,
                    title=query,
                    metadata={"source": source},
                )
            )
        return formatted, evidence

    try:
        search_queries_block = re.search(r'(?:Search queries:)(.*)', response, re.DOTALL | re.IGNORECASE)
        normalized: List[tuple[str, str]] = []
        if search_queries_block:
            queries_text = search_queries_block.group(1).strip()

            search_queries = re.findall(
                r'(?:\d+\.\s*)?([^\n]+?)\s*\((Google|Google News|Assistant|Agent|Perplexity)\)',
                queries_text,
            )
            for raw_query, source in search_queries:
                cleaned = raw_query.strip().strip('"').strip("'")
                if cleaned:
                    normalized.append((cleaned, source))

        if not normalized:
            fallback_queries: List[str] = []
            if perplexity_bucket == "historical":
                fallback_queries = search_plan.get("historical_queries") or []
            elif perplexity_bucket == "current":
                fallback_queries = search_plan.get("current_queries") or []
            else:
                fallback_queries = search_plan.get("counter_queries") or search_plan.get("data_queries") or []
            normalized = [(q, "Perplexity" if prefer_perplexity() else "Google") for q in fallback_queries]
            diagnostics["used_search_plan_fallback"] = True

        if not normalized:
            log(f"Forecaster {forecaster_id}: No valid search queries found in prompt or fallback.")
            return ResearchResult(
                formatted="",
                evidence=[],
                diagnostics={"reason": "no_valid_queries", "search_plan": search_plan},
            )

        if max_queries is not None and max_queries > 0:
            normalized = normalized[:max_queries]

        log(f"Forecaster {forecaster_id}: Processing {len(normalized)} search queries")

        tasks: List[asyncio.Task] = []
        query_sources = []

        for query, source in normalized:
            queries_seen.append(query)
            effective_source = "Perplexity" if prefer_perplexity() else source
            log(f"Forecaster {forecaster_id}: Query='{query}' Source={effective_source}")

            if effective_source in ("Google", "Google News"):
                if ENABLE_SERPER and ENABLE_BRIGHT_DATA:
                    tasks.append(
                        google_search_and_scrape(
                            query,
                            is_news=(effective_source == "Google News"),
                            question_details=question_details,
                            date_before=question_details.get("resolution_date"),
                        )
                    )
                    query_sources.append((query, effective_source))
                elif FALLBACK_TO_PERPLEXITY and PERPLEXITY_AVAILABLE:
                    log(f"Forecaster {forecaster_id}: Falling back to Perplexity for '{query}'")
                    tasks.append(call_perplexity(query))
                    query_sources.append((query, "Perplexity"))
                else:
                    formatted_results += f"\n<Summary query=\"{query}\">Search disabled by config.</Summary>\n"
            elif effective_source == "Assistant":
                if ENABLE_ASKNEWS:
                    tasks.append(call_asknews(query))
                    query_sources.append((query, "Assistant"))
                elif FALLBACK_TO_PERPLEXITY and PERPLEXITY_AVAILABLE:
                    log(f"Forecaster {forecaster_id}: Falling back to Perplexity for '{query}' (AskNews disabled)")
                    tasks.append(call_perplexity(query))
                    query_sources.append((query, "Perplexity"))
                else:
                    formatted_results += f"\n<Asknews_articles>\nQuery: {query}\nAskNews disabled by config.\n</Asknews_articles>\n"
            elif effective_source == "Agent":
                tasks.append(agentic_search(query, perplexity_bucket=perplexity_bucket))
                query_sources.append((query, "Agent"))
            elif effective_source == "Perplexity":
                tasks.append(call_perplexity(query, bucket=perplexity_bucket))
                query_sources.append((query, "Perplexity"))

        if not tasks and not formatted_results:
            log(f"Forecaster {forecaster_id}: No tasks generated")
            return ResearchResult(formatted="", evidence=[], diagnostics={"reason": "no_tasks", "search_plan": search_plan})

        results = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for (query, source), result in zip(query_sources, results):
            if isinstance(result, Exception):
                log(f"[process_search_queries] [ERROR] Forecaster {forecaster_id}: Error for '{query}' -> {str(result)}")
                diagnostics.setdefault("errors", []).append(str(result))
                if source == "Assistant":
                    formatted_results += f"\n<Asknews_articles>\nQuery: {query}\nError retrieving results: {str(result)}\n</Asknews_articles>\n"
                elif source == "Agent":
                    formatted_results += f"\n<Agent_report>\nQuery: {query}\n{result}\n</Agent_report>\n"
                else:
                    formatted_results += f"\n<Summary query=\"{query}\">\nError retrieving results: {str(result)}\n</Summary>\n"
            else:
                log(f"[process_search_queries] [OK] Forecaster {forecaster_id}: Query '{query}' processed successfully.")
                snippet, ev_items = _normalize_result(query, source, result)
                if source == "Assistant":
                    formatted_results += f"\n<Asknews_articles>\nQuery: {query}\n{snippet}</Asknews_articles>\n"
                elif source == "Agent":
                    formatted_results += f"\n<Agent_report>\nQuery: {query}\n{snippet}\n</Agent_report>\n"
                else:
                    formatted_results += snippet
                evidence_items.extend(ev_items)

        evidence_items = _dedup_evidence_items(evidence_items)

        kpis = compute_retrieval_kpis(evidence_items)
        replay_mode = os.getenv("ENABLE_REPLAY_MODE", "").strip().lower() in {"1", "true", "yes"}
        if not replay_mode and kpis.get("unique_domains", 0) < 2 and search_plan.get("missing_fact_queries"):
            follow_query = search_plan["missing_fact_queries"][0]
            follow_res = await call_perplexity(follow_query, bucket=perplexity_bucket)
            snippet, ev_items = _normalize_result(follow_query, "Perplexity", follow_res)
            formatted_results += f"\n<Followup query=\"{follow_query}\">\n{snippet}\n</Followup>\n"
            evidence_items.extend(ev_items)
            evidence_items = _dedup_evidence_items(evidence_items)
            kpis = compute_retrieval_kpis(evidence_items)
            followup_ran = True

        facts = extract_fact_candidates(evidence_items)
        synthesis = _summarize_evidence_items(evidence_items)
        formatted_results += f"\n<EvidenceSummary>\n{synthesis}\n</EvidenceSummary>\n"
        report = {
            "errors": diagnostics.get("errors", []),
            "kpis": kpis,
            "search_plan": search_plan,
            "followup_ran": followup_ran,
            "fact_candidates": facts,
            "synthesis": synthesis,
        }
        result_obj = ResearchResult(
            formatted=formatted_results,
            evidence=evidence_items,
            report=report,
            queries=queries_seen,
            diagnostics=diagnostics,
        )

        slug = question_details.get("slug") or question_details.get("title", "question")
        persist_research_result(slug, result_obj)
        report_payload = {
            "bucket": perplexity_bucket or "research",
            "kpis": kpis,
            "search_plan": search_plan,
            "queries": queries_seen,
            "formatted": formatted_results,
            "evidence": [e.to_dict() for e in evidence_items],
            "diagnostics": diagnostics,
            "facts": facts,
            "synthesis": synthesis,
        }
        question_details.setdefault("research_reports", []).append(report_payload)
        question_details["research"] = {"evidence": [e.to_dict() for e in evidence_items]}
        persist_research_report(slug, perplexity_bucket or "research", report_payload)
        record_search_result(replay_key, result_obj)
        return result_obj

    except Exception as e:
        log(f"Forecaster {forecaster_id}: Error processing search queries: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        log(f"Traceback: {trace}")
        diagnostics.setdefault("errors", []).append(str(e))
        result_obj = ResearchResult(
            formatted="Error processing some search queries. Partial results may be available.",
            evidence=evidence_items,
            report={"errors": diagnostics.get("errors", [])},
            queries=queries_seen,
            diagnostics={"exception": str(e)},
        )
        if replay_key:
            record_search_result(replay_key, result_obj)
        persist_research_result(question_details.get("slug") or question_details.get("title", "question"), result_obj)
        return result_obj
async def main():
    """
    Demonstrates the usage of process_search_queries with sample search queries.
    """
    print("Starting test for content extraction...")
    
    # This part won't be executed
    sample_response = """
    Search queries:
    1. "Nvidia stock price forecast 2024" (Google)
    2. "Ukraine Russia conflict latest developments" (Google News)
    3. "Middle East stability assessment Israel Hamas" (Perplexity)
    4. "Trump tariffs economic impact" (Assistant)
    """
    
    forecaster_id = "demo_forecaster"
    print(f"Processing sample search queries for forecaster: {forecaster_id}")
    
    # Sample question_details dict
    question_details = {
        "title": "Sample Question",
        "resolution_criteria": "Sample resolution criteria",
        "fine_print": "Sample fine print",
        "description": "Sample background information",
        "resolution_date": "2025-12-31"
    }
    
    results = await process_search_queries(sample_response, forecaster_id, question_details)
    
    print("\n=== SEARCH RESULTS ===\n")
    print(results)
    print("\n=== END OF RESULTS ===\n")

if __name__ == "__main__":
    asyncio.run(main())
