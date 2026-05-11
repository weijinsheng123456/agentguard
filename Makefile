.PHONY: run audit trend install test clean

run:
	python3 gate.py run

audit:
	python3 gate.py audit

trend:
	python3 gate.py trend

install:
	python3 gate.py install

test:
	python3 -m pytest tests/ -v

test-quick:
	python3 -m pytest tests/ -x -q

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ .eggs/ .pytest_cache/

lint:
	ruff check qg/ gate.py

fmt:
	ruff format qg/ gate.py

self-check:
	python3 gate.py run --quick

version:
	python3 gate.py version
