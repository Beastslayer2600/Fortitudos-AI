import { useEffect, useRef, useState, type FormEvent } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ClipboardCopy,
  Loader2,
  MessagesSquare,
  Save,
  Send,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { applyDeskActions, type DeskAgentAction, type VaultDocument } from "@/lib/desk-agent";
import { deskApi } from "@/lib/desk-api";
import { getLlmStatus, runDeskAgent } from "@/lib/desk-chat-ai";
import { matchClients, parseDeskIntent } from "@/lib/desk-chat";
import { buildFnaDraft } from "@/lib/fna-form";
import { buildMeetingPrep } from "@/lib/meeting-prep";
import { useFortitudo } from "@/lib/store";
import { formatDate } from "@/lib/utils";

export const Route = createFileRoute("/chat")({ component: ChatPage });

const EXAMPLES = [
  "Teams meeting with Pieter tomorrow at 14:00 — prep the FNA and save a draft note",
  "For Ayesha: net salary 45000, spouse earns 30000, two kids, retire at 60, risk balanced. Update the FNA form and set status to FNA.",
  "Change Pieter's email to pieter.new@example.co.za and add a meeting note that we still need the policy number",
];

function ChatPage() {
  const clients = useFortitudo((s) => s.clients);
  const documents = useFortitudo((s) => s.documents);
  const notes = useFortitudo((s) => s.notes);
  const emails = useFortitudo((s) => s.emails);
  const projections = useFortitudo((s) => s.projections);
  const chatMessages = useFortitudo((s) => s.chatMessages);
  const addChatMessage = useFortitudo((s) => s.addChatMessage);
  const clearChat = useFortitudo((s) => s.clearChat);
  const addNote = useFortitudo((s) => s.addNote);
  const updateClient = useFortitudo((s) => s.updateClient);
  const addDocument = useFortitudo((s) => s.addDocument);

  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [showThinking, setShowThinking] = useState(true);
  const [lastThinking, setLastThinking] = useState("");
  const [providerLabel, setProviderLabel] = useState("");
  const [llmStatus, setLlmStatus] = useState<string>("Checking local AI…");
  const [lastPrep, setLastPrep] = useState<{
    clientId: string;
    markdown: string;
    title: string;
  } | null>(null);
  const [activeClientId, setActiveClientId] = useState<string | null>(null);
  /**
   * The active client's filed documents. Loaded when the client changes so the
   * agent can be told what exists — and, just as importantly, so it can only
   * name documents belonging to the client actually on the desk.
   */
  const vaultDocs = useRef<VaultDocument[]>([]);
  const fnaFactLines = useRef<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void getLlmStatus()
      .then((s) => {
        if (s.preferred === "ollama") {
          setLlmStatus(`Local Ollama · ${s.ollama.model} · ${s.ollama.detail}`);
        } else if (s.preferred === "xai") {
          setLlmStatus(`Cloud xAI · ${s.xai.detail} (Ollama: ${s.ollama.detail})`);
        } else {
          setLlmStatus(
            `No model ready — ${s.ollama.detail}. Start Ollama and: ollama pull ${s.ollama.model}`,
          );
        }
      })
      .catch(() => setLlmStatus("Could not probe LLM status"));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages.length, busy, lastThinking]);

  useEffect(() => {
    let live = true;
    if (!activeClientId) {
      vaultDocs.current = [];
      return;
    }
    deskApi
      .vaultClient(activeClientId)
      .then((c) => {
        if (!live) return;
        vaultDocs.current = (c.documents ?? []).map((d) => ({
          id: d.id,
          filename: d.filename,
          docType: d.doc_type,
          clientId: activeClientId,
        }));
      })
      // The desk works without the backend; it just cannot touch filed PDFs.
      .catch(() => {
        if (live) vaultDocs.current = [];
      });
    return () => {
      live = false;
    };
  }, [activeClientId]);

  async function handleSend(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;
    setInput("");
    addChatMessage({ role: "user", content: text });
    setBusy(true);
    setLastThinking("");

    try {
      const recent = useFortitudo
        .getState()
        .chatMessages.slice(-10)
        .map((m) => ({ role: m.role, content: m.content }));

      const agent = await runDeskAgent({
        data: {
          userMessage: text,
          activeClientId,
          fnaFactLines: fnaFactLines.current,
          recentMessages: recent,
          clients: clients.map((c) => ({
            id: c.id,
            name: c.name,
            email: c.email,
            phone: c.phone,
            status: c.status,
          })),
          documents: documents.map((d) => ({
            clientId: d.clientId,
            filename: d.filename,
            docType: d.docType,
            text: d.text.slice(0, 800),
          })),
          notes: notes.map((n) => ({
            clientId: n.clientId,
            noteType: n.noteType,
            title: n.title,
            content: n.content.slice(0, 800),
          })),
          emails: emails.map((e) => ({
            clientId: e.clientId,
            subject: e.subject,
            status: e.status,
          })),
          projections: projections.map((p) => ({
            clientId: p.clientId,
            name: p.name,
            currentValue: p.inputs.currentValue,
            monthlyContribution: p.inputs.monthlyContribution,
          })),
        },
      });

      if (agent.ok) {
        setLastThinking(agent.thinking || "");
        if ("provider" in agent && agent.provider) {
          setProviderLabel(String(agent.provider));
        }

        const state = useFortitudo.getState();
        const applied = applyDeskActions(
          agent.actions as DeskAgentAction[],
          {
            userMessage: text,
            activeClientId,
            fnaFactLines: fnaFactLines.current,
            recentMessages: recent,
            clients: state.clients,
            documents: state.documents,
            notes: state.notes,
            emails: state.emails,
            projections: state.projections,
            vaultDocuments: vaultDocs.current,
          },
          {
            updateClient,
            addNote,
            addDocument,
          },
        );

        if (applied.activeClientId) setActiveClientId(applied.activeClientId);
        fnaFactLines.current = applied.fnaFactLines;

        // Only a real FNA draft becomes a saveable client note. `output` is
        // desk chatter — the day's brief, a follow-up, an invoice stub — and
        // filing that on a client file would put other clients' names and
        // Craft lead names into a regulated record.
        if (applied.fnaMarkdown && applied.activeClientId) {
          const c = state.clients.find((x) => x.id === applied.activeClientId);
          setLastPrep({
            clientId: applied.activeClientId,
            markdown: applied.fnaMarkdown,
            title: `FNA intake draft — ${c?.name ?? "client"}`,
          });
        }

        let reply = agent.reply;
        if (applied.applied.length) {
          reply += `\n\n—\n**File changes:**\n${applied.applied.map((a) => `· ${a}`).join("\n")}`;
        }
        // PDF operations are HTTP, so applyDeskActions resolved and scoped
        // them and left them for us to run. Each writes a new draft; none can
        // change the document it read.
        for (const req of applied.pdfRequests ?? []) {
          try {
            const result = await deskApi.pdfAction(
              req.docId,
              req.action,
              req.body,
              req.clientId,
            );
            const removed = result.removed?.length
              ? ` Removed: ${result.removed.join(", ")}.`
              : "";
            applied.applied.push(
              `${req.action} on ${req.filename} → saved ${result.saved_as}.${removed}`,
            );
          } catch (e) {
            applied.applied.push(
              `${req.action} on ${req.filename} failed: ${
                e instanceof Error ? e.message : String(e)
              }`,
            );
          }
        }

        if (applied.output) {
          reply += `\n\n---\n${applied.output}`;
        }
        if (applied.fnaMarkdown) {
          reply += `\n\n---\n### FNA intake draft\n${applied.fnaMarkdown}`;
        }

        addChatMessage({
          role: "assistant",
          kind: "general",
          clientId: applied.activeClientId ?? activeClientId ?? undefined,
          content: reply,
        });
        return;
      }

      // Model unreachable — show real error, then weak offline fallback
      const errMsg =
        "error" in agent && agent.error
          ? agent.error
          : "No local or cloud model available";
      setLastThinking(errMsg);
      toast.error("Local AI not ready", { description: errMsg });
      await offlineFallback(text, errMsg);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Chat failed");
      addChatMessage({
        role: "assistant",
        kind: "system",
        content:
          "Something went wrong talking to the desk agent. Ensure Ollama is running (ollama serve) or set XAI_API_KEY.",
      });
    } finally {
      setBusy(false);
    }
  }

  async function offlineFallback(text: string, reason: string) {
    const intent = parseDeskIntent(text);
    toast.message("Using offline rules only", {
      description: reason,
    });

    if (intent.kind === "fna_form" || intent.kind === "meeting_prep") {
      const q = intent.clientQuery;
      const matches = matchClients(q, clients);
      const client =
        matches[0] ||
        (activeClientId
          ? clients.find((c) => c.id === activeClientId)
          : undefined);
      if (!client) {
        addChatMessage({
          role: "assistant",
          content: `Name a client on this desk.\n\n${reason}\n\nClients: ${clients.map((c) => c.name).join(", ") || "(none)"}`,
        });
        return;
      }
      setActiveClientId(client.id);
      fnaFactLines.current = [...fnaFactLines.current, text].slice(-40);
      const draft = buildFnaDraft({
        client,
        documents: documents.filter((d) => d.clientId === client.id),
        notes: notes.filter((n) => n.clientId === client.id),
        emails: emails.filter((e) => e.clientId === client.id),
        projections: projections.filter((p) => p.clientId === client.id),
        chatTexts: fnaFactLines.current,
        adviserName: "Gert Fourie",
      });
      setLastPrep({
        clientId: client.id,
        markdown: draft.markdown,
        title: `FNA intake draft — ${client.name}`,
      });

      if (intent.kind === "meeting_prep") {
        const pack = buildMeetingPrep({
          client,
          documents: documents.filter((d) => d.clientId === client.id),
          notes: notes.filter((n) => n.clientId === client.id),
          emails: emails.filter((e) => e.clientId === client.id),
          projections: projections.filter((p) => p.clientId === client.id),
          whenLabel: intent.whenLabel,
          channel: intent.channel,
        });
        addChatMessage({
          role: "assistant",
          clientId: client.id,
          content: `${pack.summaryMarkdown}\n\n${draft.markdown}`,
        });
        return;
      }

      addChatMessage({
        role: "assistant",
        clientId: client.id,
        content: draft.markdown,
      });
      return;
    }

    addChatMessage({
      role: "assistant",
      content: [
        "Desk agent needs a local model (preferred) or xAI.",
        "",
        reason,
        "",
        "**Local setup**",
        "1. ollama serve",
        "2. ollama pull qwen2.5:7b",
        "3. Restart Fortitudo Desk",
        "",
        "Optional: set OLLAMA_MODEL to a model you already have (e.g. llama3.2:3b).",
      ].join("\n"),
    });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void handleSend(input);
  }

  function savePrep() {
    if (!lastPrep) return;
    addNote({
      clientId: lastPrep.clientId,
      noteType: "FNA",
      title: lastPrep.title,
      content: lastPrep.markdown,
    });
    toast.success("Saved FNA draft on the client file");
  }

  async function copyDraft() {
    if (!lastPrep) return;
    try {
      await navigator.clipboard.writeText(lastPrep.markdown);
      toast.success("Copied");
    } catch {
      toast.error("Could not copy");
    }
  }

  const activeName = clients.find((c) => c.id === activeClientId)?.name;

  return (
    <div className="mx-auto flex h-[calc(100dvh-0px)] max-w-3xl flex-col px-5 py-6 md:px-10 md:py-8">
      <div className="shrink-0">
        <p className="text-[11px] tracking-[0.22em] text-muted uppercase">
          Adviser desk · local AI
        </p>
        <div className="mt-1 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl tracking-tight md:text-4xl">
              Chat
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted">
              Desk agent runs on <strong className="font-medium text-fg/80">Ollama</strong>{" "}
              on this PC (reasoning + file edits). Falls back to xAI only if a key
              is set and Ollama is down.
            </p>
            <p className="mt-2 text-xs text-subtle">{llmStatus}</p>
            {activeName && (
              <p className="mt-1 text-xs text-subtle">Active client: {activeName}</p>
            )}
            {providerLabel && (
              <p className="mt-1 text-xs text-subtle">Last reply via: {providerLabel}</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowThinking((v) => !v)}
            >
              {showThinking ? "Hide thinking" : "Show thinking"}
            </Button>
            {lastPrep && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void copyDraft()}
                >
                  <ClipboardCopy className="size-3.5" />
                  Copy
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={savePrep}>
                  <Save className="size-3.5" />
                  Save FNA
                </Button>
              </>
            )}
            {chatMessages.length > 0 && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  clearChat();
                  setLastPrep(null);
                  setActiveClientId(null);
                  setLastThinking("");
                  fnaFactLines.current = [];
                }}
              >
                Clear
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
        {chatMessages.length === 0 && (
          <div className="rounded-xl bg-surface px-5 py-10 text-center shadow-[var(--shadow-border)]">
            <MessagesSquare className="mx-auto size-8 text-muted" />
            <p className="mt-4 text-sm text-muted">Try a full instruction</p>
            <div className="mt-4 flex flex-col gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  className="rounded-md bg-elevated px-3 py-2.5 text-left text-sm text-muted shadow-[var(--shadow-border)] hover:text-fg"
                  onClick={() => void handleSend(ex)}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {chatMessages.map((m) => (
          <div
            key={m.id}
            className={
              m.role === "user"
                ? "ml-8 rounded-xl bg-elevated px-4 py-3 text-sm shadow-[var(--shadow-border)]"
                : "mr-4 rounded-xl bg-surface px-4 py-3 text-sm shadow-[var(--shadow-border)]"
            }
          >
            <div className="mb-1 flex items-center justify-between gap-2 text-[11px] text-subtle">
              <span>{m.role === "user" ? "You" : "Desk agent"}</span>
              <span>{formatDate(m.createdAt)}</span>
            </div>
            <div className="whitespace-pre-wrap leading-relaxed text-fg/90">
              {m.content}
            </div>
            {m.clientId && (
              <Link
                to="/clients/$clientId"
                params={{ clientId: m.clientId }}
                className="mt-3 inline-block text-xs text-accent hover:underline"
              >
                Open client file →
              </Link>
            )}
          </div>
        ))}

        {showThinking && lastThinking && (
          <details
            open
            className="rounded-lg border border-border/60 bg-elevated/40 px-3 py-2 text-xs text-subtle"
          >
            <summary className="cursor-pointer text-muted">Agent thinking</summary>
            <pre className="mt-2 whitespace-pre-wrap font-sans leading-relaxed">
              {lastThinking}
            </pre>
          </details>
        )}

        {busy && (
          <div className="flex items-center gap-2 text-sm text-muted">
            <Loader2 className="size-4 animate-spin" />
            Talking to local model / applying file edits…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="mt-4 shrink-0 border-t border-border pt-4"
      >
        <label htmlFor="desk-chat" className="sr-only">
          Message
        </label>
        <Textarea
          id="desk-chat"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Reason with the file: update fields, prep FNA, save notes…"
          className="min-h-[88px]"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSend(input);
            }
          }}
        />
        <div className="mt-2 flex justify-end">
          <Button type="submit" disabled={busy || !input.trim()}>
            {busy ? <Loader2 className="animate-spin" /> : <Send />}
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}
