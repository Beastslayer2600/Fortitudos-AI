import { SEED_LEADS, type CraftLead } from "@/lib/craft";

const KEY = "fortitudo-craft-ledger-v1";
const MAX = 400;

export function loadLedger(): CraftLead[] {
  if (typeof window === "undefined") return SEED_LEADS;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) {
      saveLedger(SEED_LEADS);
      return SEED_LEADS;
    }
    const parsed = JSON.parse(raw) as CraftLead[];
    if (!Array.isArray(parsed) || parsed.length === 0) return SEED_LEADS;
    return parsed.slice(0, MAX).map((row) => ({
      ...row,
      email: row.email ?? "",
      photos: Array.isArray(row.photos) ? row.photos.slice(0, 6) : [],
    }));
  } catch {
    return SEED_LEADS;
  }
}

export function saveLedger(leads: CraftLead[]): CraftLead[] {
  const next = leads.slice(0, MAX);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(KEY, JSON.stringify(next));
    window.dispatchEvent(new Event("fortitudo-ledger"));
  }
  return next;
}

export function mergeLeads(existing: CraftLead[], incoming: CraftLead[]): CraftLead[] {
  const map = new Map(existing.map((l) => [l.id, l]));
  for (const lead of incoming) {
    const prev = map.get(lead.id);
    if (prev) {
      map.set(lead.id, {
        ...lead,
        ...prev,
        name: lead.name || prev.name,
        city: lead.city || prev.city,
        type: lead.type || prev.type,
        address: prev.address || lead.address,
        phone: prev.phone || lead.phone,
        website: prev.website || lead.website,
        email: prev.email || lead.email,
        note: prev.note.length >= lead.note.length ? prev.note : lead.note,
        touch: prev.touch !== "untouched" ? prev.touch : lead.touch,
        savedAt: prev.savedAt || lead.savedAt,
      });
    } else {
      map.set(lead.id, lead);
    }
  }
  return [...map.values()];
}
