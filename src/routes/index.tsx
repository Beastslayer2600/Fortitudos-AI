import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, BookOpen, Theater, Users } from "lucide-react";
import { PAGES } from "@/lib/product-docs";
import { useFortitudo } from "@/lib/store";
import { formatDate } from "@/lib/utils";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  const clients = useFortitudo((s) => s.clients);
  const sessions = useFortitudo((s) => s.sessions);
  const documents = useFortitudo((s) => s.documents);
  const askHistory = useFortitudo((s) => s.askHistory);

  return (
    <div className="mx-auto max-w-5xl px-5 py-10 md:px-10 md:py-14">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">
        Fortitudo Studios
      </p>
      <h1 className="mt-3 max-w-xl font-display text-4xl leading-[1.1] font-medium tracking-tight md:text-5xl">
        The desk, without the 271-page wait.
      </h1>
      <p className="mt-4 max-w-xl text-base leading-relaxed text-muted">
        Ask the product index with a page citation. Keep client files, notes,
        projections and meeting prep in one place. Mark performances with the
        same calm.
      </p>

      <div className="mt-10 grid gap-4 md:grid-cols-2">
        <DeskCard
          to="/ask"
          kicker="Adviser"
          title="Ask the index"
          body="Waiting periods, benefit scales, exclusions — retrieved as whole pages so tables stay intact."
        />
        <DeskCard
          to="/adjudication"
          kicker="Studio"
          title="Adjudication"
          body="Speech, visual arts, music, dance and choir — evidence, interpretation, then developmental feedback."
        />
      </div>

      <dl className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Indexed pages" value={String(PAGES.length)} />
        <Stat label="Clients" value={String(clients.length)} />
        <Stat label="Filed documents" value={String(documents.length)} />
        <Stat label="Open sessions" value={String(sessions.length)} />
      </dl>

      <div className="mt-12 grid gap-8 md:grid-cols-2">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-xl tracking-tight">Clients</h2>
            <Link to="/clients" className="text-sm text-muted hover:text-fg">
              All
            </Link>
          </div>
          <ul className="divide-y divide-border rounded-xl bg-surface shadow-[var(--shadow-border)]">
            {clients.slice(0, 4).map((c) => (
              <li key={c.id}>
                <Link
                  to="/clients/$clientId"
                  params={{ clientId: c.id }}
                  className="flex items-center justify-between gap-3 px-4 py-3.5 hover:bg-elevated/50"
                >
                  <span className="flex items-center gap-2.5">
                    <Users className="size-4 text-muted" />
                    <span>{c.name}</span>
                  </span>
                  <span className="text-xs text-subtle">{c.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-xl tracking-tight">Recent</h2>
            <Link to="/library" className="text-sm text-muted hover:text-fg">
              Library
            </Link>
          </div>
          <ul className="divide-y divide-border rounded-xl bg-surface shadow-[var(--shadow-border)]">
            {askHistory.slice(0, 3).map((t) => (
              <li key={t.id} className="px-4 py-3.5">
                <p className="text-sm">{t.question}</p>
                <p className="mt-1 text-xs text-subtle">{formatDate(t.createdAt)}</p>
              </li>
            ))}
            {askHistory.length === 0 && (
              <li className="flex items-start gap-3 px-4 py-3.5 text-sm text-muted">
                <BookOpen className="mt-0.5 size-4 shrink-0" />
                No questions yet. Try hearing loss waiting periods, or total
                blindness.
              </li>
            )}
            {sessions.slice(0, 2).map((s) => (
              <li key={s.id}>
                <Link
                  to="/adjudication/$sessionId"
                  params={{ sessionId: s.id }}
                  className="flex items-center gap-3 px-4 py-3.5 hover:bg-elevated/50"
                >
                  <Theater className="size-4 text-muted" />
                  <span className="min-w-0">
                    <span className="block truncate text-sm">{s.performer}</span>
                    <span className="block truncate text-xs text-subtle">
                      {s.title}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

function DeskCard({
  to,
  kicker,
  title,
  body,
}: {
  to: "/ask" | "/adjudication";
  kicker: string;
  title: string;
  body: string;
}) {
  return (
    <Link
      to={to}
      className="group rounded-xl bg-surface p-6 shadow-[var(--shadow-border)] transition-[box-shadow] duration-150 hover:shadow-[var(--shadow-border-hover)]"
    >
      <p className="text-[11px] tracking-[0.18em] text-muted uppercase">{kicker}</p>
      <h2 className="mt-2 font-display text-2xl tracking-tight">{title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
      <span className="mt-5 inline-flex items-center gap-1 text-sm text-accent">
        Open
        <ArrowRight className="size-4 transition-transform duration-150 group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-surface px-4 py-3 shadow-[var(--shadow-border)]">
      <dt className="text-[11px] text-subtle">{label}</dt>
      <dd className="mt-1 font-display text-2xl tabular-nums tracking-tight">{value}</dd>
    </div>
  );
}
