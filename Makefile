# Dev workflow. Requires Python 3.14 and Node 26 (see .nvmrc).
# The global ROS PYTHONPATH on this machine leaks into venvs, so backend targets unset it.
NODE_BIN := $(HOME)/.nvm/versions/node/v26.10.0/bin
PY := env -u PYTHONPATH backend/.venv/bin/python
NPM := env PATH=$(NODE_BIN):$(PATH) npm

.PHONY: setup backend frontend dev test seed data

setup:
	python3.14 -m venv backend/.venv
	$(PY) -m pip install -r backend/requirements.txt
	$(PY) -m playwright install chromium
	$(NPM) --prefix frontend install

backend:
	cd backend && env -u PYTHONPATH .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	$(NPM) --prefix frontend run dev

dev:
	$(MAKE) -j2 backend frontend

test:
	cd backend && env -u PYTHONPATH .venv/bin/pytest -q

seed:
	cd backend && env -u PYTHONPATH .venv/bin/python -m app.seed

data:
	env -u PYTHONPATH data/.venv/bin/python data/load_sample_sales.py
