# Contributing

Contributions to TMX Processor are welcome. For substantial changes, open an
issue first to discuss the approach.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Run the test suite before opening a pull request:

```bash
python -m pytest
```

## Pull requests

- Keep changes focused and explain the user-visible behavior they affect.
- Add or update tests for behavior changes and bug fixes.
- Update the README when commands, formats, or supported behavior change.
- Do not commit virtual environments, generated exports, credentials, or
  translation-memory files that you do not have permission to redistribute.
- Keep compatibility with Python 3.9+, as declared in `pyproject.toml`.

The project uses the MIT License; contributions are provided under that license.