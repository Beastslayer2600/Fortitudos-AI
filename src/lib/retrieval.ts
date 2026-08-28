import { PAGES, type ProductPage } from "./product-docs";
import type { AskCitation } from "./types";

const STOP = new Set([
  "the",
  "and",
  "for",
  "that",
  "with",
  "this",
  "from",
  "under",
  "what",
  "does",
  "apply",
  "applies",
  "about",
  "into",
  "your",
  "their",
  "have",
  "has",
]);

function tokens(text: string) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9%]+/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 2 && !STOP.has(t));
}

export function searchPages(query: string, topK = 3): AskCitation[] {
  const q = tokens(query);
  if (!q.length) return [];
  const scored = PAGES.map((page) => {
    const hay = `${page.source} ${page.title} ${page.text}`.toLowerCase();
    const pageTokens = tokens(page.text);
    const overlap = q.filter((t) => pageTokens.includes(t)).length;
    const literal = q.filter((t) => hay.includes(t)).length;
    const density = overlap / Math.sqrt(pageTokens.length + 1);
    const score = density + literal * 0.15;
    return { page, score };
  })
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);

  return scored.map(({ page, score }) => ({
    source: page.source,
    page: page.page,
    title: page.title,
    excerpt: excerpt(page, q),
    score,
  }));
}

function excerpt(page: ProductPage, q: string[]) {
  const text = page.text.replace(/\s+/g, " ").trim();
  const lower = text.toLowerCase();
  let idx = -1;
  for (const t of q) {
    const at = lower.indexOf(t);
    if (at >= 0 && (idx < 0 || at < idx)) idx = at;
  }
  if (idx < 0) return text.slice(0, 280);
  const start = Math.max(0, idx - 80);
  const slice = text.slice(start, start + 320);
  return `${start > 0 ? "…" : ""}${slice}${start + 320 < text.length ? "…" : ""}`;
}

export function pageByRef(source: string, page: number) {
  return PAGES.find((p) => p.source === source && p.page === page) ?? null;
}

export function sources() {
  const map = new Map<string, number>();
  for (const p of PAGES) map.set(p.source, (map.get(p.source) ?? 0) + 1);
  return [...map.entries()].map(([source, pages]) => ({ source, pages }));
}
