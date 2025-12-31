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
load_dotenv()

SERPER_KEY = os.getenv("SERPER_KEY")
ASKNEWS_CLIENT_ID = os.getenv("ASKNEWS_CLIENT_ID")
ASKNEWS_SECRET = os.getenv("ASKNEWS_SECRET")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")  # legacy, not required for OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
PERPLEXITY_AVAILABLE = bool(OPENROUTER_API_KEY) and ENABLE_PERPLEXITY

_perplexity_budget = {"historical": 0, "current": 0, "shared": 0}


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
        return "AskNews disabled by config."
    if not ASKNEWS_CLIENT_ID or not ASKNEWS_SECRET:
        return "AskNews disabled (no credentials provided)."
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

        if hot_articles:
            hot_articles = [article.__dict__ for article in hot_articles]
            hot_articles = sorted(hot_articles, key=lambda x: x["pub_date"], reverse=True)

            for article in hot_articles:
                pub_date = article["pub_date"].strftime("%B %d, %Y %I:%M %p")
                formatted_articles += f"**{article['eng_title']}**\n{article['summary']}\nOriginal language: {article['language']}\nPublish date: {pub_date}\nSource:[{article['source_id']}]({article['article_url']})\n\n"

        if historical_articles:
            historical_articles = [article.__dict__ for article in historical_articles]
            historical_articles = sorted(
                historical_articles, key=lambda x: x["pub_date"], reverse=True
            )

            for article in historical_articles:
                pub_date = article["pub_date"].strftime("%B %d, %Y %I:%M %p")
                formatted_articles += f"**{article['eng_title']}**\n{article['summary']}\nOriginal language: {article['language']}\nPublish date: {pub_date}\nSource:[{article['source_id']}]({article['article_url']})\n\n"

        if not hot_articles and not historical_articles:
            formatted_articles += "No articles were found.\n\n"
            return formatted_articles

        return formatted_articles
    except Exception as e:
        log(f"[call_asknews] Error: {str(e)}", level="error")
        return f"Error retrieving news articles: {str(e)}"
    

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
                    search_results += f"\nSearch query: {sq} (Source: {source})\n{result}\n"
            
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
                        if date_before:
                            if item_date != "Unknown" and validate_time(date_before, item_date):
                                log(f"[google_search] [OK] Keeping: {item_url} (date: {item_date})")
                                filtered_items.append(item)
                            else:
                                log(f"[google_search] [SKIP] Dropped by date: {item_url} (date: {item_date})")
                        else:
                            log(f"[google_search] [OK] Keeping: {item_url}")
                            filtered_items.append(item)

                        if len(filtered_items) >=12:
                            break
                    
                    urls = [item['link'] for item in filtered_items]
                    log(f"[google_search] Returning {len(urls)} URLs: {urls}")
                    return urls
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
            return f"<Summary query=\"{query}\">Scraping disabled by config.</Summary>\n"

        urls = await google_search(query, is_news, date_before)

        if not urls:
            log(f"[google_search_and_scrape] [ERROR] No URLs returned for query: '{query}'")
            return f"<Summary query=\"{query}\">No URLs returned from Google.</Summary>\n"
        # track attempted urls for serper stats
        logger = get_current_logger()
        logger.log(f"[serper_urls] attempted={len(urls)} success=0")

        async with FastContentExtractor() as extractor:
            log(f"[google_search_and_scrape] [INFO] Starting content extraction for {len(urls)} URLs")
            results = await extractor.extract_content(urls)
            log(f"[google_search_and_scrape] [OK] Finished content extraction")

        summarize_tasks = []
        no_results = 3
        valid_urls = []
        for url, data in results.items():
            if len(summarize_tasks) >= no_results:
                break  
            content = (data.get('content') or '').strip()
            if len(content.split()) < 100:
                log(f"[google_search_and_scrape] [WARN] Skipping low-content article: {url}")
                continue
            if content:
                truncated = content[:8000]
                log(f"[google_search_and_scrape] [TRUNC] Truncated content for summarization: {len(truncated)} chars from {url}")
                summarize_tasks.append(
                    asyncio.create_task(summarize_article(truncated, question_details))
                )
                valid_urls.append(url)
            else:
                log(f"[google_search_and_scrape] [WARN] No content for {url}, skipping summarization.")

        if not summarize_tasks:
            log("[google_search_and_scrape] [WARN] Warning: No content to summarize")
            return f"<Summary query=\"{query}\">No usable content extracted from any URL.</Summary>\n"

        summaries = await asyncio.gather(*summarize_tasks, return_exceptions=True)

        output = ""
        success_count = 0
        for url, summary in zip(valid_urls, summaries):
            if isinstance(summary, Exception):
                log(f"[google_search_and_scrape] [ERROR] Error summarizing {url}: {summary}")
                output += f"\n<Summary source=\"{url}\">\nError summarizing content: {str(summary)}\n</Summary>\n"
            else:
                success_count += 1
                output += f"\n<Summary source=\"{url}\">\n{summary}\n</Summary>\n"

        # update serper success stats
        logger.log(f"[serper_urls] attempted=0 success={success_count}")

        return output
    except Exception as e:
        log(f"[google_search_and_scrape] Error: {str(e)}")
        traceback_str = traceback.format_exc()
        log(f"Traceback: {traceback_str}")
        return f"<Summary query=\"{query}\">Error during search and scrape: {str(e)}</Summary>\n"
    

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
            return f"<RawContent query=\"{query}\">Scraping disabled by config.</RawContent>\n"

        urls = await google_search(query, is_news)

        if not urls:
            log(f"[google_search_agentic] [ERROR] No URLs returned for query: '{query}'")
            return f"<RawContent query=\"{query}\">No URLs returned from Google.</RawContent>\n"

        async with FastContentExtractor() as extractor:
            log(f"[google_search_agentic] [INFO] Starting content extraction for {len(urls)} URLs")
            results = await extractor.extract_content(urls)
            log(f"[google_search_agentic] [OK] Finished content extraction")

        output = ""
        no_results = 3
        results_count = 0
        
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
            else:
                log(f"[google_search_agentic] [WARN] No content for {url}, skipping.")

        if not output:
            log("[google_search_agentic] [WARN] Warning: No usable content found")
            return f"<RawContent query=\"{query}\">No usable content extracted from any URL.</RawContent>\n"

        return output
        
    except Exception as e:
        log(f"[google_search_agentic] Error: {str(e)}")
        import traceback
        traceback_str = traceback.format_exc()
        log(f"Traceback: {traceback_str}")
        return f"<RawContent query=\"{query}\">Error during search: {str(e)}</RawContent>\n"



