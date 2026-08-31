/**
 * Craft leads and FA clients share a desk and must not share a record.
 *
 * `backend/crossover.py` enforces this on the Python side: a lead brief
 * carrying client-file language is refused before it can reach the generator
 * or the ledger. The browser had no equivalent, so `intake_lead` would write an
 * FNA reference or an ID number straight into the Craft ledger.
 *
 * This mirrors the Python patterns. `crossover.test.ts` reads crossover.py and
 * fails if they drift, so Python stays the source of truth.
 */

/** Mirrors crossover.CLIENT_FILE — language that belongs to an advice file. */
export const CLIENT_FILE =
  /\b(fna|record of advice|needs analysis|client file|policy number|id number|said number)\b/i;

/** Mirrors crossover.PRACTICE — the advisory practice talking about itself. */
export const PRACTICE =
  /\b(fortitudo wealth|financial advis|financial planner|fsp\b|fais\b|record of advice site|practice storefront|retirement planning page|wealth site|advisor website|adviser website)\b/i;

/**
 * A South African ID number: 13 digits, often spaced or dashed. The word
 * "id number" is caught above; this catches the bare number typed on its own,
 * which is the more likely paste.
 */
export const SA_ID = /\b\d{6}[\s-]?\d{4}[\s-]?\d{3}\b/;

/**
 * What makes this text read like a client file, or "" if nothing does.
 * Returns the matched phrase so a refusal can say what tripped it — a refusal
 * that will not say why is one the user works around rather than learns from.
 */
export function clientFileLanguage(text: string): string {
  const blob = text || "";
  const phrase = CLIENT_FILE.exec(blob);
  if (phrase) return phrase[0].toLowerCase();
  if (SA_ID.test(blob)) return "an ID number";
  return "";
}

/** True when this text may be filed as a Craft lead. */
export function mayBeCraftLead(text: string): boolean {
  return clientFileLanguage(text) === "";
}
