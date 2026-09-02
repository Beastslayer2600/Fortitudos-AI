import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import type { DocType } from "./types.ts";
import type { DiskClient, DiskDocument, SyncWerkResult } from "./sync-werk-types.ts";

const FOLDER_TO_TYPE: Record<string, DocType> = {
  "01_fica": "FICA / Identity",
  fica: "FICA / Identity",
  identity: "FICA / Identity",
  "01_fica_identity": "FICA / Identity",
  rpq: "RPQ",
  "02_fna": "Signed FNA",
  fna: "Signed FNA",
  "03_advice": "Advice Report",
  advice: "Advice Report",
  "04_quotes": "Quote",
  quotes: "Quote",
  quote: "Quote",
  "05_roa": "ROA",
  roa: "ROA",
  "06_correspondence": "Correspondence",
  correspondence: "Correspondence",
  "07_other": "Other",
};

const TEXT_EXTS = new Set([".txt", ".md", ".csv", ".json"]);
const DOC_EXTS = new Set([
  ".pdf",
  ".txt",
  ".md",
  ".doc",
  ".docx",
  ".xls",
  ".xlsx",
  ".csv",
  ".jpg",
  ".jpeg",
  ".png",
]);

function guessDocType(parts: string[], filename: string): DocType {
  const hay = [...parts, filename].join(" ").toLowerCase();
  for (const [key, type] of Object.entries(FOLDER_TO_TYPE)) {
    if (hay.includes(key)) return type;
  }
  if (/\bfica\b|id[_\s-]?book|passport|proof[_\s-]?of[_\s-]?address/.test(hay))
    return "FICA / Identity";
  if (/\brpq\b|risk[_\s-]?profile/.test(hay)) return "RPQ";
  if (/\bfna\b|needs[_\s-]?analysis/.test(hay)) return "Signed FNA";
  if (/advice[_\s-]?report|recommendation/.test(hay)) return "Advice Report";
  if (/\bquote\b|quotation|premium/.test(hay)) return "Quote";
  if (/\broa\b|record[_\s-]?of[_\s-]?advice/.test(hay)) return "ROA";
  if (/email|letter|correspondence/.test(hay)) return "Correspondence";
  return "Other";
}

function contentTypeFor(ext: string) {
  switch (ext) {
    case ".pdf":
      return "application/pdf";
    case ".txt":
    case ".md":
      return "text/plain";
    case ".csv":
      return "text/csv";
    case ".json":
      return "application/json";
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".png":
      return "image/png";
    default:
      return "application/octet-stream";
  }
}

function walkClientFolder(clientRoot: string, folderName: string): DiskDocument[] {
  const out: DiskDocument[] = [];

  function walk(dir: string, relParts: string[]) {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith(".")) continue;
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full, [...relParts, entry.name]);
        continue;
      }
      if (!entry.isFile()) continue;
      const ext = extname(entry.name).toLowerCase();
      if (!DOC_EXTS.has(ext)) continue;
      let size = 0;
      try {
        size = statSync(full).size;
      } catch {
        continue;
      }
      let text = "";
      if (TEXT_EXTS.has(ext) && size < 500_000) {
        try {
          text = readFileSync(full, "utf8").slice(0, 8000);
        } catch {
          text = "";
        }
      } else if (ext === ".pdf") {
        text = `[PDF on disk] ${join(folderName, ...relParts, entry.name)}`;
      }
      out.push({
        filename: entry.name,
        relativePath: join(folderName, ...relParts, entry.name),
        docType: guessDocType(relParts, entry.name),
        contentType: contentTypeFor(ext),
        size,
        text,
      });
    }
  }

  walk(clientRoot, []);
  return out;
}

function slugHint(name: string) {
  return (
    name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 54) || "client"
  );
}

/** Server-only: scan a local FA clients root. */
export function scanWerkClients(root: string): SyncWerkResult {
  if (!existsSync(root)) {
    return {
      ok: false,
      root,
      error: `Folder not found: ${root}. Create it or set FORTITUDO_CLIENTS_DIR.`,
    };
  }

  let entries;
  try {
    entries = readdirSync(root, { withFileTypes: true });
  } catch (err) {
    return {
      ok: false,
      root,
      error: err instanceof Error ? err.message : "Cannot read client folder",
    };
  }

  const clients: DiskClient[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (entry.name.startsWith(".")) continue;
    if (entry.name.toLowerCase() === "clients") continue;
    const folder = join(root, entry.name);
    const documents = walkClientFolder(folder, entry.name);
    clients.push({
      folderName: entry.name,
      idHint: slugHint(entry.name),
      documents,
    });
  }

  clients.sort((a, b) => a.folderName.localeCompare(b.folderName));

  return {
    ok: true,
    root,
    clients,
    clientCount: clients.length,
    documentCount: clients.reduce((n, c) => n + c.documents.length, 0),
  };
}
