PYTHON ?= python3

.PHONY: help install inspect scope baselines eval

help:
	@echo "install    install Python dependencies"
	@echo "inspect    print schema and samples of data/raw/ (feasibility pilot)"
	@echo "scope      flag recursion/Big-O questions -> data/processed/scope_report.md"
	@echo "baselines  run ablation conditions (placeholder)"
	@echo "eval       compute metrics (placeholder)"

install:
	$(PYTHON) -m pip install -r requirements.txt

inspect:
	$(PYTHON) scripts/inspect_jorgpt.py

scope:
	$(PYTHON) scripts/filter_scope.py

baselines:
	@echo "TODO: not implemented yet (after the feasibility pilot and annotation)"

eval:
	@echo "TODO: not implemented yet (after the feasibility pilot and annotation)"
