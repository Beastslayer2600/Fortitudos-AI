export type CraftTouch = "untouched" | "audited" | "composed" | "sent" | "called";

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
  bakery: "loaf",
  bread: "loaf",
  salon: "chair",
  hair: "chair",
  nail: "chair",
  workshop: "wheel",
  auto: "wheel",
  mechanic: "wheel",
  plumber: "pipe",
  electrical: "pipe",
  geyser: "pipe",
  butcher: "block",
  meat: "block",
  florist: "stems",
  flower: "stems",
  broker: "file",
  attorney: "file",
  lawyer: "file",
  accountant: "file",
  advisor: "file",
  adviser: "file",
  cafe: "cup",
  coffee: "cup",
  restaurant: "plate",
  gym: "weight",
};

export function nounFor(type: string, name = ""): string {
  const hay = `${type} ${name}`.toLowerCase();
  for (const [k, v] of Object.entries(NOUN)) {
    if (hay.includes(k)) return v;
  }
  return "sign";
}

const BANNED =
  /\b(best in (sa|south africa|gauteng)|#1|award[- ]winning|24\/7|always open|guaranteed results|5[- ]star reviews?|no\. ?1)\b/i;

export function claimGuard(text: string): string {
  return text.replace(BANNED, "").replace(/\s{2,}/g, " ").replace(/\s+\./g, ".").trim();
}

export function slugify(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "shop";
}

export function jobFolderHint(lead: CraftLead) {
  return `C:\\Local AI\\shops\\${slugify(lead.name)}\\`;
}

export function mailtoLetter(lead: CraftLead, mockUrl: string) {
  const subject = encodeURIComponent(`${lead.name} — a page that answers the phone`);
  const body = encodeURIComponent(
    `Hello ${lead.name.split(" ")[0]},\n\n` +
      `I put together a one-page mock for ${lead.name} in ${lead.city.split(",")[0]}. ` +
      `Call and WhatsApp sit at the top. No invented hours or reviews.\n\n` +
      `Look: ${mockUrl}\n\n` +
      `The job is R5,500 once — R2,750 to start. If the page is useful, WhatsApp me and we finish it with your photos.\n\n` +
      `Gert\nFortitudo Studios\n+27 77 386 6299`,
  );
  const to = lead.email ? encodeURIComponent(lead.email) : "";
  return `mailto:${to}?subject=${subject}&body=${body}`;
}

export function whatsappLink(phone: string, name: string, mockUrl: string) {
  const digits = phone.replace(/\D/g, "");
  const intl = digits.startsWith("0") ? `27${digits.slice(1)}` : digits;
  const text = encodeURIComponent(`Hi ${name.split(" ")[0]}, I made a mock page for the shop. ${mockUrl}`);
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
  };
}
