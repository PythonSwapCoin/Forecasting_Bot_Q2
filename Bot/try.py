import asyncio
from search import agentic_search
from llm_calls import call_openrouter_gpt


async def call_gpt(prompt):
    return await call_openrouter_gpt(prompt, model="openai/gpt-4o-mini", max_tokens=4000)

async def main():
    query = """

    Please retrieve weekly Billboard Artist 100 top 10 charts for the past 12 months and identify how many artists each week were new entrants (previous rank ≥11 or unranked), then summarize the weekly counts and overall trend. 

    """
    ans = await agentic_search(query)

    print(ans)


if __name__ == "__main__":
    asyncio.run(main())
