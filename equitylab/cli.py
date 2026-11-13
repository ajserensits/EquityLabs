"""Command-line interface for the portable EquityLab application."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .server import serve
from .storage import Database


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Local equity valuation research tool")
    result.add_argument("--database", default="data/equitylab.sqlite3")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="initialize the SQLite database")
    server = commands.add_parser("serve", help="run the local web application")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)
    importer = commands.add_parser("import-prices", help="import an attributed price CSV")
    importer.add_argument("--symbol", required=True)
    importer.add_argument("--source", required=True)
    importer.add_argument("csv_file", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    database = Database(args.database)
    database.initialize()
    if args.command == "init-db":
        print(f"Initialized {database.path}")
        return 0
    if args.command == "serve":
        serve(args.host, args.port, args.database)
        return 0
    if args.command == "import-prices":
        result = database.import_prices(
            args.symbol, args.source, args.csv_file.read_text(encoding="utf-8")
        )
        print(json.dumps(result, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
