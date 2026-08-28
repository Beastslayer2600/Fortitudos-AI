export const CLIENT_STATUSES = [
  "Intake",
  "FNA",
  "Advice",
  "Implementation",
  "Review",
] as const;
export type ClientStatus = (typeof CLIENT_STATUSES)[number];

export const DOC_TYPES = [
  "FICA / Identity",
  "RPQ",
  "Signed FNA",
  "Advice Report",
  "Quote",
  "ROA",
  "Correspondence",
  "Other",
] as const;
export type DocType = (typeof DOC_TYPES)[number];

export const NOTE_TYPES = ["General", "FNA", "Advice", "Meeting"] as const;
export type NoteType = (typeof NOTE_TYPES)[number];

export type Client = {
  id: string;
  name: string;
  email: string;
  phone: string;
  status: ClientStatus;
  createdAt: string;
  updatedAt: string;
};

export type ClientDocument = {
  id: string;
  clientId: string;
  filename: string;
  docType: DocType;
  contentType: string;
  size: number;
  text: string;
  createdAt: string;
};

export type ClientNote = {
  id: string;
  clientId: string;
  noteType: NoteType;
  title: string;
  content: string;
  createdAt: string;
};

export type ClientEmail = {
  id: string;
  clientId: string;
  direction: "Draft" | "Logged";
  sender: string;
  recipient: string;
  subject: string;
  body: string;
  status: "Draft" | "Logged";
  createdAt: string;
};

export type ProjectionInputs = {
  currentValue: number;
  monthlyContribution: number;
  lumpSum: number;
  years: number;
  growthRate: number;
  adviceFee: number;
  unitPrice: number;
  unitsHeld: number;
};

export type ProjectionSummary = {
  openingValue: number;
  netGrowthRate: number;
  projectedValue: number;
  contributions: number;
  growthRand: number;
  feesRand: number;
};

export type ClientProjection = {
  id: string;
  clientId: string;
  name: string;
  inputs: ProjectionInputs;
  summary: ProjectionSummary;
  createdAt: string;
};

export type AskCitation = {
  source: string;
  page: number;
  title: string;
  excerpt: string;
  score: number;
};

export type AskTurn = {
  id: string;
  question: string;
  answer: string;
  citations: AskCitation[];
  pagesOnly: boolean;
  createdAt: string;
};

export type DropItem = {
  id: string;
  filename: string;
  suggestedType: DocType;
  suggestedClientId: string | null;
  text: string;
  size: number;
  createdAt: string;
  filed: boolean;
};

export type DramaDomain =
  | "Speech & Drama"
  | "Visual Arts"
  | "Music"
  | "Dance"
  | "Choirs / Vir kore";

export type DramaSession = {
  id: string;
  title: string;
  performer: string;
  category: string;
  venue: string;
  eventDate: string;
  adjudicator: string;
  domain: DramaDomain;
  outcome: string;
  overallNote: string;
  createdAt: string;
  updatedAt: string;
};

export type DramaAssessment = {
  id: string;
  sessionId: string;
  criterion: string;
  score: number;
  observation: string;
  interpretation: string;
  feedbackCompetence: string;
  feedbackAgency: string;
  feedbackChallenge: string;
  updatedAt: string;
};

export type DeskChatRole = "user" | "assistant";

export type DeskChatMessage = {
  id: string;
  role: DeskChatRole;
  content: string;
  createdAt: string;
  clientId?: string;
  kind?: "meeting_prep" | "lookup" | "general" | "system";
};
