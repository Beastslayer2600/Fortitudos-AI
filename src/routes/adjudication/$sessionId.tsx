import { useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { dramaFeedback } from "@/lib/ai";
import { DOMAINS, scoreDescriptor } from "@/lib/drama-domains";
import { useFortitudo } from "@/lib/store";
import type { DramaAssessment } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const Route = createFileRoute("/adjudication/$sessionId")({
  component: SessionPage,
});

function SessionPage() {
  const { sessionId } = Route.useParams();
  const session = useFortitudo((s) => s.sessions.find((x) => x.id === sessionId));
  const allAssessments = useFortitudo((s) => s.assessments);
  const assessments = allAssessments.filter((a) => a.sessionId === sessionId);
  const saveAssessment = useFortitudo((s) => s.saveAssessment);
  const updateSession = useFortitudo((s) => s.updateSession);
  const criteria = session ? DOMAINS[session.domain] : [];
  const [active, setActive] = useState(criteria[0]?.name ?? "");
  const [busy, setBusy] = useState(false);

  const current = criteria.find((c) => c.name === active) ?? criteria[0];
  const saved = assessments.find((a) => a.criterion === current?.name);

  const [form, setForm] = useState<Partial<DramaAssessment>>({});
  const merged = {
    score: saved?.score ?? 6,
    observation: saved?.observation ?? "",
    interpretation: saved?.interpretation ?? "",
    feedbackCompetence: saved?.feedbackCompetence ?? "",
    feedbackAgency: saved?.feedbackAgency ?? "",
    feedbackChallenge: saved?.feedbackChallenge ?? "",
    ...form,
    criterion: current?.name,
  };

  const avg = assessments.length
    ? assessments.reduce((n, a) => n + a.score, 0) / assessments.length
    : 0;

  function switchCriterion(name: string) {
    setActive(name);
    setForm({});
  }

  function save(patch: Partial<DramaAssessment> = {}) {
    if (!session || !current) return;
    const next = { ...merged, ...patch };
    saveAssessment({
      sessionId: session.id,
      criterion: current.name,
      score: Number(next.score) || 1,
      observation: String(next.observation ?? ""),
      interpretation: String(next.interpretation ?? ""),
      feedbackCompetence: String(next.feedbackCompetence ?? ""),
      feedbackAgency: String(next.feedbackAgency ?? ""),
      feedbackChallenge: String(next.feedbackChallenge ?? ""),
    });
    toast.success("Saved");
  }

  async function aiDraft() {
    if (!session || !current) return;
    setBusy(true);
    try {
      const result = await dramaFeedback({
        data: {
          domain: session.domain,
          performer: session.performer,
          title: session.title,
          criterion: current.name,
          score: Number(merged.score) || 1,
          observation: String(merged.observation ?? ""),
          interpretation: String(merged.interpretation ?? ""),
          vocabulary: current.vocabulary,
        },
      });
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      const parts = splitFeedback(result.text);
      setForm((f) => ({ ...f, ...parts }));
      saveAssessment({
        sessionId: session.id,
        criterion: current.name,
        score: Number(merged.score) || 1,
        observation: String(merged.observation ?? ""),
        interpretation: String(merged.interpretation ?? ""),
        feedbackCompetence: parts.feedbackCompetence,
        feedbackAgency: parts.feedbackAgency,
        feedbackChallenge: parts.feedbackChallenge,
      });
      toast.success("Feedback drafted — edit before you share");
    } finally {
      setBusy(false);
    }
  }

  const report = useMemo(() => {
    if (!session) return "";
    return buildReport(session, assessments);
  }, [session, assessments]);

  if (!session || !current) {
    return (
      <div className="px-5 py-16 text-center">
        <p className="text-muted">Session not found.</p>
        <Link to="/adjudication" className="mt-3 inline-block text-sm text-accent">
          Back
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-10 md:py-12">
      <Link to="/adjudication" className="text-sm text-muted hover:text-fg">
        Adjudication
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl tracking-tight">{session.performer}</h1>
          <p className="mt-1 text-muted">{session.title}</p>
        </div>
        <div className="text-right">
          <p className="font-display text-3xl tabular-nums tracking-tight">
            {assessments.length ? avg.toFixed(1) : "—"}
          </p>
          <p className="text-xs text-subtle">
            {assessments.length
              ? `${scoreDescriptor(avg)} · ${assessments.length}/${criteria.length}`
              : "No marks yet"}
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        <ul className="space-y-1 rounded-xl bg-surface p-2 shadow-[var(--shadow-border)]">
          {criteria.map((c) => {
            const a = assessments.find((x) => x.criterion === c.name);
            const on = c.name === current.name;
            return (
              <li key={c.name}>
                <button
                  type="button"
                  onClick={() => switchCriterion(c.name)}
                  className={`flex w-full items-center justify-between rounded-md px-3 py-2.5 text-left text-sm ${
                    on ? "bg-elevated text-fg" : "text-muted hover:text-fg"
                  }`}
                >
                  <span className="pr-2">{c.name}</span>
                  <span className="tabular-nums text-xs text-subtle">
                    {a ? `${a.score}` : "—"}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>

        <div className="space-y-4">
          <section className="rounded-xl bg-surface p-5 shadow-[var(--shadow-border)]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-display text-2xl tracking-tight">
                  {current.name}
                </h2>
                <p className="mt-1 text-sm text-muted">{current.description}</p>
              </div>
              <Badge>{scoreDescriptor(Number(merged.score) || 1)}</Badge>
            </div>
            <div className="mt-5">
              <Label htmlFor="score">Score {merged.score}/10</Label>
              <input
                id="score"
                type="range"
                min={1}
                max={10}
                value={merged.score}
                onChange={(e) =>
                  setForm((f) => ({ ...f, score: Number(e.target.value) }))
                }
                className="mt-2 w-full accent-accent"
              />
            </div>
            <div className="mt-4 space-y-1.5">
              <Label htmlFor="obs">Observation</Label>
              <Textarea
                id="obs"
                value={String(merged.observation)}
                onChange={(e) =>
                  setForm((f) => ({ ...f, observation: e.target.value }))
                }
              />
            </div>
            <div className="mt-4 space-y-1.5">
              <Label htmlFor="intp">Interpretation</Label>
              <Textarea
                id="intp"
                value={String(merged.interpretation)}
                onChange={(e) =>
                  setForm((f) => ({ ...f, interpretation: e.target.value }))
                }
              />
            </div>
            <p className="mt-3 text-xs text-subtle">
              Vocabulary: {current.vocabulary.join(" · ")}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" onClick={() => save()}>
                Save criterion
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => void aiDraft()}
              >
                {busy && <Loader2 className="animate-spin" />}
                Draft NEA feedback
              </Button>
            </div>
          </section>

          <section className="rounded-xl bg-surface p-5 shadow-[var(--shadow-border)]">
            <h3 className="font-display text-xl tracking-tight">
              Developmental feedback
            </h3>
            <div className="mt-4 space-y-3">
              <div className="space-y-1.5">
                <Label>Competence</Label>
                <Textarea
                  value={String(merged.feedbackCompetence)}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, feedbackCompetence: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label>Agency</Label>
                <Textarea
                  value={String(merged.feedbackAgency)}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, feedbackAgency: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label>Next challenge</Label>
                <Textarea
                  value={String(merged.feedbackChallenge)}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, feedbackChallenge: e.target.value }))
                  }
                />
              </div>
            </div>
          </section>

          <section className="rounded-xl bg-surface p-5 shadow-[var(--shadow-border)]">
            <h3 className="font-display text-xl tracking-tight">Session close</h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="out">Outcome</Label>
                <Input
                  id="out"
                  value={session.outcome}
                  onChange={(e) =>
                    updateSession(session.id, { outcome: e.target.value })
                  }
                />
              </div>
            </div>
            <div className="mt-3 space-y-1.5">
              <Label htmlFor="over">Overall note</Label>
              <Textarea
                id="over"
                value={session.overallNote}
                onChange={(e) =>
                  updateSession(session.id, { overallNote: e.target.value })
                }
              />
            </div>
            <Button
              type="button"
              variant="outline"
              className="mt-4"
              onClick={() => downloadMarkdown(session.performer, session.title, report)}
            >
              Download report
            </Button>
          </section>
        </div>
      </div>
    </div>
  );
}

function splitFeedback(text: string) {
  const competence = sliceSection(text, /competence/i, /agency/i);
  const agency = sliceSection(text, /agency/i, /next challenge|challenge/i);
  const challenge = sliceSection(text, /next challenge|challenge/i, /$/);
  return {
    feedbackCompetence: competence || text,
    feedbackAgency: agency,
    feedbackChallenge: challenge,
  };
}

function sliceSection(text: string, start: RegExp, end: RegExp) {
  const s = text.search(start);
  if (s < 0) return "";
  const after = text.slice(s);
  const firstLine = after.indexOf("\n");
  const body = firstLine >= 0 ? after.slice(firstLine + 1) : after;
  const e = body.search(end);
  return (e >= 0 ? body.slice(0, e) : body).trim();
}

function buildReport(
  session: {
    title: string;
    performer: string;
    category: string;
    venue: string;
    eventDate: string;
    adjudicator: string;
    domain: string;
    outcome: string;
    overallNote: string;
  },
  assessments: DramaAssessment[],
) {
  const lines = [
    "# Adjudication report",
    "",
    `**Production:** ${session.title}`,
    `**Performer / group:** ${session.performer}`,
    `**Category:** ${session.category || "[not recorded]"}`,
    `**Venue:** ${session.venue || "[not recorded]"}`,
    `**Date:** ${session.eventDate || "[not recorded]"}`,
    `**Adjudicator:** ${session.adjudicator || "[not recorded]"}`,
    `**Domain:** ${session.domain}`,
    `**Outcome:** ${session.outcome || "[not recorded]"}`,
    "",
    "## Overall note",
    session.overallNote || "[No overall note recorded]",
    "",
    "## Criteria",
  ];
  for (const item of assessments) {
    lines.push(
      `### ${item.criterion} — ${item.score}/10 (${scoreDescriptor(item.score)})`,
      "",
      `**Observation:** ${item.observation || "[Not recorded]"}`,
      `**Interpretation:** ${item.interpretation || "[Not recorded]"}`,
      "",
      `**Competence:** ${item.feedbackCompetence || "[Not recorded]"}`,
      `**Agency:** ${item.feedbackAgency || "[Not recorded]"}`,
      `**Next challenge:** ${item.feedbackChallenge || "[Not recorded]"}`,
      "",
    );
  }
  lines.push(
    "---",
    "Internal working record. Review for accuracy and fairness before sharing.",
  );
  return lines.join("\n");
}

function downloadMarkdown(performer: string, title: string, report: string) {
  const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${performer}_${title}.md`.replace(/[^\w.-]+/g, "_");
  a.click();
  URL.revokeObjectURL(url);
}
