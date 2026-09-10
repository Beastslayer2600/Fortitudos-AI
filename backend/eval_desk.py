"""Score the desk. `python eval_desk.py` — no Ollama needed.

Exit code is 0 only when every suite is clean, so CI fails on a regression
rather than printing a number nobody reads.

    python eval_desk.py                 # offline suites
    python eval_desk.py --verbose       # show every case
    python eval_desk.py --live          # also ask the real model (needs Ollama)
"""
from __future__ import annotations

import argparse
import sys

from eval.harness import Score, build_index, report
from eval import cases


def score_routing(verbose=False) -> Score:
    from expert_route import classify
    s = Score("routing")
    for question, expected in cases.ROUTING:
        got = classify(question).room
        s.check(got == expected, f"{question!r} → {got}, expected {expected}")
        if verbose:
            print(f"  {'ok ' if got == expected else 'FAIL'} {expected:6} {question[:60]}")
    return s


def score_retrieval(conn, top_k=4, verbose=False) -> Score:
    from retrieval import corpus_exclusions, search
    s = Score(f"retrieval@{top_k}")
    for question, source, page in cases.RETRIEVAL:
        hits = search(conn, question, top_k=top_k,
                      exclude_prefixes=corpus_exclusions("fa"))
        found = [(r[1], r[2]) for r, _ in hits]
        s.check((source, page) in found,
                f"{question!r} missed {source} p.{page} — got {found}")
        if verbose:
            mark = "ok " if (source, page) in found else "FAIL"
            print(f"  {mark} {question[:50]:52} {found}")
    return s


def score_grounding(verbose=False) -> Score:
    from versioning import span_check
    s = Score("grounding")
    for answer, context, must_go in cases.GROUNDING:
        cleaned, _ = span_check(answer, context)
        body = cleaned.split("[SPAN-CHECK]")[0]
        for figure in must_go:
            s.check(figure not in body, f"{figure!r} survived span_check")
            if verbose:
                print(f"  {'ok ' if figure not in body else 'FAIL'} drops {figure!r}")
    for answer, context, keep in cases.GROUNDED_SURVIVES:
        cleaned, _ = span_check(answer, context)
        s.check(keep in cleaned, f"{keep!r} was removed but IS in the context")
        if verbose:
            print(f"  {'ok ' if keep in cleaned else 'FAIL'} keeps {keep!r}")
    return s


def score_separation(verbose=False) -> Score:
    import mockup_router
    s = Score("craft separation")
    for brief in cases.CRAFT_REFUSALS:
        try:
            mockup_router.generate_for_lead("Shop", brief, author_html=False)
            s.check(False, f"accepted a client-file brief: {brief!r}")
        except ValueError:
            s.check(True, "")
        if verbose:
            print(f"  refuses {brief[:50]!r}")
    for brief in cases.CRAFT_ALLOWED:
        try:
            mockup_router.generate_for_lead("Shop", brief, author_html=False)
            s.check(True, "")
        except ValueError as exc:
            s.check(False, f"refused a legitimate brief {brief!r}: {exc}")
        if verbose:
            print(f"  allows  {brief[:50]!r}")
    return s


def score_gate(verbose=False) -> Score:
    from html_author import gate
    allowed = "Joe Plumbing\nKempton Park\n011 975 1234"
    s = Score("html gate")
    for html, reason in cases.GATE_REJECTS:
        verdict = gate(html, allowed)
        hit = (not verdict.ok) and any(reason in p for p in verdict.problems)
        s.check(hit, f"{reason} not caught in {html[:40]!r} → {verdict.problems}")
        if verbose:
            print(f"  {'ok ' if hit else 'FAIL'} rejects {reason}")
    return s


def score_versioning(verbose=False) -> Score:
    """Two versions of one guide must announce themselves."""
    from versioning import version_conflict, version_note
    s = Score("version conflict")
    for sources, expect in cases.VERSION_CONFLICT:
        rows = [((i, src, 1, "text", 0), 1.0) for i, src in enumerate(sources)]
        got = bool(version_conflict(rows))
        s.check(got == expect, f"{sources} → conflict={got}, expected {expect}")
        if expect:
            s.check("[VERSIONS]" in version_note(rows), f"{sources} produced no note")
        if verbose:
            print(f"  {'ok ' if got == expect else 'FAIL'} {sources}")
    return s


