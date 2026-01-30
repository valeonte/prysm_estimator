# Prysm Estimator

Small helper script to parse Prysm logs and estimate when sync will finish using total rate, last day rate and last hour rate.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install dependencies

```bash
uv sync
```

This creates a `.venv` virtual environment and installs all runtime and development dependencies.

## Usage

```bash
uv run python calc_eta.py logs/prysm_logs/
```

## Development

### Run tests

```bash
uv run pytest
```

### Run tests with coverage report

```bash
uv run pytest --cov=. --cov-report=term-missing
```

### Run linting

```bash
uv run pylint assessor.py calc_eta.py
```

### Run type checking

```bash
uv run mypy assessor.py calc_eta.py
```

### Run all checks

```bash
uv run pytest && uv run pylint assessor.py calc_eta.py && uv run mypy assessor.py calc_eta.py
```
