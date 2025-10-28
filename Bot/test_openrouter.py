#!/usr/bin/env python3
"""
Test script for OpenRouter integration
"""

import asyncio
import os
from dotenv import load_dotenv
from llm_calls import call_openrouter_claude, call_openrouter_gpt, call_claude_with_fallback

load_dotenv()

async def test_openrouter():
    """Test OpenRouter API calls"""
    
    # Check if API key is available
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ OPENROUTER_API_KEY not found in environment variables")
        print("Please add your OpenRouter API key to the .env file")
        return False
    
    print("🧪 Testing OpenRouter integration...")
    
    test_prompt = "What is 2+2? Answer with just the number."
    
    try:
        # Test Claude via OpenRouter
        print("\n1. Testing Claude via OpenRouter...")
        claude_response = await call_openrouter_claude(test_prompt)
        print(f"✅ Claude response: {claude_response}")
        
    except Exception as e:
        print(f"❌ Claude test failed: {e}")
    
    try:
        # Test GPT via OpenRouter
        print("\n2. Testing GPT via OpenRouter...")
        gpt_response = await call_openrouter_gpt(test_prompt)
        print(f"✅ GPT response: {gpt_response}")
        
    except Exception as e:
        print(f"❌ GPT test failed: {e}")
    
    try:
        # Test fallback function
        print("\n3. Testing fallback function...")
        fallback_response = await call_claude_with_fallback(test_prompt)
        print(f"✅ Fallback response: {fallback_response}")
        
    except Exception as e:
        print(f"❌ Fallback test failed: {e}")
    
    print("\n🎉 OpenRouter integration test completed!")

if __name__ == "__main__":
    asyncio.run(test_openrouter())
