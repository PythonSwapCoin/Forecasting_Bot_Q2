import datetime
import re
import numpy as np
import os
from aiohttp import ClientSession, ClientTimeout
import dotenv
from search import call_asknews, call_perplexity
from llm_calls import (
    call_claude,
    call_claude_with_fallback,
    call_gpt_o4_mini_with_fallback,
    call_forecaster_1,
    call_forecaster_2,
    call_forecaster_3,
    call_forecaster_4,
    call_forecaster_5,
    call_openrouter_gpt,
)
import asyncio
from prompts import (
    BINARY_PROMPT_TEMPLATE,
    MULTIPLE_CHOICE_PROMPT_TEMPLATE,
    RESEARCH_ASSISTANT_PROMPT_WITH_QUESTION,
)

def write(x):
    print(x)

dotenv.load_dotenv()

ASKNEWS_CLIENT_ID = os.getenv("ASKNEWS_CLIENT_ID")
ASKNEWS_SECRET = os.getenv("ASKNEWS_SECRET")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

NUM_RUNS = 5

async def run_research(question: str, write=print) -> str:
    research = ""
    if ASKNEWS_CLIENT_ID and ASKNEWS_SECRET:
        prompt = f"Please fetch all news articles relevant to this forecasting question: {question}"
        research = await call_asknews(question)

    prompt = RESEARCH_ASSISTANT_PROMPT_WITH_QUESTION.format(question=question)
    
    pplx = call_perplexity(prompt)
    research += pplx

    write(f"########################\nResearch Found:\n{research}\n########################")

    return research

# Calls o4-mini via OpenRouter
async def call_llm(prompt):
    return await call_openrouter_gpt(prompt, model="openai/o4-mini", max_tokens=4000)


def extract_binary_probability(text: str) -> float:
    matches = re.findall(r"(\d+)%", text)
    if matches:
        prob = int(matches[-1])
        return float(np.clip(prob, 1, 99))  # clip between 1 and 99
    raise ValueError(f"Could not extract binary probability from text: {text}")


def extract_mcq_probabilities(forecast_text: str, num_options: int) -> list[float]:
    import re

    matches = re.findall(r"Probabilities:\s*\[([0-9.,\s%]+)\]", forecast_text)
    if not matches:
        raise ValueError(f"Could not extract 'Probabilities' list from response:\n{forecast_text}")
    last_match = matches[-1]

    # Parse numbers
    raw_numbers = [n.strip().replace("%", "") for n in last_match.split(",") if n.strip()]
    numbers = [float(n) for n in raw_numbers]

    # Fix % scaling if necessary
    total = sum(numbers)
    if total > 1.5 and total <= 110:  # probably in %
        numbers = [x / 100 for x in numbers]
        total = sum(numbers)

    if len(numbers) != num_options:
        raise ValueError(f"Expected {num_options} probabilities, got {len(numbers)}: {numbers}")
    if not 0.98 <= total <= 1.02:
        raise ValueError(f"Probabilities do not sum to 1: {numbers}")
    
    # Normalize if close but off
    numbers = [x / total for x in numbers]
    return numbers

def format_binary_prompt(details: dict, summary: str) -> str:
    return BINARY_PROMPT_TEMPLATE.format(
        title=details["title"],
        today=datetime.datetime.now().strftime("%Y-%m-%d"),
        background=details.get("description", ""),
        resolution_criteria=details.get("resolution_criteria", ""),
        fine_print=details.get("fine_print", ""),
        summary_report=summary
    )

def format_mcq_prompt(details: dict, summary: str) -> str:
    return MULTIPLE_CHOICE_PROMPT_TEMPLATE.format(
        title=details["title"],
        today=datetime.datetime.now().strftime("%Y-%m-%d"),
        background=details.get("description", ""),
        resolution_criteria=details.get("resolution_criteria", ""),
        fine_print=details.get("fine_print", ""),
        summary_report=summary,
        options=details.get("options", [])
    )

async def binary_forecast(details: dict, write=print) -> tuple[float, str]:
    summary = await run_research(details["title"], write)
    prompt = format_binary_prompt(details, summary)
    
    # Use configurable forecaster models via OpenRouter
    responses = await asyncio.gather(
        call_forecaster_1(prompt),  # forecaster 1 - claude-haiku-4.5
        call_forecaster_2(prompt),  # forecaster 2 - gemini-2.5-flash
        call_forecaster_3(prompt),  # forecaster 3 - gpt-5-chat
        call_forecaster_4(prompt),  # forecaster 4 - o4-mini
        call_forecaster_5(prompt),  # forecaster 5 - grok-4-fast
    )
    
    parsed = []
    for i, r in enumerate(responses):
        try:
            prob = extract_binary_probability(r)
            parsed.append(prob)
        except Exception as e:
            write(f"WARNING: Error extracting probability from response {i+1}: {e}")
            parsed.append(50.0)  # Default to 50% if extraction fails
    
    avg = np.mean(parsed)
    comment = f"Binary forecast (mean): {avg}%\n\n" + "\n\n".join(f"=== Forecaster {i+1} ===\n{r}" for i, r in enumerate(responses))
    write(comment)
    return avg, comment

async def multiple_choice_forecast(details: dict, write=print) -> tuple[dict[str, float], str]:
    options = details["options"]
    summary = await run_research(details["title"], write)
    prompt = format_mcq_prompt(details, summary)

    responses = await asyncio.gather(*[call_llm(prompt) for _ in range(5)])
    
    extracted = []
    outputs = []
    for i, response in enumerate(responses):
        write(f"\n=== Raw Output #{i+1} ===")
        write(response)
        write("------------------------------------------------------------------------------------------------")
        try:
            probs = extract_mcq_probabilities(response, len(options))
            extracted.append(probs)
            outputs.append(response)
        except Exception as e:
            write(f"WARNING Error extracting probabilities: {e}")
            write("Skipping this response.\n")
    
    if not extracted:
        raise ValueError("No valid probability sets extracted.")

    avg_probs = np.mean(extracted, axis=0)
    result = {opt: float(p) for opt, p in zip(options, avg_probs)}
    comment = f"MCQ forecast (mean): {result}\n\n" + "\n\n".join(outputs)
    write(comment)
    return result, comment