def score_depth(verbose=False) -> Score:
    """The reasoning pass runs where it is worth the wait."""
    import os, ask
    s = Score("reasoning depth")
    saved = os.environ.pop("FORTITUDO_THINK", None)
    try:
        for room, expect in cases.DEEP_ROOMS:
            got = ask._should_think(room)
            s.check(got == expect, f"{room} thinks={got}, expected {expect}")
            if verbose:
                print(f"  {'ok ' if got == expect else 'FAIL'} {room} deep={got}")
        os.environ["FORTITUDO_THINK"] = "1"
        s.check(all(ask._should_think(r) for r, _ in cases.DEEP_ROOMS),
                "FORTITUDO_THINK=1 did not force every room on")
        os.environ["FORTITUDO_THINK"] = "0"
        s.check(not any(ask._should_think(r) for r, _ in cases.DEEP_ROOMS),
                "FORTITUDO_THINK=0 did not force every room off")
    finally:
        os.environ.pop("FORTITUDO_THINK", None)
        if saved is not None:
            os.environ["FORTITUDO_THINK"] = saved
    return s


def score_filing(verbose=False) -> Score:
    """The filer's rails, which hold with or without a model running.

    Accuracy needs the real classifier and lives in --live. What is checked
    here is everything that decides what happens to a document once the model
    has spoken: that a label it invents cannot reach the vault, that low
    confidence parks rather than files, and that the review area is not inside
    the drop zone it is meant to rescue documents from.
    """
    import client_store, sort_engine
    s = Score("filing rails")

    labels = set(sort_engine.doc_type_labels())
    s.check(labels == set(client_store.FOLDERS), "the filer's labels drifted from FOLDERS")
    s.check(client_store.AI_DRAFT_FOLDER not in client_store.FOLDERS.values(),
            "model drafts share a folder with filed evidence")

    for _text, expected in cases.FILING:
        s.check(expected in labels, f"{expected!r} is not a label the filer can use")

    for confidence, outcome in cases.FILING_CONFIDENCE:
        files = confidence >= sort_engine.MIN_CONFIDENCE
        s.check(files == (outcome == "filed"),
                f"confidence {confidence} -> {'filed' if files else 'review'}, "
                f"expected {outcome}")
        if verbose:
            print(f"  {confidence:.2f} -> {'filed' if files else 'review'}")

    # A parked file inside the drop zone would be picked up and reprocessed
    # forever, which looks exactly like the engine working.
    s.check(not str(sort_engine.REVIEW_ZONE).startswith(str(sort_engine.DROP_ZONE) + "/"),
            "the review area is inside the drop zone")
    s.check(sort_engine.MIN_CONFIDENCE > 0.5,
            "a coin flip is enough to file a client document")
    return s


def score_governance(verbose=False) -> Score:
    """Who decides what the desk learns, and whether the register can lie.

    The single property worth evaluating: a register that keeps saying
    "approved" after the document changed is worse than no register, because
    it certifies the wrong document rather than nothing.
    """
    import os, tempfile
    from pathlib import Path as P
    import doc_register as dr

    s = Score("ingest governance")
    keep_db, keep_mode = dr.REGISTER_DB, os.environ.get("FORTITUDO_INGEST_MODE")
    with tempfile.TemporaryDirectory() as tmp:
        dr.REGISTER_DB = P(tmp) / "documents.db"
        os.environ.pop("FORTITUDO_INGEST_MODE", None)
        try:
            src = "guide.pdf"
            dr.record_ingest(src, "sha-v3", 10)
            s.check(not dr.get(src).approved, "a fresh document arrived pre-approved")
            s.check(dr.unapproved_sources(["never-seen.pdf"]) == ["never-seen.pdf"],
                    "a document the register never heard of counted as approved")

            ok, _ = dr.approve(src, "Compliance")
            s.check(ok and dr.get(src).approved, "an approval did not take")
            s.check(dr.provenance_note([((1, src, 1, "t", "h"), 0.9)]) == "",
                    "an approved document still warned the adviser")

            dr.record_ingest(src, "sha-v4", 10)          # the file was swapped
            s.check(not dr.get(src).approved,
                    "the approval survived the document changing underneath it")
            s.check(dr.get(src).lapsed, "a lapsed approval did not read as lapsed")
            s.check("[UNAPPROVED]" in dr.provenance_note([((1, src, 1, "t", "h"), 0.9)]),
                    "an answer cited a lapsed document without saying so")
            s.check([e["event"] for e in dr.history(src)].count("approved") == 1,
                    "the approval was erased instead of kept in the history")
            s.check(dr.get(src).approved_by == "Compliance",
                    "the register forgot who had approved it")

            os.environ["FORTITUDO_INGEST_MODE"] = "controlled"
            s.check(not dr.may_ingest(src, "sha-v4")[0],
                    "controlled mode indexed a document with no current approval")
            s.check(dr.may_ingest("client:x:fna.pdf", "sha")[0],
                    "controlled mode blocked a client's own file")
            os.environ["FORTITUDO_INGEST_MODE"] = "nonsense"
            s.check(dr.mode() == "open", "a typo in the mode setting stopped the desk")
            if verbose:
                print(dr.render())
        finally:
            dr.REGISTER_DB = keep_db
            os.environ.pop("FORTITUDO_INGEST_MODE", None)
            if keep_mode is not None:
                os.environ["FORTITUDO_INGEST_MODE"] = keep_mode
    return s


