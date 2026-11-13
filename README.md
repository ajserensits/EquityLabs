# EquityLab Portable

EquityLab Portable is a local-first equity research application rebuilt from the original EquityLab project for environments where Docker, Go, PostgreSQL, npm packages, and external network access are unavailable. It keeps the parts that work well offline: exact-decimal valuation models, attributed historical-price imports, saved scenarios, a small JSON API, and a browser interface.

This version uses only Python's standard library, SQLite, HTML, CSS, and browser JavaScript. It does not download packages and does not call live financial-data services.

> Research software, not investment advice. Model estimates are sensitive to assumptions and are not predictions.

## Requirements

- Python 3.10 or newer
- A modern browser for the optional interface

No package installation, environment variables, Docker services, or internet access are required.

## Run the tests

From the project root:

```bash
python3 -m unittest discover -s tests -v
```

The suite uses temporary SQLite databases and a local ephemeral HTTP port. It does not access the internet.

## Start the application

```bash
python3 -m equitylab.cli serve
```

Open <http://127.0.0.1:8080>. Application data is stored in `data/equitylab.sqlite3`, which is ignored by Git.

To use a different database or port:

```bash
python3 -m equitylab.cli --database /tmp/equitylab.sqlite3 serve --port 8090
```

## Import price history

Use the web interface or the CLI:

```bash
python3 -m equitylab.cli import-prices \
  --symbol MCD \
  --source my_vendor_export \
  examples/price-import-template.csv
```

CSV columns:

```csv
date,raw_close,adjusted_close,dividend
```

`date` and a positive `raw_close` (or `close`) are required. The source label is required so observations retain their provenance. Importing the same symbol, date, and source again updates the existing observation instead of creating a duplicate.

## Included now

- Earnings-multiple valuation with upside and target requirement calculations
- Equity DCF with 5- or 10-year forecasts, terminal value, cash/debt adjustments, margin of safety, and exact decimal arithmetic
- Attributed, idempotent historical-price CSV imports
- SQLite persistence for prices and named valuation scenarios
- Local JSON API with a 1 MiB request limit and structured validation errors
- Responsive browser interface for calculations and price imports
- Automated valuation, storage, import, and HTTP tests

## Deliberately left for future work

The portable version is a focused offline MVP. These are real roadmap items rather than partially implemented features:

- Point-in-time historical backtests using filing availability dates
- Benchmark-series imports and benchmark-relative returns
- Scenario version history and side-by-side comparison
- Financial-health scoring with documented formulas and missing-data handling
- Offline SEC filing import from previously downloaded JSON fixtures
- Pagination and filtering for larger local price datasets

Any future feature should continue to run without network access and should include deterministic local fixtures and tests.

## Project structure

```text
equitylab/          Python valuation, SQLite, CLI, and HTTP code
web/                Dependency-free browser interface
tests/              Standard-library unittest suite
examples/           Example attributed price CSV
```
