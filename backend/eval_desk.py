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
    ]
    if args.live:
        scores.append(score_live(conn, args.verbose))
    return report(scores)


if __name__ == "__main__":
    sys.exit(main())
