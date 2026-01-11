PYTHON ?= python
DASHBOARD_DIR ?= dashboard

.PHONY: dev api api-prod dashboard-dev dashboard-build dashboard-lint lint test

dev:
	./scripts/dev.sh

api:
	$(PYTHON) scripts/run_api.py

api-prod:
	KALSHI_ENVIRONMENT=PROD $(PYTHON) scripts/run_api.py

dashboard-dev:
	cd "$(DASHBOARD_DIR)" && npm run dev

dashboard-build:
	cd "$(DASHBOARD_DIR)" && npm run build

dashboard-lint:
	cd "$(DASHBOARD_DIR)" && npm run lint

lint:
	ruff check .
	ty check .

test:
	$(PYTHON) -m pytest
