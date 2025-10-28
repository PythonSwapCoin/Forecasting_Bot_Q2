#!/usr/bin/env python3
"""
Test script for the new configurable forecaster models
"""

import asyncio
import os
from dotenv import load_dotenv
from llm_calls import call_forecaster_1, call_forecaster_2, call_forecaster_3, call_forecaster_4, call_forecaster_5
from model_config import get_model_config, print_current_config

load_dotenv()

async def test_forecaster_models():
    """Test all forecaster models with a simple prompt."""
    
    # Check if API key is available
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ OPENROUTER_API_KEY not found in environment variables")
        print("Please add your OpenRouter API key to the .env file")
        return False
    
    print("🧪 Testing Configurable Forecaster Models")
    print("=" * 50)
    
    # Show current configuration
    print_current_config()
    
    test_prompt = "What is 2+2? Answer with just the number."
    
    forecasters = [
        ("Forecaster 1", call_forecaster_1),
        ("Forecaster 2", call_forecaster_2), 
        ("Forecaster 3", call_forecaster_3),
        ("Forecaster 4", call_forecaster_4),
        ("Forecaster 5", call_forecaster_5),
    ]
    
    print(f"\nTesting with prompt: '{test_prompt}'")
    print("=" * 50)
    
    results = []
    
    for name, forecaster_func in forecasters:
        try:
            print(f"\n{name}...")
            response = await forecaster_func(test_prompt)
            print(f"✅ {name}: {response.strip()}")
            results.append((name, True, response.strip()))
        except Exception as e:
            print(f"❌ {name}: {str(e)}")
            results.append((name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    successful = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"Successful: {successful}/{total}")
    
    for name, success, result in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}: {result}")
    
    if successful == total:
        print("\n🎉 All forecasters are working correctly!")
    else:
        print(f"\n⚠️  {total - successful} forecasters failed. Check your OpenRouter API key and model availability.")
    
    return successful == total

if __name__ == "__main__":
    asyncio.run(test_forecaster_models())
