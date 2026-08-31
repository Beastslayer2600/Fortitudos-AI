/**
 * Daily operations brief — aggregates what needs attention now.
 * Stubs for calendar/invoices; live data from clients, drama, craft ledger.
 */
import { loadLedger } from "./craft-ledger";
import type { CraftLead } from "./craft";
import type { Client, DramaSession, DropItem } from "./types";

export type BriefKind =
  | "meeting"
  | "lead"
  | "mockup"
  | "invoice"
  | "drama"
  | "drop"
  | "followup"
  | "client";

export type BriefItem = {
  id: string;
  kind: BriefKind;
  title: string;
  detail?: string;
  href?: string;
  urgency: "today" | "soon" | "backlog";
};

export type OpsBrief = {
  generatedAt: string;
  items: BriefItem[];
  summary: string;
};

function leadNeedsFollowup(lead: CraftLead): boolean {
  const status = String((lead as { status?: string }).status ?? "").toLowerCase();
  if (status.includes("won") || status.includes("done") || status.includes("live")) return false;
  if (status.includes("sent") || status.includes("await") || status.includes("follow")) return true;
  return true;
}

export function buildOpsBrief(input: {
  clients: Client[];
  sessions: DramaSession[];
  dropItems: DropItem[];
  extras?: BriefItem[];
}): OpsBrief {
  const items: BriefItem[] = [];
  const today = new Date().toISOString().slice(0, 10);

  for (const d of input.dropItems.filter((x) => !x.filed).slice(0, 5)) {
    items.push({
      id: `drop-${d.id}`,
      kind: "drop",
      title: d.filename || "Unfiled drop",
      detail: "Waiting in drop zone",
      href: "/dropzone",
      urgency: "today",
    });
  }

  for (const c of input.clients.filter((x) => x.status === "Intake" || x.status === "FNA").slice(0, 5)) {
    items.push({
      id: `client-${c.id}`,
      kind: "client",
      title: c.name,
      detail: `Status: ${c.status}`,
      href: `/clients/${c.id}`,
      urgency: c.status === "FNA" ? "today" : "soon",
    });
  }

  for (const s of input.sessions.slice(0, 5)) {
    items.push({
      id: `drama-${s.id}`,
      kind: "drama",
      title: s.title || s.performer || "Session",
      detail: s.performer ? `Performer: ${s.performer}` : s.category,
      href: `/adjudication/${s.id}`,
      urgency: "soon",
    });
  }

  try {
    const leads = loadLedger();
    for (const lead of leads.filter(leadNeedsFollowup).slice(0, 6)) {
      const name = lead.name || "Lead";
      const city = lead.city ? ` · ${lead.city}` : "";
      items.push({
        id: `lead-${lead.id}`,
        kind: "lead",
        title: name,
        detail: `Craft follow-up${city}`,
        href: "/craft",
        urgency: "soon",
      });
    }
    for (const lead of leads.slice(0, 8)) {
      const st = String((lead as { status?: string }).status ?? "").toLowerCase();
      if (st.includes("mockup") || st.includes("await")) {
        items.push({
          id: `mockup-${lead.id}`,
          kind: "mockup",
          title: lead.name || "Mockup",
          detail: "Mockup awaiting send / approval",
          href: "/craft",
          urgency: "today",
        });
      }
    }
  } catch {
    /* ledger optional on SSR */
  }

  if (input.extras?.length) items.push(...input.extras);

  const seen = new Set<string>();
  const unique = items.filter((i) => {
    if (seen.has(i.id)) return false;
    seen.add(i.id);
    return true;
  });

  const todayCount = unique.filter((i) => i.urgency === "today").length;
  const summary =
    unique.length === 0
      ? `Nothing queued for ${today}. Desk is clear.`
      : `${unique.length} open item${unique.length === 1 ? "" : "s"}${
          todayCount ? ` · ${todayCount} for today` : ""
        }.`;

  return {
    generatedAt: new Date().toISOString(),
    items: unique.slice(0, 12),
    summary,
  };
}

export function briefToChatLines(brief: OpsBrief): string {
  if (!brief.items.length) return brief.summary;
  const lines = brief.items.map((i) => {
    const tag = i.kind.toUpperCase();
    return `• [${tag}] ${i.title}${i.detail ? ` — ${i.detail}` : ""}`;
  });
  return `${brief.summary}\n\n${lines.join("\n")}`;
}
