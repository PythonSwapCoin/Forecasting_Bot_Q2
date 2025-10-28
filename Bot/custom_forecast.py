#!/usr/bin/env python3
"""
Custom Question Forecasting Script

This script allows you to forecast on custom questions that are not from Metaculus.
It creates a mock question structure and uses the existing forecasting functions.

Usage:
    python custom_forecast.py

The script will prompt you for:
1. Question type (binary, numeric, multiple_choice)
2. Question title
3. Question description/background
4. Resolution criteria
5. Additional details based on question type
"""

import asyncio
import datetime
import json
import os
import sys
from typing import Dict, Any, List, Union

# Add the Bot directory to the path so we can import the forecasting modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from forecaster import binary_forecast, numeric_forecast, multiple_choice_forecast

def create_question_structure(
    question_type: str,
    title: str,
    description: str,
    resolution_criteria: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a question structure that matches the expected format for the forecasting functions.
    
    Args:
        question_type: "binary", "numeric", or "multiple_choice"
        title: The question title
        description: Background/description of the question
        resolution_criteria: How the question will be resolved
        **kwargs: Additional parameters specific to question type
    
    Returns:
        Dictionary in the format expected by forecasting functions
    """
    
    base_structure = {
        "title": title,
        "description": description,
        "resolution_criteria": resolution_criteria,
        "fine_print": kwargs.get("fine_print", ""),
        "type": question_type
    }
    
    if question_type == "binary":
        # Binary questions don't need additional structure
        pass
        
    elif question_type == "numeric":
        # Numeric questions need scaling information
        base_structure.update({
            "scaling": {
                "range_min": kwargs.get("range_min", 0),
                "range_max": kwargs.get("range_max", 100),
                "zero_point": kwargs.get("zero_point", None)
            },
            "open_upper_bound": kwargs.get("open_upper_bound", False),
            "open_lower_bound": kwargs.get("open_lower_bound", False),
            "unit": kwargs.get("unit", "")
        })
        
    elif question_type == "multiple_choice":
        # Multiple choice questions need options
        base_structure["options"] = kwargs.get("options", [])
        
    else:
        raise ValueError(f"Unsupported question type: {question_type}")
    
    return base_structure

def get_user_input() -> Dict[str, Any]:
    """
    Get user input for creating a custom question.
    
    Returns:
        Dictionary containing all the question parameters
    """
    print("=" * 60)
    print("CUSTOM QUESTION FORECASTING")
    print("=" * 60)
    print()
    
    # Get basic question information
    question_type = input("Question type (binary/numeric/multiple_choice): ").strip().lower()
    while question_type not in ["binary", "numeric", "multiple_choice"]:
        print("Please enter 'binary', 'numeric', or 'multiple_choice'")
        question_type = input("Question type: ").strip().lower()
    
    title = input("Question title: ").strip()
    if not title:
        print("Title cannot be empty!")
        return get_user_input()
    
    print("\nQuestion description/background (press Enter twice when done):")
    description_lines = []
    while True:
        line = input()
        if line == "" and description_lines and description_lines[-1] == "":
            break
        description_lines.append(line)
    description = "\n".join(description_lines[:-1])  # Remove the last empty line
    
    print("\nResolution criteria (press Enter twice when done):")
    criteria_lines = []
    while True:
        line = input()
        if line == "" and criteria_lines and criteria_lines[-1] == "":
            break
        criteria_lines.append(line)
    resolution_criteria = "\n".join(criteria_lines[:-1])  # Remove the last empty line
    
    fine_print = input("\nFine print/additional details (optional): ").strip()
    
    # Get type-specific information
    kwargs = {"fine_print": fine_print}
    
    if question_type == "numeric":
        print("\n--- Numeric Question Settings ---")
        
        try:
            range_min = float(input("Minimum value (default 0): ") or "0")
            range_max = float(input("Maximum value (default 100): ") or "100")
            kwargs["range_min"] = range_min
            kwargs["range_max"] = range_max
            
            open_lower = input("Open lower bound? (y/n, default n): ").strip().lower() == "y"
            open_upper = input("Open upper bound? (y/n, default n): ").strip().lower() == "y"
            kwargs["open_lower_bound"] = open_lower
            kwargs["open_upper_bound"] = open_upper
            
            zero_point = input("Zero point (optional, press Enter to skip): ").strip()
            if zero_point:
                kwargs["zero_point"] = float(zero_point)
            
            unit = input("Unit (e.g., 'USD', 'people', '%', optional): ").strip()
            if unit:
                kwargs["unit"] = unit
                
        except ValueError as e:
            print(f"Invalid numeric input: {e}")
            return get_user_input()
    
    elif question_type == "multiple_choice":
        print("\n--- Multiple Choice Question Settings ---")
        print("Enter options one per line (press Enter on empty line when done):")
        
        options = []
        while True:
            option = input(f"Option {len(options) + 1}: ").strip()
            if not option:
                break
            options.append(option)
        
        if len(options) < 2:
            print("You need at least 2 options for a multiple choice question!")
            return get_user_input()
        
        kwargs["options"] = options
    
    return {
        "question_type": question_type,
        "title": title,
        "description": description,
        "resolution_criteria": resolution_criteria,
        **kwargs
    }

async def forecast_custom_question(question_params: Dict[str, Any]) -> None:
    """
    Forecast on a custom question using the existing forecasting functions.
    
    Args:
        question_params: Dictionary containing question parameters from get_user_input()
    """
    # Create the question structure
    question_details = create_question_structure(**question_params)
    
    print("\n" + "=" * 60)
    print("FORECASTING IN PROGRESS...")
    print("=" * 60)
    print(f"Question: {question_details['title']}")
    print(f"Type: {question_details['type']}")
    print()
    
    # Create output directory if it doesn't exist
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_forecasts"))
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename from title
    filename = f"{''.join(c if c.isalnum() else '_' for c in question_details['title'])[:100]}.txt"
    output_path = os.path.join(output_dir, filename)
    
    # Use safe context manager for writing
    with open(output_path, "w", encoding="utf-8") as f:
        def write_to_file(line: str):
            print(f"[WRITE] {line}")
            f.write(line + "\n")
        
        # Add question details to file
        write_to_file("=" * 60)
        write_to_file("CUSTOM QUESTION FORECAST")
        write_to_file("=" * 60)
        write_to_file(f"Question: {question_details['title']}")
        write_to_file(f"Type: {question_details['type']}")
        write_to_file(f"Description: {question_details['description']}")
        write_to_file(f"Resolution Criteria: {question_details['resolution_criteria']}")
        if question_details.get('fine_print'):
            write_to_file(f"Fine Print: {question_details['fine_print']}")
        write_to_file("=" * 60)
        write_to_file("")
        
        # Run the appropriate forecasting function
        try:
            if question_details["type"] == "binary":
                forecast, comment = await binary_forecast(question_details, write=write_to_file)
                write_to_file(f"\nFINAL BINARY FORECAST: {forecast}")
                
            elif question_details["type"] == "numeric":
                forecast, comment = await numeric_forecast(question_details, write=write_to_file)
                write_to_file(f"\nFINAL NUMERIC FORECAST: {forecast}")
                
            elif question_details["type"] == "multiple_choice":
                forecast, comment = await multiple_choice_forecast(question_details, write=write_to_file)
                write_to_file(f"\nFINAL MULTIPLE CHOICE FORECAST: {json.dumps(forecast, indent=2)}")
            
            write_to_file(f"\nDETAILED COMMENT:\n{comment}")
            
        except Exception as e:
            error_msg = f"Error during forecasting: {str(e)}"
            print(f"ERROR: {error_msg}")
            write_to_file(f"\nERROR: {error_msg}")
            raise
    
    print(f"\nForecast completed! Results saved to: {output_path}")

def main():
    """Main function to run the custom forecasting script."""
    try:
        # Get user input
        question_params = get_user_input()
        
        # Run the forecast
        asyncio.run(forecast_custom_question(question_params))
        
    except KeyboardInterrupt:
        print("\n\nForecasting cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
