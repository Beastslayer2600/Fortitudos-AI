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
import client_store


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



class AdvisorNeverSelfLearns(unittest.TestCase):
    """Nothing the model wrote may come back as Advisor evidence."""

    def test_ask_excludes_machine_written_sources(self):
        import retrieval
        self.assertIn("learn:craft:", retrieval.MACHINE_WRITTEN_SOURCES)
        self.assertIn("learn:sight:", retrieval.MACHINE_WRITTEN_SOURCES)

    def test_only_the_adviser_rooms_are_restricted(self):
        import retrieval
        self.assertEqual(retrieval.corpus_exclusions("fa"), retrieval.MACHINE_WRITTEN_SOURCES)
        self.assertEqual(retrieval.corpus_exclusions("roa"), retrieval.MACHINE_WRITTEN_SOURCES)
        self.assertEqual(retrieval.corpus_exclusions("craft"), ())

    def test_search_drops_excluded_prefixes(self):
        import numpy as np
        import retrieval

        rows = [
            (1, "guide.pdf", 1, "waiting period is six months", None),
            (2, "learn:craft:flyer.md", 1, "waiting period headline for flyers", None),
            (3, "learn:sight:shot.md", 1, "waiting period seen in a photo", None),
        ]
        matrix = np.zeros((3, 2), dtype=np.float32)

        def fake_load_all(_conn):
            return rows, matrix

        real_load_all, real_embed = retrieval.store.load_all, retrieval.embed
        retrieval.store.load_all = fake_load_all
        retrieval.embed = lambda _q: [[0.0, 0.0]]
        try:
            kept = {
                r[0][1]
                for r in retrieval.search(None, "waiting period",
                                          exclude_prefixes=retrieval.MACHINE_WRITTEN_SOURCES)
            }
        finally:
            retrieval.store.load_all, retrieval.embed = real_load_all, real_embed
        self.assertEqual(kept, {"guide.pdf"})

    def test_teach_never_generates_a_lesson(self):
        self.assertFalse(hasattr(app.Handler, "research_from_shelf"))

    def test_generated_drafts_are_typed_and_quarantined(self):
        self.assertEqual(client_store.AI_DRAFT_TYPE, "AI draft")
        self.assertNotIn(client_store.AI_DRAFT_FOLDER, client_store.FOLDERS.values())

    def test_draft_context_skips_earlier_drafts(self):
        client = {"documents": [
            {"doc_type": client_store.AI_DRAFT_TYPE, "relative_path": "/nope.md", "filename": "d.md"},
        ]}
        with self.assertRaises(ValueError):
            app.client_source_text(client)