def score_access(verbose=False) -> Score:
    """Who the desk thinks is asking, and what that lets them do.

    The property worth evaluating is not "is there a login". It is that the
    name attached to an approval comes from the credential rather than from
    the request, because an audit trail recording a name the caller supplied
    records a claim and not a fact.
    """
    import os, tempfile
    from pathlib import Path as P
    import desk_users as du

    class H(dict):
        def get(self, k, default=None):
            return dict.get(self, k, default)

    def hdr(tok=""):
        return H({"Authorization": f"Bearer {tok}"} if tok else {})

    s = Score("access control")
    keep_db = du.USERS_DB
    saved = {k: os.environ.get(k) for k in
             ("FORTITUDO_LOCAL_ROLE", "FORTITUDO_DESK_TOKEN")}
    with tempfile.TemporaryDirectory() as tmp:
        du.USERS_DB = P(tmp) / "users.db"
        for k in saved:
            os.environ.pop(k, None)
        try:
            s.check(du.identify("127.0.0.1", hdr()) is not None,
                    "a desk with no directory stopped trusting its own keyboard")
            os.environ["FORTITUDO_DESK_TOKEN"] = "shared"
            s.check(du.identify("10.0.0.5", hdr("shared")) is not None,
                    "the shared token stopped working on a single-adviser desk")

            adviser, at = du.add("An Adviser", du.ADVISER)
            officer, ot = du.add("An Officer", du.APPROVER)
            s.check(du.identify("10.0.0.5", hdr(at)).id == adviser.id,
                    "a named user was not identified by their own token")
            s.check(du.identify("10.0.0.5", hdr("shared")) is None,
                    "the shared token still worked once a directory existed")
            s.check(du.identify("127.0.0.1", hdr()) is None,
                    "being at the keyboard was still an identity")

            s.check(du.require("10.0.0.5", hdr(at), "approve_documents")[0] is None,
                    "an adviser could approve a product document")
            s.check(du.require("10.0.0.5", hdr(ot), "approve_documents")[0] is not None,
                    "an approver could not approve a product document")
            s.check(du.require("10.0.0.5", hdr(ot), "clients")[0] is None,
                    "an approver could open a client's file")
            s.check(du.require("10.0.0.5", hdr(at), "manage_users")[0] is None,
                    "an adviser could manage users")

            du.disable(officer.id)
            s.check(du.identify("10.0.0.5", hdr(ot)) is None,
                    "a disabled user still got in")
            s.check(du.get(officer.id) is not None,
                    "disabling deleted the person their approvals point at")

            raw = P(du.USERS_DB).read_bytes()
            s.check(at.encode() not in raw, "a token was stored in the clear")

            s.check(du.capability_for(["api", "clients", "x"]) == "clients"
                    and du.capability_for(["api", "documents", "d"]) == "clients"
                    and du.capability_for(["api", "register", "approve"])
                    == "approve_documents"
                    and du.capability_for(["api", "anything"]) == "ask",
                    "a route mapped to the wrong capability")
            # Anchored on this file, not on the working directory: a relative
            # path here passes from backend/ and fails from the repo root,
            # making the check about where it was run rather than about code.
            # No second door to the client vault. An approver being refused
            # /api/clients is worth nothing if another route serves the same
            # information — three did, all written the same week as the rule.
            for route in (["api", "clients"], ["api", "clients", "x"],
                          ["api", "documents", "d1"], ["api", "pdf", "d1"],
                          ["api", "retention", "x"]):
                cap = du.capability_for(route)
                s.check(cap not in du.CAPABILITIES[du.APPROVER],
                        f"/{'/'.join(route)} is open to an approver")
            erase = du.capability_for(["api", "retention", "erase"])
            read = du.capability_for(["api", "retention", "x"])
            for role, caps in du.CAPABILITIES.items():
                if erase in caps:
                    s.check(read in caps,
                            f"{role} may erase a client but not read one")
            holders = set()
            for caps in du.CAPABILITIES.values():
                holders |= caps
            s.check(du.capability_for(["api", "ingest", "paste"]) == "documents",
                    "putting a document into the index is an ordinary question")
            s.check(all(c in holders for c in
                        (du.capability_for(["api", "pdf"]), erase, read)),
                    "a route needs a capability no role holds")

            approve = (P(__file__).resolve().parent / "desk_extra.py").read_text(
                encoding="utf-8")
            approve = approve[approve.index('["api", "register", "approve"]'):]
            approve = approve[:approve.index('["api", "register", "withdraw"]')]
            s.check('body.get("by")' not in approve and "user.name" in approve,
                    "the approver's name came from the request body")
            if verbose:
                print(du.render())
        finally:
            du.USERS_DB = keep_db
            for k, v in saved.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v
    return s


