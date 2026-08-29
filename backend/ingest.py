"""
Fortitudo AI - ingest

Reads PDFs/text in docs/, extracts each page (text + tables as pipe-delimited
rows), embeds it, and stores it in data/index.db.

Default mode is INCREMENTAL: only new or changed files are processed.
Unchanged files are skipped using stored mtime + size fingerprints.

Usage:
    python ingest.py                 # update only new/changed files
    python ingest.py --file "x.pdf"  # one file (still skips if unchanged)
    python ingest.py --clients       # also index client vault documents
    python ingest.py --rebuild       # full wipe + re-embed everything
                                      (only when embed model or embed format changes)
"""
import argparse
import sys
from pathlib import Path
from typing import List, Tuple, Generator, Optional, Any
import sqlite3

try:
    import pdfplumber
except Exception:  # a broken install counts too; TXT and MD still ingest.
    pdfplumber = None

import store
from llm import embed, health, has_model, OllamaError
from config import DOCS_DIR, EMBED_MODEL, MIN_PAGE_CHARS


def table_to_text(table: List[List[Optional[str]]]) -> str:
    """Render an extracted table as pipe-delimited rows."""
    lines = []
    for row in table:
        cells = [(c or "").replace("\n", " ").strip() for c in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_pages(pdf_path: Path) -> Generator[Tuple[int, str], None, None]:
    if pdfplumber is None:
        raise RuntimeError(
            "Reading PDFs needs pdfplumber. Run: pip install -r backend/requirements.txt"
        )
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            parts = []
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
            try:
                for table in page.extract_tables():
                    rendered = table_to_text(table)
                    if rendered:
                        parts.append("[TABLE]\n" + rendered)
            except Exception:
                pass
            combined = "\n\n".join(parts).strip()
            if len(combined) >= MIN_PAGE_CHARS:
                yield i, combined


MAX_SECTION_CHARS = 12000


def extract_text_pages(path: Path) -> Generator[Tuple[int, str], None, None]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    for i, chunk in enumerate(raw.split("\n\n"), start=1):
        chunk = chunk.strip()
        if len(chunk) < MIN_PAGE_CHARS:
            continue
        if len(chunk) <= MAX_SECTION_CHARS:
            yield i, chunk
            continue
        buf, size = [], 0
        for para in chunk.split("\n"):
            if size + len(para) > MAX_SECTION_CHARS and buf:
                yield i, "\n".join(buf)
                buf, size = [], 0
            buf.append(para)
            size += len(para) + 1
        if buf:
            yield i, "\n".join(buf)


def extract_any(path: Path) -> Generator[Tuple[int, str], None, None]:
    if path.suffix.lower() == ".pdf":
        return extract_pages(path)
    return extract_text_pages(path)


def _file_fingerprint(path: Path) -> Tuple[float, int]:
    st = path.stat()
    return float(st.st_mtime), int(st.st_size)


def needs_ingest(conn: sqlite3.Connection, path: Path, source: str, rebuild: bool) -> bool:
    """True only when the file is new, changed, or --rebuild was requested."""
    if rebuild:
        return True

    mtime, size = _file_fingerprint(path)
    meta = store.get_source_meta(conn, source)

    if meta:
        stored_mtime, stored_size, _pages = meta
        # Filesystem mtime can jitter slightly on copy/sync
        if abs(mtime - stored_mtime) <= 1.5 and size == stored_size:
            return False
        return True

    # No fingerprint yet (legacy index or first run after upgrade).
    existing = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE source = ?", (source,)
    ).fetchone()[0]
    if existing > 0:
        # Already indexed under the old scheme: adopt current fingerprint
        # WITHOUT re-embedding so day-to-day updates stay fast.
        store.set_source_meta(conn, source, mtime, size, existing)
        conn.commit()
        return False

    return True  # brand-new file


def ingest_file(
    conn: sqlite3.Connection,
    path: Path,
    rebuild: bool = False,
    source_name: str = None,
) -> int:
    source = source_name or path.name

    if not needs_ingest(conn, path, source, rebuild):
        existing = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE source = ?", (source,)
        ).fetchone()[0]
        print(f"  skip   {source}  ({existing} pages, unchanged)")
        return 0

    existing = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE source = ?", (source,)
    ).fetchone()[0]
    if existing:
        store.clear_source(conn, source)
        print(f"  update {source}  (was {existing} pages)")

    print(f"  read   {source} ...", end="", flush=True)
    try:
        pages = list(extract_any(path))
    except Exception as e:
        print(f" FAILED: {e}")
        return 0
    print(f" {len(pages)} pages with content")

    if not pages:
        print(f"  WARN   {source} produced no extractable text.")
        print("         If it is a scanned document it needs OCR first.")
        return 0

    batch_size = 16
    done = 0
    bar_width = 20
    for start in range(0, len(pages), batch_size):
        batch = pages[start:start + batch_size]
        embed_inputs = [
            f"Document: {source}\nPage: {page_no}\n\n{text}"
            for page_no, text in batch
        ]
        vectors = embed(embed_inputs)
        for (page_no, text), vec in zip(batch, vectors):
            store.add_page(conn, source, page_no, text, vec)
        conn.commit()
        done += len(batch)
        filled = int(bar_width * done / len(pages))
        bar = "=" * filled + "-" * (bar_width - filled)
        print(f"\r  embed  {source}  [{bar}] {done}/{len(pages)}", end="", flush=True)

    mtime, size = _file_fingerprint(path)
    store.set_source_meta(conn, source, mtime, size, len(pages))
    conn.commit()
    store.invalidate_cache()
    print()
    return len(pages)


