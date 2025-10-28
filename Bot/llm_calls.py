import asyncio
import numpy as np
import os
from aiohttp import ClientSession, ClientTimeout, ClientError
import json
import sys
from openai import OpenAI
import re
import io
from dotenv import load_dotenv
from prompts import claude_context, gpt_context
from model_config import get_forecaster_model
"""
This file contains the main forecasting logic, question-type specific functions are abstracted.
"""
def write(x):
    print(x)



load_dotenv()
METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

async def call_anthropic_api(prompt, max_tokens=16000, max_retries=7, cached_content=claude_context):
    url = "https://llm-proxy.metaculus.com/proxy/anthropic/v1/messages/"
    headers = {
        "Authorization": f"Token {METACULUS_TOKEN}",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "anthropic-metadata": json.dumps({
            "task_type": "qualitative_forecasting",
            "emphasis": "detailed_reasoning"
        })
    }
    
    data = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "thinking" : {
            "type": "enabled",
            "budget_tokens": 12000
        },
        "system": [
            {
                "type": "text",
                "text": cached_content,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    for attempt in range(max_retries):
        backoff_delay = min(2 ** attempt, 60)
        
        try:
            write(f"Starting API call attempt {attempt + 1}")
            timeout = ClientTimeout(total=300)  # 5 minutes total timeout
            
            async with ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        write(f"API error (status {response.status}): {error_text}")
                        
                        if response.status in [429, 503]:  # Rate limit or service unavailable
                            write(f"Retryable error. Waiting {backoff_delay} seconds...")
                            await asyncio.sleep(backoff_delay)
                            continue
                            
                        response.raise_for_status()
                    
                    result = await response.json()
                    text = ""
                    thinking = ""
                    for block in result.get("content", []):
                        if block.get("type") == "text":
                           text = block.get("text")
                        if block.get("type") == "thinking":
                            thinking = block.get("thinking")
                    
                    print(f"Claude's thinking: {thinking}")
                    return text
                    
                    write("No 'text' block found in content.")
                    return "No final answer found in Claude response."
                        
        except (ClientError, asyncio.TimeoutError) as e:
            write(f"Retryable error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)
            
        except Exception as e:
            write(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)

    raise Exception(f"Failed after {max_retries} attempts")


async def call_claude(prompt):
    try:
        response = await call_anthropic_api(prompt)
        
        if not response:
            write("Warning: Empty response from Anthropic API")
            return "API returned empty response"
            
        return response
        
    except Exception as e:
        write(f"Error in call_claude: {str(e)}")
        return f"Error generating response: {str(e)}"
    

def extract_and_run_python_code(llm_output: str) -> str:
    pattern = re.compile(r'<python>(.*?)</python>', re.DOTALL)
    matches = pattern.findall(llm_output)

    if not matches:
        return "No <python> block found."

    python_code = matches[0].strip()

    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout

    try:
        exec(python_code, {})  # use isolated globals
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return f"Error executing the extracted Python code:\n{tb}"
    finally:
        sys.stdout = old_stdout

    return new_stdout.getvalue()

# Calls o4-mini via OpenRouter instead of direct OpenAI
async def call_gpt(prompt):
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "openai/o4-mini",
        "messages": [
            {"role": "user", "content": gpt_context + "\n" + prompt}
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
                        write(f"[call_gpt] Error: HTTP {response.status}: {response_text}")
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            write(f"[call_gpt] Attempt {attempt} failed: {e}")
        
        if attempt < max_retries:
            wait_time = backoff_base * attempt
            await asyncio.sleep(wait_time)
        else:
            raise Exception(f"OpenRouter API failed after {max_retries} attempts")

async def call_gpt_o3_personal(prompt):
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "openai/o3",
        "messages": [
            {"role": "user", "content": gpt_context + "\n" + prompt}
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
                        write(f"[call_gpt_o3_personal] Error: HTTP {response.status}: {response_text}")
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            write(f"[call_gpt_o3_personal] Attempt {attempt} failed: {e}")
        
        if attempt < max_retries:
            wait_time = backoff_base * attempt
            await asyncio.sleep(wait_time)
        else:
            raise Exception(f"OpenRouter API failed after {max_retries} attempts")


async def call_gpt_o3(prompt):
    # Temporarily short metaculus proxy using personal credits.
    ans = await call_gpt_o3_personal(prompt)
    return ans
    try:
        url = "https://llm-proxy.metaculus.com/proxy/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {METACULUS_TOKEN}"
        }
        
        data = {
            "model": "o3",
            "messages": [{"role": "user", "content": prompt}],
        }
        
        timeout = ClientTimeout(total=300)  # 5 minutes total timeout
        
        async with ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    write(f"API error (status {response.status}): {error_text}")
                    response.raise_for_status()
                
                result = await response.json()
                
                answer = result['choices'][0]['message']['content']
                if answer is None:
                    raise ValueError("No answer returned from GPT")
                return answer
                
    except Exception as e:
        write(f"Error in call_gpt: {str(e)}")
        return f"Error generating response: {str(e)}"


async def call_gpt_o4_mini(prompt):
    prompt = gpt_context + "\n" + prompt
    try:
        url = "https://llm-proxy.metaculus.com/proxy/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {METACULUS_TOKEN}"
        }
        
        data = {
            "model": "o4-mini",
            "messages": [{"role": "user", "content": prompt}],
        }
        
        timeout = ClientTimeout(total=300)  # 5 minutes total timeout
        
        async with ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    write(f"API error (status {response.status}): {error_text}")
                    response.raise_for_status()
                
                result = await response.json()
                
                answer = result['choices'][0]['message']['content']
                if answer is None:
                    raise ValueError("No answer returned from GPT")
                return answer
                
    except Exception as e:
        write(f"Error in call_gpt: {str(e)}")
        return f"Error generating response: {str(e)}"


# OpenRouter API functions
async def call_openrouter_claude(prompt, max_tokens=16000, max_retries=3):
    """Call Claude via OpenRouter as fallback for Metaculus proxy"""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-repo",  # Optional: replace with your repo
        "X-Title": "Forecasting Bot"  # Optional: replace with your app name
    }
    
    data = {
        "model": "anthropic/claude-3.5-sonnet",
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": claude_context
            },
            {
                "role": "user", 
                "content": prompt
            }
        ]
    }
    
    for attempt in range(max_retries):
        backoff_delay = min(2 ** attempt, 30)
        
        try:
            write(f"OpenRouter Claude attempt {attempt + 1}")
            timeout = ClientTimeout(total=300)
            
            async with ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        write(f"OpenRouter API error (status {response.status}): {error_text}")
                        
                        if response.status in [429, 503]:
                            write(f"Rate limited. Waiting {backoff_delay} seconds...")
                            await asyncio.sleep(backoff_delay)
                            continue
                            
                        response.raise_for_status()
                    
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                    
        except (ClientError, asyncio.TimeoutError) as e:
            write(f"OpenRouter retryable error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)
            
        except Exception as e:
            write(f"OpenRouter unexpected error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)

    raise Exception(f"OpenRouter Claude failed after {max_retries} attempts")


async def call_openrouter_gpt(prompt, model="openai/gpt-4o", max_tokens=16000, max_retries=3):
    """Call GPT via OpenRouter as fallback for Metaculus proxy"""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-repo",
        "X-Title": "Forecasting Bot"
    }
    
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": gpt_context
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    for attempt in range(max_retries):
        backoff_delay = min(2 ** attempt, 30)
        
        try:
            write(f"OpenRouter GPT attempt {attempt + 1}")
            timeout = ClientTimeout(total=300)
            
            async with ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        write(f"OpenRouter API error (status {response.status}): {error_text}")
                        
                        if response.status in [429, 503]:
                            write(f"Rate limited. Waiting {backoff_delay} seconds...")
                            await asyncio.sleep(backoff_delay)
                            continue
                            
                        response.raise_for_status()
                    
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                    
        except (ClientError, asyncio.TimeoutError) as e:
            write(f"OpenRouter retryable error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)
            
        except Exception as e:
            write(f"OpenRouter unexpected error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)

    raise Exception(f"OpenRouter GPT failed after {max_retries} attempts")


# Enhanced functions with fallback logic
async def call_claude_with_fallback(prompt):
    """Call Claude with fallback to OpenRouter if Metaculus proxy fails"""
    try:
        # Try Metaculus proxy first
        response = await call_anthropic_api(prompt)
        if response and not response.startswith("Error generating response"):
            return response
    except Exception as e:
        write(f"Metaculus Claude failed: {str(e)}")
    
    # Fallback to OpenRouter
    try:
        write("Falling back to OpenRouter Claude...")
        return await call_openrouter_claude(prompt)
    except Exception as e:
        write(f"OpenRouter Claude also failed: {str(e)}")
        return f"Error generating response: {str(e)}"


async def call_gpt_o4_mini_with_fallback(prompt):
    """Call GPT-o4-mini with fallback to OpenRouter if Metaculus proxy fails"""
    try:
        # Try Metaculus proxy first
        prompt_with_context = gpt_context + "\n" + prompt
        url = "https://llm-proxy.metaculus.com/proxy/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {METACULUS_TOKEN}"
        }
        
        data = {
            "model": "o4-mini",
            "messages": [{"role": "user", "content": prompt_with_context}],
        }
        
        timeout = ClientTimeout(total=300)
        
        async with ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                else:
                    raise Exception(f"Metaculus proxy returned status {response.status}")
                    
    except Exception as e:
        write(f"Metaculus GPT-o4-mini failed: {str(e)}")
    
    # Fallback to OpenRouter
    try:
        write("Falling back to OpenRouter GPT-4o...")
        return await call_openrouter_gpt(prompt, model="openai/gpt-4o")
    except Exception as e:
        write(f"OpenRouter GPT-4o also failed: {str(e)}")
        return f"Error generating response: {str(e)}"


# Configurable forecaster functions using OpenRouter
async def call_forecaster_model(forecaster_id: int, prompt: str, max_tokens: int = 16000, max_retries: int = 3) -> str:
    """
    Call a specific forecaster's configured model via OpenRouter.
    
    Args:
        forecaster_id: Forecaster number (1-5)
        prompt: The prompt to send
        max_tokens: Maximum tokens to generate
        max_retries: Number of retry attempts
        
    Returns:
        Model response text
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    model = get_forecaster_model(forecaster_id)
    write(f"Using {model} for forecaster {forecaster_id}")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-repo",
        "X-Title": "Forecasting Bot"
    }
    
    # Choose appropriate context based on model type
    if "claude" in model.lower():
        system_content = claude_context
    elif "gpt" in model.lower() or "o4" in model.lower():
        system_content = gpt_context
    else:
        # Default to gpt context for other models
        system_content = gpt_context
    
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    for attempt in range(max_retries):
        backoff_delay = min(2 ** attempt, 30)
        
        try:
            write(f"OpenRouter {model} attempt {attempt + 1} for forecaster {forecaster_id}")
            timeout = ClientTimeout(total=300)
            
            async with ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        write(f"OpenRouter API error (status {response.status}): {error_text}")
                        
                        if response.status in [429, 503]:
                            write(f"Rate limited. Waiting {backoff_delay} seconds...")
                            await asyncio.sleep(backoff_delay)
                            continue
                            
                        response.raise_for_status()
                    
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                    
        except (ClientError, asyncio.TimeoutError) as e:
            write(f"OpenRouter retryable error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)
            
        except Exception as e:
            write(f"OpenRouter unexpected error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff_delay)

    raise Exception(f"OpenRouter {model} failed after {max_retries} attempts")


# Convenience functions for each forecaster
async def call_forecaster_1(prompt: str) -> str:
    """Call forecaster 1's configured model."""
    return await call_forecaster_model(1, prompt)

async def call_forecaster_2(prompt: str) -> str:
    """Call forecaster 2's configured model."""
    return await call_forecaster_model(2, prompt)

async def call_forecaster_3(prompt: str) -> str:
    """Call forecaster 3's configured model."""
    return await call_forecaster_model(3, prompt)

async def call_forecaster_4(prompt: str) -> str:
    """Call forecaster 4's configured model."""
    return await call_forecaster_model(4, prompt)

async def call_forecaster_5(prompt: str) -> str:
    """Call forecaster 5's configured model."""
    return await call_forecaster_model(5, prompt)
    
