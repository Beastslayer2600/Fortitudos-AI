import type {
  Client,
  ClientDocument,
  ClientEmail,
  ClientNote,
  ClientProjection,
  ClientStatus,
  DocType,
  NoteType,
} from "./types.ts";
import { CLIENT_STATUSES, DOC_TYPES, NOTE_TYPES } from "./types.ts";
import { matchClients } from "./desk-chat.ts";
import { buildFnaDraft } from "./fna-form.ts";
import { briefToChatLines, buildOpsBrief } from "./ops-brief.ts";
import { loadLedger, saveLedger } from "./craft-ledger.ts";
import type { CraftLead } from "./craft.ts";
import { slug } from "./utils.ts";
import { clientFileLanguage } from "./crossover.ts";

export type DeskAgentAction =
  | { type: "select_client"; clientId?: string; nameQuery?: string }
  | {
      type: "update_client";
      clientId?: string;
      name?: string;
      email?: string;
      phone?: string;
      status?: ClientStatus;
    }
  | {
      type: "add_note";
      clientId?: string;
      noteType: NoteType;
      title: string;
      content: string;
    }
  | {
      type: "add_document";
      clientId?: string;
      filename: string;
      docType: DocType;
      text?: string;
    }
  | {
      type: "upsert_fna_facts";
      clientId?: string;
      facts: Record<string, string>;
      meetingDate?: string;
    }
  | {
      type: "save_fna_note";
      clientId?: string;
      title?: string;
    }
  | { type: "list_today" }
  | { type: "list_pending" }
  | {
      type: "schedule_followup";
      who?: string;
      whenLabel?: string;
      note?: string;
      line?: "fa" | "craft" | "drama";
    }
  | {
      type: "intake_lead";
      name?: string;
      city?: string;
      businessType?: string;
      note?: string;
    }
  | {
      /**
       * Act on a filed PDF belonging to the ACTIVE client. Every one of these
       * writes a new draft; none can change the document it reads. `docId` is
       * resolved against the active client's filed documents, so a wrong or
       * invented id fails rather than reaching another client's file.
       */
      type: "pdf_action";
      docId?: number | string;
      /** Match a document by filename when the adviser names it, not an id. */
      filename?: string;
      action?: "redact" | "annotate" | "stamp" | "extract" | "assemble" | "fill";
      /** redact */
      literals?: string[];
      patterns?: ("sa_id" | "account" | "tax")[];
      /** annotate */
      page?: number;
      text?: string;
      /** assemble */
      select?: string;
    }
  | {
      type: "create_invoice";
      who?: string;
      amount?: string;
      line?: "fa" | "craft";
      dueLabel?: string;
      memo?: string;
    };

export type DeskAgentResult = {
  thinking: string;
  reply: string;
  actions: DeskAgentAction[];
  activeClientId: string | null;
  fnaMarkdown?: string;
  applied: string[];
};

export type DeskAgentContext = {
  clients: Client[];
  documents: ClientDocument[];
  notes: ClientNote[];
  emails: ClientEmail[];
  projections: ClientProjection[];
  activeClientId: string | null;
  fnaFactLines: string[];
  recentMessages: { role: string; content: string }[];
  userMessage: string;
  sessions?: import("./types").DramaSession[];
  dropItems?: import("./types").DropItem[];
  /**
   * The active client's filed documents as the vault holds them, with the text
   * of any PDF that is open. This is what lets the adviser say "redact her ID
   * number" instead of clicking through the workbench.
   */
  vaultDocuments?: VaultDocument[];
};

export type VaultDocument = {
  id: number;
  filename: string;
  docType: string;
  clientId: string;
  /** Per-page text, present only for the document currently open. */
  pages?: { page: number; text: string }[];
};

/**
 * A PDF operation the agent asked for, resolved and scoped but not yet run.
 *
 * applyDeskActions stays synchronous and pure — the part worth testing is
 * which document an instruction resolves to and whose it is, not the HTTP.
 * The caller executes these.
 */
export type PdfRequest = {
  docId: number;
  clientId: string;
  filename: string;
  action: "redact" | "annotate" | "stamp" | "extract" | "assemble" | "fill";
  body: Record<string, unknown>;
};

