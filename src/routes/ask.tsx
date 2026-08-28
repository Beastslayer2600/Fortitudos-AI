import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { askProduct } from "@/lib/ai";
import { SAMPLE_QUESTIONS } from "@/lib/product-docs";
import { searchPages } from "@/lib/retrieval";
import { useFortitudo } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";

export const Route = createFileRoute("/ask")({ component: AskPage });

function AskPage() {
  const [question, setQuestion] = useState("");
  const [pagesOnly, setPagesOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const addAskTurn = useFortitudo((s) => s.addAskTurn);
  const history = useFortitudo((s) => s.askHistory);
  const latest = history[0];

  async function run(q: string) {
    const query = q.trim();
    if (!query) return;
    const citations = searchPages(query, 3);
    if (pagesOnly) {
      addAskTurn({
        question: query,
        answer:
          citations.length === 0
            ? "No pages matched. Try a product term that appears in the guide — waiting period, otosclerosis, blindness, exclusion."
            : "Retrieved pages only. Read them below; the model was not called.",
        citations,
        pagesOnly: true,
      });
      return;
    }
    setBusy(true);
    try {
      const result = await askProduct({
        data: {
          question: query,
          extracts: citations.map((c) => ({
            source: c.source,
            page: c.page,
            title: c.title,
          })),
        },
      });
      if (!result.ok) {
        toast.error(result.error);
        addAskTurn({
          question: query,
          answer: result.error,
          citations,
          pagesOnly: false,
        });
        return;
      }
      addAskTurn({
        question: query,
        answer: result.text,
        citations,
        pagesOnly: false,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ask failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-8 md:px-10 md:py-12">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">
        Product index
      </p>
      <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">
        Ask the guide
      </h1>
      <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
        Answers come only from retrieved pages. Sample corpus — Fortitudo
        Lifestyle Protector — stands in until your own PDFs are indexed on the
        desk machine.
      </p>

      <form
        className="mt-8"
        onSubmit={(e) => {
          e.preventDefault();
          void run(question);
        }}
      >
        <label htmlFor="q" className="sr-only">
          Question
        </label>
        <Textarea
          id="q"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What waiting period applies to hearing loss?"
          className="min-h-24 text-base"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <Search />}
            {pagesOnly ? "Show pages" : "Ask"}
          </Button>
          <label className="flex h-11 items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={pagesOnly}
              onChange={(e) => setPagesOnly(e.target.checked)}
              className="size-4 accent-accent"
            />
            Pages only — no model
          </label>
        </div>
      </form>

      <div className="mt-5 flex flex-wrap gap-2">
        {SAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            className="rounded-full bg-elevated px-3 py-2 text-left text-xs text-muted shadow-[var(--shadow-border)] hover:text-fg"
            onClick={() => {
              setQuestion(q);
              void run(q);
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {latest && (
        <article className="mt-10 rounded-xl bg-surface p-5 shadow-[var(--shadow-border)] md:p-7">
          <p className="text-xs text-subtle">{formatDate(latest.createdAt)}</p>
          <h2 className="mt-1 font-display text-xl tracking-tight">
            {latest.question}
          </h2>
          {latest.pagesOnly && (
            <Badge className="mt-2" variant="accent">
              Pages only
            </Badge>
          )}
          <div className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-fg/90">
            {latest.answer}
          </div>
          <h3 className="mt-6 text-[11px] tracking-[0.18em] text-muted uppercase">
            Retrieved pages
          </h3>
          <ul className="mt-3 space-y-3">
            {latest.citations.map((c) => (
              <li
                key={`${c.source}-${c.page}`}
                className="rounded-md bg-elevated p-3 shadow-[var(--shadow-border)]"
              >
                <p className="text-sm">
                  {c.title}{" "}
                  <span className="text-subtle">
                    · p. {c.page} · {c.source}
                  </span>
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted">{c.excerpt}</p>
              </li>
            ))}
            {latest.citations.length === 0 && (
              <li className="text-sm text-muted">Nothing retrieved.</li>
            )}
          </ul>
        </article>
      )}

      {history.length > 1 && (
        <section className="mt-10">
          <h2 className="font-display text-xl tracking-tight">Earlier</h2>
          <ul className="mt-3 space-y-2">
            {history.slice(1, 8).map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className="w-full rounded-md px-3 py-2.5 text-left text-sm text-muted hover:bg-surface hover:text-fg"
                  onClick={() => setQuestion(t.question)}
                >
                  {t.question}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
