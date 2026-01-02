import asyncio
import datetime
import re
import numpy as np
from prompts import (
    BINARY_PROMPT_historical,
    BINARY_PROMPT_current,
    BINARY_PROMPT_1,
    BINARY_PROMPT_2,
)
from llm_calls import call_claude, call_gpt_o3, call_gpt_o4_mini, call_claude_with_fallback, call_gpt_o4_mini_with_fallback, call_forecaster_1, call_forecaster_2, call_forecaster_3, call_forecaster_4, call_forecaster_5
from search import process_search_queries, reset_perplexity_budget
from logging_utils import get_current_logger
from research_config import ENABLE_ASKNEWS, ENABLE_BRIGHT_DATA, ENABLE_PERPLEXITY, ENABLE_SERPER, prefer_perplexity
from replay import make_replay_key
from evidence import ResearchResult
from aggregation import aggregate_binary, cap_probability
from priors import get_binary_prior, blend_prior
from critique import run_binary_critique

"""
Program flow:
1. Take BINARY_PROMPT_historical and BINARY_PROMPT_current, format in the title, date, background, resolution criteria, fine print (as below) and run call_claude simultaneously on both prompts 
2. Take the output of call_claude, and run it through process_search_queries (programmed to handle raw LLM output, set forecaster_id = "-1" for historical and "0" for current)
3. Use the output of process_search_queries with forecaster_id = "-1" as context for binary prompt 1
4. Take Binary Prompt 1, format in the title, date, resolution_criteria, fine print and context and run, simultaneously, two instances of call_claude (forecaster_id will be 1 and 2 respectively, all strings), two instances of gpt-o4-mini (forecaster_id will be 3 and 4 respectively, all strings) and one instance of gpt-o3 (forecaster_id will be 5)
5. First, initialize a context dictionary with context[1], context[2], context[3], context[4], context[5], all equal to the result of process_search_queries with forecaster_id = "0" (we got this in step 2). Then, we will process the output of Binary Prompt 1 as follows:
    (a) The output of forecaster_id 1 is appended to context[1]
    (b) The output of forecaster_id 2 is appended to context[3]
    (c) The output of forecaster_id 3 is appended to context[2]
    (d) The output of forecaster_id 4 is appended to context[4]
    (e) The output of forecaster_id 5 is appended to context[5]
6. Now, take binary prompt 2, format in the title, date, resolution_criteria, fine_print and respective context (i.e., forecaster x gets context[x]) and run, simultaneously, all five instances we ran previously
7. Pass the output of all five instances to extract_probability_from_response_as_percentage_not_decimal to extract the five probabilities
8. Average the five probabilities, first four with weight 1 and last (from o3) with weight 2 to get the final probability
9. The output should be the final probabilities and the final outputs of binary prompt 2, clearly indicating which output belongs to which forecaster
"""


def extract_probability_from_response_as_percentage_not_decimal(forecast_text: str) -> float:
    matches = re.findall(r"Probability:\s*([0-9]+(?:\.[0-9]+)?)%", forecast_text.strip())
    if matches:
        number = float(matches[-1])
        return min(99, max(1, number))
    raise ValueError(f"Could not extract prediction from response: {forecast_text}")


