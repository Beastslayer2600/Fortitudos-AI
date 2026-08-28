import type {
  Client,
  ClientDocument,
  ClientEmail,
  ClientNote,
  ClientProjection,
  DocType,
} from "./types";

export type ChecklistItem = {
  item: string;
  docType: DocType | null;
  complete: boolean;
  instruction: string;
  evidence: string[];
};

export type MeetingPrepPack = {
  client: Client;
  whenLabel: string;
  channel: string;
  checklist: ChecklistItem[];
  agenda: string[];
  openQuestions: string[];
  fnaSkeleton: string;
  summaryMarkdown: string;
  gaps: string[];
};

const CHECKS: {
  item: string;
  docType: DocType | null;
  match: (types: Set<string>) => boolean;
  instruction: string;
}[] = [
  {
    item: "FICA / Identity",
    docType: "FICA / Identity",
    match: (t) => t.has("FICA / Identity"),
    instruction: "Confirm identity and proof of address are current before advice.",
  },
  {
    item: "Signed FNA",
    docType: "Signed FNA",
    match: (t) => t.has("Signed FNA"),
    instruction: "Signed needs analysis must be on file before recommendations.",
  },
  {
    item: "RPQ",
    docType: "RPQ",
    match: (t) => t.has("RPQ"),
    instruction: "Risk profile questionnaire — confirm score and tolerance still valid.",
  },
  {
    item: "Advice Report",
    docType: "Advice Report",
    match: (t) => t.has("Advice Report"),
    instruction: "Prior advice report — reconfirm nothing material has changed.",
  },
  {
    item: "Quote",
    docType: "Quote",
    match: (t) => t.has("Quote"),
    instruction: "Current quotes and assumptions — do not present stale figures.",
  },
  {
    item: "ROA",
    docType: "ROA",
    match: (t) => t.has("ROA"),
    instruction: "Record of advice — only after needs and product match are settled.",
  },
];

export function buildMeetingPrep(input: {
  client: Client;
  documents: ClientDocument[];
  notes: ClientNote[];
  emails: ClientEmail[];
  projections: ClientProjection[];
  whenLabel?: string;
  channel?: string;
}): MeetingPrepPack {
  const {
    client,
    documents,
    notes,
    emails,
    projections,
    whenLabel = "time not specified",
    channel = "meeting",
  } = input;

  const types = new Set(documents.map((d) => d.docType));
  const checklist: ChecklistItem[] = CHECKS.map((c) => {
    const evidence = documents
      .filter((d) => d.docType === c.docType)
      .map((d) => d.filename);
    return {
      item: c.item,
      docType: c.docType,
      complete: c.match(types),
      instruction: c.instruction,
      evidence,
    };
  });

  const gaps = checklist.filter((c) => !c.complete).map((c) => c.item);

  const agenda = [
    "Reconfirm objectives and any material changes since last contact",
    "Review information on file and flag gaps (FICA / FNA / RPQ)",
    "Walk through what is known — do not invent product figures",
    "Agree next actions, owners, and dates",
  ];

  if (gaps.includes("Signed FNA")) {
    agenda.unshift("Complete / sign FNA before any product recommendation");
  }
  if (notes.some((n) => /waiting period|otosclerosis|hearing/i.test(n.content))) {
    agenda.push("Clarify waiting periods and exclusions on any health-related need — cite the product page, do not estimate");
  }

  const openQuestions: string[] = [];
  if (gaps.includes("FICA / Identity"))
    openQuestions.push("Do we have current ID and proof of address?");
  if (gaps.includes("Signed FNA"))
    openQuestions.push("What are the priority goals, horizon, and dependants for the FNA?");
  if (gaps.includes("RPQ"))
    openQuestions.push("Has risk tolerance or capacity changed since any prior profile?");
  if (!client.email)
    openQuestions.push("Confirm preferred email for drafts and follow-up.");
  for (const n of notes.slice(0, 4)) {
    if (n.content.length > 20) openQuestions.push(`From note “${n.title}”: follow up on — ${n.content.slice(0, 120)}`);
  }

  const fnaSkeleton = [
    `# FNA working draft — ${client.name}`,
    ``,
    `_Internal working note only. Not advice. Verify every figure against filed documents and product guides._`,
    ``,
    `## Meeting`,
    `- Channel: ${channel}`,
    `- When: ${whenLabel}`,
    `- Client status on file: ${client.status}`,
    ``,
    `## Client`,
    `- Name: ${client.name}`,
    `- Email: ${client.email || "[not on file]"}`,
    `- Phone: ${client.phone || "[not on file]"}`,
    ``,
    `## File completeness`,
    ...checklist.map(
      (c) =>
        `- [${c.complete ? "x" : " "}] ${c.item}${c.evidence.length ? ` — ${c.evidence.join(", ")}` : " — missing"}`,
    ),
    ``,
    `## Known document extracts`,
    ...(documents.length
      ? documents.map(
          (d) =>
            `### ${d.docType} — ${d.filename}\n${(d.text || "[no text extract]").slice(0, 600)}`,
        )
      : ["(no documents filed)"]),
    ``,
    `## Notes on file`,
    ...(notes.length
      ? notes.map((n) => `- **${n.noteType}: ${n.title}** — ${n.content}`)
      : ["(none)"]),
    ``,
    `## Draft emails`,
    ...(emails.length
      ? emails.map((e) => `- ${e.subject} (${e.status})`)
      : ["(none)"]),
    ``,
    `## Projections on file`,
    ...(projections.length
      ? projections.map(
          (p) =>
            `- ${p.name}: projected ~R${Math.round(p.summary.projectedValue).toLocaleString("en-ZA")} (${p.inputs.years}y)`,
        )
      : ["(none)"]),
    ``,
    `## FNA fields still to confirm in meeting`,
    `- Objectives and priorities`,
    `- Time horizon and liquidity needs`,
    `- Dependants and existing cover`,
    `- Affordability / contribution capacity`,
    `- Risk capacity vs attitude`,
    `- What must NOT be recommended until gaps close: ${gaps.join(", ") || "none flagged"}`,
    ``,
    `## Suggested agenda`,
    ...agenda.map((a, i) => `${i + 1}. ${a}`),
  ].join("\n");

  const summaryMarkdown = [
    `**Meeting prep — ${client.name}**`,
    `${channel} · ${whenLabel} · status ${client.status}`,
    ``,
    `**On file:** ${documents.length} docs · ${notes.length} notes · ${emails.length} emails · ${projections.length} projections`,
    `**Gaps:** ${gaps.length ? gaps.join(", ") : "none on standard checklist"}`,
    ``,
    `Do not present product figures that are not on a filed quote or the product index. Advice remains yours under FAIS.`,
  ].join("\n");

  return {
    client,
    whenLabel,
    channel,
    checklist,
    agenda,
    openQuestions,
    fnaSkeleton,
    summaryMarkdown,
    gaps,
  };
}
