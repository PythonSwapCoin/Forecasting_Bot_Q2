# Forecasting bot

A sophisticated probabilistic forecasting system that leverages multi-agent LLM reasoning, prompt chaining, web scraping, and statistical aggregation to generate accurate predictions for Metaculus questions.

![Metaculus Bot Tournament](https://img.shields.io/badge/Tournament-Q2%202025-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen)
![LLMs](https://img.shields.io/badge/LLMs-Claude%20%7C%20GPT-orange)

## Overview

This forecasting bot competes in the Metaculus Bot Tournament by predicting outcomes for various binary, multiple-choice and numeric questions. It employs a multi-stage retrieval-augmented architecture with parallel LLM agent processing, real-time news analysis, and ensemble aggregation to generate well-calibrated probability estimates.

## Key Features

- **Multi-agent reasoning system** utilizing both Claude 3.7 Sonnet and OpenAI GPT-O3/O4-mini models
- **Asynchronous workflow** for concurrent API calls and efficient processing
- **Robust web content extraction** from diverse sources using a multi-strategy approach
- **Intelligent search aggregation** with Google Search, AskNews, and Perplexity APIs
- **Statistical ensemble methods** for probability calibration and forecast aggregation
- **Comprehensive benchmarking** with normalized peer scoring and simulation

## Architecture

The system employs a multi-stage architecture:

1. **Question Analysis**: Parses Metaculus questions to extract relevant context and parameters
2. **Search Query Generation**: Uses LLMs to generate targeted search queries based on question content
3. **Information Retrieval**: Asynchronously retrieves and extracts content from multiple sources
4. **Context Synthesis**: Filters and consolidates retrieved information
5. **Parallel Forecast Generation**: Multiple forecaster instances generate independent predictions
6. **Ensemble Aggregation**: Combines forecasts with weighted averaging based on model reliability
7. **Benchmarking**: Evaluates performance using normalized peer scoring metrics

```
Question → Query Generation → Parallel Retrieval → Content Extraction
                                     ↓
Final Prediction ← Ensemble Aggregation ← Parallel Forecasting ← Context Synthesis
```

## Technical Implementation

### Multi-Agent System

The bot implements a forecasting committee with five specialized agents:
- Two Claude 3.7 Sonnet instances for robust reasoning about evidence
- Two GPT-o4-mini instances for complementary perspective
- One GPT-o3 instance with double weighting for ensemble diversity

Each agent approaches the problem differently, with prompt engineering directing some toward outside view (historical/reference class) reasoning and others toward inside view (mechanistic/causal) reasoning.

### Asynchronous Processing

Implemented with Python's `asyncio` and `aiohttp` libraries:
- Concurrent API calls with intelligent retry mechanisms
- Configurable timeout handling and backoff strategies
- Fault-tolerant design with graceful degradation when services are unavailable

### Web Content Extraction

The `FastContentExtractor` system combines multiple extraction strategies:
- BeautifulSoup-based DOM analysis with site-specific selectors
- Trafilatura content extraction for structured content
- Readability algorithm implementation for article text
- Fallback mechanisms for handling diverse web content formats
- Metadata extraction and entity recognition

### Search and Retrieval

Integrates multiple information retrieval services:
- Google Search API for general web content
- Google News API for current events
- AskNews API for specialized news retrieval
- Perplexity API for research synthesis

### Forecasting Logic

Specialized forecast generation based on question type:
- Binary questions: probabilities as percentages (0-100%)
- Multiple-choice questions: probability distributions across options
- Numeric questions: 201-point CDF extrapolated from predicted percentile values
- Statistical calibration using historical performance data

### Benchmarking

Comprehensive evaluation system:
- Normalized peer scoring with simulated forecaster populations
- Monte Carlo simulation of good/bad forecaster behaviors
- Performance comparison against Metaculus community predictions
- Visualization of prediction distributions and calibration

## Setup and Usage

### Prerequisites

- Python 3.9+
- API keys for:
  - OpenAI (GPT)
  - Anthropic (Claude)
  - Google Serper
  - Perplexity
  - AskNews
  - Bright Data (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/metaculus-forecasting-bot.git
cd metaculus-forecasting-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Running

```bash
# Run a benchmark test
python benchmark.py

# Generate forecasts for specific questions
python forecaster.py --question_id 12345
```

## Process Visualization UI

To explore the multi-agent workflow visually, open the lightweight ReactFlow dashboard located at [`ui/index.html`](./ui/index.html).
It renders the production pipeline as an interactive node graph with contextual details for each stage and a roadmap toward live editing.

```bash
# from the repository root
cd ui
python -m http.server 8000
# then navigate to http://localhost:8000 in your browser and open index.html
```

The sidebar describes what each agent is responsible for, highlights the tools they can call, and lists the outputs they provide to the ensemble.
Use the “Add placeholder step” button to sketch experimental stages—the underlying state management is ready for future drag-and-drop editing and persistence hooks.

## Future Actionables

- Integration of structured numerical data sources (e.g., economic indicators, polls)
- Expand the process designer with drag-and-drop editing and workflow export
- Customizable forecasting strategies based on question domain
- Fine-tuning of smaller LLMs on curated forecasting dataset

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPLv3). 

You may use, modify, and distribute this code under the terms of the license, provided that:

- Any derivative works are also licensed under AGPLv3
- If used as part of a hosted service (e.g., deployed forecasting interface), source code must be made available
- Proper attribution is maintained, including citation in research papers or public reports

For the full license text, see [`LICENSE`](./LICENSE).

---
