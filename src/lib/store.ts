import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DOMAINS } from "./drama-domains";
import { mergeDiskClients } from "./merge-disk-clients";
import { project } from "./projections";
import type { DiskClient } from "./sync-werk-types";
import type {
  AskTurn,
  Client,
  ClientDocument,
  ClientEmail,
  ClientNote,
  ClientProjection,
  ClientStatus,
  DeskChatMessage,
  DocType,
  DramaAssessment,
  DramaDomain,
  DramaSession,
  DropItem,
  NoteType,
  ProjectionInputs,
} from "./types";
import { nowIso, slug } from "./utils";

type State = {
  hydrated: boolean;
  setHydrated: (v: boolean) => void;
  lastDiskSyncAt: string | null;
  lastDiskSyncRoot: string | null;

  clients: Client[];
  documents: ClientDocument[];
  notes: ClientNote[];
  emails: ClientEmail[];
  projections: ClientProjection[];
  askHistory: AskTurn[];
  dropItems: DropItem[];
  sessions: DramaSession[];
  assessments: DramaAssessment[];
  chatMessages: DeskChatMessage[];

  addClient: (input: {
    name: string;
    email?: string;
    phone?: string;
    status?: ClientStatus;
  }) => string;
  updateClient: (id: string, patch: Partial<Client>) => void;
  addDocument: (input: {
    clientId: string;
    filename: string;
    docType: DocType;
    contentType?: string;
    text?: string;
    size?: number;
  }) => void;
  addNote: (input: {
    clientId: string;
    noteType: NoteType;
    title: string;
    content: string;
  }) => void;
  addEmail: (input: {
    clientId: string;
    recipient: string;
    subject: string;
    body: string;
  }) => void;
  addProjection: (input: {
    clientId: string;
    name: string;
    inputs: ProjectionInputs;
  }) => void;
  addAskTurn: (turn: Omit<AskTurn, "id" | "createdAt">) => void;
  addDropItem: (item: Omit<DropItem, "id" | "createdAt" | "filed">) => string;
  fileDropItem: (
    dropId: string,
    clientId: string,
    docType: DocType,
  ) => void;

  addChatMessage: (
    msg: Omit<DeskChatMessage, "id" | "createdAt">,
  ) => void;
  clearChat: () => void;

  mergeFromDisk: (
    diskClients: DiskClient[],
    root: string,
  ) => {
    addedClients: number;
    addedDocuments: number;
    updatedClients: number;
  };

  addSession: (input: {
    title: string;
    performer: string;
    category?: string;
    venue?: string;
    eventDate?: string;
    adjudicator?: string;
    domain: DramaDomain;
  }) => string;
  updateSession: (
    id: string,
    patch: Partial<Pick<DramaSession, "outcome" | "overallNote">>,
  ) => void;
  saveAssessment: (input: Omit<DramaAssessment, "id" | "updatedAt">) => void;
};

function uid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

function uniqueId(base: string, existing: string[]) {
  let candidate = base;
  let n = 2;
  while (existing.includes(candidate)) {
    candidate = `${base}_${n}`;
    n += 1;
  }
  return candidate;
}

const seedStamp = "2026-03-12T09:00:00";

function seed(): Pick<
  State,
  | "clients"
  | "documents"
  | "notes"
  | "emails"
  | "projections"
  | "askHistory"
  | "dropItems"
  | "sessions"
  | "assessments"
  | "chatMessages"
