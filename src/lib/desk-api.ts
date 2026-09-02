const STORAGE_KEY = "fortitudo.apiBase";

function envBase(): string {
  if (typeof import.meta !== "undefined") {
    const fromEnv = (import.meta as { env?: { VITE_FA_API?: string } }).env?.VITE_FA_API;
    if (fromEnv) return fromEnv.replace(/\/$/, "");
  }
  return "";
}

export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) return saved.replace(/\/$/, "");
    if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
  }
  return envBase() || "http://127.0.0.1:8000";
}

export function setApiBase(url: string) {
  const clean = url.trim().replace(/\/$/, "");
  if (typeof window !== "undefined") {
    if (clean) window.localStorage.setItem(STORAGE_KEY, clean);
    else window.localStorage.removeItem(STORAGE_KEY);
  }
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBase();
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    // fetch() rejects with a bare "Failed to fetch" for a dead port, a refused
    // connection and a blocked CORS preflight alike. Name the address instead.
    throw new Error(
      `Cannot reach the desk backend at ${base}. Start it with "Start Backend Only.bat" (or START_ALL.bat), then try again.`,
    );
  }
  const data = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) {
    // "Not found." is app.py's unmatched-route fallback. The desk only calls
    // routes the current backend has, so a backend that answers but does not
    // know this one is running older code than this UI.
    if (res.status === 404 && data.error === "Not found.") {
      throw new Error(
        `${base} is running an older backend that has no ${path}. Close the "Fortitudo Backend" window and start it again from this folder.`,
      );
    }
    throw new Error(data.error || res.statusText);
  }
  return data;
}


export type PdfAction = "fill" | "annotate" | "redact" | "assemble" | "stamp" | "extract";

export type PdfField = {
  name: string;
  kind: "text" | "checkbox" | "choice" | "signature" | "button";
  value: string;
  options: string[];
  required: boolean;
};

export type PdfDescription = {
  id: string;
  filename: string;
  client_id: string;
  doc_type: string;
  page_count: number;
  /** No extractable text: an image, not a document. Limits what is offered. */
  scanned: boolean;
  pages: { page: number; text: string }[];
  fields: PdfField[];
  can: Record<PdfAction, boolean>;
  /** Whether an OCR engine is installed, and what to run if not. */
  ocr: { available: boolean; why: string };
  why: string;
};

export type PdfResult = {
  ok?: boolean;
  error?: string;
  saved_as?: string;
  path?: string;
  folder?: string;
  doc_type?: string;
  original_untouched?: string;
  note?: string;
  removed?: string[];
  notes?: string[];
  /** True when the result came from a scan: pixels blanked, page rebuilt. */
  scanned?: boolean;
  ocr?: boolean;
  lowest_confidence?: number;
  unknown_fields?: string[];
  warning?: string;
};

