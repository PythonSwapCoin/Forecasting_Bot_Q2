# Custom Question Forecasting

This directory contains tools for forecasting on custom questions that are not from Metaculus. You can create your own forecasting questions and get AI-powered forecasts using the same sophisticated forecasting system.

## Files

- `custom_forecast.py` - Interactive script for creating and forecasting custom questions
- `example_custom_forecast.py` - Example script showing how to forecast programmatically
- `CUSTOM_FORECASTING_README.md` - This documentation file

## Quick Start

### Option 1: Interactive Forecasting

Run the interactive script to create and forecast your own questions:

```bash
cd Bot
python custom_forecast.py
```

The script will prompt you for:
1. **Question type**: binary, numeric, or multiple_choice
2. **Question title**: A clear, specific question
3. **Description**: Background information and context
4. **Resolution criteria**: How the question will be resolved
5. **Type-specific details**: Additional parameters based on question type

### Option 2: Programmatic Forecasting

Use the example script as a template for creating your own forecasting code:

```bash
cd Bot
python example_custom_forecast.py
```

## Question Types

### Binary Questions
- **Format**: Yes/No questions
- **Example**: "Will Bitcoin exceed $100,000 by end of 2025?"
- **Output**: Single probability (0-1)

### Numeric Questions
- **Format**: Questions asking for a specific number
- **Example**: "What will be the US unemployment rate in Q2 2025?"
- **Additional parameters**:
  - `range_min`: Minimum possible value
  - `range_max`: Maximum possible value
  - `open_lower_bound`: Whether lower bound is open
  - `open_upper_bound`: Whether upper bound is open
  - `zero_point`: Reference point for scaling (optional)
  - `unit`: Unit of measurement (optional)
- **Output**: Continuous CDF (201 points)

### Multiple Choice Questions
- **Format**: Questions with predefined options
- **Example**: "Which company will have the highest market cap on Dec 31, 2025?"
- **Additional parameters**:
  - `options`: List of possible answers
- **Output**: Probability distribution over options

## Example Usage

### Creating a Binary Question

```python
import asyncio
from forecaster import binary_forecast

# Define your question
question_details = {
    "title": "Will AI achieve AGI by 2030?",
    "description": "This question asks whether artificial general intelligence will be achieved by January 1, 2030.",
    "resolution_criteria": "AGI is achieved when an AI system can perform any intellectual task that a human can do, as determined by a panel of AI experts.",
    "fine_print": "Resolution will be based on consensus from leading AI research institutions.",
    "type": "binary"
}

# Run the forecast
async def main():
    forecast, comment = await binary_forecast(question_details)
    print(f"Forecast: {forecast}")
    print(f"Comment: {comment}")

asyncio.run(main())
```

### Creating a Numeric Question

```python
import asyncio
from forecaster import numeric_forecast

# Define your question
question_details = {
    "title": "What will be the global average temperature in 2025?",
    "description": "This question asks for the global average surface temperature for the year 2025.",
    "resolution_criteria": "Temperature will be measured as the global average surface temperature anomaly relative to 1951-1980 baseline, as reported by NASA GISTEMP.",
    "fine_print": "Data source: NASA Goddard Institute for Space Studies Surface Temperature Analysis.",
    "type": "numeric",
    "scaling": {
        "range_min": 0.5,
        "range_max": 1.5,
        "zero_point": None
    },
    "open_upper_bound": False,
    "open_lower_bound": False,
    "unit": "°C above 1951-1980 baseline"
}

# Run the forecast
async def main():
    forecast, comment = await numeric_forecast(question_details)
    print(f"Forecast: {forecast}")
    print(f"Comment: {comment}")

asyncio.run(main())
```

### Creating a Multiple Choice Question

```python
import asyncio
from forecaster import multiple_choice_forecast

# Define your question
question_details = {
    "title": "What will be the primary energy source for electricity generation in 2030?",
    "description": "This question asks about the dominant energy source for global electricity generation in 2030.",
    "resolution_criteria": "Resolution based on the energy source with the highest share of global electricity generation in 2030, as reported by the International Energy Agency.",
    "fine_print": "Data source: IEA World Energy Outlook 2030.",
    "type": "multiple_choice",
    "options": [
        "Coal",
        "Natural Gas",
        "Nuclear",
        "Solar",
        "Wind",
        "Hydroelectric",
        "Other Renewables"
    ]
}

# Run the forecast
async def main():
    forecast, comment = await multiple_choice_forecast(question_details)
    print(f"Forecast: {forecast}")
    print(f"Comment: {comment}")

asyncio.run(main())
```

## Output

Forecasts are saved to files in the following directories:
- Custom forecasts: `../custom_forecasts/`
- Example forecasts: `../example_forecasts/`

Each forecast file contains:
- Question details
- Research and reasoning from multiple AI forecasters
- Final forecast result
- Detailed commentary

## Requirements

Make sure you have the required environment variables set up in your `.env` file:
- `METACULUS_TOKEN`
- `PERPLEXITY_API_KEY` (for research)
- `ASKNEWS_CLIENT_ID` and `ASKNEWS_SECRET` (for news research)
- `OPENAI_API_KEY` (for AI models)

## Tips for Good Questions

1. **Be specific**: Avoid vague or ambiguous wording
2. **Clear resolution**: Define exactly how the question will be resolved
3. **Reasonable timeframe**: Choose timeframes that are neither too short nor too long
4. **Measurable outcomes**: Ensure the outcome can be objectively determined
5. **Good background**: Provide sufficient context for the AI to understand the question

## Troubleshooting

- **Import errors**: Make sure you're running the script from the `Bot` directory
- **API errors**: Check that your environment variables are set correctly
- **Forecast errors**: Ensure your question details are complete and properly formatted
- **File permissions**: Make sure you have write permissions for the output directories
