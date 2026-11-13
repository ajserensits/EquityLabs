.PHONY: test check serve init-db

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

check:
	PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q equitylab tests
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

init-db:
	python3 -m equitylab.cli init-db

serve:
	python3 -m equitylab.cli serve