> {
  const clients: Client[] = [
    {
      id: "thandiwe_nkosi",
      name: "Thandiwe Nkosi",
      email: "thandiwe@example.co.za",
      phone: "082 441 2201",
      status: "Intake",
      createdAt: seedStamp,
      updatedAt: seedStamp,
    },
    {
      id: "pieter_van_der_merwe",
      name: "Pieter van der Merwe",
      email: "pieter@example.co.za",
      phone: "083 912 7740",
      status: "Advice",
      createdAt: seedStamp,
      updatedAt: "2026-06-02T11:20:00",
    },
    {
      id: "ayesha_patel",
      name: "Ayesha Patel",
      email: "ayesha@example.co.za",
      phone: "071 555 0198",
      status: "Review",
      createdAt: seedStamp,
      updatedAt: "2026-07-18T08:40:00",
    },
  ];

  const documents: ClientDocument[] = [
    {
      id: "d1",
      clientId: "thandiwe_nkosi",
      filename: "FICA_ID_Thandiwe.pdf",
      docType: "FICA / Identity",
      contentType: "application/pdf",
      size: 240112,
      text: "Green barcoded ID. Address: 14 Roux Street, Parkhurst. Utility bill dated Feb 2026.",
      createdAt: seedStamp,
    },
    {
      id: "d2",
      clientId: "pieter_van_der_merwe",
      filename: "Signed_FNA_Pieter.pdf",
      docType: "Signed FNA",
      contentType: "application/pdf",
      size: 512000,
      text: "Objectives: capital protection with moderate growth. Horizon 12 years. Dependants: spouse + two children. Existing living cover R2.5m.",
      createdAt: seedStamp,
    },
    {
      id: "d3",
      clientId: "pieter_van_der_merwe",
      filename: "RPQ_Pieter.pdf",
      docType: "RPQ",
      contentType: "application/pdf",
      size: 88000,
      text: "Risk score 18/30 — moderately conservative. Drawdown tolerance 12%.",
      createdAt: seedStamp,
    },
    {
      id: "d4",
      clientId: "ayesha_patel",
      filename: "Quote_Lifestyle_Ayesha.pdf",
      docType: "Quote",
      contentType: "application/pdf",
      size: 190400,
      text: "Living benefit R3.0m, premium R1 840 pm, accelerated against life cover R5.0m.",
      createdAt: seedStamp,
    },
    {
      id: "d5",
      clientId: "ayesha_patel",
      filename: "Advice_report_Ayesha.pdf",
      docType: "Advice Report",
      contentType: "application/pdf",
      size: 640200,
      text: "Recommendation: retain existing retirement annuity; add living benefits for income protection gap. Needs analysis signed 11 Jul 2026.",
      createdAt: "2026-07-11T10:00:00",
    },
  ];

  const notes: ClientNote[] = [
    {
      id: "n1",
      clientId: "pieter_van_der_merwe",
      noteType: "FNA",
      title: "Discovery meeting",
      content:
        "Wants to understand waiting periods on hearing loss — family history of otosclerosis. Do not quote until the signed FNA is complete.",
      createdAt: seedStamp,
    },
    {
      id: "n2",
      clientId: "ayesha_patel",
      noteType: "Meeting",
      title: "Annual review agenda",
      content:
        "Check unit price drift on RA. Confirm child cover still required for both children in full-time study.",
      createdAt: "2026-07-18T08:40:00",
    },
  ];

  const emails: ClientEmail[] = [
    {
      id: "e1",
      clientId: "pieter_van_der_merwe",
      direction: "Draft",
      sender: "adviser@fortitudostudios.site",
      recipient: "pieter@example.co.za",
      subject: "Information still needed before we can recommend",
      body: "Pieter — thank you for Friday. Before I draft the record of advice I still need the signed FNA (now on file) and confirmation of the existing living-cover policy number. Nothing in this note is advice.",
      status: "Draft",
      createdAt: "2026-06-02T11:20:00",
    },
  ];

  const inputs: ProjectionInputs = {
    currentValue: 420000,
    monthlyContribution: 3500,
    lumpSum: 0,
    years: 12,
    growthRate: 9,
    adviceFee: 0.75,
    unitPrice: 14.2,
    unitsHeld: 29577,
  };

  const projections: ClientProjection[] = [
    {
      id: "p1",
      clientId: "ayesha_patel",
      name: "RA — base case",
      inputs,
      summary: project(inputs),
      createdAt: "2026-07-18T08:40:00",
    },
  ];

  const sessions: DramaSession[] = [
    {
      id: "lebohang_molefe_antigone",
      title: "Antigone — monologue",
      performer: "Lebohang Molefe",
      category: "Senior dramatic item",
      venue: "Fortitudo Hall, Pretoria",
      eventDate: "2026-08-21",
      adjudicator: "G. J.",
      domain: "Speech & Drama",
      outcome: "",
      overallNote: "",
      createdAt: "2026-08-21T14:00:00",
      updatedAt: "2026-08-21T14:00:00",
    },
  ];

  const assessments: DramaAssessment[] = [
    {
      id: "a1",
      sessionId: "lebohang_molefe_antigone",
      criterion: "Voice & Speech",
      score: 8,
      observation:
        "Clear plosives on the opening stichomythia. Breath support held through the longer periods; a slight glottal catch on the final appeal.",
      interpretation:
        "The vocal choices served status — public voice versus private grief — without pushing volume for its own sake.",
      feedbackCompetence: "",
      feedbackAgency: "",
      feedbackChallenge: "",
      updatedAt: "2026-08-21T14:20:00",
    },
  ];

  return {
    clients,
    documents,
    notes,
    emails,
    projections,
    askHistory: [],
    dropItems: [],
    sessions,
    assessments,
    chatMessages: [],
  };
}

