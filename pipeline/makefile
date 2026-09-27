VENV = ../.venv
PYTHON = $(VENV)/bin/python

all: requirements collect structure wikipedia documents analyze

requirements:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -r requirements.txt

# 1. Structured source: Jolpica F1 database dump (CSV)
collect:
	$(PYTHON) collect_structured.py

# 2. One structured record per race and per driver
structure:
	$(PYTHON) build_structured.py

# 3. Textual source: Wikipedia articles (cached; only missing ones are downloaded)
wikipedia:
	$(PYTHON) collect_wikipedia.py

# 4. Final collection: structured + text, quality filter, links race <-> driver
documents:
	$(PYTHON) build_documents.py

# 5. Statistics and plots for the report
analyze:
	$(PYTHON) analyze.py

# Removes generated files but keeps the downloaded raw data
clean:
	rm -rf ../data/interim ../data/processed ../data/analysis

# Removes everything, including the Wikipedia cache (next run re-downloads ~2000 articles)
clean-all: clean
	rm -rf ../data/raw
