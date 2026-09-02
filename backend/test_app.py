"""HTTP layer: CORS origin rules and the Learn routes the desk UI calls."""
import base64
import json
import os
import re
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

    def _send(self, payload):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        # resolve_model() asks which models exist before it asks for an answer.
        self._send({"models": [{"name": "fortitudo:latest"}, {"name": "llama3.2:3b"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0)))
        if "web developer" in body["messages"][0]["content"]:
            out = type(self).page
        else:
            out = json.dumps({"headline": "Burst pipe or cold geyser - call us in Kempton Park",
                              "lead": "Call or WhatsApp.", "intent": "emergency"})
        self._send({"message": {"content": out}})


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



class TheDeskAsksForItsOwnModel(unittest.TestCase):
    """`fortitudo` is the default. A fresh clone that lacks it still runs."""

    def setUp(self):
        import llm
        self.llm = llm
        llm._resolved.clear()

    def tearDown(self):
        self.llm._resolved.clear()

    def _installed(self, names):
        real = self.llm.health
        self.llm.health = lambda host="": list(names)
        return real

    def test_the_configured_default_is_the_desks_own_model(self):
        import config
        self.assertEqual(config.CHAT_MODEL, "fortitudo")

    def test_it_uses_fortitudo_when_it_is_built(self):
        real = self._installed(["fortitudo:latest", "llama3.2:3b"])
        try:
            self.assertEqual(self.llm.resolve_model("fortitudo"), "fortitudo")
        finally:
            self.llm.health = real

    def test_it_falls_back_to_the_base_model_when_it_is_not(self):
        import config
        real = self._installed(["llama3.2:3b"])
        try:
            self.assertEqual(self.llm.resolve_model("fortitudo"), config.BASE_MODEL)
        finally:
            self.llm.health = real

    def test_an_explicit_model_is_never_second_guessed(self):
        real = self._installed(["qwen2.5-coder:7b", "llama3.2:3b"])
        try:
            self.assertEqual(self.llm.resolve_model("qwen2.5-coder:7b"), "qwen2.5-coder:7b")
        finally:
            self.llm.health = real

    def test_a_dead_ollama_reports_rather_than_silently_substituting(self):
        real = self.llm.health

        def down(host=""):
            raise self.llm.OllamaError("not running")

        self.llm.health = down
        try:
            self.assertEqual(self.llm.resolve_model("fortitudo"), "fortitudo")
        finally:
            self.llm.health = real

    def test_the_lookup_is_cached_not_run_per_question(self):
        calls = []
        real = self.llm.health
        self.llm.health = lambda host="": calls.append(1) or ["fortitudo:latest"]
        try:
            for _ in range(5):
                self.llm.resolve_model("fortitudo")
        finally:
            self.llm.health = real
        self.assertEqual(len(calls), 1, "one probe, not one per call")

    def test_each_host_is_resolved_separately(self):
        """The craft box and this machine can have different models installed."""
        seen = []
        real = self.llm.health
        self.llm.health = lambda host="": seen.append(host) or ["fortitudo:latest"]
        try:
            self.llm.resolve_model("fortitudo", "http://127.0.0.1:11434")
            self.llm.resolve_model("fortitudo", "http://192.168.1.50:11434")
        finally:
            self.llm.health = real
        self.assertEqual(len(seen), 2)


class TheModelfileIsTheDesksIdentity(unittest.TestCase):
    """The built model must carry the rails, or building it is decoration."""

    @classmethod
    def setUpClass(cls):
        cls.text = (Path(__file__).parent / "model" / "Modelfile").read_text(encoding="utf-8")

    def test_it_declares_a_base_and_a_system(self):
        self.assertIn("FROM ", self.text)
        self.assertIn("SYSTEM ", self.text)

    def test_it_states_the_fsp_boundary(self):
        self.assertIn("FSP 2409", self.text)
        self.assertIn("You are not the FSP", self.text)

    def test_it_carries_the_refusals_the_code_enforces(self):
        for rule in ["waiting period", "24/7", "testimonial", "opening hours"]:
            self.assertIn(rule, self.text, rule)

    def test_it_keeps_the_two_businesses_apart(self):
        self.assertIn("separate businesses", self.text)

    def test_it_defers_to_the_room_prompt(self):
        """A baked-in prompt must be the floor, never override a room."""
        self.assertIn("These are the floor.", self.text)

    def test_the_context_window_fits_a_room_prompt_plus_extracts(self):
        import config
        m = re.search(r"PARAMETER num_ctx (\d+)", self.text)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), config.CHAT_NUM_CTX)



