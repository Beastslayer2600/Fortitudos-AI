import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { deskApi, fileToBase64 } from "@/lib/desk-api";

export const Route = createFileRoute("/learn")({ component: LearnPage });

function LearnPage() {
  const [docs, setDocs] = useState<{ name: string; kind: string; bytes: number }[]>([]);
  const [sources, setSources] = useState<{ name: string; pages: number }[]>([]);
  const [how, setHow] = useState<string[]>([]);
  const [status, setStatus] = useState("Connecting to local backend…");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const data = await deskApi.learn();
      setDocs(data.docs);
      setSources(data.sources);
      setHow(data.how);
      setStatus("Desk backend is on this PC.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Backend not running. Use Start Fortitudo Desk.bat");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onGuides(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    try {
      for (const file of [...files]) {
        const b64 = await fileToBase64(file);
        const result = await deskApi.ingestGuide(file.name, b64);
        setStatus(`${file.name}: ${result.pages} pages indexed`);
      }
      await refresh();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function ingestClients() {
    setBusy(true);
    try {
      const result = await deskApi.ingestClients();
      setStatus(`Client files: ${result.pages} pages in the vault index`);
      await refresh();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Client ingest failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-8 md:px-10 md:py-12">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">One app</p>
      <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">Learn & ingest</h1>
      <p className="mt-2 text-sm text-muted">{status}</p>
      <ol className="mt-6 list-decimal space-y-2 pl-5 text-sm text-muted">
        {how.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ol>
      <div className="mt-8 rounded-xl border border-dashed border-border bg-surface px-5 py-8 text-center">
        <p className="text-sm">Product guides go into the index. Client files stay on the client.</p>
        <label className="mt-3 inline-flex h-11 cursor-pointer items-center rounded-md bg-elevated px-4 text-sm">
          {busy ? "Working…" : "Add guide PDF / MD"}
          <input type="file" accept=".pdf,.md,.txt" multiple className="sr-only" disabled={busy} onChange={(e) => void onGuides(e.target.files)} />
        </label>
        <div className="mt-3">
          <button type="button" className="h-11 rounded-md border border-border px-4 text-sm" disabled={busy} onClick={() => void ingestClients()}>
            Re-index filed client documents
          </button>
        </div>
      </div>
      <section className="mt-8">
        <h2 className="font-display text-xl">On disk</h2>
        <ul className="mt-3 divide-y divide-border rounded-xl bg-surface">
          {docs.map((d) => (
            <li key={d.name} className="flex justify-between px-4 py-3 text-sm">
              <span>{d.name}</span>
              <span className="text-subtle">{d.kind} · {Math.round(d.bytes / 1024)} KB</span>
            </li>
          ))}
          {docs.length === 0 && <li className="px-4 py-3 text-sm text-muted">No guides in backend/docs yet.</li>}
        </ul>
      </section>
      <section className="mt-8">
        <h2 className="font-display text-xl">Indexed sources</h2>
        <ul className="mt-3 divide-y divide-border rounded-xl bg-surface">
          {sources.map((s) => (
            <li key={s.name} className="flex justify-between px-4 py-3 text-sm">
              <span>{s.name}</span>
              <span className="text-subtle">{s.pages} pages</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm text-muted">
          After ingest, open <Link to="/ask">Ask the index</Link> or <Link to="/chat">Chat</Link> with the client selected.
        </p>
      </section>
    </div>
  );
}
