import asyncio
import datetime
import re
import json
import numpy as np
from aggregation import aggregate_mcq
from config import load_run_config
from prompts import (
    MULTIPLE_CHOICE_PROMPT_historical,
    MULTIPLE_CHOICE_PROMPT_current,
    MULTIPLE_CHOICE_PROMPT_1,
    MULTIPLE_CHOICE_PROMPT_2,
    MULTIPLE_CHOICE_PROMPT_MONTE_CARLO,
)
from llm_calls import call_claude, call_gpt_o3, call_gpt_o4_mini
from search import process_search_queries
from logging_utils import get_current_logger
from replay import make_replay_key
from evidence import ResearchResult


def _has_usable_research(result: ResearchResult | str) -> bool:
    text = result.formatted if isinstance(result, ResearchResult) else str(result or "")
    if not text.strip():
        return False
    lowered = text.lower()
    positive_markers = ["<summary", "<rawcontent", "<agent_report", "<asknews_articles"]
    if any(marker in lowered for marker in positive_markers):
        return True
    return len(text.strip()) > 300

def extract_option_probabilities_from_response(forecast_text: str, num_options: int) -> list[float]:
    matches = re.findall(r"Probabilities:\s*\[([0-9.,\s]+)\]", forecast_text)
    if not matches:
        raise ValueError(f"Could not extract 'Probabilities' list from response: {forecast_text}")
    last_match = matches[-1]
    numbers = [float(n.strip()) for n in last_match.split(",") if n.strip()]
    if len(numbers) != num_options:
        raise ValueError(f"Expected {num_options} probabilities, got {len(numbers)}: {numbers}")
    return numbers

def normalize_probabilities(probs: list[float]) -> list[float]:
    probs = [max(min(p, 99), 1) for p in probs]
    total = sum(probs)
    normed = [p / total for p in probs]
    normed[-1] += 1.0 - sum(normed)  # minor fix for rounding
    return normed