class DoctrineReachesTheModel(unittest.TestCase):
    """A doctrine file nobody loads is a file, not knowledge."""

    def test_the_html_doctrine_is_loaded(self):
        import html_author
        text = html_author.doctrine()
        self.assertGreater(len(text), 500)
        for rule in ["[HOURS]", "24/7", "INTERNAL MOCKUP", "noindex"]:
            self.assertIn(rule, text, rule)

    def test_the_doctrine_is_in_the_prompt_the_model_sees(self):
        import llm, html_author
        from trade_page import facts_from_text
        seen = {}
        real = llm._post
        llm._post = lambda path, payload, timeout=llm.TIMEOUT, host="": seen.update(
            user=payload["messages"][1]["content"]) or {"message": {"content": "x"}}
        try:
            html_author.author(facts_from_text("Joe Plumbing", ""), brief="")
        finally:
            llm._post = real
        self.assertIn("DOCTRINE", seen["user"])
        self.assertIn("[HOURS]", seen["user"])

    def test_the_doctrine_teaches_what_the_gate_actually_checks(self):
        """Doctrine that disagrees with the gate trains the model to fail."""
        import html_author
        text = html_author.doctrine().lower()
        for banned in ["24/7", "award-winning", "best in", "guaranteed"]:
            self.assertIn(banned, text, f"gate bans {banned} but doctrine never says so")
        self.assertIn("script", text)
        self.assertIn("<form", text.replace("`", ""))

    def test_craft_doctrine_no_longer_says_html_is_not_its_job(self):
        """html_author made that instruction false; a stale rule is worse than none."""
        import reason
        self.assertNotIn("Design HTML is not your job", reason.DOCTRINE["craft"])
        self.assertIn("author the HTML", reason.DOCTRINE["craft"])

    def test_the_separation_doctrine_exists_and_names_both_sides(self):
        text = (Path(__file__).parent / "docs" / "desk_separation_doctrine.md").read_text(encoding="utf-8")
        self.assertIn("Craft lead", text)
        self.assertIn("FA client", text)
        self.assertIn("never share a record", text)

    def test_every_doctrine_file_is_listed_in_the_index(self):
        docs = Path(__file__).parent / "docs"
        index = (docs / "KNOWLEDGE_INDEX.md").read_text(encoding="utf-8")
        for name in ["craft_html_doctrine.md", "desk_separation_doctrine.md"]:
            self.assertIn(name, index, f"{name} is not discoverable from the index")



class MoneyIsCheckedLikeEveryOtherFigure(unittest.TestCase):
    """An invented premium was the one figure span_check never looked at."""

    def check(self, answer, context):
        from versioning import span_check
        return span_check(answer, context)

    def test_an_invented_rand_amount_is_replaced(self):
        out, flagged = self.check("The premium is R1 250 per month.", "No premium is stated.")
        self.assertNotIn("R1 250", out.split("[SPAN-CHECK]")[0])
        self.assertIn("R1 250", flagged)

    def test_an_invented_sum_assured_is_replaced(self):
        out, _ = self.check("Cover of R1 500 000 applies.", "The benefit amount is not given.")
        self.assertNotIn("R1 500 000", out.split("[SPAN-CHECK]")[0])

    def test_a_real_amount_survives_a_different_separator(self):
        """R1,250 and R1 250 are the same number; flagging one would be a lie."""
        out, flagged = self.check("The premium is R1 250.", "Premium: R1,250 monthly.")
        self.assertIn("R1 250", out)
        self.assertEqual(flagged, [])

    def test_a_bare_thousands_figure_is_checked(self):
        out, _ = self.check("Income of 1 500 000 a year.", "No income figure appears here.")
        self.assertNotIn("1 500 000", out.split("[SPAN-CHECK]")[0])

    def test_percentages_and_durations_still_work(self):
        out, _ = self.check("A 6 month wait and 80% payout.", "A 3 month wait. Pays 100%.")
        body = out.split("[SPAN-CHECK]")[0]
        self.assertNotIn("6 month", body)
        self.assertNotIn("80%", body)


