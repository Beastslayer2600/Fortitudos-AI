import { useCallback, useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  answerReport,
  approveDocument,
  documentRegister,
  fullAnswer,
  markAnswer,
  residency,
  retention,
  type AnswerReport,
  type LoggedAnswer,
  type Register,
  type Residency,
  type Retention,
  type Verdict,
  wrongRateLabel,
} from "@/lib/desk-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const Route = createFileRoute("/evidence")({ component: EvidencePage });

/**
 * The compliance surface, in one place.
 *
 * Six controls were built as endpoints with nothing to reach them. The one
 * that suffers most is the answer log: it exists to turn "how often is this
 * wrong" from an estimate into a number, and it cannot, because marking an
 * answer wrong required a command line. An evidence log the adviser cannot add
 * to during the twenty seconds they have between clients does not get added
 * to, and the number stays an estimate.
 *
 * So the marking control is the first thing on the page, not a settings screen
 * three clicks in.
 */
function EvidencePage() {
  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-10 md:py-12">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">Evidence</p>
      <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">
        What this desk has done
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Every answer, what it was built from, and your verdict on it. Judge them
        as you go — the wrong-answer rate is the number that gets asked about,
        and it only exists if you mark them.
      </p>

      <Tabs defaultValue="answers" className="mt-8">
        <TabsList>
          <TabsTrigger value="answers">Answers</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="retention">Retention</TabsTrigger>
          <TabsTrigger value="residency">Residency</TabsTrigger>
        </TabsList>
        <TabsContent value="answers"><AnswersTab /></TabsContent>
        <TabsContent value="documents"><DocumentsTab /></TabsContent>
        <TabsContent value="retention"><RetentionTab /></TabsContent>
        <TabsContent value="residency"><ResidencyTab /></TabsContent>
      </Tabs>
    </div>
  );
}

/** Load once, expose a reload, and never leave the caller guessing why it is empty. */
function useDeskData<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  const refresh = useCallback(() => {
    setBusy(true);
    load()
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
    // `load` is a fresh closure each render; the caller passes a stable one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(refresh, [refresh]);
  return { data, error, busy, refresh };
}

function Panel({
  error,
  busy,
  empty,
  children,
}: {
  error: string;
  busy: boolean;
  empty?: boolean;
  children: React.ReactNode;
}) {
  if (error) {
    return (
      <p className="mt-6 rounded-md border border-border bg-card px-4 py-3 text-sm text-muted">
        {error}
      </p>
    );
  }
  if (busy) return <p className="mt-6 text-sm text-subtle">Reading the desk…</p>;
  if (empty) return <p className="mt-6 text-sm text-subtle">Nothing recorded yet.</p>;
  return <>{children}</>;
}

/* ------------------------------------------------------------------ answers */

function AnswersTab() {
  const { data, error, busy, refresh } = useDeskData<AnswerReport>(answerReport);
  const [onlyUnmarked, setOnlyUnmarked] = useState(false);

  const shown = useMemo(() => {
    if (!data) return [];
    return onlyUnmarked ? data.recent.filter((a) => !a.verdict) : data.recent;
  }, [data, onlyUnmarked]);

  return (
    <Panel error={error} busy={busy} empty={!!data && data.total === 0}>
      {data ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Questions answered" value={String(data.total)} />
            <Stat
              label="Time saved"
              value={`${data.hours_saved.toFixed(1)} h`}
              note={`at ${data.minutes_by_hand} min/question by hand`}
            />
            <Stat
              label="Judged wrong or thin"
              value={wrongRateLabel(data.wrong_rate)}
              note={
                data.wrong_rate === null
                  ? "mark a few below"
                  : `${Object.values(data.verdicts).reduce((a, b) => a + b, 0)} of ${data.total} marked`
              }
            />
            <Stat
              label="As-of questions"
              value={String(data.as_of_questions)}
              note="the normal systems cannot answer these"
            />
          </div>

          {data.unmarked > 0 ? (
            <p className="mt-4 text-sm text-muted">
              <strong className="text-fg">{data.unmarked}</strong> not yet judged.
            </p>
          ) : null}

          <div className="mt-6 flex items-center gap-3">
            <Button
              variant={onlyUnmarked ? "default" : "ghost"}
              size="sm"
              onClick={() => setOnlyUnmarked((v) => !v)}
            >
              {onlyUnmarked ? "Showing unjudged" : "Show unjudged only"}
            </Button>
            <Button variant="ghost" size="sm" onClick={refresh}>
              Refresh
            </Button>
          </div>

          <ul className="mt-4 flex flex-col gap-3">
            {shown.map((a) => (
              <AnswerRow key={a.id} answer={a} options={data.verdict_options} onMarked={refresh} />
            ))}
          </ul>
        </>
      ) : null}
    </Panel>
  );
}