async def get_multiple_choice_forecast(question_details: dict, write=print) -> tuple[dict[str, float], str]:
    run_config = load_run_config()
    sample_count = run_config.forecast_runs_per_model
    if run_config.enable_replay_mode and sample_count > 1:
        sample_count = 1
    forecaster_count = max(1, min(5, run_config.forecaster_count))
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    title = question_details["title"]
    if not question_details.get("slug"):
        slug = "".join(c.lower() if c.isalnum() else "-" for c in title).strip("-") or "mcq-question"
        question_details["slug"] = slug
    resolution_criteria = question_details["resolution_criteria"]
    background = question_details["description"]
    fine_print = question_details.get("fine_print", "")
    options = question_details["options"]
    num_options = len(options)

    logger = get_current_logger()
    if write is None:
        write = logger.log

    async def format_and_call_gpt(prompt_template, replay_suffix: str):
        content = prompt_template.format(
            title=title,
            today=today,
            background=background,
            resolution_criteria=resolution_criteria,
            fine_print=fine_print,
            options=options,
        )
        return content, await call_gpt_o3(content, replay_key=make_replay_key(question_details, replay_suffix))

    historical_task = asyncio.create_task(format_and_call_gpt(MULTIPLE_CHOICE_PROMPT_historical, "mcq:historical_context"))
    current_task = asyncio.create_task(format_and_call_gpt(MULTIPLE_CHOICE_PROMPT_current, "mcq:current_context"))
    (historical_prompt, historical_output), (current_prompt, current_output) = await asyncio.gather(historical_task, current_task)

    context_historical, context_current = await asyncio.gather(
        process_search_queries(
            historical_output,
            forecaster_id="-1",
            question_details=question_details,
            replay_key=make_replay_key(question_details, "mcq:historical_search"),
            max_queries=run_config.max_historical_queries,
        ),
        process_search_queries(
            current_output,
            forecaster_id="0",
            question_details=question_details,
            replay_key=make_replay_key(question_details, "mcq:current_search"),
            max_queries=run_config.max_current_queries,
        ),
    )

    if not _has_usable_research(context_historical) and not _has_usable_research(context_current):
        logger.error("Research failure: no usable historical or current context retrieved. Proceeding with empty context.")
        context_historical = "No usable historical research retrieved; proceed with base-rate reasoning only."
        context_current = "No usable current research retrieved; proceed with general reasoning."
    else:
        if not _has_usable_research(context_historical):
            logger.error("Historical research missing; proceeding with current context only.")
            context_historical = "No usable historical research retrieved; proceed with base-rate reasoning only."
        if not _has_usable_research(context_current):
            logger.error("Current research missing; proceeding with historical context only.")
            context_current = "No usable current research retrieved; proceed with general reasoning."

    write("\nHistorical context LLM output:\n" + historical_output)
    write("\nCurrent context LLM output:\n" + current_output)
    write("\nHistorical context search results:\n" + context_historical.formatted)
    write("\nCurrent context search results:\n" + context_current.formatted)

    prompt1 = MULTIPLE_CHOICE_PROMPT_1.format(
        title=title,
        today=today,
        resolution_criteria=resolution_criteria,
        fine_print=fine_print,
        context=context_historical.formatted,
        options=options
    )

    forecaster_funcs = [
        call_claude,
        call_claude,
        call_gpt_o4_mini,
        call_gpt_o3,
        call_gpt_o3,
    ][:forecaster_count]

    async def run_prompt1():
        tasks = []
        for idx, func in enumerate(forecaster_funcs, start=1):
            tasks.append(func(prompt1, replay_key=make_replay_key(question_details, f"mcq:prompt1:f{idx}")))
        return await asyncio.gather(*tasks)

    results_prompt1 = await run_prompt1()

    for i, res in enumerate(results_prompt1):
        write(f"\nForecaster_{i+1} step 1 output:\n{res}")

    context_map = {
        "1": f"Current context: {context_current.formatted}\nOutside view prediction: {results_prompt1[0]}",
        "2": f"Current context: {context_current.formatted}\nOutside view prediction: {results_prompt1[2]}",
        "3": f"Current context: {context_current.formatted}\nOutside view prediction: {results_prompt1[1]}",
        "4": f"Current context: {context_current.formatted}\nInside view prediction: {results_prompt1[3]}",
        "5": f"Current context: {context_current.formatted}\nInside view prediction: {results_prompt1[4]}",
    }

    def format_prompt2(f_id):
        return MULTIPLE_CHOICE_PROMPT_2.format(
            title=title,
            today=today,
            resolution_criteria=resolution_criteria,
            fine_print=fine_print,
            context=context_map[f_id],
            options=options
        )

    async def run_prompt2():
        outputs = []
        prompts = [
            format_prompt2("1"),
            format_prompt2("2"),
            format_prompt2("3"),
            format_prompt2("4"),
            format_prompt2("5"),
        ][: len(forecaster_funcs)]
        for idx, (func, prompt) in enumerate(zip(forecaster_funcs, prompts), start=1):
            samples = []
            for s in range(sample_count):
                suffix = f"mcq:prompt2:f{idx}" if sample_count == 1 else f"mcq:prompt2:f{idx}:s{s}"
                out = await func(prompt, replay_key=make_replay_key(question_details, suffix))
                samples.append(out)
            outputs.append(samples)
        return outputs

    sample_outputs = await run_prompt2()

    all_probs = []
    final_outputs = []

    for i, sample_list in enumerate(sample_outputs):
        probs_accum = []
        joined_outputs = []
        for s_idx, out in enumerate(sample_list):
            try:
                write(f"Forecaster {i+1} step 2 output (sample {s_idx}): {out}")
                probs = extract_option_probabilities_from_response(out, num_options)
                probs = normalize_probabilities(probs)
                probs_accum.append(probs)
            except Exception as e:
                write(f"Error parsing probabilities from Forecaster {i+1} sample {s_idx}: {e}")
            joined_outputs.append(out)
        if probs_accum:
            averaged = np.mean(np.array(probs_accum), axis=0).tolist()
        else:
            averaged = [1.0 / num_options] * num_options
        all_probs.append(averaged)
        final_outputs.append(f"=== Forecaster {i+1} ===\n" + "\n--- sample ---\n".join(joined_outputs) + "\n")

    probs_matrix = np.array(all_probs)
    weight_list = [1, 1, 1, 2, 2][: len(probs_matrix)]
    aggregated = aggregate_mcq(
        [{opt: float(p) for opt, p in zip(options, row)} for row in probs_matrix],
        weights=weight_list,
        mode=run_config.aggregation_mode,
    )
    probability_yes_per_category = {opt: float(aggregated.get(opt, 0.0)) for opt in options}

    comment = (
        f"Average Probability Yes Per Category: `{probability_yes_per_category}`\n\n"
        + "\n\n".join(final_outputs)
    )


    write("\nFinal averaged probabilities per category:")
    write(json.dumps(probability_yes_per_category, indent=2))
    write("\nForecast comment:")
    write(comment)

    return probability_yes_per_category, comment
