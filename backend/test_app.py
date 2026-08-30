"""HTTP layer: CORS origin rules and the Learn routes the desk UI calls."""
import base64
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        import desk_extra
        cls._docs = desk_extra.DOCS_DIR
        desk_extra.DOCS_DIR = cls.docs
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        import desk_extra
        cls.server.server_close()
        desk_extra.DOCS_DIR = cls._docs
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
        names = {d["name"] for d in payload["docs"]}
        self.assertTrue(any("lesson.md" in n for n in names), names)
        self.assertTrue(any("guide.md" in n for n in names), names)

    def test_discover_reports_shelves(self):
        status, _, payload = request(self.server, "/api/learn/discover")
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("gaps") is not None or payload.get("catalog") is not None)

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
        """Both halves are attacker-controlled: the filename and the topic."""
        body = {
            "filename": "../../escaped.md",
            "content_base64": base64.b64encode(b"# hi").decode(),
            "topic": "../../../../tmp/pwn",
        }
        status, _, _ = request(self.server, "/api/ingest/guides", "POST", body)
        self.assertEqual(status, 200)
        landed = list(self.docs.rglob("escaped.md"))
        self.assertTrue(landed, "guide was not written")
        for path in landed:
            path.resolve().relative_to(self.docs.resolve())  # raises if it escaped
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



class LeadgenAndClientsStaySeparate(unittest.TestCase):
    """Two businesses, one desk. A shop is not an advice client.

    Craft leads are shop owners the studio sells pages to; FA clients are
    advice clients in the vault under FAIS. Filing a lead as a client to reach
    a feature would put a marketing prospect in the regulated store.
    """

    def test_a_client_record_cannot_produce_a_trade_page(self):
        import mockup_router
        with self.assertRaises(ValueError) as caught:
            mockup_router.generate_for_client(
                "Joe Plumbing", "Geyser repairs Kempton Park 011 975 1234")
        self.assertIn("Craft ledger", str(caught.exception))

    def test_a_client_record_cannot_produce_a_page_from_an_fna(self):
        import mockup_router
        with self.assertRaises(ValueError):
            mockup_router.generate_for_client("Mrs Botha", "FNA and policy number 12345")

    def test_a_lead_brief_cannot_carry_client_file_language(self):
        import mockup_router
        for brief in ["record of advice for the owner", "id number 8001015009087",
                      "the client file says"]:
            with self.assertRaises(ValueError, msg=brief):
                mockup_router.generate_for_lead("Joe Plumbing", brief)

    def test_a_lead_brief_still_produces_a_shop_page(self):
        import mockup_router
        out = mockup_router.generate_for_lead(
            "Joe Plumbing", "Geyser repairs Kempton Park 011 975 1234")
        self.assertIn("Joe Plumbing", out["page"])
        self.assertIn("INTERNAL MOCKUP", out["page"])
        self.assertIn("Joe Plumbing", out["flyer"])

    def test_the_craft_door_never_touches_the_vault(self):
        """/api/craft/mock takes a brief, so no client record can be involved."""
        import inspect, mockup_router
        params = inspect.signature(mockup_router.generate_for_lead).parameters
        self.assertNotIn("client_id", params)
        self.assertNotIn("cid", params)
        source = inspect.getsource(mockup_router.generate_for_lead)
        self.assertNotIn("client_store", source)

    def test_the_unguarded_generator_is_gone(self):
        import website_mockup
        self.assertFalse(hasattr(website_mockup, "generate_from_client_documents"))



