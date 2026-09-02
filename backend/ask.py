"""Fortitudo AI - ask. Grounded answer in the room doctrine shape."""
import argparse
import os
import sys

import store
from retrieval import search, build_context, corpus_exclusions
from llm import chat, health, has_model, OllamaError
from config import CHAT_MODEL, EMBED_MODEL
from versioning import parse_as_of, query_intent, span_check, version_note
from reason import ANSWER_SHAPE, as_prompt_block, think
from rooms import get_room
from expert_route import classify, expert_system


def rewrite_query(question, history=None):
    parts = [question]
    if history:
        for turn in history[-6:]:
            text = str(turn.get("content", "")).strip()
            if text:
                parts.append(text[:400])
    return f"{question}\n{' '.join(parts)}"[:1500]


def _keep_source(room: str, source: str) -> bool:
    """The shelves a room may quote, on top of corpus_exclusions.

    corpus_exclusions drops machine-written sources before ranking so the good
    pages win the top-k slots; this narrows what is left to the room's own
    shelf.
    """
    src = str(source or "")
    # Cross-client scoping is enforced in retrieval.search(client_scope=...),
    # before ranking. This is the second layer: the roa room used to fall
    # through to `return True` here, which let a Record of Advice for one
    # client cite a page out of another client's file.
    if src.startswith("client:"):
        return room in ("roa",)
    if room == "fa":
        return not src.startswith(("learn:craft", "learn:voice", "learn:drama", "client:"))
    if room == "craft":
        return src.startswith(("learn:craft", "learn:all", "guide:")) or "craft" in src.lower()
    if room == "voice":
        return src.startswith(("learn:voice", "learn:all"))
    if room == "drama":
        return src.startswith(("learn:drama", "drama:"))
    return True


def answer(conn, question, history=None, client_excerpt="", room="", client_id=""):
    """Answer in one room, under that room's corpus rules.

    An empty `room` is classified from the question; a caller that has already
    routed (app.py) passes the room it decided on and it is honoured as-is.
    rooms.py then decides what that room may read: whether the product index is
    in scope at all, and whether filed client documents may be quoted. Passing
    an excerpt to a room that is not client-aware does not make it one.
    """
    room = (room or classify(question).room).lower()
    spec = get_room(room)
    if not spec.include_clients:
        client_excerpt = ""

    as_of = parse_as_of(question)
    results = []
    if spec.allow_product_index:
        lookup = rewrite_query(question, history)
        drop = corpus_exclusions(room)
        # The client this answer is FOR. Without it every client page is
        # dropped, so a caller that forgets cannot cite someone else's file.
        scope = client_id if (client_id and spec.include_clients) else None
        results = (search(conn, lookup, as_of=as_of, exclude_prefixes=drop,
                          client_scope=scope)
                   or search(conn, question, as_of=as_of, exclude_prefixes=drop,
                             client_scope=scope))
        results = [(row, score) for row, score in results if _keep_source(room, row[1])]
    if not results and not client_excerpt:
        if not spec.allow_product_index:
            return f"The {room} room does not answer from the product index.", []
        return "Nothing indexed for this room yet. File a lesson or run ingest.", []

    intent = query_intent(question)
    context = build_context(results) if results else "(no pages retrieved)"
    prior = ""
    if history:
        turns = []
        for turn in history[-8:]:
            role = str(turn.get("role", "user"))
            text = str(turn.get("content", "")).strip()[:900]
            if text:
                turns.append(f"{role}: {text}")
        if turns:
            prior = "Earlier in this chat:\n" + "\n".join(turns) + "\n\n"
    client_block = ""
    if client_excerpt and room in {"fa", "roa"}:
        client_block = (
            "\n\nClient-file extracts (filed documents only):\n"
            + client_excerpt[:12000]
            + "\n"
        )
    # Depth by room. Advisor and RoA carry compliance weight and are worth a
    # second model call; Craft, Voice, Drama and Learn answer in one pass so the
    # desk stays usable on a CPU. FORTITUDO_THINK forces it on or off everywhere.
    think_block = ""
    thought = None
    if _should_think(room):
        thought = think(room, question, context + "\n" + (client_excerpt or ""))
        think_block = as_prompt_block(thought) + "\n"
    user = (
        f"{ANSWER_SHAPE}\n\n{think_block}{prior}"
        f"Extracts (as_of={as_of}, intent={intent}):\n\n{context}\n"
        f"{client_block}"
        f"---\n\nQuestion: {question}\n\n"
        "Answer from the extracts only. Cite SOURCE and PAGE for figures. "
        "If a fact is from a client file, name the file. "
        "If the extracts do not contain the answer, say so. Do not invent."
    )
    # The room's own standard, doctrine and refusal — not one desk-wide prompt.
    raw = chat(expert_system(room), user, job=room)
    grounded, _missing = span_check(raw, context + "\n" + (client_excerpt or ""))

    # Two versions of one guide in the extracts means a figure could come from
    # either. Say so rather than let a real citation vouch for the wrong number.
    grounded += version_note(results)

    # The reasoning pass rates its own risk of inventing. A high rating is worth
    # the adviser's attention precisely because the answer will not look wrong.
    if thought is not None and getattr(thought, "invent_risk", "low") == "high":
        grounded += (
            "\n\n[RISK] The desk rated this answer a high risk of invention — "
            "the evidence was thin for what was asked. Treat every figure as "
            "unconfirmed until you have opened the cited page."
        )

    if spec.draft_banner and not grounded.lstrip().startswith(spec.draft_banner.strip()):
        grounded = spec.draft_banner + grounded
    return grounded, results