async def get_binary_forecast(question_details, write=None, return_details: bool = False):
    from config import load_run_config

    run_config = load_run_config()
    sample_count = run_config.forecast_runs_per_model
    if run_config.enable_replay_mode and sample_count > 1:
        sample_count = 1  # avoid missing replay fixtures
    forecaster_count = max(1, min(5, run_config.forecaster_count))
    # Configure Perplexity budget in historical/current pairs
    reset_perplexity_budget()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    title = question_details["title"]
    if not question_details.get("slug"):
        slug = "".join(c.lower() if c.isalnum() else "-" for c in title).strip("-") or "binary-question"
        question_details["slug"] = slug
    resolution_criteria = question_details["resolution_criteria"]
    background = question_details["description"]
    fine_print = question_details["fine_print"]
    logger = get_current_logger()
    question_errors = []

    def log(message: str, level: str = "info") -> None:
        logger.log(message, level=level)
        if write:
            write(message)
        if level == "error" or "[ERROR]" in message:
            question_errors.append(message)

    async def format_and_call_gpt(prompt_template, replay_suffix: str):
        content = prompt_template.format(
            title=title,
            today=today,
            background=background,
            resolution_criteria=resolution_criteria,
            fine_print=fine_print,
        )
        key = make_replay_key(question_details, replay_suffix)
        return content, await call_gpt_o3(content, replay_key=key)

    historical_task = asyncio.create_task(format_and_call_gpt(BINARY_PROMPT_historical, "binary:historical_context"))
    current_task = asyncio.create_task(format_and_call_gpt(BINARY_PROMPT_current, "binary:current_context"))
    (historical_prompt, historical_output), (current_prompt, current_output) = await asyncio.gather(
        historical_task, current_task
    )

    def has_usable_research(result: ResearchResult | str) -> bool:
        text = result.formatted if isinstance(result, ResearchResult) else str(result or "")
        if not text.strip():
            return False
        lowered = text.lower()
        negative_markers = [
            "no usable content",
            "asknews disabled",
            "no urls returned",
            "scraping disabled",
            "error retrieving",
        ]
        positive_markers = [
            "<summary",
            "<rawcontent",
            "<agent_report",
            "<asknews_articles",
        ]
        if any(marker in lowered for marker in positive_markers):
            return True
        if all(marker in lowered for marker in negative_markers):
            return False
        return len(text.strip()) > 300

    context_historical, context_current = await asyncio.gather(
        process_search_queries(
            historical_output,
            forecaster_id="-1",
            question_details=question_details,
            perplexity_bucket="historical",
            replay_key=make_replay_key(question_details, "binary:historical_search"),
            max_queries=run_config.max_historical_queries,
        ),
        process_search_queries(
            current_output,
            forecaster_id="0",
            question_details=question_details,
            perplexity_bucket="current",
            replay_key=make_replay_key(question_details, "binary:current_search"),
            max_queries=run_config.max_current_queries,
        ),
    )

    if not has_usable_research(context_historical) and not has_usable_research(context_current):
        msg = "Research failure: no usable historical or current context retrieved. Proceeding with empty context."
        log(msg, level="error")
        context_historical = ResearchResult(
            formatted="No usable historical research retrieved; proceed with base-rate reasoning only."
        )
        context_current = ResearchResult(formatted="No usable current research retrieved; proceed with general reasoning.")
    else:
        if not has_usable_research(context_historical):
            log("Historical research missing; proceeding with current context only.", level="error")
            context_historical = ResearchResult(formatted="No usable historical research retrieved; proceed with base-rate reasoning only.")
        if not has_usable_research(context_current):
            log("Current research missing; proceeding with historical context only.", level="error")
            context_current = ResearchResult(formatted="No usable current research retrieved; proceed with general reasoning.")

    log("\nHistorical context LLM output:\n" + historical_output)
    log("\nCurrent context LLM output:\n" + current_output)
    log("\nHistorical context search results:\n" + context_historical.formatted)
    log("\nCurrent context search results:\n" + context_current.formatted)

    prompt1 = BINARY_PROMPT_1.format(
        title=title,
        today=today,
        resolution_criteria=resolution_criteria,
        fine_print=fine_print,
        context=context_historical.formatted,
    )

    async def run_prompt1():
        return await asyncio.gather(
            call_forecaster_1(prompt1, replay_key=make_replay_key(question_details, "binary:prompt1:f1")),
            call_forecaster_2(prompt1, replay_key=make_replay_key(question_details, "binary:prompt1:f2")),
            call_forecaster_3(prompt1, replay_key=make_replay_key(question_details, "binary:prompt1:f3")),
            call_forecaster_4(prompt1, replay_key=make_replay_key(question_details, "binary:prompt1:f4")),
            call_forecaster_5(prompt1, replay_key=make_replay_key(question_details, "binary:prompt1:f5")),
        )

    results_prompt1 = await run_prompt1()

    for i, res in enumerate(results_prompt1):
        log(f"\nForecaster_{i+1} step 1 output:\n{res}")

    log(
        "Research sources summary: "
        f"prefer_perplexity={prefer_perplexity()} | ENABLE_PERPLEXITY={ENABLE_PERPLEXITY} | "
        f"ENABLE_SERPER={ENABLE_SERPER} | ENABLE_BRIGHT_DATA={ENABLE_BRIGHT_DATA} | ENABLE_ASKNEWS={ENABLE_ASKNEWS}"
    )

    context_map = {
        "1": f"Current context: {context_current.formatted}\nOutside view prediction: {results_prompt1[0]}",
        "2": f"Current context: {context_current.formatted}\nOutside view prediction: {results_prompt1[2]}",
        "3": f"Current context: {context_current.formatted}\nOutside view prediction: {results_prompt1[1]}",
        "4": f"Current context: {context_current.formatted}\nInside view prediction: {results_prompt1[3]}",
        "5": f"Current context: {context_current.formatted}\nInside view prediction: {results_prompt1[4]}",
    }

    def format_prompt2(f_id: str):
        return BINARY_PROMPT_2.format(
            title=title,
            today=today,
            resolution_criteria=resolution_criteria,
            fine_print=fine_print,
            context=context_map[f_id],
        )

    forecaster_funcs = [
        call_forecaster_1,
        call_forecaster_2,
        call_forecaster_3,
        call_forecaster_4,
        call_forecaster_5,
    ]
    forecaster_funcs = forecaster_funcs[:forecaster_count]
    prompts_prompt2 = []
    for idx in range(len(forecaster_funcs)):
        fid = str(idx + 1)
        if fid in context_map:
            prompts_prompt2.append(format_prompt2(fid))

    results_prompt2 = []
    probabilities = []
    for idx, (func, prompt) in enumerate(zip(forecaster_funcs, prompts_prompt2), start=1):
        samples = []
        probs = []
        for s in range(sample_count):
            suffix = f"binary:prompt2:f{idx}" if sample_count == 1 else f"binary:prompt2:f{idx}:s{s}"
            output = await func(prompt, replay_key=make_replay_key(question_details, suffix))
            samples.append(output)
            try:
                probs.append(extract_probability_from_response_as_percentage_not_decimal(output))
            except Exception as e:
                log(f"Error extracting probability from forecaster {idx} sample {s}: {e}", level="error")
                question_errors.append(f"Forecaster {idx} sample {s} missing Probability line.")
        if probs:
            avg_prob = float(np.mean(probs))
        else:
            avg_prob = None
        probabilities.append(avg_prob)
        joined = "\n--- sample ---\n".join(samples)
        results_prompt2.append(joined)

    base_weights = [1, 1, 1, 2, 2][: len(forecaster_funcs)]
    weights = base_weights
    valid_pairs = [(p / 100.0, w) for p, w in zip(probabilities, weights) if p is not None]
    if valid_pairs:
        vals, wts = zip(*valid_pairs)
        final_prob = aggregate_binary(
            list(vals),
            weights=list(wts),
            mode=run_config.aggregation_mode,
            trim_ratio=run_config.aggregation_trim_ratio,
        )
        if final_prob is not None:
            capped = cap_probability(
                final_prob,
                lo=run_config.probability_cap_low,
                hi=run_config.probability_cap_high,
            )
            if capped != final_prob:
                log("Probability capped by configured bounds", level="warn")
            final_prob = capped
    else:
        final_prob = None

    prior_info = {}
    if run_config.enable_priors and final_prob is not None:
        prior, meta = get_binary_prior(question_details)
        if prior is not None:
            final_prob = blend_prior(final_prob, prior, weight=run_config.prior_weight)
            prior_info = {"prior": prior, "meta": meta, "weight": run_config.prior_weight}
            log(f"Applied prior from {meta.get('source', 'unknown')} with weight {run_config.prior_weight}", level="info")

    critique_result = {}
    if run_config.enable_critique and final_prob is not None:
        critique_result = await run_binary_critique(
            final_prob,
            "\n".join(results_prompt2),
            context_current.formatted,
        )
        suggested = critique_result.get("suggested_probability")
        if isinstance(suggested, (int, float)):
            final_prob = cap_probability(
                float(suggested),
                lo=run_config.probability_cap_low,
                hi=run_config.probability_cap_high,
            )
            log("Critique adjusted probability", level="info")

    log(f"\nFinal predictions (raw pct): {probabilities}")
    log(f"Result (decimal): {final_prob}")
    for idx, prob in enumerate(probabilities, start=1):
        if prob is not None:
            log(f"Forecaster {idx} probability: {prob/100:.3f}", level="probability")
    if final_prob is not None:
        log(f"Ensemble probability: {final_prob:.3f}", level="probability")

    final_outputs = "\n\n".join(
        f"=== Forecaster {i+1} ===\nOutput:\n{out}\nPredicted Probability: {prob if prob is not None else 'N/A'}%"
        for i, (out, prob) in enumerate(zip(results_prompt2, probabilities))
    )

    log(final_outputs)

    # Summarize search usage for easy auditing
    try:
        search_counts = logger.get_search_counts()
        serper_attempted, serper_success = logger.get_serper_url_stats()
        log(
            f"Search summary: {search_counts} | serper_attempted={serper_attempted} serper_success={serper_success}",
            level="info",
        )
    except Exception:
        pass

    if return_details:
        details = {
            "probabilities_pct": probabilities,
            "weights": weights,
            "raw_outputs": results_prompt2,
            "errors": question_errors,
            "prior": prior_info,
            "critique": critique_result,
            "research_reports": question_details.get("research_reports", []),
        }
        return final_prob, final_outputs, details

    return final_prob, final_outputs
