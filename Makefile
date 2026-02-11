.PHONY: help install test lint format clean repl

help:
	@echo "GeoLLM - UV Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install    Install dependencies"
	@echo "  make dev        Install with dev dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test       Run tests"
	@echo "  make coverage   Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format     Format code with ruff"
	@echo "  make lint       Run linters with ruff"
	@echo "  make check      Type check with ty"
	@echo ""
	@echo "Running:"
	@echo "  make repl       Run interactive REPL"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean      Clean build artifacts"

install:
	uv sync

dev:
	uv sync --extra dev

test:
	uv run pytest tests/ -v

coverage:
	uv run pytest tests/ --cov=geollm --cov-report=term-missing

format:
	uv run ruff format geollm/ tests/

lint:
	uv run ruff check --fix geollm/ tests/

check:
	uv run ty check

repl:
	uv run python repl.py

clean:
	rm -rf .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
