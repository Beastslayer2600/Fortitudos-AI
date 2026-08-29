"""HTTP layer: CORS origin rules and the Learn routes the desk UI calls."""
import base64
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import app


def request(server, path, method="GET", body=None, origin=None):
    url = f"http://127.0.0.1:{server.server_address[1]}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, dict(resp.headers), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, dict(exc.headers), json.loads(raw) if raw else {}


class Origins(unittest.TestCase):
    def test_desk_port_allowed(self):
        self.assertTrue(app.origin_allowed("http://localhost:8080"))
        self.assertTrue(app.origin_allowed("http://192.168.1.20:8080"))

    def test_other_ports_and_schemes_denied(self):
        self.assertFalse(app.origin_allowed("https://evil.example.com"))
        self.assertFalse(app.origin_allowed("http://localhost:3000"))
        self.assertFalse(app.origin_allowed("file://"))
        self.assertFalse(app.origin_allowed(""))
        self.assertFalse(app.origin_allowed("null"))


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.docs = Path(cls.tmp.name)
        cls._docs = app.DOCS_DIR
        app.DOCS_DIR = cls.docs
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        app.DOCS_DIR = cls._docs
        cls.tmp.cleanup()

    def test_preflight_allows_the_desk(self):
        status, headers, _ = request(self.server, "/api/ask", "OPTIONS", origin="http://localhost:8080")
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "http://localhost:8080")

    def test_preflight_refuses_other_sites(self):
        status, headers, _ = request(self.server, "/api/ask", "OPTIONS", origin="https://evil.example.com")
        self.assertEqual(status, 204)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        self.assertEqual(headers.get("Vary"), "Origin")

    def test_learn_shelf(self):
        (self.docs / "learn" / "craft").mkdir(parents=True, exist_ok=True)
        (self.docs / "learn" / "craft" / "lesson.md").write_text("# Lesson", encoding="utf-8")
        (self.docs / "guide.md").write_text("# Guide", encoding="utf-8")
        status, _, payload = request(self.server, "/api/learn")
        self.assertEqual(status, 200)
        kinds = {d["name"]: d["kind"] for d in payload["docs"]}
        self.assertEqual(kinds["learn/craft/lesson.md"], "lesson")
        self.assertEqual(kinds["guide.md"], "guide")
        self.assertTrue(payload["how"])

    def test_discover_reports_shelves(self):
        status, _, payload = request(self.server, "/api/learn/discover")
        self.assertEqual(status, 200)
        self.assertTrue({g["branch"] for g in payload["gaps"]} >= {"craft", "advisor"})

    def test_self_learn_is_off_and_says_so(self):
        status, _, payload = request(self.server, "/api/learn/self")
        self.assertEqual(status, 200)
        self.assertFalse(payload["enabled"])
        status, _, payload = request(self.server, "/api/learn/self", "POST", {})
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["errors"])

    def test_teach_refuses_an_empty_lesson(self):
        status, _, payload = request(self.server, "/api/learn/teach", "POST", {"title": "T", "text": ""})
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_guides_reject_other_file_types(self):
        body = {"filename": "x.exe", "content_base64": base64.b64encode(b"hi").decode(), "topic": "misc"}
        status, _, _ = request(self.server, "/api/ingest/guides", "POST", body)
        self.assertEqual(status, 400)

    def test_guides_strip_directory_traversal(self):
        body = {
            "filename": "../../escaped.md",
            "content_base64": base64.b64encode(b"# hi").decode(),
            "topic": "misc",
        }
        status, _, payload = request(self.server, "/api/ingest/guides", "POST", body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["source"], "learn:misc:escaped.md")
        self.assertTrue((self.docs / "learn" / "misc" / "escaped.md").exists())
        self.assertFalse((self.docs.parent / "escaped.md").exists())

    def test_unknown_route_is_404(self):
        status, _, _ = request(self.server, "/api/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