def score_retention(verbose=False) -> Score:
    """Whether an erasure reaches every place the client exists.

    The property worth evaluating: an erasure that clears the vault folder and
    the database rows looks complete and reports complete, while the page index
    can still quote the client's ID number. Everything here is aimed at the two
    places that get missed.
    """
    import tempfile
    from pathlib import Path as P
    import numpy as np
    import client_store, store, answer_log, retention

    s = Score("retention")
    saved = (client_store.CLIENT_DATA_DIR, client_store.CLIENTS_DIR,
             client_store.CLIENT_DB, store.DB_PATH, store.DATA_DIR,
             answer_log.LOG_DB, retention.ERASURE_LOG)
    with tempfile.TemporaryDirectory() as tmp:
        root = P(tmp)
        client_store.CLIENT_DATA_DIR = root
        client_store.CLIENTS_DIR = root / "clients"
        client_store.CLIENT_DB = root / "clients.db"
        store.DB_PATH = root / "index.db"
        store.DATA_DIR = root
        store.invalidate_cache()
        answer_log.LOG_DB = root / "answers.db"
        retention.ERASURE_LOG = root / "erasures.db"
        try:
            id_number = "8801015800087"
            cid = client_store.create_client("Thabo Molefe", "t@example.com", "0821112222")
            client_store.add_document(cid, "fna.pdf", b"%PDF signed", "Signed FNA")
            client_store.add_note(cid, "Meeting", "Review", "Discussed cover")
            conn = store.connect()
            store.add_page(conn, f"client:{cid}:fna.pdf", 1,
                           f"Thabo Molefe. Income R48 000. ID {id_number}.",
                           np.zeros(8, dtype="float32"))
            conn.commit()
            aid = answer_log.record(question="What cover does Thabo Molefe have?",
                                    answer="Thabo Molefe's FNA shows R2.4m.",
                                    room="roa", client_id=cid,
                                    results=[((1, f"client:{cid}:fna.pdf", 1, "t", "h"), 0.9)])

            before = retention.survey(cid)
            s.check(before.index_pages == 1,
                    "the survey did not count the pages the index learned")
            s.check(before.log_rows == 1, "the survey did not count the answer log")

            dry = retention.erase(cid, by="M. Naidoo")
            s.check(dry.dry_run and retention.survey(cid).anything,
                    "erase destroyed something without being asked to")
            s.check(retention.receipts(cid) == [], "a dry run wrote a receipt")
            s.check(retention.erase(cid, by="", dry_run=False).problems != [],
                    "an erasure was accepted with nobody's name on it")

            r = retention.erase(cid, by="M. Naidoo", reason="request", dry_run=False)
            s.check(r.complete, f"erasure reported incomplete: {r.problems}")

            conn = store.connect()
            left = conn.execute("SELECT COUNT(*) FROM pages WHERE text LIKE ?",
                                (f"%{id_number}%",)).fetchone()[0]
            s.check(left == 0, "the index can still quote the erased client")
            meta = conn.execute("SELECT COUNT(*) FROM source_meta WHERE source LIKE ?",
                                (f"client:{cid}:%",)).fetchone()[0]
            s.check(meta == 0, "the source fingerprint outlived the pages")

            row = answer_log.get(aid)
            s.check(row is not None, "the audit row was deleted rather than redacted")
            s.check(row and row["question"] == answer_log.REDACTED,
                    "the question survived the erasure")
            s.check(bool(row and row["snapshot"]),
                    "redaction threw away the retrieval snapshot")
            s.check(bool(row and row["sources"] == []),
                    "the cited client filenames survived")
            s.check(b"Thabo" not in P(answer_log.LOG_DB).read_bytes(),
                    "the client's name is still in the log file")

            got = retention.receipts(cid)
            s.check(len(got) == 1 and got[0]["complete"] == 1,
                    "no receipt was written for a completed erasure")
            s.check("Thabo" not in str(got[0]),
                    "the receipt recreated what it erased")
            if verbose:
                print(retention.render_survey(retention.survey(cid)))
        finally:
            (client_store.CLIENT_DATA_DIR, client_store.CLIENTS_DIR,
             client_store.CLIENT_DB, store.DB_PATH, store.DATA_DIR,
             answer_log.LOG_DB, retention.ERASURE_LOG) = saved
            store.invalidate_cache()
    return s


