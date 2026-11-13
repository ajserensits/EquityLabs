"""Dependency-free local HTTP API and static web server."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from .storage import Database, ImportValidationError
from .valuation import ValuationError, earnings_multiple, equity_dcf


MAX_BODY_BYTES = 1_048_576


def handler_factory(database: Database, web_root: Path) -> type[BaseHTTPRequestHandler]:
    class EquityLabHandler(BaseHTTPRequestHandler):
        server_version = "EquityLabPortable/0.1"

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._json(HTTPStatus.OK, {"data": {"status": "ok"}})
                return
            if parsed.path == "/api/prices":
                query = parse_qs(parsed.query)
                symbol = query.get("symbol", [""])[0]
                if not symbol:
                    self._error(HTTPStatus.BAD_REQUEST, "validation_error", "symbol is required")
                    return
                source = query.get("source", [None])[0]
                self._json(HTTPStatus.OK, {"data": database.list_prices(symbol, source)})
                return
            if parsed.path == "/api/scenarios":
                self._json(HTTPStatus.OK, {"data": database.list_scenarios()})
                return
            self._static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/valuation/earnings":
                    self._json(
                        HTTPStatus.OK,
                        {"data": earnings_multiple(self._json_body())},
                    )
                    return
                if parsed.path == "/api/valuation/dcf":
                    self._json(HTTPStatus.OK, {"data": equity_dcf(self._json_body())})
                    return
                if parsed.path == "/api/prices/import":
                    query = parse_qs(parsed.query)
                    symbol = query.get("symbol", [""])[0]
                    source = query.get("source", [""])[0]
                    result = database.import_prices(symbol, source, self._body().decode("utf-8"))
                    self._json(HTTPStatus.OK, {"data": result})
                    return
                if parsed.path == "/api/scenarios":
                    payload = self._json_body()
                    name = str(payload.get("name", ""))
                    method = str(payload.get("method", ""))
                    assumptions = payload.get("assumptions")
                    if not isinstance(assumptions, dict):
                        raise ValueError("assumptions must be an object")
                    if method == "earnings_multiple":
                        result = earnings_multiple(assumptions)
                    elif method == "equity_dcf":
                        result = equity_dcf(assumptions)
                    else:
                        raise ValueError("unsupported scenario method")
                    saved = database.save_scenario(name, method, assumptions, result)
                    self._json(HTTPStatus.CREATED, {"data": saved})
                    return
                self._error(HTTPStatus.NOT_FOUND, "not_found", "route not found")
            except (ValueError, ValuationError, ImportValidationError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, "validation_error", str(exc))
            except json.JSONDecodeError:
                self._error(HTTPStatus.BAD_REQUEST, "invalid_json", "request body is not valid JSON")

        def _body(self) -> bytes:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer") from exc
            if length < 0 or length > MAX_BODY_BYTES:
                raise ValueError("request body must be 1 MiB or smaller")
            return self.rfile.read(length)

        def _json_body(self) -> dict[str, object]:
            payload = json.loads(self._body().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            return payload

        def _static(self, request_path: str) -> None:
            relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
            candidate = (web_root / relative).resolve()
            try:
                candidate.relative_to(web_root.resolve())
            except ValueError:
                self._error(HTTPStatus.NOT_FOUND, "not_found", "file not found")
                return
            if not candidate.is_file():
                self._error(HTTPStatus.NOT_FOUND, "not_found", "file not found")
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            content = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def _json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            content = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def _error(self, status: HTTPStatus, code: str, message: str) -> None:
            self._json(status, {"error": {"code": code, "message": message}})

    return EquityLabHandler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    database_path: str | Path = "data/equitylab.sqlite3",
    web_root: str | Path | None = None,
) -> ThreadingHTTPServer:
    database = Database(database_path)
    database.initialize()
    root = Path(web_root) if web_root else Path(__file__).resolve().parent.parent / "web"
    return ThreadingHTTPServer((host, port), handler_factory(database, root))


def serve(host: str = "127.0.0.1", port: int = 8080, database_path: str = "data/equitylab.sqlite3") -> None:
    server = create_server(host, port, database_path)
    print(f"EquityLab running at http://{host}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
