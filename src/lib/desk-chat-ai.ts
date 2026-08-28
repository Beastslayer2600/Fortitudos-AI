import { createServerFn } from "@tanstack/react-start";
import {
  buildContextBlock,
  DESK_AGENT_SYSTEM,
  parseAgentJson,
  type DeskAgentAction,
} from "./desk-agent";
import { llmChat, llmComplete, probeLlm } from "./llm";

/** Polish a grounded meeting pack — never invent product figures. */
export const refineMeetingPrep = createServerFn({ method: "POST" })
  .validator(
    (input: {
      clientName: string;
      status: string;
      whenLabel: string;
      channel: string;
      packMarkdown: string;
      userMessage: string;
    }) => input,
  )
  .handler(async ({ data }) => {
    const system = `You are an internal desk assistant for a South African financial adviser (FAIS). You help prep meetings and FNA working notes.

Rules:
- Use ONLY facts present in the provided pack. Do not invent returns, premiums, benefit %, waiting periods, or product terms.
- If something is missing, say it is missing and list it as a gap to close in the meeting.
- This is an internal working note, not advice to a client.
- Keep a calm, structured tone. Short headings. Actionable checklist.
- End with: "Verify against filed documents and the product index before the meeting. Advice remains yours under FAIS."`;

    const user = `Adviser said: ${data.userMessage}

Client: ${data.clientName} (status ${data.status})
Channel: ${data.channel}
When: ${data.whenLabel}

Grounded pack:
${data.packMarkdown.slice(0, 12000)}

Write a concise meeting-ready brief the adviser can scan in 2 minutes, then a short FNA field checklist of what to confirm live.`;

    const result = await llmComplete(system, user, {
      maxTokens: 700,
      temperature: 0.2,
    });
    if (!result.ok) return { ok: false as const, error: result.error };
    return { ok: true as const, text: result.text, provider: result.provider };
  });

export const getLlmStatus = createServerFn({ method: "GET" }).handler(
  async () => probeLlm(),
);

export const runDeskAgent = createServerFn({ method: "POST" })
  .validator(
    (input: {
      userMessage: string;
      activeClientId: string | null;
      fnaFactLines: string[];
      recentMessages: { role: string; content: string }[];
      clients: {
        id: string;
        name: string;
        email: string;
        phone: string;
        status: string;
      }[];
      documents: {
        clientId: string;
        filename: string;
        docType: string;
        text: string;
      }[];
      notes: {
        clientId: string;
        noteType: string;
        title: string;
        content: string;
      }[];
      emails: { clientId: string; subject: string; status: string }[];
      projections: {
        clientId: string;
        name: string;
        currentValue: number;
        monthlyContribution: number;
      }[];
    }) => input,
  )
  .handler(async ({ data }) => {
    const ctxBlock = buildContextBlock({
      userMessage: data.userMessage,
      activeClientId: data.activeClientId,
      fnaFactLines: data.fnaFactLines,
      recentMessages: data.recentMessages,
      clients: data.clients.map((c) => ({
        ...c,
        status: c.status as import("./types").ClientStatus,
        createdAt: "",
        updatedAt: "",
      })),
      documents: data.documents.map((d) => ({
        id: "",
        clientId: d.clientId,
        filename: d.filename,
        docType: d.docType as import("./types").DocType,
        contentType: "text/plain",
        size: d.text.length,
        text: d.text,
        createdAt: "",
      })),
      notes: data.notes.map((n) => ({
        id: "",
        clientId: n.clientId,
        noteType: n.noteType as import("./types").NoteType,
        title: n.title,
        content: n.content,
        createdAt: "",
      })),
      emails: data.emails.map((e) => ({
        id: "",
        clientId: e.clientId,
        direction: "Draft" as const,
        sender: "",
        recipient: "",
        subject: e.subject,
        body: "",
        status: e.status as "Draft" | "Logged",
        createdAt: "",
      })),
      projections: data.projections.map((p) => ({
        id: "",
        clientId: p.clientId,
        name: p.name,
        inputs: {
          currentValue: p.currentValue,
          monthlyContribution: p.monthlyContribution,
          lumpSum: 0,
          years: 10,
          growthRate: 0,
          adviceFee: 0,
          unitPrice: 0,
          unitsHeld: 0,
        },
        summary: {
          openingValue: p.currentValue,
          netGrowthRate: 0,
          projectedValue: p.currentValue,
          contributions: 0,
          growthRand: 0,
          feesRand: 0,
        },
        createdAt: "",
      })),
    });

    // Nudge local models to emit pure JSON
    const system = `${DESK_AGENT_SYSTEM}

IMPORTANT for local models: Reply with a single JSON object only. No markdown fences, no text before or after the JSON.`;

    const result = await llmChat(
      [
        { role: "system", content: system },
        { role: "user", content: ctxBlock },
      ],
      { maxTokens: 1600, temperature: 0.2 },
    );

    if (!result.ok) {
      return {
        ok: false as const,
        error: result.error,
        provider: result.provider,
        thinking: "",
        reply: "",
        actions: [] as DeskAgentAction[],
      };
    }

    const parsed = parseAgentJson(result.text);
    if (!parsed) {
      // Second pass: ask model to convert to JSON if it rambled
      const fix = await llmChat(
        [
          {
            role: "system",
            content:
              "Convert the assistant draft into the exact JSON schema: {\"thinking\":string,\"reply\":string,\"actions\":array}. JSON only.",
          },
          { role: "user", content: result.text.slice(0, 6000) },
        ],
        { maxTokens: 1200, temperature: 0.1 },
      );
      const parsed2 = fix.ok ? parseAgentJson(fix.text) : null;
      if (parsed2) {
        return {
          ok: true as const,
          thinking: parsed2.thinking,
          reply: parsed2.reply,
          actions: parsed2.actions,
          provider: result.provider,
        };
      }
      return {
        ok: true as const,
        thinking: "(model did not return structured actions)",
        reply: result.text,
        actions: [] as DeskAgentAction[],
        provider: result.provider,
      };
    }

    return {
      ok: true as const,
      thinking: parsed.thinking,
      reply: parsed.reply,
      actions: parsed.actions,
      provider: result.provider,
    };
  });
