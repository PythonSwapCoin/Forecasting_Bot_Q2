# Model Usage Summary

## 🎯 Current Model Configuration

### **Primary Forecasting Models (OpenRouter)**
```
Forecaster 1: anthropic/claude-haiku-4.5
Forecaster 2: google/gemini-2.5-flash  
Forecaster 3: openai/gpt-5-chat
Forecaster 4: openai/o4-mini
Forecaster 5: x-ai/grok-4-fast
```

### **Search & Research Models (Direct APIs)**
```
Perplexity: sonar-deep-research (Deep research)
OpenAI: o3 (Search analysis, summarization)
```

## 📊 Usage by Function

| Function | Models Used | Access Method |
|----------|-------------|---------------|
| **Binary Forecasting** | 5 OpenRouter + 1 OpenAI + Perplexity | Mixed |
| **Numeric Forecasting** | 5 OpenRouter + 1 OpenAI + Perplexity | Mixed |
| **Multiple Choice** | 5 OpenRouter + 1 OpenAI + Perplexity | Mixed |
| **Search Queries** | Perplexity + Google + Google News | Direct APIs |
| **Article Summarization** | OpenAI o3 | Direct API |
| **Agentic Search** | OpenAI o3 | Direct API |

## 🔄 API Access Patterns

### **OpenRouter (Primary)**
- **Used for**: All 5 forecaster models
- **Configuration**: `Bot/model_config.py`
- **Functions**: `call_forecaster_1()` through `call_forecaster_5()`
- **Benefits**: Unified interface, easy switching, cost transparency

### **Direct APIs**
- **Perplexity**: `sonar-deep-research` for deep research
- **OpenAI**: `o3` for search analysis and summarization
- **Google/Serper**: Web search and news search

## 🎛️ Model Switching

### **Easy to Change**
- OpenRouter models via `configure_models.py`
- Environment variables (`FORECASTER_X_MODEL`)

### **Hardcoded**
- Perplexity model (`sonar-deep-research`)
- OpenAI model (`o3`)
- Search providers (Google, Google News)

## 💰 Cost Impact

### **High Usage**
- 5 OpenRouter models per forecast
- Perplexity for research queries
- OpenAI for search analysis

### **Low Usage**
- Metaculus proxy (fallback only)
- Legacy direct OpenAI calls

## 🚀 Key Insights

1. **OpenRouter is the primary interface** for all forecasting models
2. **Perplexity provides deep research** capabilities
3. **OpenAI handles search analysis** and summarization
4. **System is well-architected** with clear separation of concerns
5. **Easy model switching** through configuration system
