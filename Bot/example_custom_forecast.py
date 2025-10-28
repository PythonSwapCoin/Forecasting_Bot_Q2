#!/usr/bin/env python3
"""
Example Custom Question Forecasting

This script shows how to forecast on custom questions programmatically.
It includes examples for all three question types.
"""

import asyncio
import os
import sys
from typing import Dict, Any

# Add the Bot directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from forecaster import binary_forecast, numeric_forecast, multiple_choice_forecast

def create_binary_question() -> Dict[str, Any]:
    """Create an example binary question."""
    return {
        "title": "Will the price of Bitcoin exceed $100,000 by the end of 2025?",
        "description": "This question asks about the future price of Bitcoin, specifically whether it will reach or exceed $100,000 USD by December 31, 2025.",
        "resolution_criteria": "This question will resolve as 'Yes' if Bitcoin's price reaches or exceeds $100,000 USD at any point before or on December 31, 2025, as measured by CoinMarketCap's closing price. The price must be sustained for at least 1 hour to count.",
        "fine_print": "Price data will be sourced from CoinMarketCap. In case of data unavailability, alternative sources like CoinGecko will be used.",
        "type": "binary"
    }

def create_numeric_question() -> Dict[str, Any]:
    """Create an example numeric question."""
    return {
        "title": "What will be the unemployment rate in the United States in Q2 2025?",
        "description": "This question asks for a forecast of the US unemployment rate for the second quarter of 2025 (April-June 2025).",
        "resolution_criteria": "This question will resolve based on the seasonally adjusted unemployment rate reported by the US Bureau of Labor Statistics for Q2 2025. The rate will be the average of the three monthly rates (April, May, June).",
        "fine_print": "Data source: US Bureau of Labor Statistics, seasonally adjusted unemployment rate.",
        "type": "numeric",
        "scaling": {
            "range_min": 0,
            "range_max": 20,
            "zero_point": None
        },
        "open_upper_bound": False,
        "open_lower_bound": False,
        "unit": "percentage points"
    }

def create_multiple_choice_question() -> Dict[str, Any]:
    """Create an example multiple choice question."""
    return {
        "title": "Which company will have the highest market capitalization on December 31, 2025?",
        "description": "This question asks which of the major tech companies will have the highest market capitalization at the end of 2025.",
        "resolution_criteria": "This question will resolve based on the market capitalization at market close on December 31, 2025, as reported by major financial data providers (Yahoo Finance, Bloomberg, etc.).",
        "fine_print": "Market cap will be calculated as shares outstanding × stock price at market close on December 31, 2025.",
        "type": "multiple_choice",
        "options": [
            "Apple",
            "Microsoft", 
            "Google (Alphabet)",
            "Amazon",
            "Tesla",
            "Meta (Facebook)",
            "Other"
        ]
    }

async def run_example_forecasts():
    """Run example forecasts for all question types."""
    
    # Create output directory
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "example_forecasts"))
    os.makedirs(output_dir, exist_ok=True)
    
    examples = [
        ("binary", create_binary_question()),
        ("numeric", create_numeric_question()),
        ("multiple_choice", create_multiple_choice_question())
    ]
    
    for question_type, question_details in examples:
        print(f"\n{'='*60}")
        print(f"FORECASTING {question_type.upper()} QUESTION")
        print(f"{'='*60}")
        print(f"Question: {question_details['title']}")
        print()
        
        # Create output file
        filename = f"example_{question_type}_forecast.txt"
        output_path = os.path.join(output_dir, filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            def write_to_file(line: str):
                print(f"[WRITE] {line}")
                f.write(line + "\n")
            
            # Write question details
            write_to_file("=" * 60)
            write_to_file(f"EXAMPLE {question_type.upper()} FORECAST")
            write_to_file("=" * 60)
            write_to_file(f"Question: {question_details['title']}")
            write_to_file(f"Type: {question_details['type']}")
            write_to_file(f"Description: {question_details['description']}")
            write_to_file(f"Resolution Criteria: {question_details['resolution_criteria']}")
            if question_details.get('fine_print'):
                write_to_file(f"Fine Print: {question_details['fine_print']}")
            write_to_file("=" * 60)
            write_to_file("")
            
            try:
                # Run the appropriate forecasting function
                if question_type == "binary":
                    forecast, comment = await binary_forecast(question_details, write=write_to_file)
                    write_to_file(f"\nFINAL BINARY FORECAST: {forecast}")
                    
                elif question_type == "numeric":
                    forecast, comment = await numeric_forecast(question_details, write=write_to_file)
                    write_to_file(f"\nFINAL NUMERIC FORECAST: {forecast}")
                    
                elif question_type == "multiple_choice":
                    forecast, comment = await multiple_choice_forecast(question_details, write=write_to_file)
                    write_to_file(f"\nFINAL MULTIPLE CHOICE FORECAST: {forecast}")
                
                write_to_file(f"\nDETAILED COMMENT:\n{comment}")
                print(f"✅ {question_type.capitalize()} forecast completed successfully!")
                
            except Exception as e:
                error_msg = f"Error during {question_type} forecasting: {str(e)}"
                print(f"❌ {error_msg}")
                write_to_file(f"\nERROR: {error_msg}")
    
    print(f"\n{'='*60}")
    print("ALL EXAMPLE FORECASTS COMPLETED!")
    print(f"Results saved to: {output_dir}")
    print(f"{'='*60}")

def main():
    """Main function to run example forecasts."""
    try:
        asyncio.run(run_example_forecasts())
    except KeyboardInterrupt:
        print("\n\nExample forecasts cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