# Rooms whose answers become evidence in a regulated file. Craft, Voice, Drama
# and Learn produce drafts a human reads and edits; these two produce the
# reasoning behind advice, so they get the slower, better path.
DEEP_ROOMS = ("fa", "roa")


def _should_think(room: str) -> bool:
    forced = os.environ.get("FORTITUDO_THINK", "").strip().lower()
    if forced in {"1", "true", "yes", "on", "all"}:
        return True
    if forced in {"0", "false", "no", "off"}:
        return False
    return room in DEEP_ROOMS


def print_citations(results):
    print("\n  Sources consulted:")
    for row, score in results:
        print(f"    {score:6.4f}  {row[1]}  p.{row[2]}")
    print("\n  Verify any figure on the page before quoting it to a client.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*")
    ap.add_argument("--sources", action="store_true")
    ap.add_argument("--show", metavar="Q")
    ap.add_argument("--room", default="")
    args = ap.parse_args()
    conn = store.connect()
    if args.sources:
        docs = store.sources(conn)
        if not docs:
            print("\nNothing indexed. Run:  python ingest.py\n")
            return
        print("\nIndexed documents:")
        for name, count in docs:
            print(f"  {count:>4} pages   {name}")
        print()
        return
    if args.show:
        for row, score in search(conn, args.show,
                                 exclude_prefixes=corpus_exclusions(args.room)):
            print(f"\n=== {row[1]} p.{row[2]}  (score {score:.4f}) ===")
            print(row[3][:1500])
        print()
        return
    try:
        installed = health()
    except OllamaError as e:
        print(f"\nERROR: {e}\n")
        sys.exit(1)
    for needed in (EMBED_MODEL, CHAT_MODEL):
        if not has_model(installed, needed):
            print(f"\nERROR: model '{needed}' not installed. Run:  ollama pull {needed}\n")
            sys.exit(1)
    if args.question:
        text, results = answer(conn, " ".join(args.question), room=args.room)
        print(f"\n{text}\n")
        print_citations(results)
        return
    print(f"\nFortitudo AI  -  {CHAT_MODEL}  -  fully offline")
    history = []
    while True:
        try:
            q = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if q.lower() in {"quit", "exit", "q"}:
            return
        if not q:
            continue
        try:
            text, results = answer(conn, q, history=history, room=args.room)
            print(f"\n{text}\n")
            print_citations(results)
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": text})
        except OllamaError as e:
            print(f"\nERROR: {e}\n")
        except Exception as e:
            print(f"\nERROR: {e}\n")


if __name__ == "__main__":
    main()
