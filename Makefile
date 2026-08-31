.PHONY: test lint build review clean install

install:
	pip install -e .

test:
	PYTHONPATH=. pytest -v tests/

lint:
	PYTHONPATH=. python3 -m synapseforge.cli.main lint

review:
	PYTHONPATH=. python3 -m synapseforge.cli.main review

build:
	PYTHONPATH=. python3 -m synapseforge.cli.main build

ci: test lint build

clean:
	rm -rf dist build *.egg-info .pytest_cache