def prune_missing(conn: sqlite3.Connection, live_sources: set) -> int:
    """Remove index rows for files that no longer exist on disk."""
    indexed = [name for name, _ in store.sources(conn)]
    removed = 0
    for name in indexed:
        if name.startswith("client:"):
            continue  # client prune is separate
        if name not in live_sources:
            store.clear_source(conn, name)
            print(f"  prune  {name}  (file gone)")
            removed += 1
    if removed:
        store.invalidate_cache()
    return removed


def ingest_clients(conn: sqlite3.Connection, rebuild: bool = False) -> int:
    import client_store

    total = 0
    clients = client_store.list_clients()
    print(f"\nScanning {len(clients)} clients for documents...\n")

    for client in clients:
        cid = client["id"]
        client_dir = client_store.CLIENTS_DIR / cid
        if not client_dir.exists():
            continue
        for doc_file in client_dir.rglob("*"):
            # A draft the model wrote is not evidence; indexing it would let the
            # next answer cite it back as if the adviser had filed it.
            if client_store.AI_DRAFT_FOLDER in doc_file.parts:
                continue
            if doc_file.is_file() and doc_file.suffix.lower() in {".pdf", ".txt", ".md"}:
                source_name = f"client:{cid}:{doc_file.name}"
                total += ingest_file(conn, doc_file, rebuild=rebuild, source_name=source_name)
    return total


def main():
    ap = argparse.ArgumentParser(
        description="Index product docs into the local Fortitudo database (incremental by default)."
    )
    ap.add_argument(
        "--rebuild",
        action="store_true",
        help="Wipe and re-embed ALL sources. Only needed after changing EMBED_MODEL or embed input format.",
    )
    ap.add_argument("--file", help="Ingest a single filename from docs/ (skips if unchanged)")
    ap.add_argument("--clients", action="store_true", help="Also index client vault documents")
    ap.add_argument(
        "--prune",
        action="store_true",
        default=True,
        help="Remove index entries for files deleted from docs/ (default: on)",
    )
    ap.add_argument("--no-prune", action="store_true", help="Do not remove deleted sources from the index")
    args = ap.parse_args()
    do_prune = args.prune and not args.no_prune and not args.file

    try:
        installed = health()
    except OllamaError as e:
        print(f"\nERROR: {e}\n")
        sys.exit(1)

    if not has_model(installed, EMBED_MODEL):
        print(f"\nERROR: embedding model '{EMBED_MODEL}' is not installed.")
        print(f"Run:  ollama pull {EMBED_MODEL}\n")
        print(f"Installed models: {', '.join(installed) or '(none)'}\n")
        sys.exit(1)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    if args.file:
        targets = [DOCS_DIR / args.file]
        if not targets[0].exists():
            print(f"Not found: {targets[0]}")
            sys.exit(1)
    else:
        targets = sorted(
            list(DOCS_DIR.glob("*.pdf"))
            + list(DOCS_DIR.glob("*.txt"))
            + list(DOCS_DIR.glob("*.md"))
        )

    if not targets and not args.clients:
        print(f"\nNo documents found in {DOCS_DIR}")
        print("Drop your product guides in there and run this again.\n")
        return

    targets = [t for t in targets if t.name.lower() not in {"readme.txt", "knowledge_index.md"}]

    conn = store.connect()
    mode = "FULL REBUILD" if args.rebuild else "incremental (new/changed only)"
    print(f"\nIngesting into {store.DB_PATH}")
    print(f"Mode: {mode}\n")

    total = 0
    skipped_note = 0

    if args.clients:
        total += ingest_clients(conn, rebuild=args.rebuild)

    live = set()
    for pdf in targets:
        live.add(pdf.name)
        try:
            n = ingest_file(conn, pdf, rebuild=args.rebuild)
            total += n
            if n == 0:
                skipped_note += 1
        except Exception as e:
            print(f"\n  ERROR on {pdf.name}: {e}")

    pruned = 0
    if do_prune and not args.rebuild:
        pruned = prune_missing(conn, live)

    print(f"\nDone. {total} pages embedded this run.")
    if skipped_note and total == 0:
        print("All listed sources were already up to date — nothing to embed.")
    if pruned:
        print(f"Pruned {pruned} removed source(s) from the index.")
    print("\nIndexed documents:")
    for name, count in store.sources(conn):
        print(f"  {count:>4} pages   {name}")
    print("\nTip: day-to-day, just run  python ingest.py")
    print("     Use --rebuild only after changing the embedding model.\n")


if __name__ == "__main__":
    main()
