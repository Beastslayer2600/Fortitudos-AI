/**
 * Gert Fourie / Fortitudo Studios — Social Media Voice Profile
 * Standing instruction set for LinkedIn, Instagram, WhatsApp Status.
 * Source: fortitudostudios.site + outreach playbook (25 Aug 2026).
 */

export const SOCIAL_BRAND = {
  site: "https://www.fortitudostudios.site",
  tagline: "You work hard for your money. Let's structure it to endure.",
  signature: "Discipline over emotion. Structure over speculation.",
  bio: "Financial strategy for high-income professionals who value clarity, discipline, and long-term growth.",
  coreBelief:
    "Wealth is not built by reacting — it is built by structure, discipline, and long-term clarity.",
  positioning:
    "Stewardship over speculation, clarity over complexity. No market prediction or reactive advice — the value is the system.",
  audience:
    "Professionals, business owners, and families for whom earning is merely a starting point — money as a collection of products rather than a structure.",
  regulatory:
    "Gert Fourie, financial adviser under Liberty Group Limited (FSP 2409), Pretoria.",
} as const;

export type SitePageRef = {
  id: string;
  section: "Insights" | "Guides" | "Services" | "Home";
  title: string;
  path: string;
  url: string;
  argument: string;
  audienceHook: string;
};

/** Live source pages — claims must stay faithful to these arguments. */
export const SITE_PAGES: SitePageRef[] = [
  {
    id: "sequence-of-returns",
    section: "Insights",
    title: "Sequence of returns risk",
    path: "/insights/sequence-of-returns-risk",
    url: "https://www.fortitudostudios.site/insights/sequence-of-returns-risk",
    argument:
      "The order of returns near retirement can matter more than the long-run average. A bad sequence early in drawdown can permanently reduce the income a portfolio can sustain, even if average returns later recover.",
    audienceHook: "pre-retirees and retirees living off capital",
  },
  {
    id: "two-pot",
    section: "Insights",
    title: "South Africa's two-pot retirement system",
    path: "/insights/two-pot-retirement-system",
    url: "https://www.fortitudostudios.site/insights/two-pot-retirement-system",
    argument:
      "Two-pot did not change retirement in the abstract — it changed what you can actually touch, and when. Contributions split into a savings component accessible before retirement and a retirement component that is not. Misreading the split creates false liquidity assumptions.",
    audienceHook: "employees and professionals still contributing",
  },
  {
    id: "diversification",
    section: "Insights",
    title: "Why diversification isn't just about asset classes",
    path: "/insights/why-diversification-isnt-just-about-asset-classes",
    url: "https://www.fortitudostudios.site/insights/why-diversification-isnt-just-about-asset-classes",
    argument:
      "Owning several funds is not the same as being diversified. Correlation, concentration in a single employer or sector, and currency exposure can leave a portfolio looking broad while behaving as one risk.",
    audienceHook: "investor-minded professionals",
  },
  {
    id: "starter-salary",
    section: "Guides",
    title: "Building wealth on a starter salary",
    path: "/guides/building-wealth-on-a-starter-salary",
    url: "https://www.fortitudostudios.site/guides/building-wealth-on-a-starter-salary",
    argument:
      "Early-career income is limited, but the structure starts now: automate a small contribution, avoid lifestyle debt that compounds against you, and treat the first units of capital as a habit, not a windfall.",
    audienceHook: "younger and early-career professionals",
  },
  {
    id: "saving-painful",
    section: "Guides",
    title: "Why saving feels painful",
    path: "/guides/why-saving-feels-painful",
    url: "https://www.fortitudostudios.site/guides/why-saving-feels-painful",
    argument:
      "Saving feels like loss in the moment because present bias is real. The pain is the point of friction — structure (automation, rules, accounts with a purpose) reduces reliance on willpower.",
    audienceHook: "broad audience who know they should save and still resist",
  },
  {
    id: "wealthy-mindset",
    section: "Guides",
    title: "Rules of a wealthy mindset",
    path: "/guides/rules-of-a-wealthy-mindset",
    url: "https://www.fortitudostudios.site/guides/rules-of-a-wealthy-mindset",
    argument:
      "Wealthy behaviour is less about intensity and more about rules: decide once, execute repeatedly, and refuse to renegotiate the plan every time markets or emotions move.",
    audienceHook: "professionals building a personal operating system",
  },
  {
    id: "retirement-clarity",
    section: "Services",
    title: "Retirement Clarity",
    path: "/services",
    url: "https://www.fortitudostudios.site/services",
    argument:
      "Retirement planning starts with numbers you can defend — income need, gap analysis, and a structure that survives sequence risk — not a product brochure.",
    audienceHook: "pre-retirees who want clarity before products",
  },
  {
    id: "investment-discipline",
    section: "Services",
    title: "Investment Discipline",
    path: "/services",
    url: "https://www.fortitudostudios.site/services",
    argument:
      "Discipline is the system that prevents reaction: policy, rebalancing rules, and a written rationale so a bad week does not become a permanent change of plan.",
    audienceHook: "investors tired of reacting to headlines",
  },
  {
    id: "home",
    section: "Home",
    title: "Fortitudo Studios — home",
    path: "/",
    url: "https://www.fortitudostudios.site/",
    argument:
      "Structure money to endure: clarity, discipline, and long-term growth for professionals who already earn well but whose capital is still a collection of products.",
    audienceHook: "general professional audience",
  },
];

