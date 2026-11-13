import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from equitylab.server import create_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        root = Path(self.temporary.name)
        web = root / "web"
        web.mkdir()
        (web / "index.html").write_text("<h1>EquityLab</h1>", encoding="utf-8")
        self.server = create_server(
            port=0, database_path=root / "test.sqlite3", web_root=web
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, path, payload=None, content_type="application/json"):
        data = None if payload is None else (
            json.dumps(payload).encode() if content_type == "application/json" else payload.encode()
        )
        request = Request(
            self.base + path,
            data=data,
            headers={"Content-Type": content_type} if data is not None else {},
        )
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_health_and_static_page(self):
        status, payload = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status"], "ok")
        with urlopen(self.base + "/", timeout=2) as response:
            self.assertIn(b"EquityLab", response.read())

    def test_earnings_api(self):
        status, payload = self.request(
            "/api/valuation/earnings",
            {"normalized_eps": "12.5", "fair_pe": "20", "market_price": "200"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["estimated_value_per_share"], "250")
        self.assertEqual(payload["data"]["upside_percent"], "25")

    def test_validation_error_is_structured(self):
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/valuation/earnings",
                {"normalized_eps": "0", "fair_pe": "20"},
            )
        self.assertEqual(raised.exception.code, 400)
        payload = json.loads(raised.exception.read())
        self.assertEqual(payload["error"]["code"], "validation_error")

    def test_price_import_and_listing(self):
        csv_text = "date,raw_close\n2024-01-02,296.52\n"
        status, payload = self.request(
            "/api/prices/import?symbol=MCD&source=test", csv_text, "text/csv"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["inserted"], 1)
        status, payload = self.request("/api/prices?symbol=MCD")
        self.assertEqual(len(payload["data"]), 1)


if __name__ == "__main__":
    unittest.main()
