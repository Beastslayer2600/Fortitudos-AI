import type { CraftLead } from "./craft";

const KEY = "fortitudo.craft.ledger.v1";

export function loadLedger(): CraftLead[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveLedger(leads: CraftLead[]): CraftLead[] {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(KEY, JSON.stringify(leads));
  }
  return leads;
}
