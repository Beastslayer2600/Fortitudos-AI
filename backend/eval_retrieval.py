"""Quick retrieval self-check (no LLM required)."""
import store
from retrieval import search

TESTS = [
    ("hearing loss both ears 90 decibels", ["hearing", "90", "100"]),
    ("waiting period", ["wait"]),
    ("survival period", ["survival", "wait"]),
]

def main():
    conn = store.connect()
    print("Indexed sources:", store.sources(conn))
    for q, needles in TESTS:
        print(f"\nQ: {q}")
        results = search(conn, q)
        if not results:
            print("  (no results)")
            continue
        for (rid, source, page, text, _), score in results[:3]:
            hit = any(n.lower() in text.lower() for n in needles)
            mark = "OK" if hit else "??"
            print(f"  [{mark}] {score:.4f}  {source} p.{page}")

if __name__ == "__main__":
    main()
