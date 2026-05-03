.PHONY: install test lint serve docker-build docker-up clean

PYTHON ?= python
STATE_DIR ?= .state/agentroom

install:
	$(PYTHON) -m pip install -e .

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m compileall agentroom tests

serve:
	$(PYTHON) -m agentroom.cli serve --host 127.0.0.1 --port 8765 --state-dir $(STATE_DIR)

docker-build:
	docker build -t agentroom:latest .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	rm -rf .state/ build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
