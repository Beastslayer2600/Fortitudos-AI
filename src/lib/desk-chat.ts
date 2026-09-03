import type { Client } from "./types.ts";

export type DeskIntent =
  | {
      kind: "meeting_prep";
      clientQuery: string;
      whenLabel: string;
      channel: string;
      wantsFna: boolean;
    }
  | {
      kind: "fna_form";
      clientQuery: string;
      factText: string;
    }
  | { kind: "client_lookup"; clientQuery: string }
  | { kind: "general"; text: string };

const CHANNEL_RE =
  /\b(teams|zoom|meet|google meet|phone|call|whatsapp|in[- ]person|office|video)\b/i;

const TIME_RE =
  /\b(?:(?:today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?|\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}[hH]\d{0,2}|at\s+\d{1,2}(?::\d{2})?)/i;

const MEETING_RE =
  /\b(meeting|meet with|teams with|call with|prep(?:are)?(?:\s+for)?|get me ready|brief(?:ing)?)\b/i;

const FNA_FORM_RE =
  /\b(fill|complete|prep(?:are)?|update|draft)\b.*\b(fna|intake|needs analysis)\b|\bfna\s+form\b|\bintake form\b|\bfor the fna\b|\bput (?:this|these) (?:on|in) (?:the )?fna\b/i;

export function parseDeskIntent(raw: string): DeskIntent {
  const text = raw.trim();
  const lower = text.toLowerCase();

  // Explicit FNA form fill takes priority when facts are being dumped
  if (FNA_FORM_RE.test(text) || looksLikeFactDump(text)) {
    return {
      kind: "fna_form",
      clientQuery: extractClientQuery(text),
      factText: text,
    };
  }

  const channelMatch = text.match(CHANNEL_RE);
  const channel = channelMatch
    ? channelMatch[1].replace(/google meet/i, "Google Meet")
    : /teams/i.test(text)
      ? "Microsoft Teams"
      : "meeting";

  const whenMatch = text.match(TIME_RE);
  const whenLabel = whenMatch ? whenMatch[0].trim() : "time not specified";

  const wantsFna = /\bfna\b|needs analysis|prep(?:are)?(?:\s+the)?\s+fna/i.test(
    text,
  );

  const isMeeting =
    MEETING_RE.test(text) ||
    CHANNEL_RE.test(text) ||
    (/\bwith\b.+/i.test(text) && wantsFna);

  if (isMeeting || (wantsFna && !looksLikeFactDump(text))) {
    const clientQuery = extractClientQuery(text);
    return {
      kind: "meeting_prep",
      clientQuery,
      whenLabel,
      channel: /teams/i.test(channel) ? "Microsoft Teams" : channel,
      wantsFna: wantsFna || true,
    };
  }

  if (/\b(who is|show|open|find)\b/i.test(lower)) {
    return { kind: "client_lookup", clientQuery: extractClientQuery(text) };
  }

  // Follow-up fact lines while an FNA draft is in play are handled in the UI
  // via fna_form when the message has structured facts.
  if (looksLikeFactDump(text)) {
    return {
      kind: "fna_form",
      clientQuery: extractClientQuery(text),
      factText: text,
    };
  }

  return { kind: "general", text };
}

function looksLikeFactDump(text: string): boolean {
  const lines = text.split(/\n/).filter((l) => l.trim());
  const kv = lines.filter((l) =>
    /^\s*[A-Za-z][A-Za-z0-9 /&()%._-]{1,40}\s*[:=]\s*.+/.test(l),
  ).length;
  if (kv >= 2) return true;
  if (
    /net salary|gross salary|spouse|dependant|retirement age|risk (?:profile|attitude)|medical aid|bond|TFSA/i.test(
      text,
    ) &&
    text.length > 60
  )
    return true;
  return false;
}

function extractClientQuery(text: string): string {
  const forMatch = text.match(
    /\b(?:for|client)\s+([A-Za-z][A-Za-z\s'-]{1,50}?)(?:\s*[—\-:]|\s+fna|\s+form|\s+intake|[.?!,]|$)/i,
  );
  if (forMatch) return forMatch[1].trim();

  const withMatch = text.match(
    /\bwith\s+([A-Za-z][A-Za-z\s'-]{1,60}?)(?:\s+(?:at|on|tomorrow|today|for|via|on teams|teams|zoom)|[.?!,]|$)/i,
  );
  if (withMatch) return withMatch[1].trim();

  const meetMatch = text.match(
    /\b(?:meeting|call|prep(?:are)?(?:\s+for)?)\s+([A-Za-z][A-Za-z\s'-]{1,40}?)(?:\s+(?:at|on|tomorrow|today)|[.?!,]|$)/i,
  );
  if (meetMatch) return meetMatch[1].trim();

  const names = text.match(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/);
  if (names) return names[0].trim();

  return "";
}

export function matchClients(query: string, clients: Client[]): Client[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];

  const tokens = q.split(/\s+/).filter(Boolean);

  const scored = clients
    .map((c) => {
      const name = c.name.toLowerCase();
      const parts = name.split(/\s+/);
      let score = 0;
      if (name === q) score += 100;
      if (name.includes(q)) score += 40;
      for (const t of tokens) {
        if (parts.some((p) => p.startsWith(t))) score += 15;
        if (name.includes(t)) score += 8;
      }
      if (parts[0] && tokens[0] && parts[0] === tokens[0]) score += 25;
      return { c, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.map((x) => x.c);
}
