import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { classifyDocument } from "@/lib/ai";
import { useFortitudo } from "@/lib/store";
import { DOC_TYPES, type DocType } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils";

export const Route = createFileRoute("/dropzone")({ component: DropzonePage });

function guessType(filename: string, text: string): DocType {
  const hay = `${filename} ${text}`.toLowerCase();
  if (/\b(fica|id book|passport|proof of address)\b/.test(hay)) return "FICA / Identity";
  if (/\brpq\b|risk profile/.test(hay)) return "RPQ";
  if (/\bfna\b|needs analysis/.test(hay)) return "Signed FNA";
  if (/advice report|recommendation/.test(hay)) return "Advice Report";
  if (/\bquote\b|quotation|premium/.test(hay)) return "Quote";
  if (/\broa\b|record of advice/.test(hay)) return "ROA";
  if (/email|letter|correspondence/.test(hay)) return "Correspondence";
  return "Other";
}

function DropzonePage() {
  const clients = useFortitudo((s) => s.clients);
  const items = useFortitudo((s) => s.dropItems);
  const addDropItem = useFortitudo((s) => s.addDropItem);
  const fileDropItem = useFortitudo((s) => s.fileDropItem);
  const [filename, setFilename] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);

  function ingest(name: string, body: string) {
    const suggestedType = guessType(name, body);
    const lower = `${name} ${body}`.toLowerCase();
    const suggestedClientId =
      clients.find((c) => lower.includes(c.name.toLowerCase().split(" ")[0] ?? ""))
        ?.id ?? null;
    addDropItem({
      filename: name,
      suggestedType,
      suggestedClientId,
      text: body,
      size: body.length,
    });
    setFilename("");
    setText("");
  }

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    for (const file of [...files]) {
      const body = file.type.startsWith("text") || file.name.endsWith(".md")
        ? await file.text()
        : "";
      ingest(file.name, body.slice(0, 8000));
    }
  }

  async function classify(id: string) {
    const item = items.find((d) => d.id === id);
    if (!item) return;
    setBusy(true);
    try {
      const result = await classifyDocument({
        data: {
          filename: item.filename,
          text: item.text,
          clientNames: clients.map((c) => c.name),
        },
      });
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.message(result.reason || "Classified", {
        description: `${result.docType ?? "Other"} · ${result.clientName || "no client match"}`,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-8 md:px-10 md:py-12">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">
        Intake
      </p>
      <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">
        Drop zone
      </h1>
      <p className="mt-2 text-sm text-muted">
        Drop a file or paste an extract. The desk guesses FICA, FNA, quote and
        the rest, then files it to a client folder.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          void onFiles(e.dataTransfer.files);
        }}
        className={`mt-8 rounded-xl border border-dashed px-5 py-10 text-center ${
          drag ? "border-accent bg-elevated" : "border-border bg-surface"
        }`}
      >
        <p className="text-sm text-muted">Drop PDFs or text here</p>
        <label className="mt-3 inline-flex h-11 cursor-pointer items-center rounded-md bg-elevated px-4 text-sm shadow-[var(--shadow-border)]">
          Choose files
          <input
            type="file"
            className="sr-only"
            multiple
            onChange={(e) => void onFiles(e.target.files)}
          />
        </label>
      </div>

      <form
        className="mt-6 space-y-3 rounded-xl bg-surface p-4 shadow-[var(--shadow-border)]"
        onSubmit={(e) => {
          e.preventDefault();
          if (!filename.trim()) return;
          ingest(filename, text);
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="drop-name">Filename</Label>
          <Input
            id="drop-name"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="Signed_FNA_Nkosi.pdf"
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="drop-text">Extract</Label>
          <Textarea
            id="drop-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <Button type="submit">Add to tray</Button>
      </form>

      <ul className="mt-8 space-y-3">
        {items.map((item) => (
          <DropRow
            key={item.id}
            item={item}
            busy={busy}
            onClassify={() => void classify(item.id)}
            onFile={(clientId, docType) => {
              fileDropItem(item.id, clientId, docType);
              toast.success("Filed");
            }}
          />
        ))}
        {items.length === 0 && (
          <li className="text-sm text-muted">Tray is empty.</li>
        )}
      </ul>
    </div>
  );
}

function DropRow({
  item,
  busy,
  onClassify,
  onFile,
}: {
  item: {
    id: string;
    filename: string;
    suggestedType: DocType;
    suggestedClientId: string | null;
    text: string;
    filed: boolean;
    createdAt: string;
  };
  busy: boolean;
  onClassify: () => void;
  onFile: (clientId: string, docType: DocType) => void;
}) {
  const clients = useFortitudo((s) => s.clients);
  const [clientId, setClientId] = useState(item.suggestedClientId ?? clients[0]?.id ?? "");
  const [docType, setDocType] = useState<DocType>(item.suggestedType);

  return (
    <li className="rounded-xl bg-surface p-4 shadow-[var(--shadow-border)]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{item.filename}</p>
        {item.filed ? <Badge variant="success">Filed</Badge> : <Badge>Tray</Badge>}
      </div>
      <p className="mt-1 text-xs text-subtle">{formatDate(item.createdAt)}</p>
      {item.text && (
        <p className="mt-2 line-clamp-3 text-sm text-muted">{item.text}</p>
      )}
      {!item.filed && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Select value={clientId} onValueChange={setClientId}>
            <SelectTrigger>
              <SelectValue placeholder="Client" />
            </SelectTrigger>
            <SelectContent>
              {clients.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={docType} onValueChange={(v) => setDocType(v as DocType)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DOC_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={onClassify}
          >
            {busy && <Loader2 className="animate-spin" />}
            Ask AI to classify
          </Button>
          <Button
            type="button"
            disabled={!clientId}
            onClick={() => onFile(clientId, docType)}
          >
            File
          </Button>
        </div>
      )}
    </li>
  );
}
