"""Local client records and files for Fortitudo AI.

This module deliberately keeps client data separate from the product-guide
index. Files are stored below clients/<client-id>/ and metadata in SQLite.
"""
import re
import sqlite3
import os
from datetime import datetime
from pathlib import Path

from config import ROOT, DATA_DIR, DATA_ROOT

# Keep client data outside the OneDrive project by default. Override this with
# FORTITUDO_CLIENT_DATA_DIR when the approved encrypted data location differs.
CLIENT_DATA_DIR = Path(os.environ.get("FORTITUDO_CLIENT_DATA_DIR") or DATA_ROOT)
CLIENTS_DIR = CLIENT_DATA_DIR / "clients"
CLIENT_DB = CLIENT_DATA_DIR / "clients.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    status TEXT NOT NULL DEFAULT 'Intake',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL REFERENCES clients(id),
    filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    content_type TEXT,
    size INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL REFERENCES clients(id),
    note_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL REFERENCES clients(id),
    direction TEXT NOT NULL,
    sender TEXT,
    recipient TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL REFERENCES clients(id),
    name TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_client ON documents(client_id);
CREATE INDEX IF NOT EXISTS idx_notes_client ON notes(client_id);
CREATE INDEX IF NOT EXISTS idx_emails_client ON emails(client_id);
CREATE INDEX IF NOT EXISTS idx_projections_client ON projections(client_id);
"""

FOLDERS = {
    "FICA / Identity": "01_FICA",
    "RPQ": "01_FICA",
    "Signed FNA": "02_FNA",
    "Advice Report": "03_Advice",
    "Quote": "04_Quotes",
    "ROA": "05_ROA",
    "Correspondence": "06_Correspondence",
    "Other": "07_Other",
}

# Model-written drafts live here and nowhere else. ingest.ingest_clients skips
# this folder, so a generated RoA can never come back as filed client evidence.
AI_DRAFT_FOLDER = "99_AI_Drafts"
AI_DRAFT_TYPE = "AI draft"


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    CLIENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CLIENT_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def slug(value):
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_")
    return value[:60] or "client"


def client_id(name):
    base = slug(name).lower()
    candidate = base
    suffix = 2
    conn = connect()
    while conn.execute("SELECT 1 FROM clients WHERE id = ?", (candidate,)).fetchone():
        candidate = f"{base}_{suffix}"
        suffix += 1
    conn.close()
    return candidate


def create_client(name, email="", phone="", status="Intake"):
    name = name.strip()
    if not name:
        raise ValueError("Client name is required.")
    cid = client_id(name)
    timestamp = now()
    conn = connect()
    conn.execute("INSERT INTO clients VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (cid, name, email.strip(), phone.strip(), status, timestamp, timestamp))
    conn.commit()
    conn.close()
    (CLIENTS_DIR / cid).mkdir(parents=True, exist_ok=True)
    return cid


def sync_from_disk():
    """Discover client folders on disk and add them to the database."""
    import shutil
    conn = connect()
    # Find all existing client IDs in DB
    existing_cids = {r["id"] for r in conn.execute("SELECT id FROM clients").fetchall()}
    
    # Locations to check
    search_paths = [CLIENTS_DIR]
    extra = CLIENTS_DIR / "Clients"
    if extra.exists() and extra.is_dir():
        search_paths.append(extra)
        
    for base in search_paths:
        # iterdir() might fail if directory is restricted or disappearing
        try:
            items = list(base.iterdir())
        except Exception:
            continue
            
        for path in items:
            if not path.is_dir(): continue
            if path.name == "Clients" and base == CLIENTS_DIR: continue
            
            # Use folder name as client name if not in DB
            folder_name = path.name
            cid = slug(folder_name).lower()
            if not cid: continue
            
            if cid not in existing_cids:
                # Create client record
                timestamp = now()
                conn.execute("INSERT INTO clients (id, name, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                             (cid, folder_name, "Intake", timestamp, timestamp))
                existing_cids.add(cid)
                
                # Move to standard location if necessary
                target = CLIENTS_DIR / cid
                if path.resolve() != target.resolve():
                    if not target.exists():
                        try:
                            shutil.move(str(path), str(target))
                            path = target
                        except Exception as e:
                            print(f"Failed to move {path} to {target}: {e}")
            
            # Now scan for documents in this folder (or the new target)
            existing_docs = {r["relative_path"] for r in conn.execute("SELECT relative_path FROM documents WHERE client_id = ?", (cid,)).fetchall()}
            
            for doc_file in path.rglob("*"):
                if not doc_file.is_file(): continue
                if doc_file.suffix.lower() not in {".pdf", ".txt", ".md"}: continue
                
                rel = str(doc_file.resolve())
                if rel not in existing_docs:
                    d_type = "Other"
                    if AI_DRAFT_FOLDER in doc_file.parts:
                        d_type = AI_DRAFT_TYPE
                    else:
                        for display, dirname in FOLDERS.items():
                            if dirname in doc_file.parts:
                                d_type = display
                                break
                    
                    try:
                        conn.execute("INSERT INTO documents (client_id, filename, relative_path, doc_type, size, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                     (cid, doc_file.name, rel, d_type, doc_file.stat().st_size, now()))
                    except sqlite3.Error:
                        pass
    
    conn.commit()
    conn.close()


def list_clients():
    conn = connect()
    rows = conn.execute("""
        SELECT c.*, COUNT(d.id) AS document_count
        FROM clients c LEFT JOIN documents d ON d.client_id = c.id
        GROUP BY c.id ORDER BY c.updated_at DESC, c.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_client(cid):
    conn = connect()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (cid,)).fetchone()
    if not client:
        conn.close()
        return None
    docs = conn.execute("SELECT * FROM documents WHERE client_id = ? ORDER BY created_at DESC", (cid,)).fetchall()
    notes = conn.execute("SELECT * FROM notes WHERE client_id = ? ORDER BY created_at DESC", (cid,)).fetchall()
    emails = conn.execute("SELECT * FROM emails WHERE client_id = ? ORDER BY created_at DESC", (cid,)).fetchall()
    projections = conn.execute("SELECT * FROM projections WHERE client_id = ? ORDER BY created_at DESC", (cid,)).fetchall()
    conn.close()
    result = dict(client)
    result["documents"] = [dict(r) for r in docs]
    result["notes"] = [dict(r) for r in notes]
    result["emails"] = [dict(r) for r in emails]
    result["projections"] = [dict(r) for r in projections]
    return result


