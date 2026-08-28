import { createServerFn } from "@tanstack/react-start";
import {
  offlineSocialBatch,
  SITE_PAGES,
  VOICE_SYSTEM,
  type SocialBatch,
} from "./social-voice";

async function chat(system: string, user: string, maxTokens: number) {
  const apiKey = process.env.XAI_API_KEY;
  if (!apiKey) return { ok: false as const, error: "AI is not available in this environment." };

  const res = await fetch("https://api.x.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "grok-4.5",
      temperature: 0.35,
      max_tokens: maxTokens,
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
    }),
  });
  if (!res.ok) {
    return { ok: false as const, error: `xAI API error ${res.status}` };
  }
  const body = (await res.json()) as {
    choices: { message: { content: string } }[];
  };
  return { ok: true as const, text: body.choices[0]?.message.content ?? "" };
}

function parseBatch(text: string, pageId: string): SocialBatch | null {
  const page = SITE_PAGES.find((p) => p.id === pageId) ?? SITE_PAGES[0];
  try {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start < 0 || end < 0) return null;
    const parsed = JSON.parse(text.slice(start, end + 1)) as {
      linkedin?: string;
      instagram?: string;
      leonardoPrompt?: string;
      whatsapp?: string;
      hashtags?: string[];
    };
    if (!parsed.linkedin || !parsed.instagram || !parsed.whatsapp) return null;
    return {
      linkedin: parsed.linkedin.trim(),
      instagram: parsed.instagram.trim(),
      leonardoPrompt:
        parsed.leonardoPrompt?.trim() ||
        offlineSocialBatch(page).leonardoPrompt,
      whatsapp: parsed.whatsapp.trim(),
      hashtags: Array.isArray(parsed.hashtags)
        ? parsed.hashtags.map(String).slice(0, 6)
        : ["#FinancialPlanning", "#WealthStructure", "#SouthAfrica"],
      pageId: page.id,
      pageUrl: page.url,
      pageTitle: page.title,
    };
  } catch {
    return null;
  }
}

export const generateSocialBatch = createServerFn({ method: "POST" })
  .validator(
    (input: {
      pageId: string;
      angle?: string;
      roleFocus?: string;
    }) => input,
  )
  .handler(async ({ data }) => {
    const page =
      SITE_PAGES.find((p) => p.id === data.pageId) ?? SITE_PAGES[0];

    const fallback = offlineSocialBatch(page);

    if (!process.env.XAI_API_KEY) {
      return { ok: true as const, batch: fallback, mode: "offline" as const };
    }

    const user = [
      `Source page: ${page.title}`,
      `URL: ${page.url}`,
      `Section: ${page.section}`,
      `Argument (do not invent beyond this): ${page.argument}`,
      `Default audience hook: ${page.audienceHook}`,
      data.roleFocus?.trim()
        ? `Role focus for this batch: ${data.roleFocus.trim()}`
        : "",
      data.angle?.trim()
        ? `Additional angle from Gert: ${data.angle.trim()}`
        : "",
      "Write LinkedIn, Instagram, Leonardo prompt, WhatsApp Status as JSON.",
    ]
      .filter(Boolean)
      .join("\n");

    const result = await chat(VOICE_SYSTEM, user, 900);
    if (!result.ok) {
      return { ok: true as const, batch: fallback, mode: "offline" as const };
    }

    const batch = parseBatch(result.text, page.id) ?? fallback;
    return {
      ok: true as const,
      batch,
      mode: (parseBatch(result.text, page.id) ? "model" : "offline") as
        | "model"
        | "offline",
    };
  });