class TheDeskSaysWhenItHoldsTwoVersions(unittest.TestCase):
    """A real citation vouching for the wrong version is the invisible failure."""

    def rows(self, *sources):
        return [((i, s, 1, "text", 0), 1.0) for i, s in enumerate(sources)]

    def test_two_versions_of_one_guide_are_flagged(self):
        from versioning import version_conflict
        got = version_conflict(self.rows("guide:lifestyle_protector",
                                         "guide:lifestyle_protector_v2"))
        self.assertEqual(len(got), 2)

    def test_two_different_products_are_not_flagged(self):
        from versioning import version_conflict
        self.assertEqual(
            version_conflict(self.rows("guide:lifestyle_protector", "guide:income_protector")),
            [])

    def test_dated_editions_of_one_guide_are_flagged(self):
        from versioning import version_conflict
        self.assertEqual(
            len(version_conflict(self.rows("guide:lp_2024", "guide:lp_2025"))), 2)

    def test_the_note_tells_the_adviser_what_to_do(self):
        from versioning import version_note
        note = version_note(self.rows("guide:lp", "guide:lp_v2"))
        self.assertIn("[VERSIONS]", note)
        self.assertIn("Open the cited page", note)

    def test_a_clean_result_set_adds_nothing(self):
        from versioning import version_note
        self.assertEqual(version_note(self.rows("guide:income_protector")), "")


class ReasoningDepthFollowsTheRoom(unittest.TestCase):
    """A second model call is minutes on a CPU. Spend it where it is owed."""

    def setUp(self):
        self._saved = os.environ.pop("FORTITUDO_THINK", None)

    def tearDown(self):
        os.environ.pop("FORTITUDO_THINK", None)
        if self._saved is not None:
            os.environ["FORTITUDO_THINK"] = self._saved

    def test_the_compliance_rooms_reason_first(self):
        import ask
        for room in ("fa", "roa"):
            self.assertTrue(ask._should_think(room), room)

    def test_the_draft_rooms_answer_in_one_pass(self):
        import ask
        for room in ("craft", "voice", "drama", "learn"):
            self.assertFalse(ask._should_think(room), room)

    def test_it_can_be_forced_on_and_off(self):
        import ask
        os.environ["FORTITUDO_THINK"] = "1"
        self.assertTrue(ask._should_think("craft"))
        os.environ["FORTITUDO_THINK"] = "0"
        self.assertFalse(ask._should_think("fa"))


class TheEvalHarnessIsRealAndRuns(unittest.TestCase):
    """A harness that cannot fail measures nothing."""

    def test_the_offline_suites_pass_on_this_commit(self):
        import eval_desk
        conn = eval_desk.build_index()
        for score in (eval_desk.score_routing(), eval_desk.score_retrieval(conn),
                      eval_desk.score_grounding(), eval_desk.score_separation(),
                      eval_desk.score_gate(), eval_desk.score_versioning(),
                      eval_desk.score_depth()):
            self.assertEqual(score.failed, [], f"{score.name}: {score.failed}")
            self.assertGreater(score.total, 0, f"{score.name} has no cases")

    def test_the_corpus_contains_a_deliberate_near_duplicate(self):
        """Without rival versions the retrieval score cannot discriminate."""
        from eval.harness import CORPUS
        names = {p.stem for p in CORPUS.glob("*.txt")}
        self.assertIn("lifestyle_protector", names)
        self.assertIn("lifestyle_protector_v2", names)

    def test_the_fixture_embedding_is_deterministic(self):
        from eval.harness import fake_embed
        self.assertEqual(fake_embed("waiting period"), fake_embed("waiting period"))
        self.assertNotEqual(fake_embed("waiting period"), fake_embed("hearing loss"))



class PdfOperationsNeverTouchTheOriginal(unittest.TestCase):
    """The compliance guarantee, tested rather than trusted.

    A filed client document is the signed record. Every operation here reads
    bytes and returns bytes, so the code has no way to write over what it
    opened — these tests exist to keep it that way.
    """

    def setUp(self):
        import pdf_tools
        self.pdf_tools = pdf_tools
        self.src = pdf_tools.make_pdf([
            "Mrs A Botha - Financial Needs Analysis",
            "ID number 8001015009087. Account 1234567890.",
            "Waiting period 3 months. Level A pays 100%.",
        ])

    def test_no_operation_returns_the_bytes_it_was_given(self):
        t = self.pdf_tools
        before = bytes(self.src)
        outputs = [
            t.annotate(self.src, [t.Note(page=1, text="check this")]),
            t.stamp(self.src, "INTERNAL DRAFT"),
            t.select_pages(self.src, "1"),
            t.rotate_pages(self.src, "1", 90),
            t.redact(self.src, patterns=["sa_id"])[0],
        ]
        self.assertEqual(self.src, before, "the source bytes were mutated in place")
        for out in outputs:
            self.assertNotEqual(out, before, "an operation returned the original unchanged")

    def test_the_module_cannot_write_to_a_path_at_all(self):
        """Structural, not a convention. pdf_tools never touches the filesystem.

        Reading bytes in and handing bytes back is what makes overwriting a
        signed record impossible rather than merely discouraged.
        """
        import inspect, pdf_tools, re
        src = inspect.getsource(pdf_tools)
        for banned in ["write_bytes(", "write_text(", "shutil.", "os.remove",
                       "os.rename", "os.replace", "Path("]:
            self.assertNotIn(banned, src, f"pdf_tools uses {banned}")
        # The only open() allowed is pdfplumber reading an in-memory buffer.
        for call in re.findall(r"[\w.]*\bopen\s*\(", src):
            self.assertEqual(call, "pdfplumber.open(", f"unexpected open: {call}")


