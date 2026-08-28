export const MOODS = ["warm", "cool", "industrial", "lush"] as const;
export const TIMES = ["dawn", "day", "golden", "night"] as const;

export type SiteSpec = {
  name: string;
  city: string;
  archetype: string;
  tagline: string;
  about: string;
  services: { title: string; blurb: string }[];
  cta: string;
  palette: { bg: string; fog: string; accent: string; mass: string; light: string };
  mood: (typeof MOODS)[number];
  time: (typeof TIMES)[number];
  phone?: string;
  address?: string;
  hours?: string;
  personality?: string;
};

const PALETTES: Record<SiteSpec["mood"], Record<SiteSpec["time"], SiteSpec["palette"]>> = {
  warm: {
    dawn: { bg: "#1a1410", fog: "#2a221c", accent: "#d4b48a", mass: "#3a322c", light: "#f0d2a8" },
    day: { bg: "#161310", fog: "#241e18", accent: "#c9b496", mass: "#3d342c", light: "#f2e6d4" },
    golden: { bg: "#1c120c", fog: "#2c1c12", accent: "#e0a060", mass: "#3a2a1c", light: "#ffc878" },
    night: { bg: "#0c0a09", fog: "#161210", accent: "#c4a070", mass: "#2a2420", light: "#e8c89a" },
  },
  cool: {
    dawn: { bg: "#101418", fog: "#1a2228", accent: "#b8c4c8", mass: "#2a3238", light: "#d8e4e8" },
    day: { bg: "#12161a", fog: "#1c2428", accent: "#c4cdd0", mass: "#2c3438", light: "#e8eef0" },
    golden: { bg: "#141210", fog: "#24201c", accent: "#c8b8a0", mass: "#32302c", light: "#eadcc4" },
    night: { bg: "#090b0c", fog: "#12161a", accent: "#9aa8b0", mass: "#22282c", light: "#c8d4dc" },
  },
  industrial: {
    dawn: { bg: "#141414", fog: "#1e1e1e", accent: "#c4c0b8", mass: "#2c2c2c", light: "#e0dcd4" },
    day: { bg: "#121212", fog: "#1c1c1c", accent: "#d0ccc4", mass: "#2a2a2a", light: "#ece8e0" },
    golden: { bg: "#161210", fog: "#241c18", accent: "#c8b090", mass: "#2e2824", light: "#e8d0a8" },
    night: { bg: "#0a0a0a", fog: "#141414", accent: "#a8a49c", mass: "#242424", light: "#d4d0c8" },
  },
  lush: {
    dawn: { bg: "#101410", fog: "#1a2218", accent: "#b8c4a8", mass: "#2a3228", light: "#dce8d0" },
    day: { bg: "#101410", fog: "#1c241c", accent: "#c4d0b4", mass: "#2c3428", light: "#e8f0dc" },
    golden: { bg: "#14120c", fog: "#221c14", accent: "#c8c090", mass: "#323024", light: "#ece4c0" },
    night: { bg: "#0a0c0a", fog: "#141814", accent: "#98a888", mass: "#222820", light: "#c8d4bc" },
  },
};

function inferArchetype(type: string): string {
  const t = type.toLowerCase();
  if (t.includes("baker") || t.includes("bread")) return "bakery";
  if (t.includes("hair") || t.includes("salon") || t.includes("nail")) return "salon";
  if (t.includes("guest") || t.includes("bnb") || t.includes("lodge")) return "guesthouse";
  if (t.includes("car") || t.includes("auto") || t.includes("workshop")) return "workshop";
  if (t.includes("cafe") || t.includes("coffee")) return "cafe";
  if (t.includes("rest")) return "restaurant";
  if (t.includes("gym") || t.includes("fit")) return "gym";
  if (t.includes("plumb") || t.includes("electr") || t.includes("geyser")) return "trade";
  if (t.includes("advis") || t.includes("broker") || t.includes("financ")) return "practice";
  return "retail";
}

function moodFor(archetype: string): SiteSpec["mood"] {
  if (archetype === "workshop" || archetype === "gym" || archetype === "trade") return "industrial";
  if (archetype === "guesthouse" || archetype === "florist") return "lush";
  if (archetype === "salon" || archetype === "retail" || archetype === "practice") return "cool";
  return "warm";
}

export function fallbackSpec(input: {
  name: string;
  city: string;
  type: string;
  note?: string;
}): SiteSpec {
  const archetype = inferArchetype(input.type);
  const mood = moodFor(archetype);
  const time: SiteSpec["time"] = archetype === "restaurant" ? "golden" : "day";
  const name = input.name.trim() || "The Studio";
  const city = input.city.trim() || "Johannesburg";
  const note = input.note?.trim();
  return {
    name,
    city,
    archetype,
    tagline: note?.split(".")[0]?.slice(0, 80) || `${name} in ${city.split(",")[0]}`,
    about:
      note && note.length > 20
        ? note.slice(0, 520)
        : `${name} is an independent ${input.type || "business"} in ${city}. The page is a proposal — Call and WhatsApp sit above the fold. Nothing invented.`,
    services: [
      { title: "What they do", blurb: note?.slice(0, 140) || `The work of a ${input.type || "local shop"}.` },
      { title: "How to reach them", blurb: "Call or WhatsApp. No invented hours or prices." },
    ],
    cta: "WhatsApp",
    palette: PALETTES[mood][time],
    mood,
    time,
    personality: note,
  };
}

export function withAtmosphere(
  spec: SiteSpec,
  patch: { mood?: SiteSpec["mood"]; time?: SiteSpec["time"] },
): SiteSpec {
  const mood = patch.mood ?? spec.mood;
  const time = patch.time ?? spec.time;
  return { ...spec, mood, time, palette: PALETTES[mood][time] };
}