export type DeskMutators = {
  updateClient: (id: string, patch: Partial<Client>) => void;
  addNote: (input: {
    clientId: string;
    noteType: NoteType;
    title: string;
    content: string;
  }) => void;
  addDocument: (input: {
    clientId: string;
    filename: string;
    docType: DocType;
    text?: string;
  }) => void;
};

function resolveClientId(
  action: { clientId?: string; nameQuery?: string },
  ctx: DeskAgentContext,
  fallback: string | null,
): string | null {
  if (action.clientId && ctx.clients.some((c) => c.id === action.clientId))
    return action.clientId;
  if (action.nameQuery) {
    const m = matchClients(action.nameQuery, ctx.clients);
    if (m[0]) return m[0].id;
  }
  return fallback;
}

export function applyDeskActions(
  actions: DeskAgentAction[],
  ctx: DeskAgentContext,
  mutators: DeskMutators,
): {
  applied: string[];
  activeClientId: string | null;
  fnaFactLines: string[];
  fnaMarkdown?: string;
  output?: string;
  pdfRequests?: PdfRequest[];
} {
  let activeClientId = ctx.activeClientId;
  let fnaFactLines = [...ctx.fnaFactLines];
  const applied: string[] = [];
  // `fnaMarkdown` IS the client's FNA draft: chat.tsx offers to save it as an
  // FNA note on the open client file. Only the FNA actions may write to it.
  // Everything else — the day's brief, a follow-up, an invoice — goes to
  // `output`, which is shown and never filed. Sharing one field meant asking
  // "what is on my plate today?" with a client open put other clients' names
  // and Craft lead names into that client's compliance record.
  let fnaMarkdown: string | undefined;
  let output: string | undefined;
  const pdfRequests: PdfRequest[] = [];
  const say = (block: string) => {
    output = (output ? output + "\n\n" : "") + block;
  };

  for (const action of actions) {
    if (action.type === "select_client") {
      const id = resolveClientId(action, ctx, activeClientId);
      if (id) {
        activeClientId = id;
        const name = ctx.clients.find((c) => c.id === id)?.name;
        applied.push(`Selected client ${name ?? id}`);
      } else {
        applied.push(`Could not select client (${action.nameQuery || action.clientId || "?"})`);
      }
      continue;
    }

    if (action.type === "update_client") {
      const id = resolveClientId(action, ctx, activeClientId);
      if (!id) {
        applied.push("update_client skipped \u2014 no client");
        continue;
      }
      const patch: Partial<Client> = {};
      if (action.name?.trim()) patch.name = action.name.trim();
      if (action.email !== undefined) patch.email = action.email.trim();
      if (action.phone !== undefined) patch.phone = action.phone.trim();
      if (action.status && (CLIENT_STATUSES as readonly string[]).includes(action.status))
        patch.status = action.status;
      if (Object.keys(patch).length) {
        mutators.updateClient(id, patch);
        activeClientId = id;
        applied.push(`Updated client ${id}: ${Object.keys(patch).join(", ")}`);
      }
      continue;
    }

    if (action.type === "add_note") {
      const id = resolveClientId(action, ctx, activeClientId);
      if (!id) {
        applied.push("add_note skipped \u2014 no client");
        continue;
      }
      const noteType = (NOTE_TYPES as readonly string[]).includes(action.noteType)
        ? action.noteType
        : "General";
      mutators.addNote({
        clientId: id,
        noteType: noteType as NoteType,
        title: action.title || "Desk note",
        content: action.content || "",
      });
      activeClientId = id;
      applied.push(`Added ${noteType} note`);
      continue;
    }

    if (action.type === "add_document") {
      const id = resolveClientId(action, ctx, activeClientId);
      if (!id) {
        applied.push("add_document skipped \u2014 no client");
        continue;
      }
      const docType = (DOC_TYPES as readonly string[]).includes(action.docType)
        ? action.docType
        : "Other";
      mutators.addDocument({
        clientId: id,
        filename: action.filename || "desk-entry.txt",
        docType: docType as DocType,
        text: action.text || "",
      });
      activeClientId = id;
      applied.push(`Filed document ${action.filename} as ${docType}`);
      continue;
    }

    if (action.type === "upsert_fna_facts") {
      const id = resolveClientId(action, ctx, activeClientId);
      if (!id) {
        applied.push("upsert_fna_facts skipped \u2014 no client");
        continue;
      }
      activeClientId = id;
      const lines = Object.entries(action.facts || {}).map(([k, v]) => `${k}: ${v}`);
      if (action.meetingDate) lines.push(`meeting_date: ${action.meetingDate}`);
      fnaFactLines = [...fnaFactLines, ...lines, ctx.userMessage].slice(-40);
      const client = ctx.clients.find((c) => c.id === id);
      if (client) {
        const draft = buildFnaDraft({
          client,
          documents: ctx.documents.filter((d) => d.clientId === id),
          notes: ctx.notes.filter((n) => n.clientId === id),
          emails: ctx.emails.filter((e) => e.clientId === id),
          projections: ctx.projections.filter((p) => p.clientId === id),
          chatTexts: fnaFactLines,
          meetingDate: action.meetingDate,
          adviserName: "Gert Fourie",
        });
        fnaMarkdown = draft.markdown;
        applied.push(`FNA draft updated (${draft.filledCount} filled / ${draft.blankCount} blank)`);
      }
      continue;
    }

    if (action.type === "save_fna_note") {
      const id = resolveClientId(action, ctx, activeClientId);
      if (!id) {
        applied.push("save_fna_note skipped \u2014 no client");
        continue;
      }
      const client = ctx.clients.find((c) => c.id === id);
      if (!client) continue;
      const draft = buildFnaDraft({
        client,
        documents: ctx.documents.filter((d) => d.clientId === id),
        notes: ctx.notes.filter((n) => n.clientId === id),
        emails: ctx.emails.filter((e) => e.clientId === id),
        projections: ctx.projections.filter((p) => p.clientId === id),
        chatTexts: fnaFactLines,
        adviserName: "Gert Fourie",
      });
      mutators.addNote({
        clientId: id,
        noteType: "FNA",
        title: action.title || `FNA intake draft \u2014 ${client.name}`,
        content: draft.markdown,
      });
      fnaMarkdown = draft.markdown;
      applied.push(`Saved FNA draft note on ${client.name}`);
      continue;
    }

    if (action.type === "list_today" || action.type === "list_pending") {
      const brief = buildOpsBrief({
        clients: ctx.clients,
        sessions: ctx.sessions ?? [],
        dropItems: ctx.dropItems ?? [],
      });
      applied.push(action.type === "list_today" ? "Listed today's brief" : "Listed pending items");
      say(briefToChatLines(brief));
      continue;
    }

    if (action.type === "schedule_followup") {
      const who = (action.who || "").trim() || "unassigned";
      const when = (action.whenLabel || "soon").trim();
      // No default line. Defaulting to "fa" meant a follow-up the model did not
      // label ran a fuzzy name match against advice clients — so a shop owner
      // whose name was close enough to a client's got a note written onto that
      // client's file. An unlabelled follow-up is logged, not filed.
      const line = action.line;
      const note = (action.note || "").trim();
      const title = `Follow-up \u00b7 ${who} \u00b7 ${when}`;
      const content = [`Line: ${line ?? "unspecified"}`, `When: ${when}`, note ? `Note: ${note}` : null, "(Stub) Full calendar write lands in a later ops store."].filter(Boolean).join("\n");
      if (line === "fa") {
        const id = resolveClientId({ nameQuery: who }, ctx, activeClientId);
        if (id) {
          mutators.addNote({ clientId: id, noteType: "Meeting", title, content });
          activeClientId = id;
          applied.push(`Scheduled follow-up note on client for ${when}`);
          continue;
        }
      }
      applied.push(`Follow-up logged (stub): ${title}`);
      say(content);
      continue;
    }

    if (action.type === "intake_lead") {
      const name = (action.name || "").trim();
      if (!name) {
        applied.push("intake_lead skipped \u2014 name required");
        continue;
      }
      // The backend refuses a lead brief carrying client-file language
      // (crossover.CLIENT_FILE, enforced in mockup_router.generate_for_lead).
      // This door had no such check, so an FNA or an ID number could be typed
      // straight into the Craft ledger — merging the two businesses in the one
      // direction the router was built to prevent.
      const smell = clientFileLanguage(`${name} ${action.note ?? ""} ${action.businessType ?? ""}`);
      if (smell) {
        applied.push(
          `intake_lead refused \u2014 that reads like a client file (${smell}). ` +
            "A Craft lead is a shop owner, not an advice client.",
        );
        continue;
      }
      const lead: CraftLead = {
        id: slug(name) + "-" + Date.now().toString(36),
        name,
        city: (action.city || "").trim(),
        type: (action.businessType || "").trim() || "business",
        address: "",
        phone: "",
        website: "",
        email: "",
        note: (action.note || "").trim(),
        touch: "untouched",
        photos: [],
        savedAt: new Date().toISOString(),
        source: "hand",
      };
      try {
        const book = loadLedger();
        saveLedger([lead, ...book]);
        applied.push(`Craft lead filed: ${name}`);
      } catch {
        applied.push(`Craft lead captured in memory only: ${name}`);
      }
      continue;
    }

    if (action.type === "pdf_action") {
      const client = activeClientId;
      if (!client) {
        applied.push("pdf_action skipped \u2014 no client is open");
        continue;
      }
      // Only this client's documents are even candidates. The id can come out
      // of a sentence, so being wrong must fail rather than reach a file.
      const mine = (ctx.vaultDocuments ?? []).filter((d) => d.clientId === client);
      let doc: VaultDocument | undefined;
      if (action.docId !== undefined && action.docId !== null && `${action.docId}` !== "") {
        doc = mine.find((d) => `${d.id}` === `${action.docId}`);
      } else if (action.filename) {
        const want = action.filename.toLowerCase();
        const hits = mine.filter((d) => d.filename.toLowerCase().includes(want));
        // An ambiguous name is refused, not guessed: acting on the wrong
        // document of the right client is still the wrong document.
        if (hits.length > 1) {
          applied.push(
            `pdf_action skipped \u2014 "${action.filename}" matches ${hits.length} documents: ` +
              hits.map((h) => h.filename).join(", "),
          );
          continue;
        }
        doc = hits[0];
      }
      if (!doc) {
        applied.push(
          "pdf_action skipped \u2014 no filed document of this client matched" +
            (action.filename ? ` "${action.filename}"` : ""),
        );
        continue;
      }

      const kind = action.action ?? "extract";
      const body: Record<string, unknown> = {};
      if (kind === "redact") {
        body.literals = action.literals ?? [];
        body.patterns = action.patterns ?? [];
        if (!(body.literals as string[]).length && !(body.patterns as string[]).length) {
          applied.push("pdf_action skipped \u2014 redact needs text or a pattern");
          continue;
        }
      } else if (kind === "annotate") {
        if (!action.text?.trim()) {
          applied.push("pdf_action skipped \u2014 annotate needs note text");
          continue;
        }
        body.notes = [{ page: action.page ?? 1, text: action.text }];
      } else if (kind === "stamp") {
        if (!action.text?.trim()) {
          applied.push("pdf_action skipped \u2014 stamp needs text");
          continue;
        }
        body.text = action.text;
      } else if (kind === "assemble") {
        if (!action.select?.trim()) {
          applied.push("pdf_action skipped \u2014 assemble needs a page selection");
          continue;
        }
        body.select = action.select;
      }

      pdfRequests.push({
        docId: doc.id,
        clientId: client,
        filename: doc.filename,
        action: kind,
        body,
      });
      applied.push(`Queued ${kind} on ${doc.filename}`);
      continue;
    }

    if (action.type === "create_invoice") {
      const who = (action.who || "client").trim();
      const amount = (action.amount || "").trim() || "TBD";
      const line = action.line || "craft";
      const due = (action.dueLabel || "").trim();
      const memo = (action.memo || "").trim();
      const block = ["INVOICE STUB (not yet in billing store)", `Who: ${who}`, `Line: ${line}`, `Amount: ${amount}`, due ? `Due: ${due}` : null, memo ? `Memo: ${memo}` : null].filter(Boolean).join("\n");
      applied.push(`Invoice stub for ${who} \u00b7 ${amount}`);
      say(block);
      continue;
    }
  }

  return { applied, activeClientId, fnaFactLines, fnaMarkdown, output, pdfRequests };
}

