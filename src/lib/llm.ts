/**
 * Local-first chat for the Fortitudo desk.
 *
 * The desk is local-first and it holds client files. A cloud call is therefore
 * never a fallback — only a choice. `auto` means Ollama, and a dead Ollama is
 * an error the caller handles offline, NOT a reason to send the prompt to a
 * third party. Reaching xAI requires FORTITUDO_LLM=xai, set deliberately.
 *
 * Env:
 *   OLLAMA_HOST=http://127.0.0.1:11434
 *   OLLAMA_MODEL=fortitudo           (falls back to FORTITUDO_CHAT_MODEL)
 *   FORTITUDO_LLM=auto|ollama|xai    (default auto — local only)
 *   XAI_API_KEY=…                    (inert unless FORTITUDO_LLM=xai)
 *   XAI_MODEL=grok-4.5
 */

export type LlmMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type LlmResult =
  | { ok: true; text: string; provider: "ollama" | "xai" }
  | { ok: false; error: string; provider: "none" | "ollama" | "xai" };

export function ollamaHost() {
  return (
    process.env.OLLAMA_HOST?.trim().replace(/\/$/, "") ||
    "http://127.0.0.1:11434"
  );
}

/**
 * The chat model. The Python desk reads FORTITUDO_CHAT_MODEL; this path used to
 * read only OLLAMA_MODEL and default to something else entirely, so the two
 * halves of the desk answered on different models. One name now, and the
 * default is the desk's own model rather than a stock one.
 */
export const DEFAULT_MODEL = "fortitudo";

export function ollamaModel() {
  return (
    process.env.OLLAMA_MODEL?.trim() ||
    process.env.FORTITUDO_CHAT_MODEL?.trim() ||
    DEFAULT_MODEL
  );
}

export function xaiModel() {
  return process.env.XAI_MODEL?.trim() || "grok-4.5";
}

export function llmMode(): "auto" | "ollama" | "xai" {
  const m = (process.env.FORTITUDO_LLM || "auto").trim().toLowerCase();
  if (m === "ollama" || m === "xai") return m;
  return "auto";
}

async function callOllama(
  messages: LlmMessage[],
  opts: { temperature: number; maxTokens: number },
): Promise<LlmResult> {
  const host = ollamaHost();
  const model = ollamaModel();
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 180_000);
    const res = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        model,
        stream: false,
        options: {
          temperature: opts.temperature,
          num_predict: opts.maxTokens,
        },
        messages: messages.map((m) => ({
          role: m.role,
          content: m.content,
        })),
      }),
    });
    clearTimeout(timer);
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      return {
        ok: false,
        provider: "ollama",
        error: `Ollama ${res.status}: ${body.slice(0, 200) || res.statusText}. Is model “${model}” pulled? (ollama pull ${model})`,
      };
    }
    const data = (await res.json()) as {
      message?: { content?: string };
      response?: string;
    };
    const text = data.message?.content ?? data.response ?? "";
    return { ok: true, text, provider: "ollama" };
  } catch (err) {
    const msg =
      err instanceof Error
        ? err.name === "AbortError"
          ? "Ollama timed out (model too slow or busy)"
          : err.message
        : "Ollama unreachable";
    return {
      ok: false,
      provider: "ollama",
      error: `${msg}. Start Ollama and run: ollama pull ${model}`,
    };
  }
}

async function callXai(
  messages: LlmMessage[],
  opts: { temperature: number; maxTokens: number },
): Promise<LlmResult> {
  const apiKey = process.env.XAI_API_KEY;
  if (!apiKey) {
    return { ok: false, provider: "xai", error: "XAI_API_KEY not set" };
  }
  try {
    const res = await fetch("https://api.x.ai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: xaiModel(),
        temperature: opts.temperature,
        max_tokens: opts.maxTokens,
        messages,
      }),
    });
    if (!res.ok) {
      return {
        ok: false,
        provider: "xai",
        error: `xAI API error ${res.status}`,
      };
    }
    const body = (await res.json()) as {
      choices: { message: { content: string } }[];
    };
    return {
      ok: true,
      text: body.choices[0]?.message.content ?? "",
      provider: "xai",
    };
  } catch (err) {
    return {
      ok: false,
      provider: "xai",
      error: err instanceof Error ? err.message : "xAI request failed",
    };
  }
}

/**
 * Chat completion. Local Ollama first in auto mode.
 */
export async function llmChat(
  messages: LlmMessage[],
  opts: { temperature?: number; maxTokens?: number } = {},
): Promise<LlmResult> {
  const temperature = opts.temperature ?? 0.2;
  const maxTokens = opts.maxTokens ?? 800;
  const mode = llmMode();

  if (mode === "ollama") {
    return callOllama(messages, { temperature, maxTokens });
  }
  if (mode === "xai") {
    return callXai(messages, { temperature, maxTokens });
  }

  // auto is local. A dead Ollama is an error, not a reason to leave the machine:
  // the prompt on this path can carry client work, and the moment it silently
  // reached a third party the desk stopped being local-first without saying so.
  const local = await callOllama(messages, { temperature, maxTokens });
  if (local.ok) return local;

  return {
    ok: false,
    provider: "ollama",
    error: process.env.XAI_API_KEY
      ? `${local.error} — xAI is configured but is not used as a fallback. Set FORTITUDO_LLM=xai to send this prompt off the machine.`
      : local.error,
  };
}

/** Convenience: system + user string. */
export async function llmComplete(
  system: string,
  user: string,
  opts?: { temperature?: number; maxTokens?: number },
) {
  return llmChat(
    [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
    opts,
  );
}

export async function probeLlm(): Promise<{
  ollama: { ok: boolean; host: string; model: string; detail: string };
  xai: { ok: boolean; detail: string };
  preferred: "ollama" | "xai" | "none";
}> {
  const host = ollamaHost();
  const model = ollamaModel();
  let ollamaOk = false;
  let ollamaDetail = "";
  try {
    const res = await fetch(`${host}/api/tags`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = (await res.json()) as {
        models?: { name: string }[];
      };
      const names = (data.models || []).map((m) => m.name);
      const has =
        names.some((n) => n === model || n.startsWith(`${model}:`) || n.startsWith(model));
      ollamaOk = true;
      ollamaDetail = has
        ? `online · model ${model} available`
        : `online · model “${model}” not found. Installed: ${names.slice(0, 8).join(", ") || "(none)"}. Run: ollama pull ${model}`;
      if (!has) ollamaOk = false;
    } else {
      ollamaDetail = `HTTP ${res.status}`;
    }
  } catch {
    ollamaDetail = `not reachable at ${host} — is Ollama running?`;
  }

  const xaiOk = Boolean(process.env.XAI_API_KEY);
  const mode = llmMode();
  let preferred: "ollama" | "xai" | "none" = "none";
  if (mode === "ollama") preferred = ollamaOk ? "ollama" : "none";
  else if (mode === "xai") preferred = xaiOk ? "xai" : "none";
  // No `else if (xaiOk)`: auto never prefers the cloud, however healthy it is.
  else preferred = ollamaOk ? "ollama" : "none";

  return {
    ollama: { ok: ollamaOk, host, model, detail: ollamaDetail },
    xai: {
      ok: xaiOk,
      detail: xaiOk
        ? mode === "xai"
          ? "XAI_API_KEY set · in use (FORTITUDO_LLM=xai)"
          : "XAI_API_KEY set · not used — auto stays on this machine"
        : "XAI_API_KEY not set",
    },
    preferred,
  };
}