def get_document(doc_id):
    conn = connect()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(doc) if doc else None


def _safe_filename(filename):
    name = Path(filename or "upload.bin").name
    name = re.sub(r"[^a-zA-Z0-9._ -]", "_", name).strip(" .")
    return name[:160] or "upload.bin"


def add_document(cid, filename, content, doc_type, content_type="application/octet-stream", folder=None):
    if not re.fullmatch(r"[a-z0-9_]+", cid) or not get_client(cid):
        raise ValueError("Client not found.")
    filename = _safe_filename(filename)
    folder = folder or FOLDERS.get(doc_type, FOLDERS["Other"])
    client_dir = (CLIENTS_DIR / cid).resolve()
    if not client_dir.exists() or not client_dir.is_dir():
        raise ValueError("Client not found.")
    target_dir = client_dir / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    if target.exists():
        stem, suffix = target.stem, target.suffix
        target = target_dir / f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"
    target.write_bytes(content)
    relative = str(target)
    conn = connect()
    conn.execute("INSERT INTO documents (client_id, filename, relative_path, doc_type, content_type, size, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (cid, filename, relative, doc_type, content_type, len(content), now()))
    conn.execute("UPDATE clients SET updated_at = ? WHERE id = ?", (now(), cid))
    conn.commit()
    conn.close()
    return relative


def add_note(cid, note_type, title, content):
    if not get_client(cid):
        raise ValueError("Client not found.")
    conn = connect()
    conn.execute("INSERT INTO notes (client_id, note_type, title, content, created_at) VALUES (?, ?, ?, ?, ?)",
                 (cid, note_type or "General", title.strip() or "Untitled note", content.strip(), now()))
    conn.execute("UPDATE clients SET updated_at = ? WHERE id = ?", (now(), cid))
    conn.commit()
    conn.close()


def add_email(cid, direction, sender, recipient, subject, body, status="Draft"):
    if not get_client(cid):
        raise ValueError("Client not found.")
    conn = connect()
    conn.execute("INSERT INTO emails (client_id, direction, sender, recipient, subject, body, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (cid, direction, sender, recipient, subject.strip(), body.strip(), status, now()))
    conn.execute("UPDATE clients SET updated_at = ? WHERE id = ?", (now(), cid))
    conn.commit()
    conn.close()


def add_projection(cid, name, inputs, summary):
    if not get_client(cid):
        raise ValueError("Client not found.")
    import json
    conn = connect()
    conn.execute("INSERT INTO projections (client_id, name, inputs_json, summary_json, created_at) VALUES (?, ?, ?, ?, ?)",
                 (cid, name.strip() or "Projection scenario", json.dumps(inputs), json.dumps(summary), now()))
    conn.execute("UPDATE clients SET updated_at = ? WHERE id = ?", (now(), cid))
    conn.commit()
    conn.close()


def add_generated_file(cid, filename, content, doc_type="Other"):
    """Save a model-written draft into the AI drafts folder.

    Deliberately not the upload path: anything filed as a real client document
    is indexed and can be cited back as evidence, and a draft the model wrote
    is not evidence of anything.
    """
    del doc_type  # a model draft is never an Advice Report, whatever asked for it
    return add_document(
        cid, filename, content.encode("utf-8"), AI_DRAFT_TYPE, "text/markdown",
        folder=AI_DRAFT_FOLDER,
    )


def meeting_prep(cid):
    client = get_client(cid)
    if not client:
        raise ValueError("Client not found.")
    doc_types = {d["doc_type"] for d in client["documents"]}
    checks = [
        ("FICA", "Confirm identity and residence verification is on file."),
        ("Signed FNA", "Confirm the signed FNA is on file."),
        ("RPQ", "Confirm the risk profile questionnaire is on file."),
        ("Advice Report", "Confirm the advice report is on file before discussing recommendations."),
        ("Quote", "Confirm current quotes and assumptions."),
    ]
    return {
        "client": client["name"],
        "agenda": ["Reconfirm objectives and material changes", "Review information supplied and limitations", "Discuss recommendations and costs", "Agree actions, owners and dates"],
        "checks": [{"item": kind, "complete": kind in doc_types, "instruction": instruction} for kind, instruction in checks],
        "documents": len(client["documents"]),
        "notes": len(client["notes"]),
    }
