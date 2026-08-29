import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  SKU,
  TERRITORIES,
  claimGuard,
  doorLetter,
  jobFolderHint,
  mailtoLetter,
  mayContactElectronically,
  newHandLead,
  nounFor,
  whatsappLink,
  type CraftLead,
} from "@/lib/craft";
import { morningRoute, routeLabel, scoreLead } from "@/lib/craft-leadgen";
import { loadLedger, saveLedger } from "@/lib/craft-ledger";
import { fallbackSpec } from "@/lib/craft-spec";
import { TradeObject } from "@/craft/TradeObject";

const STEPS = ["Jobs", "Audit", "3D", "Page", "Send"] as const;
type Step = (typeof STEPS)[number];

export function CraftApp() {
  const [leads, setLeads] = useState<CraftLead[]>(() => loadLedger());
  const [step, setStep] = useState<Step>("Jobs");
  const [activeId, setActiveId] = useState<string | null>(leads[0]?.id ?? null);
  const [form, setForm] = useState({ name: "", city: "Kempton Park", type: "", phone: "", note: "" });
  const [auditUrl, setAuditUrl] = useState("");

  const lead = leads.find((l) => l.id === activeId) ?? leads[0] ?? null;
  const spec = useMemo(
    () =>
      lead
        ? fallbackSpec({
            name: lead.name,
            city: lead.city,
            type: lead.type,
            note: claimGuard(lead.note),
          })
        : null,
    [lead],
  );
  const route = useMemo(() => morningRoute(leads), [leads]);

  function commit(next: CraftLead[]) {
    setLeads(saveLedger(next));
  }

  function patchLead(id: string, patch: Partial<CraftLead>) {
    commit(leads.map((l) => (l.id === id ? { ...l, ...patch } : l)));
  }

  function addHand() {
    const created = newHandLead(form);
    commit([created, ...leads]);
    setActiveId(created.id);
    setForm({ name: "", city: "Kempton Park", type: "", phone: "", note: "" });
  }

  const mockPath = lead ? `/craft?shop=${encodeURIComponent(lead.id)}&view=page` : "/craft";
  const mockUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}${mockPath}`
      : `https://fortitudostudios.site${mockPath}`;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">Fortitudo Craft</p>
          <h1 className="font-serif text-3xl">One shop. One page. One letter.</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            R{SKU.price.toLocaleString("en-ZA")} once · R{SKU.deposit.toLocaleString("en-ZA")} to start.
            Walk the hot list. Do not blast WhatsApp.
          </p>
        </div>
        <nav className="flex flex-wrap gap-1">
          {STEPS.map((s) => (
            <Button key={s} size="sm" variant={step === s ? "default" : "outline"} onClick={() => setStep(s)}>
              {s}
            </Button>
          ))}
        </nav>
      </header>

      {step === "Jobs" && (
        <section className="grid gap-6 md:grid-cols-[1fr_280px]">
          <div className="space-y-3">
            {route.length > 0 && (
              <div className="rounded-lg border border-border p-3 text-sm">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">This morning</p>
                <p className="font-medium">{routeLabel(route)}</p>
                <p className="text-muted-foreground">{route.length} shops · print the letter · walk</p>
              </div>
            )}
            {leads.map((row) => {
              const s = scoreLead(row);
              return (
                <button
                  key={row.id}
                  type="button"
                  onClick={() => setActiveId(row.id)}
                  className={`flex w-full items-start justify-between rounded-lg border px-3 py-3 text-left ${
                    row.id === activeId ? "border-foreground/40 bg-muted/40" : "border-border"
                  }`}
                >
                  <span>
                    <span className="block font-medium">{row.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {row.type} · {row.city} · {s.reasons[0]}
                    </span>
                  </span>
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {s.band} · {row.touch}
                  </span>
                </button>
              );
            })}
          </div>
          <aside className="space-y-2 rounded-lg border border-border p-3">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Hand intake</p>
            <Input placeholder="Shop name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input placeholder="Trade" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} />
            <Input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            <select
              className="h-9 w-full rounded-md border border-input bg-transparent px-2 text-sm"
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
            >
              {TERRITORIES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <Textarea placeholder="Facts only — hours, trades, what is on the door" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
            <Button className="w-full" onClick={addHand} disabled={!form.name.trim()}>
              Add to book
            </Button>
          </aside>
        </section>
      )}

      {step === "Audit" && lead && (
        <section className="space-y-4">
          <p className="text-sm text-muted-foreground">Job folder: {jobFolderHint(lead)}</p>
          <p className="text-xs text-muted-foreground">{scoreLead(lead).reasons.join(" · ")}</p>
          <Input placeholder="Existing site or Facebook URL" value={auditUrl || lead.website} onChange={(e) => setAuditUrl(e.target.value)} />
          <Textarea rows={6} value={lead.note} onChange={(e) => patchLead(lead.id, { note: claimGuard(e.target.value) })} />
          <Button
            onClick={() => {
              patchLead(lead.id, { touch: "audited", website: auditUrl || lead.website });
              setStep("3D");
            }}
          >
            Mark audited → 3D
          </Button>
        </section>
      )}

      {step === "3D" && lead && spec && (
        <section className="grid gap-6 md:grid-cols-[1fr_auto] items-start">
          <div className="space-y-3">
            <p className="text-sm">
              Noun test: a {lead.type.toLowerCase()} gets a <strong>{nounFor(lead.type, lead.name)}</strong>.
            </p>
            <Button
              onClick={() => {
                patchLead(lead.id, { touch: "composed" });
                setStep("Page");
              }}
            >
              Lock object → Page
            </Button>
          </div>
          <TradeObject type={lead.type} name={lead.name} accent={spec.palette.accent} />
        </section>
      )}

      {step === "Page" && lead && spec && (
        <section className="overflow-hidden rounded-xl border" style={{ background: spec.palette.bg, color: spec.palette.light }}>
          <div className="p-6">
            <p className="text-xs uppercase tracking-[0.2em] opacity-70">{lead.city}</p>
            <h2 className="mt-1 font-serif text-4xl">{spec.name}</h2>
            <p className="mt-2 text-lg opacity-90">{spec.tagline}</p>
            <TradeObject type={lead.type} name={lead.name} accent={spec.palette.accent} />
          </div>
          <div className="flex justify-end p-4">
            <Button variant="outline" onClick={() => setStep("Send")}>
              Print letter
            </Button>
          </div>
        </section>
      )}

      {step === "Send" && lead && (
        <section className="space-y-4">
          <pre className="whitespace-pre-wrap rounded-lg border border-border p-4 text-sm">{doorLetter(lead, mockUrl)}</pre>
          <Button onClick={() => window.print()}>Print door letter</Button>
          <p className="text-xs text-muted-foreground">
            Electronic send only after YES. First WhatsApp is a consent ask.
          </p>
          {mayContactElectronically(lead).allowed ? (
            <>
              {mailtoLetter(lead, mockUrl) && (
                <a className="block text-sm underline" href={mailtoLetter(lead, mockUrl)}>
                  Email (consent-aware)
                </a>
              )}
              {whatsappLink(lead.phone, lead.name, mockUrl, lead.consent) && (
                <a className="block text-sm underline" href={whatsappLink(lead.phone, lead.name, mockUrl, lead.consent)}>
                  WhatsApp (consent-aware)
                </a>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No electronic send: {mayContactElectronically(lead).reason} The printed door letter is still fine.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => patchLead(lead.id, { consent: "asked", touch: "sent" })}>
              Mark asked
            </Button>
            <Button variant="outline" size="sm" onClick={() => patchLead(lead.id, { consent: "consented" })}>
              They said yes
            </Button>
            <Button variant="outline" size="sm" onClick={() => patchLead(lead.id, { consent: "refused" })}>
              They said no
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}