export const deskApi = {
  get base() {
    return getApiBase();
  },
  status: () => json<{ ok: boolean; models: string[]; sources: { name: string; pages: number }[];
      /** Which machine answers which job. `pinned_local` means the desk refused to
       *  send that job to the configured host because it can carry client data. */
      compute: { job: string; model: string; host: string; client_data: boolean;
                 pinned_local: boolean; why: string }[] }>("/api/status"),
  build: () => json<{ desk_build: string; public_base: string | null }>("/api/build"),
  learn: () =>
    json<{ docs: { name: string; kind: string; bytes: number }[]; sources: { name: string; pages: number }[]; how: string[] }>("/api/learn"),
  selfLearnStatus: () =>
    json<{ enabled: boolean; interval_hours: number; last: { title?: string; at?: string; pages?: number } | null; curriculum: { id: string; title: string; why: string }[]; note: string }>("/api/learn/self"),
  discover: () =>
    json<{ catalog: { id: string; branch: string; title: string; why: string; url: string; ask: string }[]; gaps: { id: string; title: string; branch: string; have: boolean }[]; rule: string }>("/api/learn/discover"),
  selfLearnRun: (topicId?: string) =>
    json<{ ok: boolean; title?: string; pages?: number; errors?: string[] }>("/api/learn/self", { method: "POST", body: JSON.stringify({ topic_id: topicId || "" }) }),
  sight: (input: { imageBase64: string; filename: string; caption?: string; intent?: "learn" | "client" | "idea" | "chat"; clientId?: string }) =>
    json<{ ok: boolean; extract: string; pages: number; vision: string; note: string }>("/api/sight", {
      method: "POST",
      body: JSON.stringify({ image_base64: input.imageBase64, filename: input.filename, caption: input.caption || "", intent: input.intent || "chat", client_id: input.clientId || "" }),
    }),
  ingestGuide: (filename: string, contentBase64: string, topic = "misc") =>
    json<{ ok: boolean; pages: number; topic?: string; source?: string }>("/api/ingest/guides", { method: "POST", body: JSON.stringify({ filename, content_base64: contentBase64, topic }) }),
  teach: (title: string, text: string, research = false, applies = "craft") =>
    json<{ ok: boolean; pages: number; source?: string; researched?: { title?: string } | null }>("/api/learn/teach", { method: "POST", body: JSON.stringify({ title, text, research, applies }) }),
  ingestPaste: (title: string, text: string) =>
    json<{ ok: boolean; pages: number; source?: string; branches?: string[] }>("/api/ingest/paste", { method: "POST", body: JSON.stringify({ title, text }) }),
  ingestClients: () => json<{ ok: boolean; pages: number }>("/api/ingest/clients", { method: "POST", body: JSON.stringify({}) }),
  /** Which room a job lands in, and why — without answering it. */
  route: (question: string, room?: string) =>
    json<{ room: string; why: string; standard: string; refuse: string; tools: string[] }>("/api/route", { method: "POST", body: JSON.stringify({ question, room: room || "" }) }),
  ask: (question: string, history: { role: string; content: string }[], clientId?: string, room?: string) =>
    json<{ answer: string; room: string; why: string; standard: string; refuse: string; sources: { source: string; page: number; score: number }[]; used_client_files: boolean }>("/api/ask", { method: "POST", body: JSON.stringify({ question, history, client_id: clientId || "", room: room || "" }) }),
  craftPage: (input: { name: string; city?: string; facts: string; url?: string }) =>
    json<{ ok: boolean; slug: string; path: string; spec: Record<string, unknown>; missing: string[];
      /** true when the model wrote the HTML; false when the gate refused it and the template ran. */
      authored: boolean; author_notes: string[] }>("/api/craft/page", { method: "POST", body: JSON.stringify(input) }),
  /** The client as the vault holds it, including the documents filed on disk. */
  vaultClient: (clientId: string) =>
    json<{ id: string; name: string; status?: string;
      documents: { id: number; filename: string; doc_type: string; content_type?: string;
                   size?: number; created_at?: string }[] }>(`/api/clients/${encodeURIComponent(clientId)}`),
  /** What a filed PDF is: pages, text, form fields, and what can be done to it. */
  pdf: (docId: string | number, clientId?: string) =>
    json<PdfDescription>(
      `/api/pdf/${encodeURIComponent(String(docId))}` +
        (clientId ? `?client_id=${encodeURIComponent(clientId)}` : ""),
    ),
  /**
   * Run an operation on a filed PDF. Every one of these writes a NEW file into
   * the client's AI-drafts folder; none can modify the document it reads.
   */
  pdfAction: (
    docId: string | number,
    action: PdfAction,
    body: Record<string, unknown>,
    /**
     * Whose document the caller believes this is. The backend refuses a
     * mismatch. Always pass it from the chat agent, where the id comes out of
     * a sentence and could be wrong or invented.
     */
    clientId?: string,
  ) =>
    json<PdfResult>(`/api/pdf/${encodeURIComponent(String(docId))}/${action}`, {
      method: "POST",
      body: JSON.stringify(clientId ? { ...body, client_id: clientId } : body),
    }),
  consent: (identifier: string, action = "check") =>
    json<{ allowed: boolean; kind: string; reason: string; state: string }>("/api/consent", { method: "POST", body: JSON.stringify({ identifier, action }) }),
  fileClientDoc: (clientId: string, filename: string, contentBase64: string, docType = "Other") =>
    json<{ path: string }>(`/api/clients/${encodeURIComponent(clientId)}/documents`, { method: "POST", body: JSON.stringify({ filename, content_base64: contentBase64, doc_type: docType }) }),
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