def score_fence(verbose=False) -> Score:
    """The ring-fence: does the shared code state anybody's identity?

    A one-time sweep is not a fence. The strings come back — a name in a
    default, a product in a comment — each looking like a small convenience
    rather than like the thing that contaminates the shared codebase. So this
    runs on every evaluation.
    """
    import json, os, tempfile
    from pathlib import Path as P
    import identity, fence

    s = Score("ring-fence")
    keep_file, keep_root = identity.IDENTITY_FILE, fence.ROOT
    env = {k: v for k, v in os.environ.items() if k.startswith(identity.ENV_PREFIX)}
    for k in env:
        os.environ.pop(k, None)
    with tempfile.TemporaryDirectory() as tmp:
        identity.IDENTITY_FILE = P(tmp) / "identity.json"
        identity.reset()
        try:
            # Against the real tree. Identity is per-desk and may be unset here,
            # but the employer list is fixed and always checkable.
            rep = fence.check()
            employer = [b for b in rep.breaches
                        if b.value in fence.FORBIDDEN_IN_SHARED]
            s.check(not employer, "employer material in shared code: " + "; ".join(
                f"{b.path}:{b.line} {b.value}" for b in employer[:4]))
            s.check(rep.checked > 50, "the fence barely checked anything")
            checked = {p.relative_to(fence.ROOT).as_posix()
                       for p in fence.shared_files()}
            s.check("backend/expert_route.py" in checked,
                    "the advice room is outside the fence")
            s.check("src/lib/fortitudo.ts" in checked,
                    "the frontend prompts are outside the fence")
            s.check("backend/identity.py" not in checked,
                    "the identity module is inside its own fence")

            # An unconfigured desk must claim no licence rather than a made-up
            # one, and must not be reported as a pass.
            s.check(identity.load().licence_line == "",
                    "an unconfigured desk claims a licence")
            s.check("FSP" not in identity.evidence_engine_line(),
                    "an unconfigured desk states an FSP in the advice prompt")
            s.check("not a pass" in fence.render(fence.Report()),
                    "a desk with nothing to look for was reported as clean")
            s.check("the practice" not in rep.fenced_values
                    and "the studio" not in rep.fenced_values,
                    "the fence is looking for its own generic defaults")

            # Against a synthetic tree, so the fixture is not written into the
            # real one — where the fence would rightly find it.
            root = P(tmp) / "repo" / "backend"
            root.mkdir(parents=True)
            (root / "thing.py").write_text('A = "Nomsa Dlamini"\n', encoding="utf-8")
            P(identity.IDENTITY_FILE).write_text(
                json.dumps({"adviser_name": "Nomsa Dlamini"}), encoding="utf-8")
            identity.reset()
            fence.ROOT = P(tmp) / "repo"
            caught = fence.check()
            s.check(not caught.ok and caught.breaches[0].value == "Nomsa Dlamini",
                    "the fence did not catch a configured name in shared code")
            s.check(caught.breaches[0].line == 1,
                    "the fence did not report the line to look at")
            if verbose:
                print(fence.render(rep))
        finally:
            identity.IDENTITY_FILE, fence.ROOT = keep_file, keep_root
            identity.reset()
            os.environ.update(env)
    return s