async def process_search_queries(response: str, forecaster_id: str, question_details: dict, perplexity_bucket: str | None = None):
    """
    Parses out search queries from the forecaster's response, executes them
    (AskNews, Agent or Google/Google News), and returns formatted summaries.
    Note: Agent replaces the previous Perplexity functionality.
    """
    try:
        # 1) Extract the "Search queries:" block
        search_queries_block = re.search(r'(?:Search queries:)(.*)', response, re.DOTALL | re.IGNORECASE)
        if not search_queries_block:
            log(f"Forecaster {forecaster_id}: No search queries block found")
            return ""

        queries_text = search_queries_block.group(1).strip()

        # 2) Try to find queries of the form: 1. "text" (Source)
        # Support both "Perplexity" (legacy) and "Agent" (new)
        search_queries = re.findall(
            r'(?:\d+\.\s*)?(["\']?(.*?)["\']?)\s*\((Google|Google News|Assistant|Agent|Perplexity)\)',
            queries_text
        )
        # 3) Fallback to unquoted queries if none found
        if not search_queries:
            search_queries = re.findall(
                r'(?:\d+\.\s*)?([^(\n]+)\s*\((Google|Google News|Assistant|Agent|Perplexity)\)',
                queries_text
            )

        if not search_queries:
            log(f"Forecaster {forecaster_id}: No valid search queries found:\n{queries_text}")
            return ""

        log(f"Forecaster {forecaster_id}: Processing {len(search_queries)} search queries")

        # 4) Kick off one asyncio task per query
        tasks = []
        query_sources = []  # Track which source goes with which task
        formatted_results = ""
        
        for match in search_queries:
            # match can be ("\"text\"", "text", "Source") or ("text", "Source")
            if len(match) == 3:
                _, raw_query, source = match
            else:
                raw_query, source = match

            query = raw_query.strip().strip('"').strip("'")
            if not query:
                continue

            effective_source = "Perplexity" if prefer_perplexity() else source
            log(f"Forecaster {forecaster_id}: Query='{query}' Source={effective_source}")

            if effective_source in ("Google", "Google News"):
                if ENABLE_SERPER and ENABLE_BRIGHT_DATA:
                    tasks.append(
                        google_search_and_scrape(
                            query,
                            is_news=(effective_source == "Google News"),
                            question_details=question_details,
                            date_before=question_details.get("resolution_date")
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

        if not tasks:
            log(f"Forecaster {forecaster_id}: No tasks generated")
            return formatted_results

        # 5) Await all tasks
        # First gather with return_exceptions=True to prevent one failure from breaking everything
        results = await asyncio.gather(*tasks, return_exceptions=True)
            
        # 6) Format the outputs
        for (query, source), result in zip(query_sources, results):
            if isinstance(result, Exception):
                log(f"[process_search_queries] [ERROR] Forecaster {forecaster_id}: Error for '{query}' -> {str(result)}")
                # Add a message about the error in the formatted results
                if source == "Assistant":
                    formatted_results += f"\n<Asknews_articles>\nQuery: {query}\nError retrieving results: {str(result)}\n</Asknews_articles>\n"
                elif source == "Agent":
                    formatted_results += f"\n<Agent_report>\nQuery: {query}\n{result}\n</Agent_report>\n"
                else:
                    formatted_results += f"\n<Summary query=\"{query}\">\nError retrieving results: {str(result)}\n</Summary>\n"
            else:
                log(f"[process_search_queries] [OK] Forecaster {forecaster_id}: Query '{query}' processed successfully.")
                
                if source == "Assistant":
                    formatted_results += f"\n<Asknews_articles>\nQuery: {query}\n{result}</Asknews_articles>\n"
                elif source == "Agent":
                    formatted_results += f"\n<Agent_report>\nQuery: {query}\n{result}</Agent_report>\n"
                else:
                    # Google/Google News tasks already return <Summary> blocks
                    formatted_results += result

        return formatted_results

    except Exception as e:
        log(f"Forecaster {forecaster_id}: Error processing search queries: {str(e)}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        # Return what we have so far instead of nothing
        return "Error processing some search queries. Partial results may be available."


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
