"""SQLite persistence for attributed price history and saved scenarios."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS price_observations (
    symbol TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    raw_close TEXT NOT NULL,
    adjusted_close TEXT,
    dividend TEXT,
    source TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    PRIMARY KEY (symbol, observation_date, source)
);
CREATE INDEX IF NOT EXISTS prices_symbol_date_idx
    ON price_observations(symbol, observation_date);
CREATE TABLE IF NOT EXISTS valuation_scenarios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    method TEXT NOT NULL CHECK (method IN ('earnings_multiple', 'equity_dcf')),
    assumptions TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class ImportValidationError(ValueError):
    """Raised for invalid or incomplete price CSV data."""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def import_prices(self, symbol: str, source: str, csv_text: str) -> dict[str, int]:
        symbol = symbol.strip().upper()
        source = source.strip()
        if not symbol or not symbol.replace(".", "").replace("-", "").isalnum():
            raise ImportValidationError("symbol must contain letters, numbers, dots, or hyphens")
        if not source:
            raise ImportValidationError("source is required")

        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            raise ImportValidationError("CSV must include a header")
        fields = {name.strip() for name in reader.fieldnames if name}
        if "date" not in fields or not ({"raw_close", "close"} & fields):
            raise ImportValidationError("CSV requires date and raw_close (or close) columns")

        rows: list[tuple[str, str, str, str | None, str | None, str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                observed = date.fromisoformat((row.get("date") or "").strip()).isoformat()
            except ValueError as exc:
                raise ImportValidationError(f"line {line_number}: date must use YYYY-MM-DD") from exc
            raw_close = self._positive_decimal(
                row.get("raw_close") or row.get("close"), line_number, "raw_close"
            )
            adjusted = self._optional_decimal(row.get("adjusted_close"), line_number, "adjusted_close")
            if adjusted is not None and Decimal(adjusted) <= 0:
                raise ImportValidationError(f"line {line_number}: adjusted_close must be positive")
            dividend = self._optional_decimal(row.get("dividend"), line_number, "dividend")
            if dividend is not None and Decimal(dividend) < 0:
                raise ImportValidationError(f"line {line_number}: dividend cannot be negative")
            rows.append(
                (
                    symbol,
                    observed,
                    raw_close,
                    adjusted,
                    dividend,
                    source,
                    datetime.now(timezone.utc).isoformat(),
                )
            )
        if not rows:
            raise ImportValidationError("CSV must include at least one data row")

        with self.connect() as connection:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT observation_date FROM price_observations WHERE symbol=? AND source=?",
                    (symbol, source),
                )
            }
            connection.executemany(
                """
                INSERT INTO price_observations
                    (symbol, observation_date, raw_close, adjusted_close, dividend, source, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, observation_date, source) DO UPDATE SET
                    raw_close=excluded.raw_close,
                    adjusted_close=excluded.adjusted_close,
                    dividend=excluded.dividend,
                    imported_at=excluded.imported_at
                """,
                rows,
            )
        inserted = sum(1 for row in rows if row[1] not in existing)
        return {"imported": len(rows), "inserted": inserted, "updated": len(rows) - inserted}

    def list_prices(self, symbol: str, source: str | None = None) -> list[dict[str, object]]:
        sql = "SELECT * FROM price_observations WHERE symbol=?"
        parameters: list[str] = [symbol.strip().upper()]
        if source:
            sql += " AND source=?"
            parameters.append(source)
        sql += " ORDER BY observation_date"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, parameters)]

    def save_scenario(
        self, name: str, method: str, assumptions: dict[str, object], result: dict[str, object]
    ) -> dict[str, object]:
        name = name.strip()
        if not name:
            raise ValueError("scenario name is required")
        if method not in {"earnings_multiple", "equity_dcf"}:
            raise ValueError("unsupported scenario method")
        now = datetime.now(timezone.utc).isoformat()
        scenario_id = str(uuid.uuid4())
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id, created_at FROM valuation_scenarios WHERE name=?", (name,)
            ).fetchone()
            if existing:
                scenario_id = existing["id"]
                created = existing["created_at"]
            else:
                created = now
            connection.execute(
                """
                INSERT INTO valuation_scenarios
                    (id, name, method, assumptions, result, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    method=excluded.method,
                    assumptions=excluded.assumptions,
                    result=excluded.result,
                    updated_at=excluded.updated_at
                """,
                (
                    scenario_id,
                    name,
                    method,
                    json.dumps(assumptions, sort_keys=True),
                    json.dumps(result, sort_keys=True),
                    created,
                    now,
                ),
            )
        return {"id": scenario_id, "name": name, "method": method, "updated_at": now}

    def list_scenarios(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM valuation_scenarios ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {
                **dict(row),
                "assumptions": json.loads(row["assumptions"]),
                "result": json.loads(row["result"]),
            }
            for row in rows
        ]

    @staticmethod
    def _positive_decimal(value: str | None, line: int, field: str) -> str:
        result = Database._optional_decimal(value, line, field)
        if result is None or Decimal(result) <= 0:
            raise ImportValidationError(f"line {line}: {field} must be positive")
        return result

    @staticmethod
    def _optional_decimal(value: str | None, line: int, field: str) -> str | None:
        text = (value or "").strip()
        if not text:
            return None
        try:
            result = Decimal(text)
        except InvalidOperation as exc:
            raise ImportValidationError(f"line {line}: {field} must be a decimal") from exc
        if not result.is_finite():
            raise ImportValidationError(f"line {line}: {field} must be finite")
        return format(result, "f")
