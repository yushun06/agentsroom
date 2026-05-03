.PHONY: install install-dev test lint format check review-check ci serve docker-build docker-up docker-down clean

PYTHON ?= python
STATE_DIR ?= .state/agentroom

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	ruff check agentroom tests showcase scripts

format:
	ruff format agentroom tests showcase scripts

format-check:
	ruff format --check agentroom tests showcase scripts

check: lint format-check test review-check

review-check:
	$(PYTHON) scripts/review-check.py

ci: check
	@echo "CI pipeline complete"

serve:
	$(PYTHON) -m agentroom.cli serve --host 127.0.0.1 --port 8765 --state-dir $(STATE_DIR)

docker-build:
	docker build -t agentroom:latest .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	rm -rf .state/ build/ dist/ *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
