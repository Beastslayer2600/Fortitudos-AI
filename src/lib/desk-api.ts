const BASE =
  (typeof import.meta !== "undefined" &&
    (import.meta as { env?: { VITE_FA_API?: string } }).env?.VITE_FA_API) ||
  "http://127.0.0.1:8000";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const data = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

export const deskApi = {
  base: BASE,
  status: () => json<{ ok: boolean; models: string[]; sources: { name: string; pages: number }[] }>("/api/status"),
  learn: () =>
    json<{
      docs: { name: string; kind: string; bytes: number }[];
      sources: { name: string; pages: number }[];
      how: string[];
    }>("/api/learn"),
  ingestGuide: (filename: string, contentBase64: string) =>
    json<{ ok: boolean; pages: number }>("/api/ingest/guides", {
      method: "POST",
      body: JSON.stringify({ filename, content_base64: contentBase64 }),
    }),
  ingestClients: () =>
    json<{ ok: boolean; pages: number }>("/api/ingest/clients", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  ask: (question: string, history: { role: string; content: string }[], clientId?: string) =>
    json<{ answer: string; sources: { source: string; page: number; score: number }[]; used_client_files: boolean }>(
      "/api/ask",
      {
        method: "POST",
        body: JSON.stringify({ question, history, client_id: clientId || "" }),
      },
    ),
  fileClientDoc: (clientId: string, filename: string, contentBase64: string, docType = "Other") =>
    json<{ path: string }>(`/api/clients/${encodeURIComponent(clientId)}/documents`, {
      method: "POST",
      body: JSON.stringify({ filename, content_base64: contentBase64, doc_type: docType }),
    }),
};

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.readAsDataURL(file);
  });
}