def score_residency(verbose=False) -> Score:
    """Can the desk still say, truthfully, that the data is on this machine?

    A residency claim decays: someone adds a font, a map tile, an analytics
    beacon, and the claim quietly stops being true while the document still
    says it is. This reads the configuration and the source rather than a list
    somebody maintains, so it is current or it fails.
    """
    import tempfile
    from pathlib import Path as P
    import residency as res

    s = Score("data residency")
    found, root = res.stores()
    by_name = {st.name: st for st in found}

    for name in ("client vault", "client records", "answer log",
                 "user directory", "product index", "drop zone"):
        s.check(name in by_name, f"the residency report does not know about {name}")

    s.check(by_name["product index"].holds_personal_data,
            "the index is not treated as personal data — it holds the extracted "
            "text of client documents")
    s.check(not by_name["product documents"].holds_personal_data,
            "product guides are being counted as personal data")

    for hop in res.hops():
        if hop.job == "craft":
            continue                       # the one job allowed out, by design
        s.check(hop.local, f"{hop.job} resolves to {hop.host}, not this machine")

    unknown = [e.host for e in res.external() if not e.classified]
    s.check(not unknown, "unclassified external host(s): " + ", ".join(unknown[:4]))

    by_host = {e.host: e for e in res.external()}
    s.check(by_host.get("api.qrserver.com") is not None
            and by_host["api.qrserver.com"].who_calls == res.FETCHED_BY_THE_DESK,
            "the QR service is no longer reported as something the desk calls")

    with tempfile.TemporaryDirectory() as tmp:
        # Assembled at runtime. A literal external URL written here would be
        # found by the very scan this is testing — eval_desk.py is source the
        # scanner reads — and the fixture would report itself as a finding.
        host = "analytics." + "somebody" + ".net"
        beacon = P(tmp) / "beacon.py"
        beacon.write_text(f'U = "https://{host}/x"\n', encoding="utf-8")
        caught = res.external([beacon])
        s.check([e.host for e in caught] == [host] and not caught[0].classified,
                "a new external host was not caught")
        quiet = P(tmp) / "local.py"
        quiet.write_text('H = "http://127.0.0.1:11434"\n', encoding="utf-8")
        s.check(res.external([quiet]) == [],
                "a local host was reported as egress")

    s.check("does not check that the disk is encrypted" in res.render(),
            "the report no longer admits what it cannot check")

    # The scan must cover the whole desk. Reading the backend only is how the
    # first version reported clean while the frontend held a path to a hosted
    # model and a platform sign-in layer.
    scanned = {p.as_posix() for p in res.scanned_files()}
    s.check(any("/src/lib/" in p for p in scanned),
            "the residency scan does not read the frontend")
    s.check(not any("node_modules" in p for p in scanned),
            "the residency scan is reading node_modules")

    off = {e.host for e in res.check().can_leave_the_machine}
    s.check("api.x.ai" in off,
            "the opt-in hosted model is no longer reported")
    s.check("Off by configuration, which is not the same as absent"
            in res.render(),
            "things that are merely switched off stopped being listed")

    llm = P(res.ROOT) / "src" / "lib" / "llm.ts"
    if llm.exists():
        auto = llm.read_text(encoding="utf-8")
        auto = auto[auto.index("// auto is local"):]
        s.check("callXai" not in auto,
                "the local model path falls back to the hosted one again")
    if verbose:
        print(res.render())
    return s


