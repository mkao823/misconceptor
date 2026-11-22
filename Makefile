PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
COND ?= 0
ARGS ?=

.PHONY: help install test inspect scope baselines eval

help:
	@echo "install    install Python dependencies"
	@echo "test       run the unit tests (pytest)"
	@echo "inspect    print schema and samples of data/raw/ (feasibility pilot)"
	@echo "scope      flag recursion/Big-O questions -> data/processed/scope_report.md"
	@echo "baselines  run one ablation condition: make baselines COND=0|1 [ARGS='--limit 5 --model ollama/gpt-oss:20b']"
	@echo "eval       score a run: make eval RUN=<run_id> [ARGS='--compare <other_run_id>']"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

inspect:
	$(PYTHON) scripts/inspect_jorgpt.py

scope:
	$(PYTHON) scripts/filter_scope.py

baselines:
	$(PYTHON) scripts/run_condition.py --cond $(COND) $(ARGS)

eval:
ifndef RUN
	$(error RUN is required: make eval RUN=<run_id>  (see results/))
endif
	$(PYTHON) scripts/evaluate.py --run $(RUN) $(ARGS)
