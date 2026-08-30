import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { deskApi, fileToBase64, getApiBase, setApiBase } from "@/lib/desk-api";
import { SightDrop } from "@/components/sight-drop";

export const Route = createFileRoute("/learn")({ component: LearnPage });

function LearnPage() {
  const [docs, setDocs] = useState<{ name: string; kind: string; bytes: number }[]>([]);
  const [status, setStatus] = useState("Connecting…");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"teach" | "files" | "discover">("teach");
  const [pasteTitle, setPasteTitle] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [alsoResearch, setAlsoResearch] = useState(false);
  const [applies, setApplies] = useState<"craft" | "advisor" | "voice" | "drama" | "all">("craft");
  const [homeUrl, setHomeUrl] = useState("");
  const [gaps, setGaps] = useState<{ title: string; branch: string; have: boolean }[]>([]);

  async function refresh() {
    try {
      const data = await deskApi.learn();
      setDocs(data.docs);
      setStatus("Desk backend reached.");
      setHomeUrl(getApiBase());
      try {
        const disc = await deskApi.discover();
        setGaps(disc.gaps);
      } catch {
        /* older */
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Start the desk on the PC");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-5 py-8">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">One app</p>
      <h1 className="mt-2 font-display text-3xl">Learn</h1>
      <p className="mt-2 text-sm text-muted">{status}</p>
      <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); setApiBase(homeUrl); void refresh(); }}>
        <input className="h-11 flex-1 rounded-md border border-border bg-transparent px-3 text-sm" placeholder="Home backend http://192.168.x.x:8000" value={homeUrl} onChange={(e) => setHomeUrl(e.target.value)} />
        <button className="h-11 rounded-md border border-border px-4 text-sm" type="submit">Use this PC</button>
      </form>
      <div className="mt-6 flex gap-1">
        {(["teach", "files", "discover"] as const).map((key) => (
          <button key={key} type="button" className={`h-10 rounded-md px-4 text-sm ${tab === key ? "bg-elevated text-accent" : "border border-border"}`} onClick={() => setTab(key)}>
            {key === "teach" ? "Tell it" : key === "files" ? "Files" : "Discover"}
          </button>
        ))}
      </div>
      {tab === "teach" && (
        <>
          <form className="mt-6 space-y-3 rounded-xl border border-border bg-surface p-5" onSubmit={(e) => { e.preventDefault(); void (async () => { setBusy(true); try { await deskApi.teach(pasteTitle || "Lesson", pasteText, alsoResearch, applies); setPasteText(""); await refresh(); } catch (err) { setStatus(err instanceof Error ? err.message : "Teach failed"); } finally { setBusy(false); } })(); }}>
            <p className="text-sm">File a rule for one room. Craft lessons feed the page designer. Advisor lessons stay out of plumber pages.</p>
            <input className="h-11 w-full rounded-md border border-border bg-transparent px-3 text-sm" placeholder="Topic" value={pasteTitle} onChange={(e) => setPasteTitle(e.target.value)} />
            <select className="h-11 w-full rounded-md border border-border bg-transparent px-3 text-sm" value={applies} onChange={(e) => setApplies(e.target.value as typeof applies)}>
              <option value="craft">Applies to: Craft</option>
              <option value="advisor">Applies to: Advisor</option>
              <option value="voice">Applies to: Voice</option>
              <option value="drama">Applies to: Drama</option>
              <option value="all">Applies to: all rooms</option>
            </select>
            <textarea className="min-h-32 w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm" placeholder="The rule. Short. Example. What it must never do." value={pasteText} onChange={(e) => setPasteText(e.target.value)} />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={alsoResearch} onChange={(e) => setAlsoResearch(e.target.checked)} /> Research after filing (off — file the rule yourself)</label>
            <button type="submit" className="h-11 rounded-md bg-accent px-4 text-sm text-accent-fg" disabled={busy}>Learn this</button>
          </form>
          <div className="mt-6"><SightDrop /></div>
        </>
      )}
      {tab === "discover" && (
        <ul className="mt-6 divide-y divide-border rounded-xl bg-surface">
          {gaps.map((g) => (
            <li key={g.title} className="flex justify-between px-4 py-3 text-sm"><span>{g.title}</span><span className="text-subtle">{g.have ? "on file" : g.branch}</span></li>
          ))}
        </ul>
      )}
      {tab === "files" && (
        <>
          <label className="mt-6 inline-flex h-11 cursor-pointer items-center rounded-md bg-elevated px-4 text-sm">
            Add PDF / MD
            <input type="file" accept=".pdf,.md,.txt" multiple className="sr-only" onChange={(e) => { const files = e.target.files; if (!files) return; void (async () => { for (const f of [...files]) { await deskApi.ingestGuide(f.name, await fileToBase64(f), "all"); } await refresh(); })(); }} />
          </label>
          <ul className="mt-4 divide-y divide-border rounded-xl bg-surface">
            {docs.map((d) => (
              <li key={d.name} className="px-4 py-3 text-sm">{d.name}</li>
            ))}
          </ul>
          <p className="mt-4 text-sm"><Link to="/chat">Chat</Link></p>
        </>
      )}
    </div>
  );
}