def score_backup(verbose=False) -> Score:
    """The properties that separate a backup from a hope."""
    import sqlite3, tempfile
    from pathlib import Path as P
    import vault_backup as vb

    s = Score("backup")
    with tempfile.TemporaryDirectory() as tmp:
        root = P(tmp)
        vault, arch = root / "vault", root / "archive"
        (vault / "clients" / "botha").mkdir(parents=True)
        (vault / "clients" / "botha" / "fna.pdf").write_bytes(b"%PDF signed")
        conn = sqlite3.connect(vault / "clients.db")
        conn.execute("CREATE TABLE c (id TEXT)")
        conn.execute("INSERT INTO c VALUES ('botha')")
        conn.commit()                      # left open, as the desk leaves it

        first = vb.back_up(vault, arch).id
        s.check(vb.verify(arch).ok, "a fresh backup did not verify")

        out = root / "restored"
        vb.restore(arch, out)
        s.check((out / "clients" / "botha" / "fna.pdf").read_bytes() == b"%PDF signed",
                "a restored file did not match")
        rdb = sqlite3.connect(out / "clients.db")
        s.check(rdb.execute("SELECT id FROM c").fetchall() == [("botha",)],
                "a live database did not survive the round trip")
        rdb.close()
        conn.close()

        # Immutability: a deletion must not reach the archive.
        (vault / "clients" / "botha" / "fna.pdf").unlink()
        vb.back_up(vault, arch)
        old_dir = root / "old"
        vb.restore(arch, old_dir, snapshot_id=first)
        s.check((old_dir / "clients" / "botha" / "fna.pdf").exists(),
                "a deleted file was not recoverable from an older snapshot")

        # Same-second runs must not overwrite each other.
        ids = {vb.back_up(vault, arch).id for _ in range(3)}
        s.check(len(ids) == 3, "backups in the same second collided")
        s.check(vb.snapshots(arch)[-1].id == max(ids, key=vb._order_key),
                "the newest snapshot did not sort last")

        # Corruption must be caught rather than restored.
        obj = next(p for p in (arch / "objects").rglob("*") if p.is_file())
        obj.write_bytes(b"rot")
        # Archive-wide: the rotted object is held only by an older snapshot,
        # which is precisely the case verifying the newest one misses.
        s.check(not vb.verify_archive(arch).ok, "corruption was not detected")
        try:
            vb.restore(arch, root / "bad", snapshot_id=first)
            s.check(False, "a corrupt object was restored")
        except vb.BackupError:
            s.check(True, "")
        if verbose:
            print(f"  snapshots: {[x.id for x in vb.snapshots(arch)]}")
    return s


def score_client_scope(verbose=False) -> Score:
    """No answer for one client may be built from another client's file."""
    import numpy as np
    from retrieval import _scope_clients
    from ask import _keep_source
    s = Score("client scope")
    for scope, source, allowed in cases.CLIENT_SCOPE:
        rows = [(1, source, 1, "text", 0)]
        kept, _ = _scope_clients(rows, np.eye(1, dtype="float32"), scope)
        got = bool(kept)
        s.check(got == allowed, f"scope={scope!r} {source} -> {got}, expected {allowed}")
        if verbose:
            print(f"  {'ok ' if got == allowed else 'FAIL'} {scope!r:10} {source}")
    # Through search() itself, not just the filter — a guard that exists but is
    # not wired in is the failure mode this whole suite is for.
    conn = build_index()
    from retrieval import search
    for scope, forbidden in [("botha", "client:naidoo:fna.pdf"),
                             ("naidoo", "client:botha:fna.pdf"),
                             (None, "client:botha:fna.pdf")]:
        hits = search(conn, "net salary monthly waiting period", top_k=8,
                      client_scope=scope)
        sources = {r[1] for r, _ in hits}
        s.check(forbidden not in sources,
                f"search(client_scope={scope!r}) returned {forbidden}")
        if verbose:
            print(f"  scope={scope!r:8} -> {sorted(sources)}")
    own = {r[1] for r, _ in search(conn, "net salary monthly", top_k=8,
                                   client_scope="botha")}
    s.check("client:botha:fna.pdf" in own, "a client cannot reach their own file")

    for room, allowed in cases.CLIENT_ROOMS:
        got = _keep_source(room, "client:botha:fna.pdf")
        s.check(got == allowed, f"{room} keeps a client file -> {got}, expected {allowed}")
    return s