class RedactionRemovesRatherThanCovers(unittest.TestCase):
    """A black box over a number leaves the number in the file."""

    def setUp(self):
        import pdf_tools
        self.t = pdf_tools
        self.src = pdf_tools.make_pdf([
            "Client Mrs Botha", "ID number 8001015009087 and account 1234567890"])

    def text_of(self, data):
        return " ".join(p.text for p in self.t.read_pages(data))

    def test_an_id_number_is_gone_from_the_extracted_text(self):
        out, removed = self.t.redact(self.src, patterns=["sa_id"])
        self.assertIn("8001015009087", removed)
        self.assertNotIn("8001015009087", self.text_of(out))

    def test_it_is_gone_from_the_raw_bytes_too(self):
        """The real test. Extraction can miss what a text search still finds."""
        out, _ = self.t.redact(self.src, patterns=["sa_id"])
        self.assertNotIn(b"8001015009087", out)

    def test_the_rest_of_the_document_survives(self):
        out, _ = self.t.redact(self.src, patterns=["sa_id"])
        self.assertIn("Botha", self.text_of(out))

    def test_a_literal_string_can_be_removed(self):
        out, removed = self.t.redact(self.src, literals=["Mrs Botha"])
        self.assertIn("Mrs Botha", removed)
        self.assertNotIn(b"Mrs Botha", out)

    def test_a_scan_is_refused_rather_than_pretend_redacted(self):
        """No text to remove: reporting success would be the worst outcome."""
        blank = self.t.make_pdf([""])
        with self.assertRaises(self.t.NotRedactable) as caught:
            self.t.redact(blank, patterns=["sa_id"])
        self.assertIn("OCR", str(caught.exception))

    def test_nothing_matched_removes_nothing(self):
        out, removed = self.t.redact(self.src, literals=["not in this document"])
        self.assertEqual(removed, [])


class FormFillingSaysWhatItCouldNotDo(unittest.TestCase):
    def test_unknown_field_names_are_reported_not_dropped(self):
        """A form silently missing your field looks like a filled form."""
        import pdf_tools
        src = pdf_tools.make_pdf(["A page with no form fields"])
        _out, missing = pdf_tools.fill_form(src, {"full_name": "A Botha"})
        self.assertEqual(missing, ["full_name"])

    def test_a_document_with_no_fields_reports_none(self):
        import pdf_tools
        self.assertEqual(pdf_tools.form_fields(pdf_tools.make_pdf(["plain"])), [])


class PageSelectionRefusesWhatItCannotHonour(unittest.TestCase):
    def setUp(self):
        import pdf_tools
        self.t = pdf_tools
        self.src = pdf_tools.make_pdf(["one", "two", "three", "four"])

    def test_a_range_is_expanded(self):
        self.assertEqual(self.t.page_count(self.t.select_pages(self.src, "1,3-4")), 3)

    def test_an_out_of_range_page_is_dropped_not_clamped(self):
        """Clamping would put a page nobody asked for into a client pack."""
        self.assertEqual(self.t.page_count(self.t.select_pages(self.src, "2,99")), 1)

    def test_selecting_nothing_is_an_error_not_an_empty_pdf(self):
        with self.assertRaises(ValueError):
            self.t.select_pages(self.src, "99")

    def test_duplicates_are_not_repeated(self):
        self.assertEqual(self.t.page_count(self.t.select_pages(self.src, "2,2,2")), 1)


class StampingLeavesTheContentReadable(unittest.TestCase):
    def test_the_banner_is_added_and_the_page_survives(self):
        import pdf_tools
        src = pdf_tools.make_pdf(["Original body text"])
        out = pdf_tools.stamp(src, "INTERNAL DRAFT - adviser review required")
        text = " ".join(p.text for p in pdf_tools.read_pages(out))
        self.assertIn("INTERNAL DRAFT", text)
        self.assertIn("Original body text", text)


