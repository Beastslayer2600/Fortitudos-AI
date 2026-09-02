import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  deskApi,
  getApiBase,
  type PdfAction,
  type PdfDescription,
  type PdfResult,
} from "@/lib/desk-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/**
 * The PDF workbench: the document on the left, what you can do to it on the right.
 *
 * The viewer is the browser's own PDF renderer in an iframe rather than
 * pdf.js. That is a deliberate trade — pdf.js would give per-page coordinates
 * for highlighting, at the cost of a worker bundle and a version to keep
 * pinned on a machine that already fights its Python wheels. The AI does not
 * read pixels; it reads the per-page text the backend extracts. When
 * highlighting a specific span on the page becomes the thing you want, that is
 * the point to take the dependency.
 *
 * Every action here writes a NEW file into 99_AI_Drafts. None of them can
 * change the document on the left. That is not a setting.
 */

type Props = { docId: number | string; clientId?: string; onClose?: () => void };

const ACTION_LABEL: Record<PdfAction, string> = {
  fill: "Fill form",
  annotate: "Add note",
  redact: "Redact",
  assemble: "Pages",
  stamp: "Stamp",
  extract: "Extract to draft",
};

export function PdfWorkbench({ docId, clientId, onClose }: Props) {
  const [doc, setDoc] = useState<PdfDescription | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<PdfAction | null>(null);
  const [error, setError] = useState("");
  const [results, setResults] = useState<PdfResult[]>([]);
  const [tab, setTab] = useState<PdfAction>("annotate");

  // Action inputs
  const [fields, setFields] = useState<Record<string, string>>({});
  const [noteText, setNoteText] = useState("");
  const [notePage, setNotePage] = useState(1);
  const [literals, setLiterals] = useState("");
  const [patterns, setPatterns] = useState<string[]>(["sa_id"]);
  const [select, setSelect] = useState("");
  const [stampText, setStampText] = useState("INTERNAL DRAFT — adviser review required");

  const src = useMemo(
    () => `${getApiBase()}/api/documents/${encodeURIComponent(String(docId))}`,
    [docId],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await deskApi.pdf(docId, clientId);
      setDoc(next);
      setFields(Object.fromEntries(next.fields.map((f) => [f.name, f.value])));
      if (next.fields.length) setTab("fill");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [docId, clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(action: PdfAction, body: Record<string, unknown>) {
    setBusy(action);
    try {
      const result = await deskApi.pdfAction(docId, action, body, clientId);
      setResults((prev) => [result, ...prev]);
      toast.success(`Saved as ${result.saved_as ?? "a new draft"}`);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setResults((prev) => [{ error: message }, ...prev]);
      toast.error(message);
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-muted">
        <Loader2 className="h-4 w-4 animate-spin" /> Opening the document…
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="rounded-lg bg-surface p-6 shadow-[var(--shadow-border)]">
        <p className="text-sm text-danger">{error || "Could not open this document."}</p>
        {onClose && (
          <Button variant="outline" className="mt-4" onClick={onClose}>
            Back to documents
          </Button>
        )}
      </div>
    );
  }

  const enabled = (a: PdfAction) => doc.can[a];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{doc.filename}</h2>
          <p className="text-xs text-subtle">
            {doc.doc_type} · {doc.page_count} page{doc.page_count === 1 ? "" : "s"}
            {doc.scanned ? " · scanned image" : ""}
          </p>
        </div>
        {onClose && (
          <Button variant="outline" onClick={onClose}>
            Back to documents
          </Button>
        )}
      </header>

      {doc.why && (
        <p className="rounded-lg bg-surface px-4 py-3 text-sm text-muted shadow-[var(--shadow-border)]">
          {doc.why}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* The document itself. */}
        <div className="min-h-[28rem] overflow-hidden rounded-lg bg-surface shadow-[var(--shadow-border)]">
          <iframe
            title={doc.filename}
            src={src}
            className="h-[36rem] w-full border-0 lg:h-[44rem]"
          />
        </div>

        {/* What you can do to it. */}
        <div className="space-y-4">
          <p className="rounded-lg bg-surface px-4 py-3 text-xs text-muted shadow-[var(--shadow-border)]">
            Every action below writes a <strong>new</strong> file into the client&apos;s
            AI-drafts folder. This document is the filed record and is never changed.
          </p>

          <div className="flex flex-wrap gap-2">
            {(Object.keys(ACTION_LABEL) as PdfAction[]).map((a) => (
              <Button
                key={a}
                variant={tab === a ? "default" : "outline"}
                disabled={!enabled(a)}
                title={enabled(a) ? undefined : "Not available for this document"}
                onClick={() => setTab(a)}
              >
                {ACTION_LABEL[a]}
              </Button>
            ))}
          </div>

          <div className="rounded-lg bg-surface p-4 shadow-[var(--shadow-border)]">
            {tab === "fill" && (
              <div className="space-y-3">
                {doc.fields.length === 0 && (
                  <p className="text-sm text-muted">This PDF has no fillable fields.</p>
                )}
                {doc.fields.map((f) => (
                  <div key={f.name}>
                    <Label htmlFor={`f-${f.name}`}>
                      {f.name}
                      {f.required && <span className="text-danger"> *</span>}
                    </Label>
                    <Input
                      id={`f-${f.name}`}
                      value={fields[f.name] ?? ""}
                      onChange={(e) =>
                        setFields((prev) => ({ ...prev, [f.name]: e.target.value }))
                      }
                    />
                  </div>
                ))}
                {doc.fields.length > 0 && (
                  <Button disabled={busy === "fill"} onClick={() => run("fill", { values: fields })}>
                    {busy === "fill" ? "Filling…" : "Save filled copy"}
                  </Button>
                )}
              </div>
            )}

            {tab === "annotate" && (
              <div className="space-y-3">
                <Label htmlFor="note-page">Page</Label>
                <Input
                  id="note-page"
                  type="number"
                  min={1}
                  max={doc.page_count}
                  value={notePage}
                  onChange={(e) => setNotePage(Number(e.target.value) || 1)}
                />
                <Label htmlFor="note-text">Note</Label>
                <Textarea
                  id="note-text"
                  rows={3}
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Confirm the waiting period against the current guide."
                />
                <Button
                  disabled={busy === "annotate" || !noteText.trim()}
                  onClick={() =>
                    run("annotate", { notes: [{ page: notePage, text: noteText }] })
                  }
                >
                  {busy === "annotate" ? "Adding…" : "Save annotated copy"}
                </Button>
              </div>
            )}

            {tab === "redact" && (
              <div className="space-y-3">
                <p className="text-xs text-muted">
                  Removes the text from the new file&apos;s content — not a black box
                  drawn over it. The original still contains it.
                </p>
                <div className="flex flex-wrap gap-2">
                  {(["sa_id", "account", "tax"] as const).map((p) => (
                    <Button
                      key={p}
                      variant={patterns.includes(p) ? "default" : "outline"}
                      onClick={() =>
                        setPatterns((prev) =>
                          prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
                        )
                      }
                    >
                      {p === "sa_id" ? "ID numbers" : p === "account" ? "Account numbers" : "Tax numbers"}
                    </Button>
                  ))}
                </div>
                <Label htmlFor="literals">Exact text to remove (one per line)</Label>
                <Textarea
                  id="literals"
                  rows={3}
                  value={literals}
                  onChange={(e) => setLiterals(e.target.value)}
                />
                <Button
                  disabled={busy === "redact"}
                  onClick={() =>
                    run("redact", {
                      patterns,
                      literals: literals.split("\n").map((l) => l.trim()).filter(Boolean),
                    })
                  }
                >
                  {busy === "redact" ? "Redacting…" : "Save redacted copy"}
                </Button>
              </div>
            )}

            {tab === "assemble" && (
              <div className="space-y-3">
                <Label htmlFor="select">Keep pages</Label>
                <Input
                  id="select"
                  value={select}
                  onChange={(e) => setSelect(e.target.value)}
                  placeholder={`1,3-${doc.page_count}`}
                />
                <Button
                  disabled={busy === "assemble" || !select.trim()}
                  onClick={() => run("assemble", { select })}
                >
                  {busy === "assemble" ? "Building…" : "Save page selection"}
                </Button>
              </div>
            )}

            {tab === "stamp" && (
              <div className="space-y-3">
                <Label htmlFor="stamp">Stamp text</Label>
                <Textarea
                  id="stamp"
                  rows={2}
                  value={stampText}
                  onChange={(e) => setStampText(e.target.value)}
                />
                <Button
                  disabled={busy === "stamp" || !stampText.trim()}
                  onClick={() => run("stamp", { text: stampText, where: "top" })}
                >
                  {busy === "stamp" ? "Stamping…" : "Save stamped copy"}
                </Button>
              </div>
            )}

            {tab === "extract" && (
              <div className="space-y-3">
                <p className="text-xs text-muted">
                  Writes the text into a markdown draft you can edit. The PDF stays
                  the untouched original — this is the honest version of editing
                  the words, because PDF prose cannot be rewritten in place.
                </p>
                <Button disabled={busy === "extract"} onClick={() => run("extract", {})}>
                  {busy === "extract" ? "Extracting…" : "Save working draft"}
                </Button>
              </div>
            )}
          </div>

          {results.length > 0 && (
            <ul className="space-y-2">
              {results.map((r, i) => (
                <li
                  key={i}
                  className="rounded-lg bg-surface px-4 py-3 text-sm shadow-[var(--shadow-border)]"
                >
                  {r.error ? (
                    <p className="text-danger">{r.error}</p>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span>{r.saved_as}</span>
                        <Badge>{r.doc_type}</Badge>
                      </div>
                      {r.removed && r.removed.length > 0 && (
                        <p className="mt-1 text-xs text-muted">
                          Removed: {r.removed.join(", ")}
                        </p>
                      )}
                      {r.warning && <p className="mt-1 text-xs text-danger">{r.warning}</p>}
                      <p className="mt-1 text-xs text-subtle">{r.note}</p>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
