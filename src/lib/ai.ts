import { createServerFn } from "@tanstack/react-start";
import { llmComplete } from "./llm.ts";
import { pageByRef } from "./retrieval.ts";
import { withIdentity } from "./fortitudo.ts";

const PRODUCT_TASK = `You answer questions about financial product documentation for a South African financial adviser.

Rules:
- Answer ONLY from the provided document extracts.
- Quote exact benefit wording, percentages and waiting periods verbatim.
- Always cite the source document and page number for every figure you give.
- If the extracts do not contain the answer, say so plainly. Never infer or estimate a benefit percentage, waiting period or exclusion that is not written in the text.
- If a benefit table is ambiguous or appears truncated, say so and tell the adviser to check the page directly.

You are a fast index, not an authority. The adviser is responsible for the advice given.`;

function offlineProductAnswer(
  question: string,
  blocks: string[],
  refs: { source: string; page: number; title: string }[],
) {
  if (!blocks.length) {
    return {
      ok: true as const,
      text: "No matching pages were retrieved. Try a more specific product term, or open the Library and read the page directly.",
    };
  }

  const cites = refs
    .map((r) => `p. ${r.page} — ${r.title} (${r.source})`)
    .join("; ");

  const body = blocks
    .map((b, i) => {
      const ref = refs[i];
      const label = ref
        ? `### ${ref.title} · page ${ref.page}`
        : `### Extract ${i + 1}`;
      return `${label}\n${b.replace(/^SOURCE:.*\n/, "")}`;
    })
    .join("\n\n");

  return {
    ok: true as const,
    text: `No local/cloud model answered. Retrieved pages for:\n\n“${question}”\n\nCitations: ${cites}\n\n${body}\n\n—\nStart Ollama (ollama serve) or set XAI_API_KEY. Verify every figure against the page.`,
  };
}

export const askProduct = createServerFn({ method: "POST" })
  .validator(
    (input: {
      question: string;
      extracts: { source: string; page: number; title: string }[];
    }) => input,
  )
  .handler(async ({ data }) => {
    const question = data.question.trim().slice(0, 800);
    if (!question) return { ok: false as const, error: "Ask a question first." };

    const refs = data.extracts.slice(0, 3);
    const blocks = refs.map((ref) => {
      const page = pageByRef(ref.source, ref.page);
      const body = page?.text ?? "";
      const clipped = body.slice(0, 3500);
      return `SOURCE: ${ref.source} — page ${ref.page} — ${ref.title}\n${clipped}`;
    });

    if (!blocks.length) {
      return {
        ok: true as const,
        text: "No matching pages were retrieved. Try a more specific product term, or open the library and read the page directly.",
      };
    }

    const user = `Question: ${question}\n\nDocument extracts:\n\n${blocks.join("\n\n---\n\n")}`;
    // Product wording is Advisor room work: same identity, standard and
    // refusals the Python desk applies, so the answer does not change character
    // depending on which half of the app the adviser reached.
    const result = await llmComplete(withIdentity("fa", PRODUCT_TASK), user, {
      maxTokens: 500,
      temperature: 0.1,
    });
    if (!result.ok) {
      return offlineProductAnswer(question, blocks, refs);
    }
    return { ok: true as const, text: result.text, provider: result.provider };
  });

export const draftClientNote = createServerFn({ method: "POST" })
  .validator(
    (input: {
      kind: "advice" | "roa" | "follow-up";
      clientName: string;
      status: string;
      notes: string;
      documents: string;
    }) => input,
  )
  .handler(async ({ data }) => {
    const kindLabel =
      data.kind === "advice"
        ? "an advice-summary draft"
        : data.kind === "roa"
          ? "an ROA structure draft"
          : "a follow-up action list";
    const system = `You draft internal working notes for a South African financial adviser. You are not giving advice to a client. Flag missing FICA/FNA/RPQ items. Do not invent product figures. Keep it concise.`;
    const user = `Write ${kindLabel} for client ${data.clientName} (status: ${data.status}).\n\nFiled documents:\n${data.documents.slice(0, 2000) || "(none listed)"}\n\nExisting notes:\n${data.notes.slice(0, 2000) || "(none)"}\n\nUse headings. Mark anything that must be verified against the product guide.`;
    const result = await llmComplete(system, user, {
      maxTokens: 450,
      temperature: 0.2,
    });
    if (!result.ok) return { ok: false as const, error: result.error };
    return { ok: true as const, text: result.text, provider: result.provider };
  });

export const dramaFeedback = createServerFn({ method: "POST" })
  .validator(
    (input: {
      domain: string;
      performer: string;
      title: string;
      criterion: string;
      score: number;
      observation: string;
      interpretation: string;
      vocabulary: string[];
    }) => input,
  )
  .handler(async ({ data }) => {
    const system = `You are a master adjudicator and performance psychologist specializing in ${data.domain}.\nYour goal is to transform the adjudicator's raw observations into professional, developmentally supportive feedback following the NEA Philosophy.\nUse psychologically safe language: avoid identity labels ("You are..."), focus on trainable choices ("The performance showed...").\nRespond with three short sections: Competence, Agency, and Next Challenge.`;
    const user = `Performer: ${data.performer}\nPerformance: ${data.title}\nCriterion: ${data.criterion}\nScore: ${data.score}/10\nRaw observations: ${data.observation || "(none)"}\nInterpretation: ${data.interpretation || "(none)"}\nTechnical vocabulary to use if accurate: ${data.vocabulary.join(", ")}\n\nWrite the drafted feedback now.`;
    const result = await llmComplete(system, user, {
      maxTokens: 400,
      temperature: 0.3,
    });
    if (!result.ok) return { ok: false as const, error: result.error };
    return { ok: true as const, text: result.text, provider: result.provider };
  });

export const classifyDocument = createServerFn({ method: "POST" })
  .validator(
    (input: { filename: string; text: string; clientNames: string[] }) => input,
  )
  .handler(async ({ data }) => {
    const system = `Classify a South African financial-advice file. Reply with JSON only: {"docType": one of ["FICA / Identity","RPQ","Signed FNA","Advice Report","Quote","ROA","Correspondence","Other"], "clientName": string or empty, "reason": short}.`;
    const user = `Filename: ${data.filename}\nKnown clients: ${data.clientNames.join("; ") || "(none)"}\nExtract (may be empty): ${data.text.slice(0, 1500)}`;
    const result = await llmComplete(system, user, {
      maxTokens: 200,
      temperature: 0.1,
    });
    if (!result.ok) return result;
    try {
      const jsonStart = result.text.indexOf("{");
      const jsonEnd = result.text.lastIndexOf("}");
      const parsed = JSON.parse(result.text.slice(jsonStart, jsonEnd + 1)) as {
        docType?: string;
        clientName?: string;
        reason?: string;
      };
      return { ok: true as const, ...parsed, provider: result.provider };
    } catch {
      return {
        ok: true as const,
        docType: "Other",
        clientName: "",
        reason: result.text,
        provider: result.provider,
      };
    }
  });