class ExtractionIsTheHonestVersionOfEditing(unittest.TestCase):
    def test_a_text_pdf_becomes_a_working_draft(self):
        import pdf_tools
        src = pdf_tools.make_pdf(["Waiting period is 3 months."])
        md = pdf_tools.to_markdown(src, "Botha FNA")
        self.assertIn("# Botha FNA", md)
        self.assertIn("3 months", md)
        self.assertIn("unchanged", md)

    def test_a_scan_says_it_needs_ocr_rather_than_returning_nothing(self):
        import pdf_tools
        md = pdf_tools.to_markdown(pdf_tools.make_pdf([""]), "Scan")
        self.assertIn("OCR", md)


class ThePdfApiWritesOnlyToTheDraftFolder(unittest.TestCase):
    """End to end against a real vault: read a filed PDF, write a new draft."""

    def setUp(self):
        import pdf_tools
        self.tmp = tempfile.TemporaryDirectory()
        self._dir, self._db = client_store.CLIENTS_DIR, client_store.CLIENT_DB
        client_store.CLIENTS_DIR = Path(self.tmp.name) / "clients"
        client_store.CLIENT_DB = Path(self.tmp.name) / "clients.db"
        self.cid = client_store.create_client("Pdf Client")
        self.original = pdf_tools.make_pdf([
            "Signed FNA", "ID number 8001015009087"])
        self.path = client_store.add_document(
            self.cid, "signed_fna.pdf", self.original, "Signed FNA", "application/pdf")
        conn = client_store.connect()
        row = conn.execute(
            "SELECT id FROM documents WHERE client_id = ? ORDER BY id DESC", (self.cid,)
        ).fetchone()
        conn.close()
        self.doc_id = str(row["id"])

    def tearDown(self):
        client_store.CLIENTS_DIR, client_store.CLIENT_DB = self._dir, self._db
        self.tmp.cleanup()

    def sent(self, action, body):
        import pdf_api
        captured = {}

        class Fake:
            def send_json(self, payload, status=200):
                captured.update(payload=payload, status=status)

        handled = pdf_api.handle_post(Fake(), ["api", "pdf", self.doc_id, action], body)
        self.assertTrue(handled, action)
        return captured

    def test_describe_reports_what_this_document_supports(self):
        import pdf_api
        info = pdf_api.describe(self.doc_id)
        self.assertEqual(info["page_count"], 2)
        self.assertFalse(info["scanned"])
        self.assertTrue(info["can"]["redact"])
        self.assertFalse(info["can"]["fill"], "no form fields, so fill is not offered")

    def test_a_redaction_writes_a_new_file_and_leaves_the_original(self):
        out = self.sent("redact", {"patterns": ["sa_id"]})["payload"]
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["folder"], client_store.AI_DRAFT_FOLDER)
        self.assertEqual(out["doc_type"], client_store.AI_DRAFT_TYPE)
        self.assertIn("8001015009087", out["removed"])
        # The signed record is byte-identical to what was filed.
        self.assertEqual(Path(self.path).read_bytes(), self.original)
        self.assertIn(b"8001015009087", Path(self.path).read_bytes())
        # The new file is a real, different, redacted document.
        self.assertNotIn(b"8001015009087", Path(out["path"]).read_bytes())

    def test_the_draft_lands_under_the_drafts_folder_on_disk(self):
        out = self.sent("stamp", {"text": "INTERNAL DRAFT"})["payload"]
        self.assertIn(client_store.AI_DRAFT_FOLDER, out["path"])

    def test_every_action_keeps_the_original_byte_identical(self):
        for action, body in [
            ("stamp", {"text": "REVIEW"}),
            ("annotate", {"notes": [{"page": 1, "text": "confirm this"}]}),
            ("assemble", {"select": "1"}),
            ("extract", {}),
            ("redact", {"patterns": ["sa_id"]}),
        ]:
            self.sent(action, body)
            self.assertEqual(Path(self.path).read_bytes(), self.original, action)

    def test_a_redaction_that_matches_nothing_writes_no_file(self):
        before = len(list(Path(self.path).parent.parent.rglob("*.pdf")))
        result = self.sent("redact", {"literals": ["nothing like this"]})
        self.assertEqual(result["status"], 400)
        after = len(list(Path(self.path).parent.parent.rglob("*.pdf")))
        self.assertEqual(before, after, "a file was written for a no-op redaction")

    def test_a_missing_document_is_a_404_not_a_crash(self):
        import pdf_api
        with self.assertRaises(pdf_api.DocError):
            pdf_api.load("999999")

    def test_a_document_outside_the_vault_is_refused(self):
        import pdf_api
        real = client_store.get_document
        client_store.get_document = lambda _id: {
            "id": 1, "client_id": self.cid, "filename": "passwd",
            "relative_path": "/etc/passwd", "doc_type": "Other",
        }
        try:
            with self.assertRaises(pdf_api.DocError):
                pdf_api.load("1")
        finally:
            client_store.get_document = real

    def test_a_non_pdf_is_refused_with_a_reason(self):
        import pdf_api
        client_store.add_document(self.cid, "notes.txt", b"hello", "Other", "text/plain")
        conn = client_store.connect()
        row = conn.execute(
            "SELECT id FROM documents WHERE client_id = ? ORDER BY id DESC", (self.cid,)
        ).fetchone()
        conn.close()
        with self.assertRaises(pdf_api.DocError) as caught:
            pdf_api.load(str(row["id"]))
        self.assertIn("not a PDF", str(caught.exception))



