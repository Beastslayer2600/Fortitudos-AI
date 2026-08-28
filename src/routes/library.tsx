import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PAGES } from "@/lib/product-docs";
import { sources } from "@/lib/retrieval";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export const Route = createFileRoute("/library")({ component: LibraryPage });

function LibraryPage() {
  const [q, setQ] = useState("");
  const [active, setActive] = useState<(typeof PAGES)[number] | null>(PAGES[0]);
  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return PAGES;
    return PAGES.filter(
      (p) =>
        p.title.toLowerCase().includes(needle) ||
        p.text.toLowerCase().includes(needle),
    );
  }, [q]);

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-10 md:py-12">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">Index</p>
      <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">
        Library
      </h1>
      <p className="mt-2 max-w-xl text-sm text-muted">
        Page-level index. Tables are kept as pipe-delimited rows so a benefit
        matrix still reads as a matrix.
      </p>

      <ul className="mt-6 flex flex-wrap gap-2">
        {sources().map((s) => (
          <li key={s.source}>
            <Badge>
              {s.source} · {s.pages} pages
            </Badge>
          </li>
        ))}
      </ul>

      <div className="mt-6">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter pages"
          aria-label="Filter pages"
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        <ul className="max-h-[28rem] space-y-1 overflow-auto rounded-xl bg-surface p-2 shadow-[var(--shadow-border)] lg:max-h-[36rem]">
          {list.map((p) => (
            <li key={`${p.source}-${p.page}`}>
              <button
                type="button"
                onClick={() => setActive(p)}
                className={`w-full rounded-md px-3 py-2.5 text-left text-sm ${
                  active?.page === p.page
                    ? "bg-elevated text-fg"
                    : "text-muted hover:text-fg"
                }`}
              >
                <span className="block text-[11px] text-subtle">p. {p.page}</span>
                {p.title}
              </button>
            </li>
          ))}
          {list.length === 0 && (
            <li className="px-3 py-4 text-sm text-muted">No pages match.</li>
          )}
        </ul>
        {active && (
          <article className="rounded-xl bg-surface p-5 shadow-[var(--shadow-border)] md:p-7">
            <p className="text-xs text-subtle">
              {active.source} · page {active.page}
            </p>
            <h2 className="mt-1 font-display text-2xl tracking-tight">
              {active.title}
            </h2>
            <pre className="mt-4 whitespace-pre-wrap font-sans text-sm leading-relaxed text-fg/90">
              {active.text}
            </pre>
          </article>
        )}
      </div>
    </div>
  );
}
