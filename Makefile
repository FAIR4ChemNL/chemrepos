PYTHON ?= venv/bin/python

.PHONY: all check build serve test clean venv collect collect-cached

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