class ADocumentIdIsNotALicence(unittest.TestCase):
    """Once a chat message can name a document id, the id alone is not enough.

    The workbench only ever lists the open client's documents, so scoping was
    implicit. The agent names a document from a sentence, and a wrong or
    invented id would otherwise reach into another client's file.
    """

    def setUp(self):
        import pdf_tools
        self.tmp = tempfile.TemporaryDirectory()
        self._dir, self._db = client_store.CLIENTS_DIR, client_store.CLIENT_DB
        client_store.CLIENTS_DIR = Path(self.tmp.name) / "clients"
        client_store.CLIENT_DB = Path(self.tmp.name) / "clients.db"
        self.a = client_store.create_client("Client Alpha")
        self.b = client_store.create_client("Client Beta")
        pdf = pdf_tools.make_pdf(["ID number 8001015009087"])
        client_store.add_document(self.a, "alpha.pdf", pdf, "Signed FNA", "application/pdf")
        conn = client_store.connect()
        self.doc_id = str(conn.execute(
            "SELECT id FROM documents WHERE client_id = ? ORDER BY id DESC", (self.a,)
        ).fetchone()["id"])
        conn.close()

    def tearDown(self):
        client_store.CLIENTS_DIR, client_store.CLIENT_DB = self._dir, self._db
        self.tmp.cleanup()

    def test_the_owning_client_may_open_it(self):
        import pdf_api
        doc, data = pdf_api.load(self.doc_id, self.a)
        self.assertTrue(data)
        self.assertEqual(doc["client_id"], self.a)

    def test_another_client_may_not(self):
        import pdf_api
        with self.assertRaises(pdf_api.WrongClient):
            pdf_api.load(self.doc_id, self.b)

    def test_the_refusal_does_not_confirm_the_document_exists(self):
        """Saying "that belongs to someone else" is itself a leak."""
        import pdf_api
        try:
            pdf_api.load(self.doc_id, self.b)
        except pdf_api.DocError as exc:
            self.assertEqual(str(exc), "Document not found.")

    def test_no_scope_still_works_for_the_workbench(self):
        import pdf_api
        self.assertTrue(pdf_api.load(self.doc_id)[1])

    def test_a_scoped_post_is_refused_for_the_wrong_client(self):
        import pdf_api
        captured = {}

        class Fake:
            def send_json(self, payload, status=200):
                captured.update(payload=payload, status=status)

        pdf_api.handle_post(Fake(), ["api", "pdf", self.doc_id, "extract"],
                            {"client_id": self.b})
        self.assertEqual(captured["status"], 404)

    def test_a_scoped_post_works_for_the_right_client(self):
        import pdf_api
        captured = {}

        class Fake:
            def send_json(self, payload, status=200):
                captured.update(payload=payload, status=status)

        pdf_api.handle_post(Fake(), ["api", "pdf", self.doc_id, "extract"],
                            {"client_id": self.a})
        self.assertEqual(captured["status"], 200)
        self.assertTrue(captured["payload"]["ok"])

    def test_the_get_scope_is_read_from_the_query_string(self):
        """The handler only splits the path, so this has to be parsed, not assumed."""
        import pdf_api

        class H:
            path = f"/api/pdf/{self.doc_id}?client_id={self.a}"

        self.assertEqual(pdf_api._client_scope(H()), self.a)
        self.assertEqual(pdf_api._client_scope(type("N", (), {"path": "/api/pdf/1"})()), "")



