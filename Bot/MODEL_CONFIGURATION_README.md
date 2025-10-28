# Model Configuration System

This system allows you to easily configure which models each forecaster uses through OpenRouter. All forecasters now use OpenRouter by default with your specified models.

## 🎯 Default Configuration

The system is pre-configured with these models:

- **Forecaster 1**: `anthropic/claude-haiku-4.5`
- **Forecaster 2**: `google/gemini-2.5-flash`
- **Forecaster 3**: `openai/gpt-5-chat`
- **Forecaster 4**: `openai/o4-mini`
- **Forecaster 5**: `x-ai/grok-4-fast`

## 🚀 Quick Start

### 1. Set up OpenRouter API Key

Add to your `.env` file:
```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### 2. Test the Configuration

```bash
cd Bot
python test_forecaster_models.py
```

### 3. Run a Forecast

```bash
python custom_forecast.py
```

## 🔧 Changing Models

### Option 1: Interactive Configuration

```bash
cd Bot
python configure_models.py
```

This will open an interactive menu where you can:
- View current configuration
- Change individual forecaster models
- View available models
- Reset to defaults

### Option 2: Environment Variables

Add to your `.env` file:
```bash
# Override specific forecasters
FORECASTER_1_MODEL=anthropic/claude-3.5-sonnet
FORECASTER_2_MODEL=google/gemini-2.5-pro
FORECASTER_3_MODEL=openai/gpt-4o
FORECASTER_4_MODEL=openai/gpt-4o-mini
FORECASTER_5_MODEL=meta-llama/llama-3.1-405b
```

### Option 3: Direct Code Changes

Edit `Bot/model_config.py` and change the `DEFAULT_MODEL_CONFIG`:

```python
DEFAULT_MODEL_CONFIG = {
    "forecaster_1": "anthropic/claude-3.5-sonnet",
    "forecaster_2": "google/gemini-2.5-pro", 
    "forecaster_3": "openai/gpt-4o",
    "forecaster_4": "openai/gpt-4o-mini",
    "forecaster_5": "meta-llama/llama-3.1-405b"
}
```

## 📋 Available Models

The system supports many models through OpenRouter:

### Claude Models
- `anthropic/claude-3.5-sonnet`
- `anthropic/claude-3.5-haiku`
- `anthropic/claude-haiku-4.5`

### GPT Models
- `openai/gpt-4o`
- `openai/gpt-4o-mini`
- `openai/gpt-5-chat`
- `openai/o4-mini`

### Gemini Models
- `google/gemini-2.5-flash`
- `google/gemini-2.5-pro`

### Grok Models
- `x-ai/grok-4-fast`
- `x-ai/grok-4`

### Other Models
- `meta-llama/llama-3.1-405b`
- `qwen/qwen-2.5-72b`
- And many more...

## 🧠 Context Selection

The system automatically chooses the appropriate context for each model:

- **Claude models**: Use Claude context (detailed reasoning, structured analysis)
- **GPT models**: Use GPT context (concise, direct responses)
- **Other models**: Default to GPT context

## 💰 Cost Considerations

OpenRouter pricing varies by model:

- **Claude Haiku 4.5**: ~$0.25-1.25 per 1M tokens
- **Gemini 2.5 Flash**: ~$0.075-0.3 per 1M tokens
- **GPT-5 Chat**: ~$5-15 per 1M tokens
- **GPT-4o Mini**: ~$0.15-0.6 per 1M tokens
- **Grok-4 Fast**: ~$1-5 per 1M tokens

## 🔍 Troubleshooting

### Common Issues

1. **"OPENROUTER_API_KEY not found"**
   - Make sure your `.env` file contains the API key
   - Check that the file is in the project root

2. **"Model not available"**
   - Some models might not be available on OpenRouter
   - Check the OpenRouter website for current model availability
   - Try a different model from the available list

3. **Rate limiting**
   - The system includes automatic retry logic
   - Consider using faster/cheaper models for testing

4. **High costs**
   - Use cheaper models like `gpt-4o-mini` or `claude-haiku-4.5` for testing
   - Monitor your OpenRouter usage dashboard

### Debugging

Check the console output for messages like:
- "Using anthropic/claude-haiku-4.5 for forecaster 1"
- "OpenRouter anthropic/claude-haiku-4.5 attempt 1 for forecaster 1"

This shows which models are being used and if there are any issues.

## 📁 File Structure

```
Bot/
├── model_config.py              # Central configuration
├── llm_calls.py                 # LLM calling functions
├── binary.py                    # Binary forecasting
├── forecaster_template.py       # Template forecasting
├── configure_models.py          # Interactive configuration
├── test_forecaster_models.py    # Test script
└── MODEL_CONFIGURATION_README.md # This file
```

## 🎛️ Advanced Configuration

### Custom Model Selection

You can add new models to `model_config.py`:

```python
ALTERNATIVE_MODELS = {
    # Add your custom models here
    "my_custom_model": "provider/model-name",
    # ...
}
```

### Runtime Model Changes

For runtime model changes (not persistent), you can modify the `DEFAULT_MODEL_CONFIG` dictionary in `model_config.py` and restart the application.

## 🔄 Migration from Old System

The old system used:
- Metaculus proxy (unreliable)
- Mixed API providers
- Hardcoded model assignments

The new system:
- Uses OpenRouter exclusively
- Centralized configuration
- Easy model switching
- Better error handling
- Cost transparency

## 📊 Performance Monitoring

Monitor your usage:
1. Check OpenRouter dashboard for usage and costs
2. Use `test_forecaster_models.py` to verify all models work
3. Check console output for any errors or warnings

## 🚀 Next Steps

1. **Test the system**: Run `test_forecaster_models.py`
2. **Configure models**: Use `configure_models.py` or environment variables
3. **Run forecasts**: Use `custom_forecast.py` to test with real questions
4. **Monitor costs**: Check your OpenRouter usage dashboard
5. **Optimize**: Adjust models based on performance and cost

The system is now much more reliable and flexible! 🎉
