export type CraftTouch = "untouched" | "audited" | "composed" | "sent" | "called";
export type CraftConsent = "unknown" | "asked" | "consented" | "refused" | "customer";

export type CraftLead = {
  id: string;
  name: string;
  city: string;
  type: string;
  address: string;
  phone: string;
  website: string;
  email: string;
  note: string;
  touch: CraftTouch;
  photos: string[];
  savedAt: string;
  source: "hand" | "yello" | "osm" | "import";
  consent?: CraftConsent;
};

export const SKU = {
  price: 5500,
  deposit: 2750,
  label: "One craft page",
  includes: [
    "Mobile page that loads on a shop phone",
    "Sticky Call + WhatsApp",
    "Map, suburb, NAP from facts you have",
    "Real photos only",
    "One trade 3D object",
  ],
  not: ["Wix clone", "Awwwards scroll prison", "Fake reviews", "Invented 24/7"],
};

export const TERRITORIES = ["Kempton Park", "Centurion", "Irene", "Edenvale", "Boksburg"];

const NOUN: Record<string, string> = {
  bakery: "loaf", bread: "loaf", salon: "chair", hair: "chair", nail: "chair",
  workshop: "wheel", auto: "wheel", mechanic: "wheel", plumber: "pipe",
  electrical: "pipe", geyser: "pipe", butcher: "block", meat: "block",
  florist: "stems", flower: "stems", broker: "file", attorney: "file",
  lawyer: "file", accountant: "file", advisor: "file", adviser: "file",
  cafe: "cup", coffee: "cup", restaurant: "plate", gym: "weight",
};

export function nounFor(type: string, name = ""): string {
  const hay = `${type} ${name}`.toLowerCase();
  for (const [k, v] of Object.entries(NOUN)) {
    if (hay.includes(k)) return v;
  }
  return "sign";
}

// Global: without /g, replace() strips only the first claim and a note that
// stacks several keeps all but one.
const BANNED =
  /\b(best in (sa|south africa|gauteng)|#1|award[- ]winning|24\/7|always open|guaranteed results|5[- ]star reviews?|no\. ?1)\b/gi;

export function claimGuard(text: string): string {
  return text.replace(BANNED, "").replace(/\s{2,}/g, " ").replace(/\s+\./g, ".").trim();
}

export function slugify(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "shop";
}

export function jobFolderHint(lead: CraftLead) {
  return `C:\\Local AI\\shops\\${slugify(lead.name)}\\`;
}

export function canPitchElectronically(lead: CraftLead): boolean {
  return lead.consent === "consented" || lead.consent === "customer";
}

export type ConsentDecision = { allowed: boolean; kind: "pitch" | "ask" | "none"; reason: string };

/**
 * POPIA s69, same rules as backend/consent.py. A refusal is permanent, and one
 * unanswered ask is the only ask — silence is not consent. The door letter is
 * print, not electronic, so it is always allowed.
 */
export function mayContactElectronically(lead: CraftLead): ConsentDecision {
  switch (lead.consent) {
    case "refused":
      return { allowed: false, kind: "none", reason: "They said no. That is permanent." };
    case "asked":
      return { allowed: false, kind: "none", reason: "Already asked once. Silence is not consent." };
    case "consented":
      return { allowed: true, kind: "pitch", reason: "Consent on record." };
    case "customer":
      return { allowed: true, kind: "pitch", reason: "Existing customer — s69(3), similar services only." };
    default:
      return { allowed: true, kind: "ask", reason: "First message must ask for consent, not pitch." };
  }
}

/** Printed page. Not electronic. Always allowed. */
export function doorLetter(lead: CraftLead, mockUrl: string) {
  return (
    `For the owner of ${lead.name}\n\n` +
    `I drafted a one-page website for you. Nothing invented — only what is ` +
    `already on your door and your van.\n\n` +
    `See it: ${mockUrl}\n\n` +
    `R${SKU.price.toLocaleString("en-ZA")} once, R${SKU.deposit.toLocaleString("en-ZA")} to start. If it is not useful, throw this away.\n\n` +
    `Gert Fourie · Fortitudo Studios · +27 77 386 6299`
  );
}

export function consentAskText(lead: CraftLead) {
  return (
    `Hello, this is Gert Fourie at Fortitudo Studios. ` +
    `May I send you a one-page website mock for ${lead.name} in ${lead.city}? ` +
    `Reply YES and I will send it. Reply NO and I will not contact you again about this.`
  );
}

export function mailtoLetter(lead: CraftLead, mockUrl: string) {
  const subject = encodeURIComponent(`${lead.name} — a page that answers the phone`);
  const pitch =
    `Hello ${lead.name.split(" ")[0]},\n\n` +
    `I put together a one-page mock for ${lead.name} in ${lead.city.split(",")[0]}. ` +
    `Call and WhatsApp sit at the top. No invented hours or reviews.\n\n` +
    `Look: ${mockUrl}\n\n` +
    `The job is R5,500 once — R2,750 to start.\n\nGert\nFortitudo Studios\n+27 77 386 6299`;
  const decision = mayContactElectronically(lead);
  if (!decision.allowed) return "";
  const body = encodeURIComponent(decision.kind === "pitch" ? pitch : consentAskText(lead));
  const to = lead.email ? encodeURIComponent(lead.email) : "";
  return `mailto:${to}?subject=${subject}&body=${body}`;
}

export function whatsappLink(phone: string, name: string, mockUrl: string, consent: CraftConsent = "unknown") {
  const decision = mayContactElectronically({ consent } as CraftLead);
  if (!decision.allowed) return "";
  const digits = phone.replace(/\D/g, "");
  const intl = digits.startsWith("0") ? `27${digits.slice(1)}` : digits;
  const pitch = `Hi ${name.split(" ")[0]}, I made a mock page for the shop. ${mockUrl}`;
  const ask = `Hi, Gert at Fortitudo Studios. May I send you a one-page website mock for ${name}? Reply YES or NO.`;
  const text = encodeURIComponent(decision.kind === "pitch" ? pitch : ask);
  return intl.length >= 10 ? `https://wa.me/${intl}?text=${text}` : "";
}

export function newHandLead(partial: Partial<CraftLead>): CraftLead {
  const name = partial.name?.trim() || "Untitled shop";
  return {
    id: `hand-${Date.now()}`,
    name,
    city: partial.city?.trim() || "Kempton Park",
    type: partial.type?.trim() || "Shop",
    address: partial.address ?? "",
    phone: partial.phone ?? "",
    website: partial.website ?? "",
    email: partial.email ?? "",
    note: claimGuard(partial.note ?? ""),
    touch: "untouched",
    photos: [],
    savedAt: new Date().toISOString(),
    source: "hand",
    consent: partial.consent ?? "unknown",
  };
}