export function parseAgentJson(text: string): {
  thinking: string;
  reply: string;
  actions: DeskAgentAction[];
} | null {
  try {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start < 0 || end < 0) return null;
    const parsed = JSON.parse(text.slice(start, end + 1)) as {
      thinking?: string;
      reply?: string;
      actions?: DeskAgentAction[];
    };
    if (!parsed.reply) return null;
    return {
      thinking: String(parsed.thinking || ""),
      reply: String(parsed.reply),
      actions: Array.isArray(parsed.actions) ? parsed.actions : [],
    };
  } catch {
    return null;
  }
}

export function buildContextBlock(ctx: DeskAgentContext): string {
  const list = ctx.clients
    .map((c) => {
      const nDoc = ctx.documents.filter((d) => d.clientId === c.id).length;
      const nNote = ctx.notes.filter((n) => n.clientId === c.id).length;
      return `- ${c.id} | ${c.name} | ${c.status} | ${c.email || "no email"} | ${c.phone || "no phone"} | ${nDoc} docs | ${nNote} notes`;
    })
    .join("\n");

  const active = ctx.activeClientId
    ? ctx.clients.find((c) => c.id === ctx.activeClientId)
    : null;

  let activeBlock = "(none selected)";
  if (active) {
    const docs = ctx.documents.filter((d) => d.clientId === active.id);
    const notes = ctx.notes.filter((n) => n.clientId === active.id);
    const emails = ctx.emails.filter((e) => e.clientId === active.id);
    const projs = ctx.projections.filter((p) => p.clientId === active.id);
    activeBlock = [
      `id: ${active.id}`,
      `name: ${active.name}`,
      `status: ${active.status}`,
      `email: ${active.email}`,
      `phone: ${active.phone}`,
      `documents:`,
      ...docs.map((d) => `  - [${d.docType}] ${d.filename}: ${(d.text || "").slice(0, 280)}`),
      `notes:`,
      ...notes.map((n) => `  - [${n.noteType}] ${n.title}: ${n.content.slice(0, 280)}`),
      `emails:`,
      ...emails.map((e) => `  - ${e.subject} (${e.status})`),
      `projections:`,
      ...projs.map((p) => `  - ${p.name}: current R${p.inputs.currentValue}, monthly R${p.inputs.monthlyContribution}`),
      `fna_fact_lines:`,
      ...ctx.fnaFactLines.slice(-30).map((l) => `  - ${l}`),
    ].join("\n");
  }

  // Documents as the vault holds them, which is what pdf_action operates on.
  // Only this client's are listed: the agent cannot name what it cannot see.
  const vault = (ctx.vaultDocuments ?? []).filter(
    (d) => !!active && d.clientId === active.id,
  );
  const vaultBlock = vault.length
    ? vault
        .map((d) => {
          const head = `  - id ${d.id} | ${d.filename} | ${d.docType}`;
          if (!d.pages?.length) return head;
          // The open document's text, so "redact her ID number" can be acted on.
          const body = d.pages
            .map((pg) => `      p${pg.page}: ${pg.text.slice(0, 1400)}`)
            .join("\n");
          return `${head}  (OPEN)\n${body}`;
        })
        .join("\n")
    : "  (none filed, or the backend is not running)";

  const history = ctx.recentMessages
    .slice(-8)
    .map((m) => `${m.role}: ${m.content.slice(0, 1200)}`)
    .join("\n\n");

  return `CLIENTS ON DESK:\n${list || "(none)"}\n\nACTIVE CLIENT:\n${activeBlock}\n\nFILED DOCUMENTS (pdf_action works on these):\n${vaultBlock}\n\nRECENT CHAT:\n${history || "(empty)"}\n\nADVISER MESSAGE:\n${ctx.userMessage}`;
}

