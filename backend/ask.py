"""Fortitudo AI - ask. Grounded answer in the room doctrine shape."""
import argparse
import os
import sys

import store
from retrieval import search, build_context
from llm import chat, health, has_model, OllamaError
from config import CHAT_MODEL, EMBED_MODEL
from versioning import parse_as_of, query_intent, span_check
from reason import ANSWER_SHAPE, DOCTRINE, as_prompt_block, think
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
    src = str(source or "")
    if room == "fa":
        return not src.startswith(("learn:craft", "learn:voice", "learn:drama", "client:"))
    if room == "craft":
        return src.startswith(("learn:craft", "learn:all", "guide:")) or "craft" in src.lower()
    if room == "voice":
        return src.startswith(("learn:voice", "learn:all"))
    if room == "drama":
        return src.startswith(("learn:drama", "drama:"))
    return True


def answer(conn, question, history=None, client_excerpt="", room="fa"):
    route = classify(question, hinted_room=room)
    room = route.room
    lookup = rewrite_query(question, history)
    results = search(conn, lookup) or search(conn, question)
    results = [(row, score) for row, score in results if _keep_source(room, row[1])]
    if not results and not client_excerpt:
        return "Nothing indexed for this room yet. File a lesson or run ingest.", []

    as_of = parse_as_of(question)
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
    doctrine = DOCTRINE.get(room, DOCTRINE["fa"])
    think_block = ""
    if os.environ.get("FORTITUDO_THINK", "").strip() in {"1", "true", "yes"}:
        thought = think(room, question, context + "\n" + (client_excerpt or ""))
        think_block = as_prompt_block(thought) + "\n"
    user = (
        f"{doctrine}\n\n{ANSWER_SHAPE}\n\n{think_block}{prior}"
        f"Extracts (as_of={as_of}, intent={intent}):\n\n{context}\n"
        f"{client_block}"
        f"---\n\nQuestion: {question}\n\n"
        "Answer from the extracts only. Cite SOURCE and PAGE for figures. "
        "If a fact is from a client file, name the file. "
        "If the extracts do not contain the answer, say so. Do not invent."
    )
    raw = chat(expert_system(room), user)
    grounded, _missing = span_check(raw, context + "\n" + (client_excerpt or ""))
    return grounded, results


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
        for row, score in search(conn, args.show):
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