class VaultBoundary(unittest.TestCase):
    def test_a_document_outside_the_vault_is_not_served(self):
        """The stored path decides what is read, so it must stay in the vault."""
        outside = Path(tempfile.gettempdir()) / "fortitudo-outside.txt"
        outside.write_text("not a client file", encoding="utf-8")
        real = client_store.get_document
        client_store.get_document = lambda _id: {
            "relative_path": str(outside), "content_type": "text/plain",
        }
        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, _, payload = request(server, "/api/documents/whatever")
            finally:
                server.shutdown()
                server.server_close()
        finally:
            client_store.get_document = real
            outside.unlink(missing_ok=True)
        self.assertEqual(status, 404)
        self.assertNotIn("not a client file", json.dumps(payload))

    def test_a_negative_content_length_is_refused(self):
        class FakeHeaders(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        handler = type("H", (), {"headers": FakeHeaders({"Content-Length": "-1"}), "rfile": None})()
        with self.assertRaises(ValueError):
            app.json_body(handler)



class DeepRouting(unittest.TestCase):
    """The room decides the corpus, not the caller."""

    def test_a_room_without_the_product_index_does_not_search(self):
        import ask
        for room in ("craft", "voice", "drama", "learn"):
            text, results = ask.answer(None, "anything", room=room)
            self.assertIn("does not answer from the product index", text, room)
            self.assertEqual(results, [], room)

    def test_a_room_that_is_not_client_aware_drops_the_excerpt(self):
        import ask, rooms
        self.assertFalse(rooms.get_room("fa").include_clients)
        self.assertTrue(rooms.get_room("roa").include_clients)
        # fa is not client-aware, so an excerpt alone must not produce an answer.
        text, _ = ask.answer(None, "q", client_excerpt="SECRET CLIENT TEXT", room="craft")
        self.assertNotIn("SECRET", text)

    def test_the_roa_room_carries_the_draft_banner(self):
        import rooms
        self.assertIn("INTERNAL DRAFT", rooms.get_room("roa").draft_banner)
        self.assertEqual(rooms.get_room("fa").draft_banner, "")


class RouteEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_route_explains_the_room_it_picked(self):
        status, _, payload = request(
            self.server, "/api/route", "POST",
            {"question": "Build a shop page for Joe Plumbing"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["room"], "craft")
        self.assertTrue(payload["why"])
        self.assertTrue(payload["refuse"])

    def test_a_client_file_brief_falls_back_to_the_adviser_room(self):
        _, _, payload = request(
            self.server, "/api/route", "POST",
            {"question": "Build a site from this FNA and policy number"},
        )
        self.assertEqual(payload["room"], "fa")
        self.assertIn("client file", payload["why"])

    def test_ask_reports_the_room_and_declines_outside_it(self):
        _, _, payload = request(
            self.server, "/api/ask", "POST",
            {"question": "Design a flyer with a QR code"},
        )
        self.assertEqual(payload["room"], "craft")
        self.assertFalse(payload["used_client_files"])
        self.assertIn("does not answer from the product index", payload["answer"])



class SaveFolders(unittest.TestCase):
    """Where each write lands, and what the index is allowed to see."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._dir, self._db = client_store.CLIENTS_DIR, client_store.CLIENT_DB
        client_store.CLIENTS_DIR = Path(self.tmp.name) / "clients"
        client_store.CLIENT_DB = Path(self.tmp.name) / "clients.db"

    def tearDown(self):
        client_store.CLIENTS_DIR, client_store.CLIENT_DB = self._dir, self._db
        self.tmp.cleanup()

    def test_a_client_photo_is_filed_on_the_client_not_the_shared_shelf(self):
        import sight
        cid = client_store.create_client("Vault Client")
        real = sight.describe_image
        sight.describe_image = lambda *a, **k: "a photo of an id document"
        try:
            out = sight.ingest_sight("aGk=", "id.png", "id", intent="client", client_id=cid)
        finally:
            sight.describe_image = real
        note = Path(out["note"])
        self.assertTrue(str(note).startswith(str(client_store.CLIENTS_DIR)), note)
        self.assertIn(client_store.AI_DRAFT_FOLDER, note.parts)
        # Model-written, so it must not reach the search index.
        self.assertEqual(out["pages"], 0)
        types = {d["doc_type"] for d in client_store.get_client(cid)["documents"]}
        self.assertEqual(types, {client_store.AI_DRAFT_TYPE})

    def test_generated_files_never_land_in_an_evidence_folder(self):
        cid = client_store.create_client("Folder Client")
        path = Path(client_store.add_generated_file(cid, "roa_draft.md", "text"))
        self.assertIn(client_store.AI_DRAFT_FOLDER, path.parts)
        for evidence_folder in client_store.FOLDERS.values():
            self.assertNotIn(evidence_folder, path.parts)


class DraftsAreChecked(unittest.TestCase):
    def test_an_unsupported_figure_is_stripped_from_a_draft(self):
        import versioning
        source = "Client file: the survival period is 14 days."
        draft = "The waiting period is 6 months and the survival period is 14 days."
        checked, flagged = versioning.span_check(draft, source)
        self.assertEqual(flagged, ["6 months"])
        body = checked.split("[SPAN-CHECK]")[0]
        self.assertNotIn("6 months", body)          # gone from the draft itself
        self.assertIn("[MISSING", body)
        self.assertIn("14 days", body)              # supported figure survives
        self.assertIn("6 months", checked)          # but is named in the footer

    def test_the_roa_banner_is_enforced_not_merely_requested(self):
        import rooms
        banner = rooms.get_room("roa").draft_banner
        self.assertIn("INTERNAL DRAFT", banner)


if __name__ == "__main__":
    unittest.main()