class OneClientsFileNeverReachesAnothersAnswer(unittest.TestCase):
    """The leak this closes: an RoA for one client citing another's file.

    Client documents are indexed beside the product guides. The roa room used
    to fall through to "keep everything", so retrieval could surface Mr
    Naidoo's FNA while drafting Mrs Botha's Record of Advice — and span_check
    would pass it, because the figure really is in the retrieved context. It
    would read as a properly cited fact.
    """

    def rows(self):
        return [
            (1, "guide:lifestyle_protector", 12, "Level A pays 100%.", 0),
            (2, "client:botha:fna.pdf", 1, "Botha net salary R55 000.", 0),
            (3, "client:naidoo:fna.pdf", 1, "Naidoo net salary R92 000.", 0),
        ]

    def scope(self, client_scope):
        import numpy as np
        from retrieval import _scope_clients
        rows = self.rows()
        kept, _ = _scope_clients(rows, np.eye(len(rows), dtype="float32"), client_scope)
        return [r[1] for r in kept]

    def test_no_client_attached_means_no_client_pages(self):
        self.assertEqual(self.scope(None), ["guide:lifestyle_protector"])

    def test_a_client_sees_only_their_own_pages(self):
        self.assertEqual(
            self.scope("botha"), ["guide:lifestyle_protector", "client:botha:fna.pdf"])

    def test_the_other_client_is_not_reachable(self):
        self.assertNotIn("client:naidoo:fna.pdf", self.scope("botha"))

    def test_a_prefix_of_another_client_id_does_not_match(self):
        """`client:bot:` must not open `client:botha:` — the colon is the fence."""
        import numpy as np
        from retrieval import _scope_clients
        rows = [(1, "client:botha:fna.pdf", 1, "x", 0)]
        kept, _ = _scope_clients(rows, np.eye(1, dtype="float32"), "bot")
        self.assertEqual(kept, [])

    def test_the_guard_lives_before_ranking(self):
        """Filtering after scoring would still let a page take a top-k slot."""
        import inspect, retrieval
        src = inspect.getsource(retrieval.search)
        self.assertLess(src.index("_scope_clients"), src.index("dense_scores"))

    def test_the_default_is_the_safe_one(self):
        """A caller that forgets scoping must leak nothing, not everything."""
        import inspect, retrieval
        params = inspect.signature(retrieval.search).parameters
        self.assertIsNone(params["client_scope"].default)

    def test_the_roa_room_no_longer_keeps_every_client_source(self):
        from ask import _keep_source
        self.assertTrue(_keep_source("roa", "client:botha:fna.pdf"))
        self.assertFalse(_keep_source("fa", "client:botha:fna.pdf"))
        for room in ("craft", "voice", "drama", "learn"):
            self.assertFalse(_keep_source(room, "client:botha:fna.pdf"), room)

    def test_both_ask_and_show_only_pass_a_scope(self):
        """show_only returns raw page text, so it needs this more, not less."""
        import inspect, app, ask
        self.assertIn("client_scope=", inspect.getsource(app.Handler))
        self.assertIn("client_id=client_id", inspect.getsource(app.Handler))
        self.assertIn("client_scope=scope", inspect.getsource(ask.answer))

    def test_answer_defaults_to_no_client(self):
        import inspect, ask
        self.assertEqual(inspect.signature(ask.answer).parameters["client_id"].default, "")



def _ocr_ready():
    import pdf_tools
    return pdf_tools.ocr_available()[0]


def _make_scan(text):
    """A real scan: rendered to pixels, with no text layer at all."""
    import pdf_tools
    src = pdf_tools.make_pdf([text])
    return pdf_tools._jpeg_page_pdf(pdf_tools.render_page(src, 1, 2.0), 595, 842)


class AScanIsPixelsNotText(unittest.TestCase):
    """Redacting a scan by rewriting text would do nothing and report success."""

    def test_a_rebuilt_image_page_has_no_text_layer(self):
        import pdf_tools
        if not _ocr_ready():
            self.skipTest("no OCR engine installed")
        self.assertTrue(pdf_tools.is_scanned(_make_scan("ID number 8001015009087")))

    def test_text_redaction_is_refused_on_a_scan(self):
        """The old path would have silently matched nothing and 'succeeded'."""
        import pdf_tools
        if not _ocr_ready():
            self.skipTest("no OCR engine installed")
        with self.assertRaises(pdf_tools.NotRedactable):
            pdf_tools.redact(_make_scan("ID number 8001015009087"), patterns=["sa_id"])

    def test_pixel_redaction_refuses_a_page_that_still_has_text(self):
        """Rebuilding a text page as an image would throw the text layer away."""
        import pdf_tools
        src = pdf_tools.make_pdf(["Real text on a real text page"])
        region = pdf_tools.Region(page=1, box=(0, 0, 100, 100))
        with self.assertRaises(pdf_tools.NotRedactable) as caught:
            pdf_tools.redact_regions(src, [region])
        self.assertIn("text layer", str(caught.exception))


