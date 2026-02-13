.PHONY: help install test lint format clean repl demo

help:
	@echo "GeoLLM - UV Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install    Install dependencies"
	@echo "  make dev        Install with dev dependencies"
	@echo "  make download-data Download SwissNames3D dataset"
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
	@echo "  make demo       Run the demo app"

	@echo ""
	@echo "Maintenance:"
	@echo "  make clean      Clean build artifacts"

install:
	uv sync

dev:
	uv sync --extra dev

DATA_PKT = data/swissNAMES3D_PLY.shp

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

demo:
	uv run uvicorn demo.main:app --port 8000 --reload

download-data: $(DATA_PKT)

$(DATA_PKT):
	mkdir -p data
	curl -L https://data.geo.admin.ch/ch.swisstopo.swissnames3d/swissnames3d_2025/swissnames3d_2025_2056.shp.zip -o data/swissnames3d.zip
	unzip -o data/swissnames3d.zip -d data/
	rm data/swissnames3d.zip

clean:
	rm -rf .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