export const DESK_AGENT_SYSTEM = `You are the Fortitudo desk agent for a South African financial adviser (FAIS). You reason carefully, then edit the desk records when asked.

You can THINK and EDIT FILES on this desk via actions. The desk stores clients, documents, notes, emails, projections, and FNA intake drafts in the browser workspace.

Rules:
1. Reason in "thinking" first: what the adviser wants, which client, what is already on file, what is missing, what to change.
2. Never invent product figures, premiums, waiting periods, or benefit %. If unknown, say so and leave blank or ask.
3. Prefer editing the file when the adviser states facts ("his net is 55k", "update email", "save the FNA").
4. When prepping a meeting or FNA, call upsert_fna_facts with structured facts extracted from the message AND known file data you restate only if present in ACTIVE CLIENT.
5. select_client before other edits when the client is named.
6. status must be one of: Intake, FNA, Advice, Implementation, Review.
7. noteType must be one of: General, FNA, Advice, Meeting.
8. docType must be one of: FICA / Identity, RPQ, Signed FNA, Advice Report, Quote, ROA, Correspondence, Other.
9. reply is for the adviser: clear, structured, calm. No hype. Mention what you changed.
10. This is internal working material, not advice to the client.
11. PDF work uses pdf_action on a document listed under FILED DOCUMENTS. Every
    one writes a NEW draft; the filed original is never changed, so say "saved a
    redacted copy", never "redacted the document". Name the document by filename
    if you are unsure of the id, and never invent an id.
12. You cannot rewrite the words inside a PDF — it is a page format, not a text
    document. If asked to change wording, use action "extract" to produce an
    editable markdown draft and say that is what you did.
13. A scanned PDF has no text: it can be annotated, stamped and reordered, but
    not read or redacted. Say so rather than trying.

Respond with JSON ONLY (no markdown fence):
{
  "thinking": "step-by-step reasoning",
  "reply": "message shown to the adviser",
  "actions": [ /* zero or more actions */ ]
}

Action schemas:
{ "type": "select_client", "clientId": "optional", "nameQuery": "optional" }
{ "type": "update_client", "clientId": "optional", "name": "optional", "email": "optional", "phone": "optional", "status": "optional" }
{ "type": "add_note", "clientId": "optional", "noteType": "FNA|Meeting|General|Advice", "title": "...", "content": "..." }
{ "type": "add_document", "clientId": "optional", "filename": "...", "docType": "...", "text": "optional extract" }
{ "type": "upsert_fna_facts", "clientId": "optional", "meetingDate": "optional", "facts": { "net_salary": "55000", "occupation": "Engineer", ... } }
{ "type": "save_fna_note", "clientId": "optional", "title": "optional" }
{ "type": "pdf_action", "docId": 12, "filename": "optional instead of docId", "action": "redact|annotate|stamp|extract|assemble", "literals": ["exact text"], "patterns": ["sa_id","account","tax"], "page": 1, "text": "note or stamp text", "select": "1,3-5" }
{ "type": "list_today" }
{ "type": "list_pending" }
{ "type": "schedule_followup", "who": "optional", "whenLabel": "optional", "note": "optional", "line": "fa|craft|drama" }
{ "type": "intake_lead", "name": "...", "city": "optional", "businessType": "optional", "note": "optional" }
{ "type": "create_invoice", "who": "optional", "amount": "optional", "line": "fa|craft", "dueLabel": "optional", "memo": "optional" }

Use list_today / list_pending when the adviser asks what is on the plate, what is pending, or for a morning brief.
Use schedule_followup for reminders; intake_lead for Craft/web-design shops; create_invoice only as a stub until billing ships.

FNA fact keys (use snake_case): net_salary, gross_salary, spouse_net_salary, occupation, employer, id_number, date_of_birth, residential_address, marital_status, smoker, dependants, number_of_children, housing, transport, medical_scheme, target_retirement_age, attitude_to_risk, top_priority_1, top_priority_2, existing_life, income_protection, etc. \u2014 any label that maps to the intake form.
`;
