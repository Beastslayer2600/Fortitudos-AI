import { useState, type FormEvent } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Plus, Theater } from "lucide-react";
import { DOMAIN_LIST, DOMAINS, scoreDescriptor } from "@/lib/drama-domains";
import { useFortitudo } from "@/lib/store";
import type { DramaDomain } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/utils";

export const Route = createFileRoute("/adjudication/")({
  component: AdjudicationList,
});

function AdjudicationList() {
  const sessions = useFortitudo((s) => s.sessions);
  const assessments = useFortitudo((s) => s.assessments);
  const [open, setOpen] = useState(false);

  function exportCsv() {
    const rows = [
      [
        "Session",
        "Performer",
        "Title",
        "Domain",
        "Criterion",
        "Score",
        "Observation",
        "Interpretation",
        "Competence",
        "Agency",
        "Challenge",
      ],
    ];
    for (const s of sessions) {
      const items = assessments.filter((a) => a.sessionId === s.id);
      if (!items.length) {
        rows.push([s.id, s.performer, s.title, s.domain, "", "", "", "", "", "", ""]);
        continue;
      }
      for (const a of items) {
        rows.push([
          s.id,
          s.performer,
          s.title,
          s.domain,
          a.criterion,
          String(a.score),
          a.observation,
          a.interpretation,
          a.feedbackCompetence,
          a.feedbackAgency,
          a.feedbackChallenge,
        ]);
      }
    }
    const csv = rows
      .map((r) => r.map((c) => `"${c.replaceAll('"', '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "fortitudo_adjudications.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-10 md:py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] tracking-[0.22em] text-muted uppercase">
            Studio
          </p>
          <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">
            Adjudication
          </h1>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Mark the performance, then write competence, agency and the next
            challenge. Identity labels stay off the page.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportCsv} disabled={!sessions.length}>
            Export CSV
          </Button>
          <Button onClick={() => setOpen(true)}>
            <Plus />
            New session
          </Button>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="mt-12 rounded-xl bg-surface px-6 py-14 text-center shadow-[var(--shadow-border)]">
          <Theater className="mx-auto size-8 text-muted" />
          <p className="mt-4 font-display text-xl tracking-tight">No sessions yet</p>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
            Open a marking sheet for a performer or group. Speech & Drama, Visual
            Arts, Music, Dance and Choirs are ready.
          </p>
          <Button className="mt-6" onClick={() => setOpen(true)}>
            <Plus />
            New session
          </Button>
        </div>
      ) : (
        <ul className="mt-8 space-y-3">
          {sessions.map((s) => {
            const items = assessments.filter((a) => a.sessionId === s.id);
            const avg = items.length
              ? items.reduce((n, a) => n + a.score, 0) / items.length
              : 0;
            const total = DOMAINS[s.domain].length;
            return (
              <li key={s.id}>
                <Link
                  to="/adjudication/$sessionId"
                  params={{ sessionId: s.id }}
                  className="block rounded-xl bg-surface px-5 py-4 shadow-[var(--shadow-border)] transition-[box-shadow] duration-150 hover:shadow-[var(--shadow-border-hover)]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-display text-xl tracking-tight">
                        {s.performer}
                      </p>
                      <p className="text-sm text-muted">{s.title}</p>
                    </div>
                    <Badge>{s.domain}</Badge>
                  </div>
                  <p className="mt-3 text-xs text-subtle">
                    {s.venue || "Venue not recorded"} · {formatDate(s.eventDate)} ·{" "}
                    {items.length}/{total} criteria
                    {items.length > 0 &&
                      ` · ${avg.toFixed(1)}/10 ${scoreDescriptor(avg)}`}
                  </p>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      <NewSessionDialog open={open} onOpenChange={setOpen} />
    </div>
  );
}

function NewSessionDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const addSession = useFortitudo((s) => s.addSession);
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [performer, setPerformer] = useState("");
  const [category, setCategory] = useState("");
  const [venue, setVenue] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [adjudicator, setAdjudicator] = useState("");
  const [domain, setDomain] = useState<DramaDomain>("Speech & Drama");

  function submit(e: FormEvent) {
    e.preventDefault();
    const id = addSession({
      title,
      performer,
      category,
      venue,
      eventDate,
      adjudicator,
      domain,
    });
    onOpenChange(false);
    setTitle("");
    setPerformer("");
    setCategory("");
    setVenue("");
    setEventDate("");
    setAdjudicator("");
    setDomain("Speech & Drama");
    void navigate({ to: "/adjudication/$sessionId", params: { sessionId: id } });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New session</DialogTitle>
          <DialogDescription>
            Production title and performer are required.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-3" onSubmit={submit}>
          <div className="space-y-1.5">
            <Label htmlFor="perf">Performer / group</Label>
            <Input
              id="perf"
              value={performer}
              onChange={(e) => setPerformer(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>Domain</Label>
            <Select
              value={domain}
              onValueChange={(v) => setDomain(v as DramaDomain)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DOMAIN_LIST.map((d) => (
                  <SelectItem key={d} value={d}>
                    {d}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cat">Category</Label>
              <Input
                id="cat"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="venue">Venue</Label>
              <Input
                id="venue"
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date">Date</Label>
              <Input
                id="date"
                type="date"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="adj">Adjudicator</Label>
              <Input
                id="adj"
                value={adjudicator}
                onChange={(e) => setAdjudicator(e.target.value)}
              />
            </div>
          </div>
          <Button type="submit" className="w-full">
            Open marking sheet
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
