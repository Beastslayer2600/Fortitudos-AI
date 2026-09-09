/**
 * Who this desk belongs to — loaded, never hardcoded.
 *
 * The mirror of backend/identity.py. Same rule, same reason: an adviser's name
 * or an FSP number compiled into shared source is a fact about one person baked
 * into code that is meant to be handed over, and a product name compiled in is
 * employer material living in a repository meant to be provably clean of it.
 *
 * Defaults are blank or generic on purpose. Not a plausible-looking placeholder
 * — a desk that ships with "FSP 00000" will eventually put that on a document.
 * Where a field is unset, the code using it must omit the claim rather than
 * invent one, which is the rule the rest of the desk already follows about
 * facts it does not have.
 *
 * The backend owns the values; the browser asks for them once via
 * `GET /api/identity` and calls `setIdentity`. Until then, everything reads the
 * generic defaults, so a page that renders before the fetch lands states
 * nothing untrue.
 */

export type Identity = {
  adviserName: string;
  fspName: string;
  fspNumber: string;
  practiceName: string;
  studioName: string;
  studioSite: string;
  studioEmail: string;
  contactPhone: string;
  city: string;
  sampleProduct: string;
};

export const BLANK_IDENTITY: Identity = {
  adviserName: "",
  fspName: "",
  fspNumber: "",
  practiceName: "the practice",
  studioName: "the studio",
  studioSite: "",
  studioEmail: "",
  contactPhone: "",
  city: "Gauteng",
  sampleProduct: "",
};

let current: Identity = { ...BLANK_IDENTITY };

export function identity(): Identity {
  return current;
}

/** Replace the desk's identity. Unknown keys are ignored; blanks do not overwrite. */
export function setIdentity(next: Partial<Identity> | null | undefined): Identity {
  if (!next) return current;
  const merged = { ...current };
  for (const key of Object.keys(BLANK_IDENTITY) as (keyof Identity)[]) {
    const value = next[key];
    // An empty string from the server means "not configured", which must not
    // wipe a default like "the practice" and leave the page rendering nothing.
    if (typeof value === "string" && value.trim()) merged[key] = value.trim();
  }
  current = merged;
  return current;
}

export function resetIdentity(): Identity {
  current = { ...BLANK_IDENTITY };
  return current;
}

/**
 * "Name (Body FSP 1234)" — or as much of it as is actually known.
 *
 * Assembled rather than stored, so a half-configured desk states half a fact
 * instead of a malformed whole one.
 */
export function licenceLine(id: Identity = current): string {
  const who = id.adviserName.trim();
  const body = id.fspName.trim();
  const num = id.fspNumber.trim();
  const licence = [body, num ? `FSP ${num}` : ""].filter(Boolean).join(" ");
  if (who && licence) return `${who} (${licence})`;
  return who || licence;
}

/** Whether anyone has told this desk who it belongs to. */
export function isConfigured(id: Identity = current): boolean {
  return Boolean(id.adviserName || id.fspNumber || id.fspName);
}

/** Identity fields a regulated document needs and does not have. */
export function missingForDocument(id: Identity = current): string[] {
  return (["adviserName", "fspName", "fspNumber"] as const).filter(
    (k) => !id[k].trim(),
  );
}

/** Fetch the desk's identity once and install it. Never throws. */
export async function loadIdentity(
  fetcher: typeof fetch = fetch,
  base = "",
): Promise<Identity> {
  try {
    const res = await fetcher(`${base}/api/identity`);
    if (!res.ok) return current;
    return setIdentity((await res.json()) as Partial<Identity>);
  } catch {
    // A desk that will not render because it could not learn its own name is
    // worse than one that renders without stating it.
    return current;
  }
}
