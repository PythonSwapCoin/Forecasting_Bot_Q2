import asyncio
import time
import numpy as np
from numeric import get_numeric_forecast
from binary import get_binary_forecast
import os
import requests
from aiohttp import ClientSession, ClientTimeout, ClientError
import json
import sys
import re
import io
from multiple_choice import get_multiple_choice_forecast
from asknews_sdk import AskNewsSDK
from prompts import context
from dotenv import load_dotenv
import aiohttp
from prompts import claude_context, gpt_context
"""
This file contains the main forecasting logic, question-type specific functions are abstracted.
"""

load_dotenv()

METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
ASKNEWS_CLIENT_ID = os.getenv("ASKNEWS_CLIENT_ID")
ASKNEWS_SECRET = os.getenv("ASKNEWS_SECRET")
EXA_API_KEY = os.getenv("EXA_API_KEY")

async def numeric_forecast(question_details, write=None):
    return await get_numeric_forecast(question_details, write)

async def binary_forecast(question_details, write=None, return_details: bool = False):
    """
    Run binary forecast pipeline.

    Args:
        question_details: question dict
        write: logger function
        return_details: when True, returns (forecast, comment, details) where details
                        includes per-forecaster probabilities, weights, and raw outputs.
    """
    return await get_binary_forecast(question_details, write, return_details=return_details)

async def multiple_choice_forecast(question_details, write=None):
    return await get_multiple_choice_forecast(question_details, write)


