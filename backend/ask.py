"""Fortitudo AI - ask — hybrid retrieval CLI."""
import argparse
import sys
import store
from retrieval import search, build_context
from llm import chat, health, has_model, OllamaError
from config import SYSTEM_PROMPT, CHAT_MODEL, EMBED_MODEL

def answer(conn, question):
    results = search(conn, question)
    if not results:
        return "Nothing indexed yet. Run:  python ingest.py", []
    context = build_context(results)
    user = (
        f"Document extracts:\n\n{context}\n\n---\n\nAdviser's question: {question}\n\n"
        "Answer from the extracts above only. Cite SOURCE and PAGE for every figure."
    )
    return chat(SYSTEM_PROMPT, user), results

def print_citations(results):
    print("\n  Sources consulted:")
    for (rid, source, page, text, _emb), score in results:
        print(f"    {score:6.4f}  {source}  p.{page}")
    print()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*")
    ap.add_argument("--sources", action="store_true")
    ap.add_argument("--show", metavar="Q")
    args = ap.parse_args()
    conn = store.connect()
    if args.sources:
        for name, count in store.sources(conn):
            print(f"  {count:>4} pages   {name}")
        return
    if args.show:
        for (rid, source, page, text, _e), score in search(conn, args.show):
            print(f"\n=== {source} p.{page}  (score {score:.4f}) ===")
            print(text[:1500])
        return
    try:
        installed = health()
    except OllamaError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    for needed in (EMBED_MODEL, CHAT_MODEL):
        if not has_model(installed, needed):
            print(f"ERROR: model '{needed}' not installed. Run: ollama pull {needed}")
            sys.exit(1)
    if args.question:
        text, results = answer(conn, " ".join(args.question))
        print(f"\n{text}\n")
        print_citations(results)
        return
    print(f"\nFortitudo AI  -  {CHAT_MODEL}")
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
        text, results = answer(conn, q)
        print(f"\n{text}\n")
        print_citations(results)

if __name__ == "__main__":
    main()
