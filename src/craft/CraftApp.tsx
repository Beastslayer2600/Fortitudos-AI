import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  SKU,
  TERRITORIES,
  claimGuard,
  jobFolderHint,
  mailtoLetter,
  newHandLead,
  nounFor,
  whatsappLink,
  type CraftLead,
} from "@/lib/craft";
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
            No invented claims.
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
          <div className="space-y-2">
            {leads.map((row) => (
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
                    {row.type} · {row.city} · {row.source}
                  </span>
                </span>
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{row.touch}</span>
              </button>
            ))}
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
            <Textarea placeholder="Facts only" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
            <Button className="w-full" onClick={addHand} disabled={!form.name.trim()}>
              Add to book
            </Button>
          </aside>
        </section>
      )}

      {step === "Audit" && lead && (
        <section className="space-y-4">
          <p className="text-sm text-muted-foreground">Job folder: {jobFolderHint(lead)}</p>
          <Input placeholder="https://their-site.example" value={auditUrl || lead.website} onChange={(e) => setAuditUrl(e.target.value)} />
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
              Send or call
            </Button>
          </div>
        </section>
      )}

      {step === "Send" && lead && (
        <section className="space-y-4">
          <p className="text-sm">Mock: {mockUrl}</p>
          <a href={mailtoLetter(lead, mockUrl)}>Open letter</a>
          {whatsappLink(lead.phone, lead.name, mockUrl) && (
            <a href={whatsappLink(lead.phone, lead.name, mockUrl)}>WhatsApp</a>
          )}
          <Button variant="outline" onClick={() => patchLead(lead.id, { touch: "sent" })}>
            Mark sent
          </Button>
        </section>
      )}
    </div>
  );
}
