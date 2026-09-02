import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { draftClientNote } from "@/lib/ai";
import { emptyProjectionInputs, project, zar } from "@/lib/projections";
import { useFortitudo } from "@/lib/store";
import {
  CLIENT_STATUSES,
  DOC_TYPES,
  NOTE_TYPES,
  type ClientStatus,
  type DocType,
  type NoteType,
  type ProjectionInputs,
} from "@/lib/types";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatBytes, formatDate } from "@/lib/utils";
import { deskApi } from "@/lib/desk-api";
import { PdfWorkbench } from "@/components/pdf-workbench";

export const Route = createFileRoute("/clients/$clientId")({
  component: ClientPage,
});

const CHECKS: { item: DocType | "FICA"; label: string; match: DocType }[] = [
  {
    item: "FICA",
    label: "Confirm identity and residence verification is on file.",
    match: "FICA / Identity",
  },
  {
    item: "Signed FNA",
    label: "Confirm the signed FNA is on file.",
    match: "Signed FNA",
  },
  {
    item: "RPQ",
    label: "Confirm the risk profile questionnaire is on file.",
    match: "RPQ",
  },
  {
    item: "Advice Report",
    label: "Confirm the advice report is on file before discussing recommendations.",
    match: "Advice Report",
  },
  {
    item: "Quote",
    label: "Confirm current quotes and assumptions.",
    match: "Quote",
  },
];

