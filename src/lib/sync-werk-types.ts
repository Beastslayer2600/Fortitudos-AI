import type { DocType } from "./types.ts";

/** Default FA client root on the adviser's Windows desk. Override with FORTITUDO_CLIENTS_DIR. */
export const DEFAULT_WERK_CLIENTS = "C:\\Werk\\Clients";

export type DiskDocument = {
  filename: string;
  relativePath: string;
  docType: DocType;
  contentType: string;
  size: number;
  text: string;
};

export type DiskClient = {
  folderName: string;
  idHint: string;
  documents: DiskDocument[];
};

export type SyncWerkResult =
  | {
      ok: true;
      root: string;
      clients: DiskClient[];
      clientCount: number;
      documentCount: number;
    }
  | { ok: false; root: string; error: string };