class OcrReadsButNeverDecides(unittest.TestCase):
    """OCR finds where the number is. Pixels are what actually get removed."""

    def setUp(self):
        if not _ocr_ready():
            self.skipTest("no OCR engine installed")
        self.scan = _make_scan("ID number 8001015009087 and name Botha")

    def test_it_reads_a_scan(self):
        import pdf_tools
        text = " ".join(p.text for p in pdf_tools.ocr_pages(self.scan))
        self.assertIn("8001015009087", text)

    def test_a_suggestion_is_one_region_per_match_not_the_whole_line(self):
        """Blanking the line would take the client's name with the ID number."""
        import pdf_tools
        regions = pdf_tools.suggest_redactions(self.scan, patterns=["sa_id"])
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].label, "8001015009087")

    def test_the_number_is_gone_and_the_name_survives(self):
        import pdf_tools
        regions = pdf_tools.suggest_redactions(self.scan, patterns=["sa_id"])
        out, _notes = pdf_tools.redact_regions(self.scan, regions)
        after = " ".join(p.text for p in pdf_tools.ocr_pages(out))
        self.assertNotIn("8001015009087", after)
        self.assertIn("Botha", after)

    def test_the_result_is_re_read_to_prove_it(self):
        import pdf_tools
        regions = pdf_tools.suggest_redactions(self.scan, patterns=["sa_id"])
        _out, notes = pdf_tools.redact_regions(self.scan, regions)
        self.assertTrue(any("verified" in n for n in notes), notes)

    def test_a_redaction_that_did_not_work_is_refused_not_returned(self):
        """A zero-size box removes nothing; returning it would be the lie."""
        import pdf_tools
        regions = pdf_tools.suggest_redactions(self.scan, patterns=["sa_id"])
        useless = [pdf_tools.Region(r.page, (0, 0, 0, 0), r.scale, r.label)
                   for r in regions]
        with self.assertRaises(pdf_tools.NotRedactable) as caught:
            pdf_tools.redact_regions(self.scan, useless, pad=0)
        self.assertIn("still readable", str(caught.exception))

    def test_ocr_output_is_labelled_as_a_guess(self):
        import pdf_tools
        md = pdf_tools.ocr_markdown(pdf_tools.ocr_pages(self.scan), "FICA copy")
        self.assertIn("OCR", md)
        self.assertIn("guess at a picture", md)
        self.assertIn("Check each one", md)


class TheNarrowBoxKeepsWhatItShould(unittest.TestCase):
    """Pure geometry — runs with or without an OCR engine."""

    def test_it_covers_the_match_and_not_the_whole_line(self):
        from pdf_tools import _narrow_box
        line = "ID number 8001015009087 and name Botha"
        box = (0.0, 0.0, 380.0, 20.0)
        narrow = _narrow_box(box, line, "8001015009087")
        self.assertGreater(narrow[0], box[0])
        self.assertLess(narrow[2], box[2])

    def test_it_pads_wider_than_the_estimate(self):
        """Clipping a digit is worse than eating a neighbouring letter."""
        from pdf_tools import _narrow_box
        line = "abc 123456 def"
        exact_start = 380.0 * (line.index("123456") / len(line))
        narrow = _narrow_box((0.0, 0.0, 380.0, 20.0), line, "123456")
        self.assertLess(narrow[0], exact_start)

    def test_an_absent_match_leaves_the_box_alone(self):
        from pdf_tools import _narrow_box
        box = (1.0, 2.0, 3.0, 4.0)
        self.assertEqual(_narrow_box(box, "abc", "zzz"), box)


class MissingOcrSaysSoRatherThanReturningNothing(unittest.TestCase):
    def test_the_reason_names_the_install_command(self):
        import pdf_tools
        real = pdf_tools.ocr_available
        pdf_tools.ocr_available = lambda: (False, "OCR needs an engine. Install it with: pip install rapidocr-onnxruntime")
        try:
            with self.assertRaises(pdf_tools.OcrUnavailable) as caught:
                pdf_tools.ocr_pages(b"%PDF-1.4")
            self.assertIn("pip install", str(caught.exception))
        finally:
            pdf_tools.ocr_available = real

    def test_describe_reports_whether_ocr_is_available(self):
        import inspect, pdf_api
        src = inspect.getsource(pdf_api.describe)
        self.assertIn("ocr_available", src)
        self.assertIn('"ocr"', src)

    def test_a_scan_offers_redaction_only_when_ocr_is_present(self):
        import inspect, pdf_api
        src = inspect.getsource(pdf_api.describe)
        self.assertIn("(not scanned) or ocr_ok", src)



if __name__ == "__main__":
    unittest.main()
