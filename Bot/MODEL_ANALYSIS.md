# Model Usage Analysis - Forecasting Bot Q2

## Overview
This document provides a comprehensive analysis of all models used across the forecasting system, including their access methods (direct API vs OpenRouter) and usage patterns.

## 🎯 LLM Models Used

### 1. **Forecasting Models (via OpenRouter)**
These are the main models used for forecasting predictions:

| Forecaster | Model | Provider | Access Method | Usage |
|------------|-------|----------|---------------|-------|
| Forecaster 1 | `anthropic/claude-haiku-4.5` | Anthropic | OpenRouter | Binary, Numeric, Multiple Choice forecasting |
| Forecaster 2 | `google/gemini-2.5-flash` | Google | OpenRouter | Binary, Numeric, Multiple Choice forecasting |
| Forecaster 3 | `openai/gpt-5-chat` | OpenAI | OpenRouter | Binary, Numeric, Multiple Choice forecasting |
| Forecaster 4 | `openai/o4-mini` | OpenAI | OpenRouter | Binary, Numeric, Multiple Choice forecasting |
| Forecaster 5 | `x-ai/grok-4-fast` | xAI | OpenRouter | Binary, Numeric, Multiple Choice forecasting |

**Configuration**: `Bot/model_config.py`
**Access**: All via `call_forecaster_1()` through `call_forecaster_5()` functions

### 2. **Search & Research Models**

#### Perplexity API (Direct)
- **Model**: `sonar-deep-research`
- **Provider**: Perplexity
- **Access Method**: Direct API
- **Usage**: Deep research for search queries
- **Location**: `Bot/search.py` - `call_perplexity()`

#### OpenAI GPT (Direct)
- **Model**: `o3` (GPT-4o)
- **Provider**: OpenAI
- **Access Method**: Direct API
- **Usage**: 
  - Search query analysis in `agentic_search()`
  - Article summarization
  - General LLM tasks in search
- **Location**: `Bot/search.py` - `call_gpt()`

### 3. **Legacy/Alternative Models**

#### Metaculus Proxy Models
- **Claude Sonnet 4**: `claude-sonnet-4-20250514`
- **Provider**: Anthropic (via Metaculus proxy)
- **Access Method**: Metaculus proxy API
- **Usage**: Fallback for Claude calls
- **Location**: `Bot/llm_calls.py` - `call_anthropic_api()`

#### Direct OpenAI Models
- **GPT-4o Mini**: `o4-mini`
- **GPT-4o**: `o3`
- **Provider**: OpenAI
- **Access Method**: Direct API
- **Usage**: Various forecasting tasks (legacy)
- **Location**: `Bot/llm_calls.py` - `call_gpt()`, `call_gpt_o3()`, `call_gpt_o4_mini()`

#### Metaculus Bot Models
- **Perplexity**: `llama-3.1-sonar-huge-128k-online`
- **Provider**: Perplexity
- **Access Method**: Direct API
- **Usage**: Research in Metaculus bot
- **Location**: `Bot/metaculus_bot.py` - `call_perplexity()`

## 🔄 Model Access Patterns

### OpenRouter (Primary)
**Used for**: All main forecasting models (Forecasters 1-5)
**Configuration**: `Bot/model_config.py`
**Functions**: `call_forecaster_1()` through `call_forecaster_5()`
**Benefits**: 
- Unified API interface
- Easy model switching
- Cost transparency
- Fallback handling

### Direct APIs
**Used for**:
- **Perplexity**: Deep research (`sonar-deep-research`)
- **OpenAI**: Search analysis, article summarization (`o3`)
- **Metaculus Proxy**: Fallback Claude calls

## 📊 Usage by Functionality

### 1. **Binary Forecasting** (`Bot/binary.py`)
- **Historical Research**: `call_gpt_o3()` (Direct OpenAI)
- **Current Research**: `call_gpt_o3()` (Direct OpenAI)
- **Forecasting**: All 5 forecaster models via OpenRouter
- **Search**: Google, Google News, Perplexity via `process_search_queries()`

### 2. **Numeric Forecasting** (`Bot/numeric.py`)
- **Historical Research**: `call_gpt_o3()` (Direct OpenAI)
- **Current Research**: `call_gpt_o3()` (Direct OpenAI)
- **Forecasting**: All 5 forecaster models via OpenRouter
- **Search**: Google, Google News, Perplexity via `process_search_queries()`

### 3. **Multiple Choice Forecasting** (`Bot/multiple_choice.py`)
- **Historical Research**: `call_gpt_o3()` (Direct OpenAI)
- **Current Research**: `call_gpt_o3()` (Direct OpenAI)
- **Forecasting**: All 5 forecaster models via OpenRouter
- **Search**: Google, Google News, Perplexity via `process_search_queries()`

### 4. **Search & Research** (`Bot/search.py`)
- **Agentic Search**: `call_gpt()` (Direct OpenAI - `o3`)
- **Perplexity Research**: `call_perplexity()` (Direct API - `sonar-deep-research`)
- **Article Summarization**: `call_gpt()` (Direct OpenAI - `o3`)

### 5. **Custom Forecasting** (`Bot/custom_forecast.py`)
- **Uses**: All above functionality through `binary_forecast()`, `numeric_forecast()`, `multiple_choice_forecast()`

## 🔧 Model Configuration

### Environment Variables Required
```bash
# OpenRouter (Primary)
OPENROUTER_API_KEY=your_key_here

# Direct APIs
OPENAI_API_KEY=your_key_here
PERPLEXITY_API_KEY=your_key_here

# Optional (Legacy)
METACULUS_TOKEN=your_token_here
SERPER_KEY=your_key_here
ASKNEWS_CLIENT_ID=your_id_here
ASKNEWS_SECRET=your_secret_here
```

### Model Switching
- **Forecasting Models**: Use `Bot/configure_models.py` or environment variables
- **Search Models**: Hardcoded in respective functions
- **Legacy Models**: Hardcoded in respective functions

## 📈 Cost Considerations

### High Usage
- **OpenRouter Models**: All 5 forecasters used in every forecast
- **Perplexity**: Used for deep research queries
- **OpenAI o3**: Used for search analysis and summarization

### Low Usage
- **Metaculus Proxy**: Only as fallback
- **Direct OpenAI**: Legacy usage, being phased out

## 🚀 Recommendations

1. **Primary System**: OpenRouter for all forecasting models
2. **Search Enhancement**: Perplexity for deep research
3. **Cost Optimization**: Monitor OpenRouter usage dashboard
4. **Model Updates**: Use `configure_models.py` for easy switching
5. **Fallback Strategy**: Keep Metaculus proxy as backup

## 📁 Key Files

- `Bot/model_config.py` - Model configuration
- `Bot/llm_calls.py` - LLM calling functions
- `Bot/search.py` - Search and research models
- `Bot/configure_models.py` - Interactive configuration
- `Bot/test_forecaster_models.py` - Model testing

This analysis shows a well-structured system with OpenRouter as the primary interface for forecasting models and direct APIs for specialized tasks like search and research.
