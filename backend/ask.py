"""
Fortitudo AI - ask

Hybrid retrieval over the page index, then a grounded answer.
Figures that are not in the extracts are stripped.
"""
import argparse
import sys

import store
from retrieval import search, build_context
from llm import chat, health, has_model, OllamaError
from config import SYSTEM_PROMPT, CHAT_MODEL, EMBED_MODEL
from versioning import parse_as_of, query_intent, span_check


def rewrite_query(question, history=None):
    parts = [question]
    if history:
        for turn in history[-6:]:
            text = str(turn.get("content", "")).strip()
            if not text:
                continue
            parts.append(text[:400])
    blob = " ".join(parts)
    return f"{question}\n{blob}"[:1500]


def answer(conn, question, history=None, client_excerpt=""):
    lookup = rewrite_query(question, history)
    results = search(conn, lookup) or search(conn, question)
    if not results and not client_excerpt:
        return "Nothing indexed yet. Run:  python ingest.py", []

    as_of = parse_as_of(question)
    intent = query_intent(question)
    context = build_context(results) if results else "(no product pages retrieved)"
    prior = ""
    if history:
        turns = []
        for turn in history[-8:]:
            role = str(turn.get("role", "user"))
            text = str(turn.get("content", "")).strip()[:900]
            if text:
                turns.append(f"{role}: {text}")
        if turns:
            prior = "Earlier in this chat (keep these pages and names live):\n" + "\n".join(turns) + "\n\n"
    client_block = ""
    if client_excerpt:
        client_block = (
            "\n\nClient-file extracts (filed documents only — not product guides):\n"
            + client_excerpt[:12000]
            + "\n"
        )
    user = (
        f"{prior}"
        f"Product-guide extracts (as_of={as_of}, intent={intent}):\n\n{context}\n"
        f"{client_block}"
        f"---\n\nAdviser's question: {question}\n\n"
        "Answer from the extracts above only. For every figure, percentage, "
        "waiting period or definition, cite SOURCE and PAGE exactly as labelled. "
        "If a fact comes from a client file, say so and name the file. "
        "If the extracts do not contain the answer, say so plainly — do not infer. "
        "Do not invent a percentage, day-count or definition. "
        "Keep continuity with earlier turns; do not drop a cited page the adviser is still using."
    )
    raw = chat(SYSTEM_PROMPT, user)
    grounded, _missing = span_check(raw, context + "\n" + (client_excerpt or ""))
    return grounded, results


def print_citations(results):
    print("\n  Sources consulted:")
    for row, score in results:
        source, page = row[1], row[2]
        print(f"    {score:6.4f}  {source}  p.{page}")
    print("\n  Verify any figure on the page before quoting it to a client.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*", help="question to ask")
    ap.add_argument("--sources", action="store_true", help="list indexed documents")
    ap.add_argument("--show", metavar="Q", help="show retrieved pages without calling the model")
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
            print(f"\nERROR: model '{needed}' not installed.")
            print(f"Installed models: {', '.join(installed) or '(none)'}")
            print(f"Run:  ollama pull {needed}\n")
            sys.exit(1)

    if args.question:
        text, results = answer(conn, " ".join(args.question))
        print(f"\n{text}\n")
        print_citations(results)
        return

    print(f"\nFortitudo AI  -  {CHAT_MODEL}  -  fully offline")
    print("Ask a product question. Ctrl+C or 'quit' to exit.\n")
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
            text, results = answer(conn, q, history=history)
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
