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
    ]
    if args.live:
        scores.append(score_live(conn, args.verbose))
    return report(scores)


if __name__ == "__main__":
    sys.exit(main())
