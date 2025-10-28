#!/usr/bin/env python3
"""
Model Configuration Manager

This script allows you to easily change which models each forecaster uses.
All models will be called through OpenRouter.
"""

import os
import sys
from model_config import get_model_config, get_available_models, print_current_config, set_forecaster_model

def main():
    """Interactive model configuration manager."""
    print("🤖 Forecaster Model Configuration Manager")
    print("=" * 50)
    
    while True:
        print("\nCurrent Configuration:")
        print_current_config()
        
        print("\nOptions:")
        print("1. Change a forecaster's model")
        print("2. View available models")
        print("3. Reset to defaults")
        print("4. Set via environment variables")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == "1":
            change_forecaster_model()
        elif choice == "2":
            view_available_models()
        elif choice == "3":
            reset_to_defaults()
        elif choice == "4":
            show_env_instructions()
        elif choice == "5":
            print("Goodbye! 👋")
            break
        else:
            print("Invalid choice. Please try again.")

def change_forecaster_model():
    """Change a specific forecaster's model."""
    try:
        forecaster_id = int(input("Enter forecaster ID (1-5): "))
        if forecaster_id < 1 or forecaster_id > 5:
            print("Forecaster ID must be between 1 and 5")
            return
        
        print(f"\nAvailable models for forecaster {forecaster_id}:")
        models = get_available_models()
        for i, (name, model) in enumerate(models.items(), 1):
            print(f"{i}. {name}: {model}")
        
        model_choice = input(f"\nEnter model number (1-{len(models)}) or model name: ").strip()
        
        # Try to parse as number first
        try:
            model_index = int(model_choice) - 1
            if 0 <= model_index < len(models):
                selected_model = list(models.values())[model_index]
            else:
                print("Invalid model number")
                return
        except ValueError:
            # Try to find by name
            selected_model = None
            for name, model in models.items():
                if name.lower() == model_choice.lower() or model == model_choice:
                    selected_model = model
                    break
            
            if not selected_model:
                print("Model not found")
                return
        
        print(f"\nSetting forecaster {forecaster_id} to use: {selected_model}")
        print(f"To make this permanent, add this to your .env file:")
        print(f"FORECASTER_{forecaster_id}_MODEL={selected_model}")
        
        # For runtime changes, we could implement a global state here
        # For now, just show the environment variable instruction
        
    except ValueError:
        print("Invalid input")

def view_available_models():
    """Show all available models."""
    print("\nAvailable Models:")
    print("=" * 30)
    models = get_available_models()
    for name, model in models.items():
        print(f"{name}: {model}")

def reset_to_defaults():
    """Reset all forecasters to default models."""
    print("\nDefault Model Configuration:")
    print("=" * 30)
    print("Forecaster 1: anthropic/claude-haiku-4.5")
    print("Forecaster 2: google/gemini-2.5-flash")
    print("Forecaster 3: openai/gpt-5-chat")
    print("Forecaster 4: openai/o4-mini")
    print("Forecaster 5: x-ai/grok-4-fast")
    print("\nTo reset, remove any FORECASTER_X_MODEL variables from your .env file")

def show_env_instructions():
    """Show instructions for setting models via environment variables."""
    print("\nEnvironment Variable Configuration:")
    print("=" * 40)
    print("Add these variables to your .env file to set models:")
    print()
    print("# Forecaster Models (optional - uses defaults if not set)")
    print("FORECASTER_1_MODEL=anthropic/claude-haiku-4.5")
    print("FORECASTER_2_MODEL=google/gemini-2.5-flash")
    print("FORECASTER_3_MODEL=openai/gpt-5-chat")
    print("FORECASTER_4_MODEL=openai/o4-mini")
    print("FORECASTER_5_MODEL=x-ai/grok-4-fast")
    print()
    print("You can use any model from the available models list.")
    print("The system will automatically choose the appropriate context")
    print("(Claude context for Claude models, GPT context for others).")

if __name__ == "__main__":
    main()
