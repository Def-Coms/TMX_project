# TMX Processor - Project Rules and Information

## Project Overview

TMX Processor is a professional platform for processing TMX (Translation Memory eXchange) language files for AI model training. It provides a complete toolkit for parsing, cleaning, validating, deduplicating, and converting translation data to 13 different AI training formats.

## Key Commands

### Installation
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with all dependencies
pip install -e ".[all]"

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=tmx_processor

# Run specific test file
python -m pytest tests/test_converter.py
```

### CLI Usage
```bash
# Parse TMX file
tmx-proc parse examples/sample_en_bg.tmx

# Convert to format
tmx-proc convert examples/sample_en_bg.tmx -o output.jsonl --fmt dpo

# Full pipeline
tmx-proc pipeline examples/sample_en_bg.tmx -o output_folder --fmt hf_dataset
```

### Web UI
```bash
# FastAPI Web UI
tmx-web --port 8000

# Streamlit UI
streamlit run src/tmx_processor/web_streamlit.py
```

## Project Structure

```
src/tmx_processor/
├── __init__.py         # Public API exports
├── parser.py           # TMX streaming XML parser
├── cleaner.py          # Data cleaning and filtering
├── converter.py        # Conversion to 13 formats
├── validator.py        # Validation of translation units
├── deduper.py          # Exact + fuzzy deduplication
├── analyzer.py         # Statistics and analysis
├── cli.py              # Typer CLI (tmx-proc)
├── web_api.py          # FastAPI + REST endpoints (tmx-web)
├── web_streamlit.py    # Streamlit UI
└── web/
    └── index.html      # TailwindCSS + Alpine.js SPA
```

## Supported Formats (13)

### Basic Formats
- JSONL, JSON, CSV, TSV, Parquet

### AI Training Formats
- Alpaca (instruction tuning)
- ShareGPT (chat/multi-turn)
- ChatML (messages format)
- OpenAI (messages format)
- DPO/ORPO (preference tuning)
- Prompt/Completion (generic instruction)
- Reasoning (chain-of-thought)

### Dataset Splits
- HuggingFace Dataset (train/validation/test)

## Configuration

### Virtual Environment
- Located at `.venv/` in project root
- Python 3.9+ required
- Use `source .venv/bin/activate` to activate

### Dependencies
- Main dependencies in `pyproject.toml`
- Dev dependencies include pytest, pytest-cov, httpx2
- Optional: streamlit, tiktoken

## Testing

- Total tests: 79
- Test files in `tests/` directory
- All tests pass: `python -m pytest`
- Web API tests use FastAPI TestClient

## Web API Configuration

- Default port: 8000
- Max upload size: 100 MB
- Max sessions: 50
- Session TTL: 1 hour
- Session cleanup interval: 60 seconds

## Important Notes

- Large TMX files (500-1000 MB) should be processed via CLI streaming mode
- Web API has upload limits (100 MB)
- Streaming mode requires `--no-dedupe` flag
- All 13 formats are supported in all interfaces (CLI, Web API, Streamlit, FastAPI UI)

## Recent Changes

- Added 3 new AI training formats: DPO/ORPO, Prompt/Completion, Reasoning
- Updated all interfaces to support new formats
- Added 7 new tests for new formats
- Updated README.md with professional structure
- Total formats: 13 (was 10)
- Total tests: 79 (was 72)
