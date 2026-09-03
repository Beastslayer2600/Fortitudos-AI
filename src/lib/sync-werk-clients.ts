import { createServerFn } from "@tanstack/react-start";
import {
  DEFAULT_WERK_CLIENTS,
  type DiskClient,
  type DiskDocument,
  type SyncWerkResult,
} from "./sync-werk-types.ts";

export type { DiskClient, DiskDocument, SyncWerkResult };
export { DEFAULT_WERK_CLIENTS };

/**
 * Client-safe export: only the server function RPC surface.
 * Node fs lives in `sync-werk-scan.server.ts` and is loaded only inside the handler.
 */
export const syncWerkClients = createServerFn({ method: "GET" }).handler(
  async (): Promise<SyncWerkResult> => {
    const { scanWerkClients } = await import("./sync-werk-scan.server");
    const root =
      process.env.FORTITUDO_CLIENTS_DIR?.trim() || DEFAULT_WERK_CLIENTS;
    return scanWerkClients(root);
  },
);
