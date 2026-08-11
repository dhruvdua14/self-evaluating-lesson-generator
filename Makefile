.PHONY: help setup test run run-offline verify inject memory rubric rubric-doc graph clean demo

PY  ?= python3
VENV = .venv
BIN  = $(VENV)/bin
# PYTHONPATH is set explicitly rather than relying on the editable install:
# some Python builds skip `__editable__*.pth` files, which leaves the console
# script installed but the package unimportable.
RUN  = PYTHONPATH=src $(BIN)/python -m lessonforge

help:
	@echo "setup        Create venv and install dependencies"
	@echo "test         Run the test suite (offline, no API key needed)"
	@echo "run-offline  Full loop on the mock provider (no API key needed)"
	@echo "run          Full loop on Gemini (needs GEMINI_API_KEY)"
	@echo "verify       Prove the evaluator catches deliberate errors"
	@echo "inject       Run the loop with a planted factual error"
	@echo "memory       Show what the system has learned across runs"
	@echo "rubric       Print the rubric"
	@echo "graph        Print the agent graph"
	@echo "demo         Full walkthrough: rubric, graph, verify, run, memory"
	@echo "clean        Remove venv, caches, and generated output"

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"
	@echo "\nNow: cp .env.example .env  and add your GEMINI_API_KEY"

test:
	$(BIN)/python -m pytest

run-offline:
	$(RUN) run --provider mock

run:
	$(RUN) run

verify:
	$(RUN) verify

inject:
	$(RUN) run --inject-error factual

memory:
	$(RUN) memory

rubric:
	$(RUN) rubric

graph:
	$(RUN) graph

demo:
	@echo "\n=== 1. The rubric the content must clear ==="
	@$(RUN) rubric
	@echo "\n=== 2. The agent graph ==="
	@$(RUN) graph
	@echo "\n=== 3. Proof the evaluator catches planted errors ==="
	@$(RUN) verify
	@echo "\n=== 4. Full generate -> evaluate -> regenerate loop ==="
	@$(RUN) run
	@echo "\n=== 5. What the system has learned ==="
	@$(RUN) memory

clean:
	rm -rf $(VENV) .pytest_cache **/__pycache__ src/*.egg-info output/2* memory/*.db

rubric-doc:
	$(RUN) export-rubric --out docs/RUBRIC.md
