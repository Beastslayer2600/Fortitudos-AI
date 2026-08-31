"use client";

import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import {
  CalendarClock,
  FileWarning,
  Hammer,
  Inbox,
  Receipt,
  Theater,
  Users,
} from "lucide-react";
import { buildOpsBrief, type BriefItem, type BriefKind } from "@/lib/ops-brief";
import { useFortitudo } from "@/lib/store";
import { cn } from "@/lib/utils";

const ICONS: Record<BriefKind, typeof Inbox> = {
  meeting: CalendarClock,
  lead: Hammer,
  mockup: Hammer,
  invoice: Receipt,
  drama: Theater,
  drop: Inbox,
  followup: CalendarClock,
  client: Users,
};

function ItemChip({ item }: { item: BriefItem }) {
  const Icon = ICONS[item.kind] ?? FileWarning;
  const body = (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-elevated/80 px-2.5 py-1 text-[11px] text-muted",
        item.urgency === "today" && "border-accent/40 text-fg",
      )}
    >
      <Icon className="size-3 shrink-0 text-accent" />
      <span className="truncate">{item.title}</span>
    </span>
  );
  if (item.href) {
    return (
      <Link to={item.href} className="hover:opacity-90">
        {body}
      </Link>
    );
  }
  return body;
}

export function OpsBriefStrip({ className }: { className?: string }) {
  const clients = useFortitudo((s) => s.clients);
  const sessions = useFortitudo((s) => s.sessions);
  const dropItems = useFortitudo((s) => s.dropItems);
  const hydrated = useFortitudo((s) => s.hydrated);

  const brief = useMemo(
    () => buildOpsBrief({ clients, sessions, dropItems }),
    [clients, sessions, dropItems],
  );

  if (!hydrated) return null;

  return (
    <section
      className={cn(
        "rounded-xl border border-border bg-surface/80 px-4 py-3 shadow-[var(--shadow-border)]",
        className,
      )}
      aria-label="Today's brief"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[11px] tracking-[0.18em] text-accent uppercase">
          Today
        </p>
        <p className="text-xs text-subtle">{brief.summary}</p>
      </div>
      {brief.items.length > 0 ? (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {brief.items.map((item) => (
            <ItemChip key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted">
          No pending drops, intakes, or craft follow-ups. Ask in chat to start
          an FNA, log a lead, or schedule a session.
        </p>
      )}
    </section>
  );
}
