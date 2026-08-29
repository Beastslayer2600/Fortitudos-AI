import { TERRITORIES, type CraftLead } from "./craft";

export type LeadScore = {
  score: number;
  band: "hot" | "warm" | "cold" | "skip";
  reasons: string[];
};

function hasRealSite(website: string): boolean {
  const w = (website || "").trim().toLowerCase();
  if (!w) return false;
  if (w.includes("facebook.com") || w.includes("fb.me") || w.includes("instagram.com")) return false;
  return /^https?:\/\//.test(w) || w.includes(".");
}

export function scoreLead(lead: CraftLead): LeadScore {
  let score = 0;
  const reasons: string[] = [];
  if (TERRITORIES.some((t) => lead.city.toLowerCase().includes(t.toLowerCase()))) {
    score += 3;
    reasons.push("in territory");
  } else {
    reasons.push("outside core suburbs");
  }
  if (lead.phone.replace(/\D/g, "").length >= 10) {
    score += 2;
    reasons.push("phone on file");
  } else {
    reasons.push("no phone — photograph the door");
  }
  if (lead.address.trim()) {
    score += 2;
    reasons.push("walkable address");
  }
  if (!hasRealSite(lead.website)) {
    score += 4;
    reasons.push(lead.website ? "social only — no real page" : "no website");
  } else {
    score -= 3;
    reasons.push("already has a site — only if it is broken");
  }
  if (lead.consent === "refused") {
    return { score: 0, band: "skip", reasons: ["refused — do not approach"] };
  }
  if (lead.consent === "asked") {
    score -= 4;
    reasons.push("already asked once electronically");
  }
  if (lead.touch === "sent" || lead.touch === "called") {
    score -= 2;
    reasons.push("already touched");
  }
  if (lead.source === "hand") {
    score += 1;
    reasons.push("seen in person");
  }
  const band: LeadScore["band"] =
    score >= 8 ? "hot" : score >= 5 ? "warm" : score >= 2 ? "cold" : "skip";
  return { score, band, reasons };
}

export function morningRoute(leads: CraftLead[], cap = 8): CraftLead[] {
  return [...leads]
    .map((l) => ({ l, s: scoreLead(l) }))
    .filter((x) => x.s.band === "hot" || x.s.band === "warm")
    .sort((a, b) => b.s.score - a.s.score || a.l.city.localeCompare(b.l.city))
    .slice(0, cap)
    .map((x) => x.l);
}

export function routeLabel(leads: CraftLead[]): string {
  const cities = [...new Set(leads.map((l) => l.city.split(",")[0]))];
  return cities.length ? cities.join(" → ") : "No walkable jobs yet";
}
