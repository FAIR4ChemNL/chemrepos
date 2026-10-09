PYTHON ?= venv/bin/python

.PHONY: all check build serve test clean venv

all: build

venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt

# Check the decision tree in questions/: broken links, unreachable questions,
# loops and missing lists.
check:
	$(PYTHON) scripts/check_questions.py

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
