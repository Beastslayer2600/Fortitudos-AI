import type { DiskClient } from "./sync-werk-types";
import type { Client, ClientDocument, ClientStatus } from "./types";
import { nowIso, slug } from "./utils";

function uid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

export type MergeDiskResult = {
  clients: Client[];
  documents: ClientDocument[];
  addedClients: number;
  addedDocuments: number;
  updatedClients: number;
};

/**
 * Merge disk folders into existing in-browser records.
 * - Matching is by client id (slug of folder name) or exact name (case-insensitive).
 * - Documents are keyed by clientId + filename; existing filenames are skipped.
 * - Demo seed clients are kept; disk clients are appended/updated.
 */
export function mergeDiskClients(
  existingClients: Client[],
  existingDocuments: ClientDocument[],
  diskClients: DiskClient[],
): MergeDiskResult {
  const clients = [...existingClients];
  const documents = [...existingDocuments];
  let addedClients = 0;
  let addedDocuments = 0;
  let updatedClients = 0;
  const stamp = nowIso();

  for (const disk of diskClients) {
    const name = disk.folderName.trim();
    if (!name) continue;

    let client =
      clients.find((c) => c.id === disk.idHint) ||
      clients.find((c) => c.name.toLowerCase() === name.toLowerCase());

    if (!client) {
      let id = disk.idHint || slug(name);
      const taken = new Set(clients.map((c) => c.id));
      let n = 2;
      while (taken.has(id)) {
        id = `${disk.idHint}_${n}`;
        n += 1;
      }
      client = {
        id,
        name,
        email: "",
        phone: "",
        status: "Intake" as ClientStatus,
        createdAt: stamp,
        updatedAt: stamp,
      };
      clients.unshift(client);
      addedClients += 1;
    }

    const knownNames = new Set(
      documents
        .filter((d) => d.clientId === client!.id)
        .map((d) => d.filename.toLowerCase()),
    );

    let touched = false;
    for (const doc of disk.documents) {
      if (knownNames.has(doc.filename.toLowerCase())) continue;
      documents.unshift({
        id: uid("doc"),
        clientId: client.id,
        filename: doc.filename,
        docType: doc.docType,
        contentType: doc.contentType,
        size: doc.size,
        text: doc.text,
        createdAt: stamp,
      });
      knownNames.add(doc.filename.toLowerCase());
      addedDocuments += 1;
      touched = true;
    }

    if (touched) {
      const idx = clients.findIndex((c) => c.id === client!.id);
      if (idx >= 0) {
        clients[idx] = { ...clients[idx], updatedAt: stamp };
        updatedClients += 1;
      }
    }
  }

  return {
    clients,
    documents,
    addedClients,
    addedDocuments,
    updatedClients,
  };
}
