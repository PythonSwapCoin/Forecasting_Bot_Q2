import datetime
import re
import numpy as np
import os
from aiohttp import ClientSession, ClientTimeout
import dotenv
from search import call_asknews, call_perplexity
from llm_calls import call_claude, call_claude_with_fallback, call_gpt_o4_mini_with_fallback, call_forecaster_1, call_forecaster_2, call_forecaster_3, call_forecaster_4, call_forecaster_5
from openai import OpenAI
import asyncio

def write(x):
    print(x)

dotenv.load_dotenv()

METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
ASKNEWS_CLIENT_ID = os.getenv("ASKNEWS_CLIENT_ID")
ASKNEWS_SECRET = os.getenv("ASKNEWS_SECRET")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

NUM_RUNS = 5

BINARY_PROMPT_TEMPLATE = """
You are a professional forecaster interviewing for a job.

Your interview question is:
{title}

Question background:
{background}

This question's outcome will be determined by the specific criteria below. These criteria have not yet been satisfied:
{resolution_criteria}

{fine_print}

Your research assistant says:
{summary_report}

Today is {today}.

Before answering you write:
(a) The time left until the outcome to the question is known.
(b) The status quo outcome if nothing changed.
(c) A brief description of a scenario that results in a No outcome.
(d) A brief description of a scenario that results in a Yes outcome.

You write your rationale remembering that good forecasters put extra weight on the status quo outcome since the world changes slowly most of the time. Think deeply about the question and approach it from multiple possible viewpoints.

The last thing you write is your final answer as: "Probability: ZZ%", 0-100
"""

MULTIPLE_CHOICE_PROMPT_TEMPLATE = """
You are a professional forecaster interviewing for a job.

Your interview question is:
{title}

The options are: {options}

Background:
{background}

{resolution_criteria}

{fine_print}

Your research assistant says:
{summary_report}

Today is {today}.

Before answering you write:
(a) The time left until the outcome to the question is known.
(b) The status quo outcome if nothing changed.
(c) A description of an scenario that results in an unexpected outcome.

You write your rationale remembering that (1) good forecasters put extra weight on the status quo outcome since the world changes slowly most of the time, and (2) good forecasters leave some moderate probability on most options to account for unexpected outcomes.

The last thing you write is your final probabilities for the N options in this order {options}. Format your output **EXACTLY** as below, ensuring that the **probabilities are between 0 and 100, sum to 100, and are not followed by a % sign**:

Probabilities: [Probability_1, Probability_2, ..., Probability_N]
"""

async def run_research(question: str, write=print) -> str:
    research = ""
    if ASKNEWS_CLIENT_ID and ASKNEWS_SECRET:
        prompt = f"Please fetch all news articles relevant to this forecasting question: {question}"
        research = await call_asknews(question)

    prompt = f"""
            You are an assistant to a superforecaster.
            The superforecaster will give you a question they intend to forecast on.
            To be a great assistant, you generate a concise but detailed rundown of the most relevant news, including if the question would resolve Yes or No based on current information.
            You do not produce forecasts yourself.

            Question:
            {question}
            """
    
    pplx = call_perplexity(prompt)
    research += pplx

    write(f"########################\nResearch Found:\n{research}\n########################")

    return research

# Calls o4-mini via OpenRouter instead of direct OpenAI
async def call_llm(prompt):
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "openai/o4-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 16000
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {OPENROUTER_API_KEY}"
    }

    max_retries = 3
    backoff_base = 2

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=300)
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        response_text = await response.text()
                        write(f"[call_llm] Error: HTTP {response.status}: {response_text}")
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            write(f"[call_llm] Attempt {attempt} failed: {e}")
        
        if attempt < max_retries:
            wait_time = backoff_base * attempt
            await asyncio.sleep(wait_time)
        else:
            raise Exception(f"OpenRouter API failed after {max_retries} attempts")


async def call_gpt(prompt):
    # Use OpenRouter instead of direct OpenAI
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "openai/o4-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 16000
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {OPENROUTER_API_KEY}"
    }

    max_retries = 3
    backoff_base = 2

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=300)
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        answer = data['choices'][0]['message']['content']
                        if answer is None:
                            raise ValueError("No answer returned from GPT")
                        return answer
                    else:
                        response_text = await response.text()
                        write(f"[call_gpt] Error: HTTP {response.status}: {response_text}")
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            write(f"[call_gpt] Attempt {attempt} failed: {e}")
        
        if attempt < max_retries:
            wait_time = backoff_base * attempt
            await asyncio.sleep(wait_time)
        else:
            write(f"Error in call_gpt: OpenRouter API failed after {max_retries} attempts")
            return f"Error generating response: OpenRouter API failed after {max_retries} attempts"


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