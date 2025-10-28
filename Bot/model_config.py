#!/usr/bin/env python3
"""
Centralized model configuration for forecasting system.

This file allows you to easily change which models each forecaster uses
through OpenRouter. All forecasters will use OpenRouter by default.
"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# Default model configuration for each forecaster
DEFAULT_MODEL_CONFIG = {
    "forecaster_1": "anthropic/claude-haiku-4.5",
    "forecaster_2": "google/gemini-2.5-flash", 
    "forecaster_3": "openai/gpt-5-chat",
    "forecaster_4": "openai/o4-mini",
    "forecaster_5": "x-ai/grok-4-fast"
}

# Alternative model options (you can easily switch to these)
ALTERNATIVE_MODELS = {
    # Claude models
    "claude_3_5_sonnet": "anthropic/claude-3.5-sonnet",
    "claude_3_5_haiku": "anthropic/claude-3.5-haiku",
    "claude_haiku_4_5": "anthropic/claude-haiku-4.5",
    
    # GPT models
    "gpt_4o": "openai/gpt-4o",
    "gpt_4o_mini": "openai/gpt-4o-mini",
    "gpt_5_chat": "openai/gpt-5-chat",
    "o4_mini": "openai/o4-mini",
    
    # Gemini models
    "gemini_2_5_flash": "google/gemini-2.5-flash",
    "gemini_2_5_pro": "google/gemini-2.5-pro",
    
    # Grok models
    "grok_4_fast": "x-ai/grok-4-fast",
    "grok_4": "x-ai/grok-4",
    
    # Other models
    "llama_3_1_405b": "meta-llama/llama-3.1-405b",
    "qwen_2_5_72b": "qwen/qwen-2.5-72b",
}

def get_model_config() -> Dict[str, str]:
    """
    Get the current model configuration.
    
    You can override the default models by setting environment variables:
    - FORECASTER_1_MODEL
    - FORECASTER_2_MODEL
    - FORECASTER_3_MODEL
    - FORECASTER_4_MODEL
    - FORECASTER_5_MODEL
    
    Returns:
        Dictionary mapping forecaster names to model names
    """
    config = DEFAULT_MODEL_CONFIG.copy()
    
    # Override with environment variables if set
    for i in range(1, 6):
        env_var = f"FORECASTER_{i}_MODEL"
        if os.getenv(env_var):
            config[f"forecaster_{i}"] = os.getenv(env_var)
    
    return config

def get_forecaster_model(forecaster_id: int) -> str:
    """
    Get the model for a specific forecaster.
    
    Args:
        forecaster_id: Forecaster number (1-5)
        
    Returns:
        Model name for the forecaster
    """
    config = get_model_config()
    return config.get(f"forecaster_{forecaster_id}", DEFAULT_MODEL_CONFIG[f"forecaster_{forecaster_id}"])

def set_forecaster_model(forecaster_id: int, model: str) -> None:
    """
    Set the model for a specific forecaster (runtime only, not persistent).
    
    Args:
        forecaster_id: Forecaster number (1-5)
        model: Model name to use
    """
    if forecaster_id < 1 or forecaster_id > 5:
        raise ValueError("Forecaster ID must be between 1 and 5")
    
    # This would need to be implemented with a global state if you want runtime changes
    # For now, use environment variables for persistence
    print(f"To set forecaster {forecaster_id} to use {model}, set environment variable:")
    print(f"FORECASTER_{forecaster_id}_MODEL={model}")

def print_current_config() -> None:
    """Print the current model configuration."""
    config = get_model_config()
    print("Current Forecaster Model Configuration:")
    print("=" * 50)
    for forecaster, model in config.items():
        print(f"{forecaster}: {model}")
    print("=" * 50)

def get_available_models() -> Dict[str, str]:
    """Get all available model options."""
    return ALTERNATIVE_MODELS.copy()

if __name__ == "__main__":
    # Print current configuration when run directly
    print_current_config()
    print("\nAvailable model options:")
    for name, model in get_available_models().items():
        print(f"  {name}: {model}")
