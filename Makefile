PYTHON ?= venv/bin/python

.PHONY: all check build serve test clean venv collect collect-cached collect-nfdi4cat collect-nfdi4chem collect-elixir collect-biotools collect-tess collect-taxila collect-fair4chemnl collect-documentation

all: build

venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt

# Check the decision tree in questions/: broken links, unreachable questions,
# loops and missing lists.
check:
	$(PYTHON) scripts/check_questions.py

# Collect chemistry repositories from FAIRsharing into _data/repositories/.
# Needs FAIRSHARING_USER and FAIRSHARING_PASSWORD in the environment.
collect:
	$(PYTHON) scripts/collect_fairsharing.py

# The same, from the answers saved in cache/ by the last `make collect`.
collect-cached:
	$(PYTHON) scripts/collect_fairsharing.py --from-cache

# Collect the services of NFDI4Cat into _data/services/.
collect-nfdi4cat:
	$(PYTHON) scripts/collect_nfdi4cat.py

# Collect the services of NFDI4Chem into _data/services/.
collect-nfdi4chem:
	$(PYTHON) scripts/collect_nfdi4chem.py

# Collect the ELIXIR Data Platform services (from bio.tools) into _data/services/.
collect-elixir:
	$(PYTHON) scripts/collect_elixir.py

# Find documentation for the repositories: API documentation in bio.tools, training
# materials and events in TeSS and Taxila. bio.tools takes about 45 minutes.
collect-biotools:
	$(PYTHON) scripts/collect_biotools.py

# TeSS and Taxila use the bio.tools matches, so run collect-biotools first.
collect-tess:
	$(PYTHON) scripts/collect_tess.py

collect-taxila:
	$(PYTHON) scripts/collect_taxila.py

# The materials of FAIR4ChemNL (from their repository on GitHub).
collect-fair4chemnl:
	$(PYTHON) scripts/collect_fair4chemnl.py

collect-documentation: collect-biotools collect-tess collect-taxila collect-fair4chemnl

# Write the static website to build/, for GitHub Pages.
build: check
	$(PYTHON) freeze.py

# Run the website at http://localhost:8200/.
serve:
	$(PYTHON) runserver.py

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -rf build