function AnswerRow({
  answer,
  options,
  onMarked,
}: {
  answer: LoggedAnswer;
  options: Record<string, string>;
  onMarked: () => void;
}) {
  const [note, setNote] = useState(answer.verdict_note);
  const [full, setFull] = useState<string | null>(null);
  const [saving, setSaving] = useState<Verdict | "">("");
  const [failed, setFailed] = useState("");

  async function mark(verdict: Verdict) {
    setSaving(verdict);
    setFailed("");
    try {
      await markAnswer(answer.id, verdict, note);
      onMarked();
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving("");
    }
  }

  return (
    <li className="rounded-md border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-subtle">
        <Badge>{answer.room}</Badge>
        <span>{answer.asked_at.slice(0, 16).replace("T", " ")}</span>
        {answer.as_of ? <span>as of {answer.as_of}</span> : null}
        {answer.client_id ? <span>client file</span> : null}
        {answer.asked_by ? <span>asked by {answer.asked_by}</span> : null}
        {answer.flags.map((f) => (
          <Badge key={f}>{f}</Badge>
        ))}
        {answer.verdict ? (
          <Badge>judged {answer.verdict}</Badge>
        ) : null}
      </div>

      <p className="mt-2 text-sm text-fg">{answer.question}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-muted">
        {full ?? answer.preview}
        {answer.truncated && full === null ? "…" : ""}
      </p>
      {answer.truncated && full === null ? (
        <Button
          variant="ghost"
          size="sm"
          className="mt-1 px-0"
          onClick={() => void fullAnswer(answer.id).then((r) => setFull(r.answer))}
        >
          Show the whole answer
        </Button>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {(Object.keys(options) as Verdict[]).map((v) => (
          <Button
            key={v}
            size="sm"
            variant={answer.verdict === v ? "default" : "ghost"}
            disabled={saving !== ""}
            title={options[v]}
            onClick={() => void mark(v)}
          >
            {saving === v ? "…" : v}
          </Button>
        ))}
        <Input
          className="h-8 max-w-xs text-sm"
          placeholder="what was wrong with it?"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      {failed ? <p className="mt-2 text-sm text-muted">{failed}</p> : null}
    </li>
  );
}

/* ---------------------------------------------------------------- documents */

function DocumentsTab() {
  const { data, error, busy, refresh } = useDeskData<Register>(documentRegister);
  const [failed, setFailed] = useState("");

  async function approve(source: string) {
    setFailed("");
    try {
      // No name is sent. The backend takes the approver from the credential,
      // because a name typed here would be a claim rather than a fact.
      const res = await approveDocument(source);
      if (!res.ok) setFailed(res.message);
      refresh();
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <Panel error={error} busy={busy} empty={!!data && data.documents.length === 0}>
      {data ? (
        <>
          <p className="mt-6 text-sm text-muted">
            Governance is <strong className="text-fg">{data.mode}</strong>.{" "}
            {data.mode === "controlled"
              ? "A product document with no current approval is not indexed at all."
              : "Everything indexes, and answers citing an unapproved document say so."}
          </p>
          {failed ? <p className="mt-2 text-sm text-muted">{failed}</p> : null}
          <ul className="mt-4 flex flex-col gap-2">
            {data.documents.map((d) => (
              <li
                key={d.source}
                className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-card px-4 py-3"
              >
                <span className="flex-1 text-sm text-fg">{d.source}</span>
                <span className="text-[11px] text-subtle">{d.pages}p</span>
                {!d.governed ? (
                  <Badge>{d.kind} · not governed</Badge>
                ) : d.approved ? (
                  <Badge>
                    approved by {d.approved_by} · {d.approved_at.slice(0, 10)}
                  </Badge>
                ) : d.lapsed ? (
                  // Different from never approved, and the only one of the two
                  // that means somebody should be told.
                  <Badge>approval lapsed — the file changed</Badge>
                ) : (
                  <Badge>unapproved</Badge>
                )}
                {d.governed && !d.approved ? (
                  <Button size="sm" variant="ghost" onClick={() => void approve(d.source)}>
                    Approve
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </Panel>
  );
}

/* ---------------------------------------------------------------- retention */

function RetentionTab() {
  const { data, error, busy } = useDeskData<Retention>(retention);
  return (
    <Panel error={error} busy={busy}>
      {data ? (
        <>
          <p className="mt-6 max-w-2xl text-sm text-muted">{data.basis}</p>
          {data.due.length === 0 ? (
            <p className="mt-4 text-sm text-subtle">
              Nothing is past its retention period. Only closed clients are
              counted — an active client&rsquo;s records are not up for erasure
              however old they are.
            </p>
          ) : (
            <>
              <ul className="mt-4 flex flex-col gap-2">
                {data.due.map((d) => (
                  <li
                    key={d.client_id}
                    className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-card px-4 py-3 text-sm"
                  >
                    <span className="flex-1 text-fg">{d.client_id}</span>
                    <Badge>{d.status}</Badge>
                    <span className="text-subtle">
                      expired {d.expires_on} · {d.over_by_days} days ago
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 max-w-2xl text-sm text-muted">
                Nothing is erased on a timer, and there is no erase button here.
                Erasure is irreversible and reaches four separate places, so it
                runs from the command line where the dry run is the default:
                <code className="ml-1 text-fg">
                  python retention.py erase &lt;id&gt; --by &quot;name&quot;
                </code>
              </p>
            </>
          )}
        </>
      ) : null}
    </Panel>
  );
}

/* ---------------------------------------------------------------- residency */

function ResidencyTab() {
  const { data, error, busy } = useDeskData<Residency>(residency);
  return (
    <Panel error={error} busy={busy}>
      {data ? (
        <>
          {data.findings.length > 0 ? (
            <ul className="mt-6 flex flex-col gap-2">
              {data.findings.map((f) => (
                <li
                  key={f}
                  className="rounded-md border border-border bg-card px-4 py-3 text-sm text-fg"
                >
                  {f}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-6 text-sm text-muted">
              Every store holding personal data is under the data root, every
              job runs on this machine, and every external host in the source is
              a known one.
            </p>
          )}

          <Section title="Compute">
            <ul className="flex flex-wrap gap-2">
              {data.compute.map((c) => (
                <li key={c.job}>
                  <Badge>
                    {c.job} · {c.local ? "this machine" : "REMOTE"}
                  </Badge>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Outbound">
            <ul className="flex flex-col gap-2">
              {data.outbound.map((o) => (
                <li key={o.host} className="rounded-md border border-border bg-card px-4 py-3">
                  <p className="text-sm text-fg">{o.host}</p>
                  <p className="text-[11px] text-subtle">{o.purpose}</p>
                  <p className="text-[11px] text-muted">{o.who_calls}</p>
                </li>
              ))}
            </ul>
          </Section>

          <p className="mt-6 max-w-2xl text-[11px] text-subtle">
            This does not check that the disk is encrypted. That is the
            operating system&rsquo;s job and the desk cannot verify it honestly.
          </p>
        </>
      ) : null}
    </Panel>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <p className="text-[11px] tracking-[0.14em] text-subtle uppercase">{label}</p>
      <p className="mt-1 font-display text-2xl tracking-tight text-fg">{value}</p>
      {note ? <p className="mt-1 text-[11px] text-subtle">{note}</p> : null}
    </div>
  );
}
