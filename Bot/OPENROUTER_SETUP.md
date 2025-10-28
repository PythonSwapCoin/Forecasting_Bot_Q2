# OpenRouter Setup Guide

This guide explains how to set up OpenRouter as a fallback for LLM calls when the Metaculus proxy fails.

## Why OpenRouter?

The forecasting system was experiencing 400 Bad Request errors when using the Metaculus LLM proxy. OpenRouter provides access to multiple LLM providers (Claude, GPT-4, etc.) through a single API, making it an excellent fallback option.

## Setup Instructions

### 1. Get an OpenRouter API Key

1. Go to [OpenRouter.ai](https://openrouter.ai/)
2. Sign up for an account
3. Add credits to your account (minimum $5 recommended)
4. Generate an API key from your dashboard

### 2. Set Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Metaculus API Token (for Metaculus proxy - optional if using OpenRouter)
METACULUS_TOKEN=your_metaculus_token_here

# OpenAI API Key (for personal OpenAI API calls)
OPENAI_API_KEY=your_openai_api_key_here

# OpenRouter API Key (for fallback LLM calls)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Research APIs
PERPLEXITY_API_KEY=your_perplexity_api_key_here
ASKNEWS_CLIENT_ID=your_asknews_client_id_here
ASKNEWS_SECRET=your_asknews_secret_here

# Optional: Exa API for smart search
EXA_API_KEY=your_exa_api_key_here
```

### 3. How It Works

The system now uses a fallback strategy:

1. **Primary**: Try Metaculus proxy (if available)
2. **Fallback**: Use OpenRouter if Metaculus fails
3. **Personal OpenAI**: Some calls use personal OpenAI API directly

### 4. Available Models via OpenRouter

- **Claude**: `anthropic/claude-3.5-sonnet`
- **GPT-4**: `openai/gpt-4o`
- **GPT-4o Mini**: `openai/gpt-4o-mini`
- **Many others**: Check OpenRouter's model list

### 5. Cost Considerations

OpenRouter typically offers competitive pricing:
- Claude 3.5 Sonnet: ~$3-15 per 1M tokens
- GPT-4o: ~$2.50-5 per 1M tokens
- GPT-4o Mini: ~$0.15-0.6 per 1M tokens

### 6. Testing the Setup

Run a custom forecast to test:

```bash
cd Bot
python custom_forecast.py
```

The system will automatically try Metaculus first, then fall back to OpenRouter if needed.

## Troubleshooting

### Common Issues

1. **"OPENROUTER_API_KEY not found"**: Make sure your `.env` file is in the project root and contains the correct API key.

2. **Rate limiting**: OpenRouter has rate limits. The system includes automatic retry logic with exponential backoff.

3. **Model not available**: Some models might not be available. The system uses `anthropic/claude-3.5-sonnet` and `openai/gpt-4o` by default.

### Debugging

Check the console output for messages like:
- "Metaculus Claude failed: ..."
- "Falling back to OpenRouter Claude..."
- "OpenRouter Claude attempt 1"

This will help you understand which API is being used and if there are any issues.

## Benefits

1. **Reliability**: Multiple fallback options ensure forecasts can complete
2. **Cost-effective**: OpenRouter often has better pricing than direct API access
3. **Variety**: Access to multiple LLM providers through one API
4. **Transparency**: Clear logging shows which API is being used

## Future Improvements

- Add more model options
- Implement cost tracking
- Add model performance comparison
- Automatic model selection based on question type