def score_pdf(verbose=False) -> Score:
    """A redaction that only looks done is the failure worth catching."""
    import pdf_tools
    s = Score("pdf")
    for text, patterns, gone, kept in cases.REDACTION:
        src = pdf_tools.make_pdf([text])
        out, removed = pdf_tools.redact(src, patterns=patterns)
        body = " ".join(p.text for p in pdf_tools.read_pages(out))
        s.check(gone not in body, f"{gone} survived extraction")
        # The stronger check: gone from the file, not merely from the render.
        s.check(gone.encode() not in out, f"{gone} still in the raw bytes")
        s.check(kept in body, f"{kept} was destroyed by the redaction")
        s.check(bool(removed), f"{patterns} reported nothing removed")
        if verbose:
            print(f"  redact {patterns} -> removed {removed}")

    four = pdf_tools.make_pdf(["a", "b", "c", "d"])
    for spec, expected in cases.PAGE_SPECS:
        got = pdf_tools.page_count(pdf_tools.select_pages(four, spec))
        s.check(got == expected, f"select {spec!r} -> {got} pages, expected {expected}")
        if verbose:
            print(f"  select {spec!r} -> {got}")

    # A scan cannot be redacted, and saying so is the whole point.
    try:
        pdf_tools.redact(pdf_tools.make_pdf([""]), patterns=["sa_id"])
        s.check(False, "a scan was redacted instead of refused")
    except pdf_tools.NotRedactable:
        s.check(True, "")

    # Stamping must not destroy what it marks.
    stamped = pdf_tools.stamp(pdf_tools.make_pdf(["Original body"]), "DRAFT")
    body = " ".join(p.text for p in pdf_tools.read_pages(stamped))
    s.check("DRAFT" in body and "Original body" in body, "stamp lost the page content")
    return s


def score_filing_live(verbose=False) -> Score:
    """Does the classifier actually get documents right? Needs Ollama.

    This is the number that says whether auto-filing is safe to leave on. A
    wrong answer here files a client document under the wrong person, and
    nobody finds out until it is needed.
    """
    import client_store, sort_engine
    s = Score("live filing")
    engine = sort_engine.SortEngine()
    real = client_store.list_clients
    client_store.list_clients = lambda: [
        {"id": "botha", "name": "Mrs A Botha"},
        {"id": "naidoo", "name": "Mr S Naidoo"},
    ]
    try:
        for text, expected in cases.FILING:
            result = engine._classify(text, "document.pdf")
            if not result:
                s.check(False, f"no answer for {expected}")
                continue
            got = result.get("doc_type")
            confidence = float(result.get("confidence") or 0)
            s.check(got == expected,
                    f"{text[:40]!r} -> {got!r} at {confidence:.0%}, expected {expected!r}")
            # Confidently wrong is the dangerous state, not wrong.
            if got != expected and confidence >= sort_engine.MIN_CONFIDENCE:
                s.check(False, f"CONFIDENTLY WRONG: {got!r} at {confidence:.0%} "
                               f"would have been filed as {expected!r}")
            if verbose:
                mark = "ok " if got == expected else "FAIL"
                print(f"  {mark} {expected:16} got {str(got):16} {confidence:.0%}")
    finally:
        client_store.list_clients = real
    return s


def score_live(conn, verbose=False) -> Score:
    """Ask the real model. Only meaningful with Ollama running."""
    from ask import answer
    s = Score("live answers")
    for question, source, page in cases.RETRIEVAL[:4]:
        try:
            text, results = answer(conn, question, room="fa")
        except Exception as exc:
            s.check(False, f"{question!r} raised {exc}")
            continue
        cited = source.split(":")[-1].lower() in text.lower() or str(page) in text
        s.check(cited, f"{question!r} answered without citing {source} p.{page}")
        if verbose:
            print(f"  {'ok ' if cited else 'FAIL'} {question[:40]:42} {text[:70]!r}")
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also ask the real model")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--top-k", type=int, default=4)
    args = ap.parse_args()

    conn = build_index()
    scores = [
        score_routing(args.verbose),
        score_retrieval(conn, args.top_k, args.verbose),
        score_grounding(args.verbose),
        score_separation(args.verbose),
        score_gate(args.verbose),
        score_versioning(args.verbose),
        score_depth(args.verbose),
        score_pdf(args.verbose),
        score_client_scope(args.verbose),
        score_backup(args.verbose),
        score_filing(args.verbose),
        score_governance(args.verbose),
        score_access(args.verbose),
        score_retention(args.verbose),
        score_fence(args.verbose),
        score_residency(args.verbose),
    ]
    if args.live:
        scores.append(score_live(conn, args.verbose))
        scores.append(score_filing_live(args.verbose))
    return report(scores)


if __name__ == "__main__":
    sys.exit(main())
