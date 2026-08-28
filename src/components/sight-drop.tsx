import { useState } from "react";
import { deskApi, fileToBase64 } from "@/lib/desk-api";

type Intent = "learn" | "client" | "idea" | "chat";

export function SightDrop({ clientId, onExtract }: { clientId?: string; onExtract?: (extract: string, intent: Intent) => void }) {
  const [intent, setIntent] = useState<Intent>("learn");
  const [caption, setCaption] = useState("");
  const [status, setStatus] = useState("Drop a screenshot — topic, client message, or web idea.");
  const [busy, setBusy] = useState(false);
  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    try {
      for (const file of [...files]) {
        const b64 = await fileToBase64(file);
        const result = await deskApi.sight({ imageBase64: b64, filename: file.name, caption, intent, clientId });
        setStatus(result.vision ? `Read with ${result.vision}` : "Filed caption");
        onExtract?.(result.extract, intent);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Could not read the shot");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="rounded-xl border border-dashed border-border bg-surface p-4">
      <p className="text-sm">{status}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {(["learn", "client", "idea", "chat"] as Intent[]).map((key) => (
          <button key={key} type="button" className={`h-9 rounded-md px-3 text-xs ${intent === key ? "bg-elevated" : "border border-border"}`} onClick={() => setIntent(key)}>
            {key === "learn" ? "Learn this" : key === "client" ? "Client message" : key === "idea" ? "Web idea" : "Chat context"}
          </button>
        ))}
      </div>
      <input className="mt-3 h-11 w-full rounded-md border border-border bg-transparent px-3 text-sm" placeholder="What should I take from this shot?" value={caption} onChange={(e) => setCaption(e.target.value)} />
      <label className="mt-3 inline-flex h-11 cursor-pointer items-center rounded-md bg-elevated px-4 text-sm">
        {busy ? "Reading…" : "Attach screenshot"}
        <input type="file" accept="image/*" multiple className="sr-only" disabled={busy} onChange={(e) => void handleFiles(e.target.files)} />
      </label>
    </div>
  );
}