class PublicMockPages(unittest.TestCase):
    """/m/<slug> is the only thing this server hands to a stranger."""

    def setUp(self):
        import desk_extra
        self.tmp = tempfile.TemporaryDirectory()
        self._dir = desk_extra.MOCK_DIR
        desk_extra.MOCK_DIR = Path(self.tmp.name) / "mocks"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        import desk_extra
        self.server.shutdown()
        self.server.server_close()
        desk_extra.MOCK_DIR = self._dir
        self.tmp.cleanup()

    def publish(self, name="Joe Plumbing", facts="Geyser repairs Kempton Park 011 975 1234"):
        return request(self.server, "/api/craft/page", "POST", {"name": name, "facts": facts})

    def test_publishing_serves_the_page_and_the_flyer(self):
        status, _, payload = self.publish()
        self.assertEqual(status, 200)
        self.assertEqual(payload["slug"], "joe-plumbing")
        base = f"http://127.0.0.1:{self.server.server_address[1]}"
        for path in (payload["path"], payload["flyer"]):
            with urllib.request.urlopen(base + path, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("Joe Plumbing", resp.read().decode())

    def test_a_localhost_qr_is_never_printable(self):
        _, _, payload = self.publish()
        self.assertFalse(payload["qr_printable"])
        self.assertIn("Do not print", payload["note"])
        base = f"http://127.0.0.1:{self.server.server_address[1]}"
        with urllib.request.urlopen(base + payload["flyer"], timeout=10) as resp:
            flyer = resp.read().decode()
        # No QR image at all off a public host — a printed dead QR is worse
        # than none, so the flyer shows the URL and a warning instead.
        self.assertNotIn("api.qrserver.com", flyer)
        self.assertIn("Do not print a QR yet", flyer)

    def test_a_published_page_is_still_marked_a_mockup(self):
        _, _, payload = self.publish()
        base = f"http://127.0.0.1:{self.server.server_address[1]}"
        with urllib.request.urlopen(base + payload["path"], timeout=10) as resp:
            page = resp.read().decode()
        self.assertIn("INTERNAL MOCKUP", page)
        self.assertIn("noindex", page)

    def test_a_lead_brief_with_client_language_is_never_published(self):
        status, _, _ = self.publish(facts="record of advice, id number 8001015009087")
        self.assertEqual(status, 400)

    def test_an_unknown_slug_is_404(self):
        for bad in ["nope", "../../../../etc/passwd", "joe-plumbing"]:
            status, _, _ = request(self.server, f"/m/{bad}")
            self.assertEqual(status, 404, bad)


class ClientMockupsTakeABriefOnly(unittest.TestCase):
    """The filed documents decide whether a mockup is allowed, never what it says."""

    def test_no_client_document_text_reaches_the_generator(self):
        import mockup_router
        seen = {}
        real = mockup_router.generate_mockup
        mockup_router.generate_mockup = lambda brief, **kw: seen.update(
            brief=brief, kwargs=kw) or "<html></html>"
        try:
            mockup_router.generate_for_client(
                "Fortitudo Wealth",
                "Practice storefront. Turnover was R4,200,000 and the secret code is HUSH.",
                extra_brief="calm, one CTA",
            )
        finally:
            mockup_router.generate_mockup = real
        self.assertEqual(seen["kwargs"], {}, "no client_context may be passed")
        self.assertNotIn("HUSH", seen["brief"])
        self.assertNotIn("4,200,000", seen["brief"])
        self.assertIn("calm, one CTA", seen["brief"])


GOOD_PAGE = """<!DOCTYPE html>
<!-- INTERNAL MOCKUP — adviser review required; not live. -->
<html lang="en-ZA"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><style>body{margin:0}</style></head>
<body><h1>Burst pipe in Kempton Park</h1>
<p>Internal mockup · not live</p>
<a href="tel:0119751234">011 975 1234</a>
<p>Open 08:00-17:00</p></body></html>"""


class TheGateOnModelWrittenHtml(unittest.TestCase):
    """The model may write the page. It may not write the facts."""

    ALLOWED = "Joe Plumbing\nKempton Park\n011 975 1234\n08:00-17:00"

    def gate(self, html, allowed=None):
        import html_author
        return html_author.gate(html, allowed if allowed is not None else self.ALLOWED)

    def test_an_honest_page_passes(self):
        self.assertTrue(self.gate(GOOD_PAGE).ok, self.gate(GOOD_PAGE).problems)

    def test_a_truncated_document_is_refused(self):
        # The single most likely model failure: the token budget runs out.
        v = self.gate(GOOD_PAGE[: len(GOOD_PAGE) // 2])
        self.assertFalse(v.ok)
        self.assertTrue(any("truncated" in p for p in v.problems), v.problems)

    def test_an_invented_phone_number_is_refused(self):
        v = self.gate(GOOD_PAGE.replace("011 975 1234", "082 555 9000"))
        self.assertFalse(v.ok)
        self.assertTrue(any("phone not in the brief" in p for p in v.problems), v.problems)

    def test_an_invented_price_is_refused(self):
        v = self.gate(GOOD_PAGE.replace("<p>Open", "<p>Callout from R450.</p><p>Open"))
        self.assertFalse(v.ok)
        self.assertTrue(any("price not in the brief" in p for p in v.problems), v.problems)

    def test_invented_hours_are_refused(self):
        v = self.gate(GOOD_PAGE.replace("08:00-17:00", "06:00-22:00"))
        self.assertFalse(v.ok)
        self.assertTrue(any("time not in the brief" in p for p in v.problems), v.problems)

    def test_an_invented_year_is_refused(self):
        v = self.gate(GOOD_PAGE.replace("<p>Open", "<p>Serving Kempton Park since 1998.</p><p>Open"))
        self.assertFalse(v.ok)
        self.assertTrue(any("year not in the brief" in p for p in v.problems), v.problems)

    def test_unearned_claims_are_refused(self):
        for claim in ["Open 24/7", "Award-winning service", "Best in Gauteng", "5-star rated"]:
            v = self.gate(GOOD_PAGE.replace("<p>Open", f"<p>{claim}</p><p>Open"))
            self.assertFalse(v.ok, claim)
            self.assertTrue(any("unearned claim" in p for p in v.problems), claim)

    def test_script_form_and_handlers_are_refused(self):
        for bad, why in [
            ("<script>fetch('/x')</script>", "<script>"),
            ("<iframe src='//x'></iframe>", "<iframe>"),
            ("<form action='/x'></form>", "<form>"),
            ("<a onclick='x()'>Call</a>", "inline event handler"),
            ("<a href='javascript:x()'>Call</a>", "javascript:"),
        ]:
            v = self.gate(GOOD_PAGE.replace("</body>", bad + "</body>"))
            self.assertFalse(v.ok, bad)
            self.assertTrue(any(why in p for p in v.problems), (bad, v.problems))

    def test_a_mockup_must_say_it_is_a_mockup(self):
        stripped = GOOD_PAGE.replace(
            "<!-- INTERNAL MOCKUP — adviser review required; not live. -->", ""
        ).replace("Internal mockup · not live", "")
        v = self.gate(stripped)
        self.assertFalse(v.ok)
        self.assertTrue(any("INTERNAL MOCKUP" in p for p in v.problems), v.problems)

    def test_a_mockup_must_be_noindex(self):
        v = self.gate(GOOD_PAGE.replace('content="noindex,nofollow"', 'content="index,follow"'))
        self.assertFalse(v.ok)
        self.assertIn("missing noindex", v.problems)

    def test_a_live_page_needs_no_mockup_marker(self):
        import html_author
        stripped = GOOD_PAGE.replace(
            "<!-- INTERNAL MOCKUP — adviser review required; not live. -->", ""
        ).replace('<meta name="robots" content="noindex,nofollow">', "")
        self.assertTrue(html_author.gate(stripped, self.ALLOWED, live=True).ok)

    def test_facts_inside_style_and_head_are_not_read_as_claims(self):
        # A CSS rule is not a promise. Only visible text is judged.
        v = self.gate(GOOD_PAGE.replace("body{margin:0}", "body{margin:0;line-height:1.24}"))
        self.assertTrue(v.ok, v.problems)


class TheAuthorFallsBackRatherThanShipJunk(unittest.TestCase):
    """A page always comes out. A wrong one never does."""

    def _stub(self, reply):
        import llm
        real = llm.chat
        llm.chat = lambda *a, **kw: reply
        return real

    def test_a_rejected_page_returns_none_with_reasons(self):
        import llm, html_author
        from trade_page import facts_from_text
        real = self._stub("<html><body>Call 082 555 9000</body></html>")
        try:
            page, notes = html_author.author(
                facts_from_text("Joe Plumbing", "Geyser repairs 011 975 1234"),
                brief="Geyser repairs 011 975 1234")
        finally:
            llm.chat = real
        self.assertIsNone(page)
        self.assertTrue(notes)

    def test_an_unreachable_model_is_reported_not_raised(self):
        import llm, html_author
        from trade_page import facts_from_text

        def boom(*a, **kw):
            raise OSError("ollama is not running")

        real = llm.chat
        llm.chat = boom
        try:
            page, notes = html_author.author(facts_from_text("Joe Plumbing", ""), brief="")
        finally:
            llm.chat = real
        self.assertIsNone(page)
        self.assertTrue(any("model unavailable" in n for n in notes), notes)

    def test_an_accepted_page_is_returned_verbatim(self):
        import llm, html_author
        from trade_page import facts_from_text
        real = self._stub("```html\n" + GOOD_PAGE + "\n```")
        try:
            page, notes = html_author.author(
                facts_from_text("Joe Plumbing", "Geyser repairs 011 975 1234 08:00-17:00"),
                brief="Geyser repairs 011 975 1234 08:00-17:00")
        finally:
            llm.chat = real
        self.assertIsNotNone(page)
        self.assertTrue(page.startswith("<!DOCTYPE html>"), page[:40])
        self.assertTrue(any("model wrote the page" in n for n in notes), notes)

    def test_the_request_asks_for_room_to_write_a_whole_page(self):
        """A page does not fit in the desk defaults. Assert what Ollama is sent.

        num_predict alone is not enough: prompt and answer share num_ctx, so a
        long answer in a small window corrupts the page instead of shortening
        it, and the desk's 300s timeout aborts it before either matters.
        """
        import llm, html_author, config
        from trade_page import facts_from_text
        sent = {}
        real = llm._post
        llm._post = lambda path, payload, timeout=llm.TIMEOUT, host="": sent.update(
            payload=payload, timeout=timeout, host=host) or {"message": {"content": GOOD_PAGE}}
        try:
            html_author.author(facts_from_text("Joe Plumbing", ""), brief="")
        finally:
            llm._post = real
        opts = sent["payload"]["options"]
        self.assertEqual(opts["num_predict"], html_author.HTML_NUM_PREDICT)
        self.assertEqual(opts["num_ctx"], html_author.HTML_NUM_CTX)
        self.assertGreater(opts["num_predict"], config.CHAT_NUM_PREDICT * 4)
        self.assertGreater(opts["num_ctx"], opts["num_predict"])
        self.assertEqual(sent["timeout"], html_author.HTML_TIMEOUT)
        self.assertGreater(sent["timeout"], llm.TIMEOUT)

    def test_the_desk_default_call_is_unchanged(self):
        """Raising the cap for pages must not raise it for every answer."""
        import llm, config
        sent = {}
        real = llm._post
        llm._post = lambda path, payload, timeout=llm.TIMEOUT, host="": sent.update(
            payload=payload, timeout=timeout, host=host) or {"message": {"content": "hi"}}
        try:
            llm.chat("sys", "user")
        finally:
            llm._post = real
        self.assertEqual(sent["payload"]["options"]["num_predict"], config.CHAT_NUM_PREDICT)
        self.assertEqual(sent["payload"]["options"]["num_ctx"], config.CHAT_NUM_CTX)
        self.assertEqual(sent["timeout"], llm.TIMEOUT)

    def test_authoring_can_be_switched_off_on_a_thin_machine(self):
        import html_author
        real = html_author.ENABLED
        html_author.ENABLED = False
        try:
            from trade_page import facts_from_text
            page, notes = html_author.author(facts_from_text("Joe", ""), brief="")
        finally:
            html_author.ENABLED = real
        self.assertIsNone(page)
        self.assertTrue(any("off" in n for n in notes), notes)

    def test_a_refused_page_still_leaves_a_page_on_disk(self):
        import mockup_router
        out = mockup_router.generate_for_lead(
            "Joe Plumbing", "Geyser repairs Kempton Park 011 975 1234",
            author_html=False)
        self.assertFalse(out["authored"])
        self.assertIn("INTERNAL MOCKUP", out["page"])

    def test_the_answer_says_who_wrote_the_page(self):
        """A silent downgrade to the template would be indistinguishable."""
        import mockup_router
        out = mockup_router.generate_for_lead(
            "Joe Plumbing", "Geyser repairs Kempton Park 011 975 1234")
        self.assertIn("authored", out)
        self.assertIn("author_notes", out)



MODEL_PAGE = """<!DOCTYPE html>
<!-- INTERNAL MOCKUP - adviser review required; not live. -->
<html lang="en-ZA"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Joe Plumbing</title>
<style>:root{--acc:#c8102e}body{margin:0;font:16px/1.5 system-ui,sans-serif}
.bar{position:fixed;bottom:0;left:0;right:0}@media print{.bar{display:none}}</style>
</head><body>
<header><h1>Burst pipe or cold geyser - call us in Kempton Park</h1>
<p>Internal mockup - not live</p></header>
<a href="tel:0119751234">Call PHONE_HERE</a>
<main><p>Phone: PHONE_HERE</p><p>Hours: [HOURS]</p></main>
<div class="bar"><a href="tel:0119751234">Call</a></div>
</body></html>"""


class AStubOllama(BaseHTTPRequestHandler):
    """Answers design_reason with JSON and html_author with a page."""

    page = MODEL_PAGE.replace("PHONE_HERE", "011 975 1234")

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0)))
        if "web developer" in body["messages"][0]["content"]:
            out = type(self).page
        else:
            out = json.dumps({"headline": "Burst pipe or cold geyser - call us in Kempton Park",
                              "lead": "Call or WhatsApp.", "intent": "emergency"})
        raw = json.dumps({"message": {"content": out}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class TheModelWritesTheServedPage(unittest.TestCase):
    """End to end: POST a brief, and read back what /m/<slug> actually serves."""

    BRIEF = "Geyser repairs and burst pipes in Kempton Park. Phone 011 975 1234."

    @classmethod
    def setUpClass(cls):
        import desk_extra, llm
        cls.ollama = ThreadingHTTPServer(("127.0.0.1", 0), AStubOllama)
        threading.Thread(target=cls.ollama.serve_forever, daemon=True).start()
        cls._host = llm.OLLAMA_HOST
        llm.OLLAMA_HOST = f"http://127.0.0.1:{cls.ollama.server_address[1]}"

        cls.tmp = tempfile.TemporaryDirectory()
        cls._mocks = desk_extra.MOCK_DIR
        desk_extra.MOCK_DIR = Path(cls.tmp.name) / "mocks"

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        import desk_extra, llm
        llm.OLLAMA_HOST = cls._host
        desk_extra.MOCK_DIR = cls._mocks
        cls.server.shutdown()
        cls.ollama.shutdown()
        cls.tmp.cleanup()

    def build(self):
        return request(self.server, "/api/craft/page", method="POST",
                       body={"name": "Joe Plumbing", "facts": self.BRIEF,
                             "city": "Kempton Park"})

    def served(self, path):
        url = f"http://127.0.0.1:{self.server.server_address[1]}{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read().decode()

    def test_a_page_the_model_wrote_is_the_page_that_is_served(self):
        AStubOllama.page = MODEL_PAGE.replace("PHONE_HERE", "011 975 1234")
        status, _, out = self.build()
        self.assertEqual(status, 200)
        self.assertTrue(out["authored"], out["author_notes"])
        page = self.served(out["path"])
        self.assertIn("--acc:#c8102e", page, "this is the template, not the model's page")
        self.assertIn("INTERNAL MOCKUP", page)

    def test_a_page_that_invents_a_phone_number_never_reaches_the_slug(self):
        AStubOllama.page = MODEL_PAGE.replace("PHONE_HERE", "082 555 9000")
        status, _, out = self.build()
        self.assertEqual(status, 200)
        self.assertFalse(out["authored"])
        self.assertTrue(any("phone" in n for n in out["author_notes"]), out["author_notes"])
        page = self.served(out["path"])
        self.assertNotIn("082 555 9000", page)
        self.assertIn("INTERNAL MOCKUP", page)



LAN = "http://192.168.1.50:11434"
HERE = "http://127.0.0.1:11434"


class ClientDataStaysOnThisMachine(unittest.TestCase):
    """Pointing the desk at a faster box must not put client files on the LAN."""

    def setUp(self):
        import compute
        self.compute = compute
        self._allow = compute.ALLOW_REMOTE_CLIENT_DATA
        self._env = dict(os.environ)

    def tearDown(self):
        self.compute.ALLOW_REMOTE_CLIENT_DATA = self._allow
        os.environ.clear()
        os.environ.update(self._env)

    def test_craft_may_run_on_another_machine(self):
        plan = self.compute.resolve("craft", LAN)
        self.assertEqual(plan.host, LAN)
        self.assertFalse(plan.carries_client_data)

    def test_every_other_job_is_pinned_back_to_this_machine(self):
        for job in ["fa", "roa", "voice", "drama", "learn", "filing", "sight"]:
            plan = self.compute.resolve(job, LAN)
            self.assertTrue(plan.pinned_local, job)
            self.assertTrue(self.compute.is_local(plan.host), (job, plan.host))

    def test_an_unnamed_job_is_pinned_too(self):
        """Forgetting to name a job must fail safe, not fast."""
        for job in ["", "something_new", "toaster"]:
            self.assertTrue(self.compute.resolve(job, LAN).pinned_local, job)

    def test_the_pin_says_why_and_how_to_lift_it(self):
        why = self.compute.resolve("roa", LAN).why
        self.assertIn(LAN, why)
        self.assertIn("FORTITUDO_ALLOW_REMOTE_CLIENT_DATA", why)

    def test_the_operator_can_opt_out_deliberately(self):
        self.compute.ALLOW_REMOTE_CLIENT_DATA = True
        self.assertEqual(self.compute.resolve("roa", LAN).host, LAN)

    def test_nothing_is_pinned_when_the_host_is_already_local(self):
        for job in ["fa", "roa", "filing"]:
            self.assertFalse(self.compute.resolve(job, HERE).pinned_local, job)

    def test_a_host_that_cannot_be_read_is_not_treated_as_local(self):
        for host in ["", "not a url", "http://", "http://evil.example.com",
                     "http://127.0.0.1.evil.com", "http://0.0.0.0:11434"]:
            self.assertFalse(self.compute.is_local(host), host)

    def test_loopback_spellings_are_local(self):
        for host in ["http://127.0.0.1:11434", "http://localhost:11434",
                     "http://[::1]:11434", "127.0.0.1:11434"]:
            self.assertTrue(self.compute.is_local(host), host)

    def test_a_job_can_be_given_its_own_model(self):
        os.environ["FORTITUDO_CRAFT_MODEL"] = "qwen2.5-coder:7b"
        self.assertEqual(self.compute.resolve("craft", HERE).model, "qwen2.5-coder:7b")
        import config
        self.assertEqual(self.compute.resolve("fa", HERE).model, config.CHAT_MODEL)

    def test_a_job_can_be_given_its_own_host(self):
        os.environ["FORTITUDO_CRAFT_HOST"] = LAN
        self.assertEqual(self.compute.resolve("craft", HERE).host, LAN)
        self.assertEqual(self.compute.resolve("fa", HERE).host, HERE)

    def test_a_per_job_host_cannot_smuggle_client_data_out(self):
        """The pin is on the job, not on where the host came from."""
        os.environ["FORTITUDO_ROA_HOST"] = LAN
        plan = self.compute.resolve("roa", HERE)
        self.assertTrue(plan.pinned_local)
        self.assertTrue(self.compute.is_local(plan.host))


class EveryModelCallNamesItsJob(unittest.TestCase):
    """A call with no job is routed as client data, so an unlabelled one is a bug."""

    def test_the_client_carrying_call_sites_are_labelled(self):
        import inspect, app, sort_engine, ask
        self.assertIn('job="filing"', inspect.getsource(sort_engine.SortEngine._classify))
        self.assertIn('job="roa"', inspect.getsource(app.Handler))
        self.assertIn("job=room", inspect.getsource(ask.answer))

    def test_no_chat_call_in_the_backend_is_unlabelled(self):
        import pathlib, re
        root = pathlib.Path(__file__).parent
        misses = []
        for py in sorted(root.glob("*.py")):
            if py.name.startswith("test_") or py.name in {"llm.py", "compute.py"}:
                continue
            src = py.read_text(encoding="utf-8")
            for call in re.findall(r"\bchat\(\s*[A-Z_]+\w*\s*,.*?\)", src, re.S):
                if "job=" not in call:
                    misses.append(f"{py.name}: {call[:60]}")
        self.assertEqual(misses, [], "these calls would be routed as client data")

    def test_chat_sends_craft_to_the_fast_box_and_roa_to_this_one(self):
        """The whole point, exercised through llm.chat rather than resolve()."""
        import llm
        lan = "http://192.168.1.50:11434"
        seen = []
        real = llm._post
        env = dict(os.environ)
        os.environ["FORTITUDO_CRAFT_HOST"] = lan
        os.environ["FORTITUDO_CRAFT_MODEL"] = "qwen2.5-coder:7b"
        llm._post = lambda path, payload, timeout=llm.TIMEOUT, host="": seen.append(
            (host, payload["model"])) or {"message": {"content": "x"}}
        try:
            llm.chat("sys", "brief", job="craft")
            llm.chat("sys", "client file", job="roa")
            llm.chat("sys", "unlabelled")
        finally:
            llm._post = real
            os.environ.clear()
            os.environ.update(env)
        import compute, config
        self.assertEqual(seen[0], (lan, "qwen2.5-coder:7b"), "craft should use the fast box")
        for host, model in seen[1:]:
            self.assertTrue(compute.is_local(host), host)
            self.assertEqual(model, config.CHAT_MODEL)

    def test_health_reports_where_each_job_runs(self):
        import compute, llm
        jobs = {p.job for p in compute.plans(llm.OLLAMA_HOST)}
        for expected in ["fa", "roa", "craft", "filing", "sight"]:
            self.assertIn(expected, jobs)



if __name__ == "__main__":
    unittest.main()