export const useFortitudo = create<State>()(
  persist(
    (set, get) => ({
      hydrated: false,
      setHydrated: (v) => set({ hydrated: v }),
      lastDiskSyncAt: null,
      lastDiskSyncRoot: null,
      ...seed(),

      addClient: ({ name, email = "", phone = "", status = "Intake" }) => {
        const id = uniqueId(
          slug(name),
          get().clients.map((c) => c.id),
        );
        const stamp = nowIso();
        set((s) => ({
          clients: [
            {
              id,
              name: name.trim(),
              email: email.trim(),
              phone: phone.trim(),
              status,
              createdAt: stamp,
              updatedAt: stamp,
            },
            ...s.clients,
          ],
        }));
        return id;
      },

      updateClient: (id, patch) =>
        set((s) => ({
          clients: s.clients.map((c) =>
            c.id === id ? { ...c, ...patch, updatedAt: nowIso() } : c,
          ),
        })),

      addDocument: ({
        clientId,
        filename,
        docType,
        contentType = "text/plain",
        text = "",
        size,
      }) =>
        set((s) => ({
          documents: [
            {
              id: uid("doc"),
              clientId,
              filename,
              docType,
              contentType,
              size: size ?? text.length,
              text,
              createdAt: nowIso(),
            },
            ...s.documents,
          ],
          clients: s.clients.map((c) =>
            c.id === clientId ? { ...c, updatedAt: nowIso() } : c,
          ),
        })),

      addNote: ({ clientId, noteType, title, content }) =>
        set((s) => ({
          notes: [
            {
              id: uid("note"),
              clientId,
              noteType,
              title: title.trim() || "Untitled note",
              content: content.trim(),
              createdAt: nowIso(),
            },
            ...s.notes,
          ],
          clients: s.clients.map((c) =>
            c.id === clientId ? { ...c, updatedAt: nowIso() } : c,
          ),
        })),

      addEmail: ({ clientId, recipient, subject, body }) =>
        set((s) => ({
          emails: [
            {
              id: uid("mail"),
              clientId,
              direction: "Draft",
              sender: "adviser@fortitudostudios.site",
              recipient,
              subject,
              body,
              status: "Draft",
              createdAt: nowIso(),
            },
            ...s.emails,
          ],
        })),

      addProjection: ({ clientId, name, inputs }) =>
        set((s) => ({
          projections: [
            {
              id: uid("proj"),
              clientId,
              name: name.trim() || "Projection scenario",
              inputs,
              summary: project(inputs),
              createdAt: nowIso(),
            },
            ...s.projections,
          ],
        })),

      addAskTurn: (turn) =>
        set((s) => ({
          askHistory: [
            {
              id: uid("ask"),
              createdAt: nowIso(),
              ...turn,
            },
            ...s.askHistory,
          ].slice(0, 40),
        })),

      addDropItem: (item) => {
        const id = uid("drop");
        set((s) => ({
          dropItems: [
            { id, createdAt: nowIso(), filed: false, ...item },
            ...s.dropItems,
          ],
        }));
        return id;
      },

      fileDropItem: (dropId, clientId, docType) => {
        const item = get().dropItems.find((d) => d.id === dropId);
        if (!item) return;
        get().addDocument({
          clientId,
          filename: item.filename,
          docType,
          text: item.text,
          size: item.size,
        });
        set((s) => ({
          dropItems: s.dropItems.map((d) =>
            d.id === dropId
              ? {
                  ...d,
                  filed: true,
                  suggestedClientId: clientId,
                  suggestedType: docType,
                }
              : d,
          ),
        }));
      },

      addChatMessage: (msg) =>
        set((s) => ({
          chatMessages: [
            ...s.chatMessages,
            {
              id: uid("chat"),
              createdAt: nowIso(),
              ...msg,
            },
          ].slice(-80),
        })),

      clearChat: () => set({ chatMessages: [] }),

      mergeFromDisk: (diskClients, root) => {
        const result = mergeDiskClients(
          get().clients,
          get().documents,
          diskClients,
        );
        set({
          clients: result.clients,
          documents: result.documents,
          lastDiskSyncAt: nowIso(),
          lastDiskSyncRoot: root,
        });
        return {
          addedClients: result.addedClients,
          addedDocuments: result.addedDocuments,
          updatedClients: result.updatedClients,
        };
      },

      addSession: (input) => {
        const id = uniqueId(
          `${slug(input.performer)}_${slug(input.title)}`,
          get().sessions.map((x) => x.id),
        );
        const stamp = nowIso();
        const domain = DOMAINS[input.domain] ? input.domain : "Speech & Drama";
        set((s) => ({
          sessions: [
            {
              id,
              title: input.title.trim(),
              performer: input.performer.trim(),
              category: input.category?.trim() ?? "",
              venue: input.venue?.trim() ?? "",
              eventDate: input.eventDate?.trim() ?? "",
              adjudicator: input.adjudicator?.trim() ?? "",
              domain,
              outcome: "",
              overallNote: "",
              createdAt: stamp,
              updatedAt: stamp,
            },
            ...s.sessions,
          ],
        }));
        return id;
      },

      updateSession: (id, patch) =>
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === id ? { ...sess, ...patch, updatedAt: nowIso() } : sess,
          ),
        })),

      saveAssessment: (input) =>
        set((s) => {
          const existing = s.assessments.find(
            (a) =>
              a.sessionId === input.sessionId && a.criterion === input.criterion,
          );
          const next: DramaAssessment = {
            id: existing?.id ?? uid("as"),
            ...input,
            score: Math.max(1, Math.min(10, Number(input.score) || 1)),
            updatedAt: nowIso(),
          };
          return {
            assessments: existing
              ? s.assessments.map((a) => (a.id === existing.id ? next : a))
              : [next, ...s.assessments],
            sessions: s.sessions.map((sess) =>
              sess.id === input.sessionId
                ? { ...sess, updatedAt: nowIso() }
                : sess,
            ),
          };
        }),
    }),
    {
      name: "fortitudo-ai-v1",
      skipHydration: true,
      partialize: (s) => ({
        clients: s.clients,
        documents: s.documents,
        notes: s.notes,
        emails: s.emails,
        projections: s.projections,
        askHistory: s.askHistory,
        dropItems: s.dropItems,
        sessions: s.sessions,
        assessments: s.assessments,
        chatMessages: s.chatMessages,
        lastDiskSyncAt: s.lastDiskSyncAt,
        lastDiskSyncRoot: s.lastDiskSyncRoot,
      }),
    },
  ),
);
