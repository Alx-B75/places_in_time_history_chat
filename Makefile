PY ?= python
ENVFILE := .env

.PHONY: smoke-admin
smoke-admin:
	@echo "Running smoke-admin (will source .env if present)..."
	@if [ -f $(ENVFILE) ]; then . $(ENVFILE); fi; $(PY) scripts/smoke.py