export const VOICE_SYSTEM = `You write social media posts as Gert Fourie of Fortitudo Studios (fortitudostudios.site).

Brand:
- Tagline: "${SOCIAL_BRAND.tagline}"
- Signature (use sparingly, not every post): "${SOCIAL_BRAND.signature}"
- Core belief: "${SOCIAL_BRAND.coreBelief}"
- Regulatory identity (public accuracy only when needed): ${SOCIAL_BRAND.regulatory}

Voice rules (non-negotiable):
1. Short, declarative sentences. Follow a short line with one longer sentence that builds the logic — not a string of short slogans.
2. State the problem or blind spot before the solution.
3. No hype, no exclamation points, no emojis.
4. Soft close only — open door language ("worth a conversation", "worth twenty minutes"), never a hard sell or urgency CTA.
5. Speak to a role or pattern, not a generic demographic.
6. First person, direct address ("I run into", "most people I speak to"). Avoid third-person brand-speak.
7. Jargon is fine if explained in the same breath.

Compliance:
- Do not invent returns, percentages, benefit figures, or product claims not present in the source argument provided.
- Do not give personalised advice to a named non-client.
- Gert remains responsible under FAIS for anything published under his name.

Output format — reply with valid JSON only, no markdown fence:
{
  "linkedin": "...",
  "instagram": "...",
  "leonardoPrompt": "...",
  "whatsapp": "...",
  "hashtags": ["#FinancialPlanning", "#WealthStructure", "#SouthAfrica"]
}

Platform constraints:
- LinkedIn: 80–150 words, short paragraphs with line breaks (use \n\n), specific article URL in the post, soft close.
- Instagram: 2–4 short lines, warmer but still no hype; say "link in bio" or name the guide; no raw URL required.
- Leonardo prompt: minimalist editorial, deep green / warm gold / cream paper feel, geometric or architectural structure motifs, no cash piles, no handshake stock, no people unless essential, negative space for text, no text in the image itself.
- WhatsApp Status: one line, sometimes two; optional short www.fortitudostudios.site link.
`;

export type SocialBatch = {
  linkedin: string;
  instagram: string;
  leonardoPrompt: string;
  whatsapp: string;
  hashtags: string[];
  pageId: string;
  pageUrl: string;
  pageTitle: string;
};

/** Offline deep-insight drafts faithful to the page argument (no model required). */
export function offlineSocialBatch(page: SitePageRef): SocialBatch {
  const linkedin = [
    `Most people I speak to still treat “${page.title.toLowerCase()}” as a headline, not a mechanic that changes their own numbers.`,
    ``,
    page.argument,
    ``,
    `Worth sitting with that for ${page.audienceHook} — not as a product pitch, as a structure question.`,
    ``,
    page.url,
  ].join("\n");

  const instagram = [
    `${page.title}: the part that actually changes behaviour is quieter than the headlines.`,
    page.argument.split(". ")[0] + ".",
    `Broke it down properly — link in bio.`,
  ].join("\n\n");

  const leonardoPrompt =
    "Minimalist editorial still life of a calm architectural foundation or balanced structure against soft negative space, deep green ink and warm gold accents on cream paper tones, quiet directional light, no people, no money piles, no logos or text, shot on 50mm, composition with empty upper third for caption overlay.";

  const whatsapp =
    page.id === "two-pot"
      ? "Two-pot changed what you can touch, not just what you're told. Worth actually understanding your own split. www.fortitudostudios.site"
      : `${page.argument.split(". ")[0]}. www.fortitudostudios.site`;

  return {
    linkedin,
    instagram,
    leonardoPrompt,
    whatsapp,
    hashtags: ["#FinancialPlanning", "#WealthStructure", "#SouthAfrica"],
    pageId: page.id,
    pageUrl: page.url,
    pageTitle: page.title,
  };
}