function ClientPage() {
  const { clientId } = Route.useParams();
  const client = useFortitudo((s) => s.clients.find((c) => c.id === clientId));
  const allDocuments = useFortitudo((s) => s.documents);
  const allNotes = useFortitudo((s) => s.notes);
  const allEmails = useFortitudo((s) => s.emails);
  const allProjections = useFortitudo((s) => s.projections);
  const documents = allDocuments.filter((d) => d.clientId === clientId);
  const notes = allNotes.filter((n) => n.clientId === clientId);
  const emails = allEmails.filter((e) => e.clientId === clientId);
  const projections = allProjections.filter((p) => p.clientId === clientId);
  const updateClient = useFortitudo((s) => s.updateClient);

  if (!client) {
    return (
      <div className="px-5 py-16 text-center">
        <p className="text-muted">Client not found.</p>
        <Link to="/clients" className="mt-3 inline-block text-sm text-accent">
          Back to clients
        </Link>
      </div>
    );
  }

  const types = new Set(documents.map((d) => d.docType));

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-10 md:py-12">
      <Link to="/clients" className="text-sm text-muted hover:text-fg">
        Clients
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl tracking-tight md:text-4xl">
            {client.name}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {client.email || "No email"} · {client.phone || "No phone"}
          </p>
        </div>
        <Select
          value={client.status}
          onValueChange={(v) =>
            updateClient(client.id, { status: v as ClientStatus })
          }
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CLIENT_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Tabs defaultValue="overview" className="mt-8">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
          <TabsTrigger value="projections">Projections</TabsTrigger>
          <TabsTrigger value="mail">Correspondence</TabsTrigger>
          <TabsTrigger value="prep">Meeting prep</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <Mini label="Documents" value={String(documents.length)} />
            <Mini label="Notes" value={String(notes.length)} />
            <Mini label="Updated" value={formatDate(client.updatedAt)} />
          </div>
          <h2 className="mt-8 font-display text-xl tracking-tight">Filing</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {CHECKS.map((c) => (
              <li
                key={c.label}
                className="flex items-start gap-3 rounded-lg bg-surface px-4 py-3 shadow-[var(--shadow-border)]"
              >
                <Badge variant={types.has(c.match) ? "success" : "warn"}>
                  {types.has(c.match) ? "On file" : "Missing"}
                </Badge>
                <span className="text-sm">
                  <span className="block font-medium">{c.item}</span>
                  <span className="text-muted">{c.label}</span>
                </span>
              </li>
            ))}
          </ul>
          <DraftPanel
            clientName={client.name}
            status={client.status}
            notes={notes.map((n) => `${n.title}: ${n.content}`).join("\n")}
            documents={documents.map((d) => `${d.docType} — ${d.filename}`).join("\n")}
            onSave={(title, content) =>
              useFortitudo.getState().addNote({
                clientId: client.id,
                noteType: "Advice",
                title,
                content,
              })
            }
          />
        </TabsContent>

        <TabsContent value="documents" className="mt-6">
          <Documents clientId={client.id} local={documents} />
          <FileForm clientId={client.id} />
        </TabsContent>

        <TabsContent value="notes" className="mt-6">
          <NoteForm clientId={client.id} />
          <ul className="mt-6 space-y-3">
            {notes.map((n) => (
              <li
                key={n.id}
                className="rounded-lg bg-surface px-4 py-3 shadow-[var(--shadow-border)]"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">{n.title}</p>
                  <Badge>{n.noteType}</Badge>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-muted">
                  {n.content}
                </p>
                <p className="mt-2 text-xs text-subtle">{formatDate(n.createdAt)}</p>
              </li>
            ))}
          </ul>
        </TabsContent>

        <TabsContent value="projections" className="mt-6">
          <ProjectionForm clientId={client.id} />
          <ul className="mt-6 space-y-3">
            {projections.map((p) => (
              <li
                key={p.id}
                className="rounded-lg bg-surface px-4 py-4 shadow-[var(--shadow-border)]"
              >
                <p className="text-sm font-medium">{p.name}</p>
                <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <div>
                    <dt className="text-xs text-subtle">Projected</dt>
                    <dd className="tabular-nums">{zar(p.summary.projectedValue)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-subtle">Contributions</dt>
                    <dd className="tabular-nums">{zar(p.summary.contributions)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-subtle">Growth</dt>
                    <dd className="tabular-nums">{zar(p.summary.growthRand)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-subtle">Advice fees</dt>
                    <dd className="tabular-nums">{zar(p.summary.feesRand)}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        </TabsContent>

        <TabsContent value="mail" className="mt-6">
          <MailForm clientId={client.id} defaultRecipient={client.email} />
          <ul className="mt-6 space-y-3">
            {emails.map((e) => (
              <li
                key={e.id}
                className="rounded-lg bg-surface px-4 py-3 shadow-[var(--shadow-border)]"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">{e.subject}</p>
                  <Badge>{e.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-subtle">
                  To {e.recipient} · {formatDate(e.createdAt)}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-muted">{e.body}</p>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-subtle">
            Sending and mailbox ingestion stay off until the firm’s approved
            mailbox and retention rules are known.
          </p>
        </TabsContent>

        <TabsContent value="prep" className="mt-6">
          <div className="rounded-xl bg-surface p-5 shadow-[var(--shadow-border)]">
            <h2 className="font-display text-xl tracking-tight">Meeting prep</h2>
            <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm text-muted">
              <li>Reconfirm objectives and material changes</li>
              <li>Review information supplied and limitations</li>
              <li>Discuss recommendations and costs</li>
              <li>Agree actions, owners and dates</li>
            </ol>
            <ul className="mt-5 space-y-2">
              {CHECKS.map((c) => (
                <li key={c.label} className="flex items-start gap-3 text-sm">
                  <Badge variant={types.has(c.match) ? "success" : "warn"}>
                    {types.has(c.match) ? "Done" : "Open"}
                  </Badge>
                  <span>
                    <span className="font-medium">{c.item}</span>
                    <span className="block text-muted">{c.label}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-surface px-4 py-3 shadow-[var(--shadow-border)]">
      <div className="text-[11px] text-subtle">{label}</div>
      <div className="mt-1 font-display text-xl tabular-nums">{value}</div>
    </div>
  );
}

function FileForm({ clientId }: { clientId: string }) {
  const addDocument = useFortitudo((s) => s.addDocument);
  const [filename, setFilename] = useState("");
  const [docType, setDocType] = useState<DocType>("Other");
  const [text, setText] = useState("");

  return (
    <form
      className="space-y-3 rounded-xl bg-surface p-4 shadow-[var(--shadow-border)]"
      onSubmit={(e) => {
        e.preventDefault();
        if (!filename.trim()) return;
        addDocument({ clientId, filename, docType, text });
        setFilename("");
        setText("");
        toast.success("Filed");
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="fn">Filename</Label>
          <Input
            id="fn"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label>Type</Label>
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
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="extract">Extract / note</Label>
        <Textarea
          id="extract"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the useful text. Binary PDFs stay on the encrypted drive in the desktop build."
        />
      </div>
      <Button type="submit">File document</Button>
    </form>
  );
}

function NoteForm({ clientId }: { clientId: string }) {
  const addNote = useFortitudo((s) => s.addNote);
  const [title, setTitle] = useState("");
  const [noteType, setNoteType] = useState<NoteType>("General");
  const [content, setContent] = useState("");
  return (
    <form
      className="space-y-3 rounded-xl bg-surface p-4 shadow-[var(--shadow-border)]"
      onSubmit={(e) => {
        e.preventDefault();
        addNote({ clientId, noteType, title, content });
        setTitle("");
        setContent("");
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="nt">Title</Label>
          <Input id="nt" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Type</Label>
          <Select value={noteType} onValueChange={(v) => setNoteType(v as NoteType)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {NOTE_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <Textarea value={content} onChange={(e) => setContent(e.target.value)} required />
      <Button type="submit">Add note</Button>
    </form>
  );
}

function MailForm({
  clientId,
  defaultRecipient,
}: {
  clientId: string;
  defaultRecipient: string;
}) {
  const addEmail = useFortitudo((s) => s.addEmail);
  const [recipient, setRecipient] = useState(defaultRecipient);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  return (
    <form
      className="space-y-3 rounded-xl bg-surface p-4 shadow-[var(--shadow-border)]"
      onSubmit={(e) => {
        e.preventDefault();
        addEmail({ clientId, recipient, subject, body });
        setSubject("");
        setBody("");
        toast.success("Draft saved locally");
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="to">To</Label>
          <Input
            id="to"
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sub">Subject</Label>
          <Input
            id="sub"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
          />
        </div>
      </div>
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} required />
      <Button type="submit">Save draft</Button>
    </form>
  );
}

function ProjectionForm({ clientId }: { clientId: string }) {
  const addProjection = useFortitudo((s) => s.addProjection);
  const [name, setName] = useState("Base case");
  const [inputs, setInputs] = useState<ProjectionInputs>(emptyProjectionInputs);
  const summary = useMemo(() => project(inputs), [inputs]);

  function num(key: keyof ProjectionInputs) {
    return (
      <Input
        type="number"
        step="any"
        value={inputs[key]}
        onChange={(e) =>
          setInputs((s) => ({ ...s, [key]: Number(e.target.value) }))
        }
      />
    );
  }

  return (
    <form
      className="rounded-xl bg-surface p-4 shadow-[var(--shadow-border)]"
      onSubmit={(e) => {
        e.preventDefault();
        addProjection({ clientId, name, inputs });
        toast.success("Scenario saved");
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Current value (R)">{num("currentValue")}</Field>
        <Field label="Monthly contribution">{num("monthlyContribution")}</Field>
        <Field label="Lump sum">{num("lumpSum")}</Field>
        <Field label="Years">{num("years")}</Field>
        <Field label="Growth %">{num("growthRate")}</Field>
        <Field label="Advice fee %">{num("adviceFee")}</Field>
        <Field label="Unit price">{num("unitPrice")}</Field>
        <Field label="Units held">{num("unitsHeld")}</Field>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-subtle">Projected</dt>
          <dd className="font-display text-lg tabular-nums">
            {zar(summary.projectedValue)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-subtle">Net growth</dt>
          <dd className="tabular-nums">{summary.netGrowthRate.toFixed(2)}%</dd>
        </div>
        <div>
          <dt className="text-xs text-subtle">Fees (illustrative)</dt>
          <dd className="tabular-nums">{zar(summary.feesRand)}</dd>
        </div>
        <div className="flex items-end">
          <Button type="submit">Save scenario</Button>
        </div>
      </dl>
    </form>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function DraftPanel({
  clientName,
  status,
  notes,
  documents,
  onSave,
}: {
  clientName: string;
  status: string;
  notes: string;
  documents: string;
  onSave: (title: string, content: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  async function run(kind: "advice" | "roa" | "follow-up") {
    setBusy(true);
    try {
      const result = await draftClientNote({
        data: { kind, clientName, status, notes, documents },
      });
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      const title =
        kind === "advice"
          ? "Advice summary draft"
          : kind === "roa"
            ? "ROA structure draft"
            : "Follow-up list";
      onSave(title, result.text);
      toast.success("Draft saved as a note");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-8 rounded-xl bg-surface p-4 shadow-[var(--shadow-border)]">
      <h2 className="font-display text-xl tracking-tight">Internal drafts</h2>
      <p className="mt-1 text-sm text-muted">
        Working notes only. Verify every figure against the product page.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="outline" disabled={busy} onClick={() => void run("advice")}>
          {busy && <Loader2 className="animate-spin" />}
          Advice summary
        </Button>
        <Button variant="outline" disabled={busy} onClick={() => void run("roa")}>
          ROA structure
        </Button>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void run("follow-up")}
        >
          Follow-up list
        </Button>
      </div>
    </div>
  );
}


/**
 * One list, not two.
 *
 * The desk has always had two ideas of a document: the vault on disk, which is
 * the FAIS record, and a browser-side list used for working notes. They were
 * shown as separate unjoined lists in the same tab, which makes "where did my
 * file go" inevitable — and worse, lets someone believe a document is filed
 * when it only exists in this browser.
 *
 * So they are merged and each row says where it actually lives. A row that is
 * only on this device is not filed, and says so.
 */
function Documents({
  clientId,
  local,
}: {
  clientId: string;
  local: { id: string; filename: string; docType: string; size: number; createdAt: string; text?: string }[];
}) {
  const [vault, setVault] = useState<
    { id: number; filename: string; doc_type: string }[]
  >([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "offline">("loading");

  useEffect(() => {
    let live = true;
    deskApi
      .vaultClient(clientId)
      .then((c) => {
        if (!live) return;
        setVault(c.documents ?? []);
        setState("ready");
      })
      .catch(() => live && setState("offline"));
    return () => {
      live = false;
    };
  }, [clientId]);

  if (openId !== null) {
    return <PdfWorkbench docId={openId} clientId={clientId} onClose={() => setOpenId(null)} />;
  }

  const filedNames = new Set(vault.map((d) => d.filename.toLowerCase()));
  const rows = [
    ...vault.map((d) => ({
      key: `vault-${d.id}`,
      filename: d.filename,
      docType: d.doc_type,
      where: "filed" as const,
      docId: d.id,
      detail: "",
    })),
    // Only the ones the vault does not already have, so a document filed
    // through the desk is not listed twice.
    ...local
      .filter((d) => !filedNames.has(d.filename.toLowerCase()))
      .map((d) => ({
        key: `local-${d.id}`,
        filename: d.filename,
        docType: d.docType,
        where: "device" as const,
        docId: null,
        detail: `${formatBytes(d.size)} · ${formatDate(d.createdAt)}`,
      })),
  ];

  return (
    <div className="mb-6">
      {state === "offline" && (
        <p className="mb-4 rounded-lg bg-surface px-4 py-3 text-sm text-muted shadow-[var(--shadow-border)]">
          The desk backend is not running, so filed documents cannot be listed or
          opened. Only what is held in this browser is shown. Start it with
          &ldquo;Start Backend Only.bat&rdquo;.
        </p>
      )}
      <ul className="space-y-2">
        {rows.map((row) => (
          <li
            key={row.key}
            className="rounded-lg bg-surface px-4 py-3 shadow-[var(--shadow-border)]"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm">{row.filename}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{row.docType}</Badge>
                {row.where === "filed" ? (
                  <span className="text-xs text-subtle">In the client file</span>
                ) : (
                  <span className="text-xs text-danger">On this device only</span>
                )}
                {row.docId !== null && row.filename.toLowerCase().endsWith(".pdf") && (
                  <Button variant="outline" onClick={() => setOpenId(row.docId)}>
                    Open
                  </Button>
                )}
              </div>
            </div>
            {row.detail && <p className="mt-1 text-xs text-subtle">{row.detail}</p>}
          </li>
        ))}
        {rows.length === 0 && state !== "loading" && (
          <li className="text-sm text-muted">No documents yet.</li>
        )}
      </ul>
      {rows.some((r) => r.where === "device") && (
        <p className="mt-3 text-xs text-muted">
          &ldquo;On this device only&rdquo; means the file is in this browser and{" "}
          <strong>not in the client&apos;s file on disk</strong>. It is not part of
          the record and will not survive clearing the browser. Upload it below to
          file it properly.
        </p>
      )}
    </div>
  );
}
