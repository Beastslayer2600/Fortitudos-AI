import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Copy, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { generateSocialBatch } from "@/lib/social-ai";
import {
  SITE_PAGES,
  SOCIAL_BRAND,
  type SocialBatch,
} from "@/lib/social-voice";

export const Route = createFileRoute("/social")({ component: SocialPage });

function SocialPage() {
  const [pageId, setPageId] = useState(SITE_PAGES[1]?.id ?? SITE_PAGES[0].id);
  const [roleFocus, setRoleFocus] = useState("");
  const [angle, setAngle] = useState("");
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState<SocialBatch | null>(null);
  const [mode, setMode] = useState<"model" | "offline" | null>(null);

  const page = useMemo(
    () => SITE_PAGES.find((p) => p.id === pageId) ?? SITE_PAGES[0],
    [pageId],
  );

  async function run() {
    setBusy(true);
    try {
      const result = await generateSocialBatch({
        data: { pageId, roleFocus, angle },
      });
      if (!result.ok) {
        toast.error("Could not generate posts");
        return;
      }
      setBatch(result.batch);
      setMode(result.mode);
      toast.success(
        result.mode === "model"
          ? "Deep insight draft ready — review before posting"
          : "Offline draft from page argument — review before posting",
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-10 md:py-12">
      <p className="text-[11px] tracking-[0.22em] text-muted uppercase">
        Fortitudo Studios
      </p>
      <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">
        Social Studio
      </h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
        LinkedIn, Instagram, and WhatsApp Status in Gert's voice — problem first,
        no hype, soft close, always tied to a real page on{" "}
        <a
          href={SOCIAL_BRAND.site}
          className="text-fg/80 underline-offset-2 hover:underline"
          target="_blank"
          rel="noreferrer"
        >
          fortitudostudios.site
        </a>
        . You remain responsible under FAIS for anything published under your
        name.
      </p>
      <p className="mt-3 max-w-2xl text-xs text-subtle">
        {SOCIAL_BRAND.signature}
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="space-y-4 rounded-xl bg-surface p-5 shadow-[var(--shadow-border)]">
          <div className="space-y-1.5">
            <Label>Source page</Label>
            <Select value={pageId} onValueChange={setPageId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SITE_PAGES.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.section}: {p.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs leading-relaxed text-subtle">{page.argument}</p>
            <a
              href={page.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-accent hover:underline"
            >
              {page.url}
            </a>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="role">Role focus (optional)</Label>
            <Input
              id="role"
              value={roleFocus}
              onChange={(e) => setRoleFocus(e.target.value)}
              placeholder="e.g. SaaS founder with equity + variable pay"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="angle">Angle note (optional)</Label>
            <Textarea
              id="angle"
              value={angle}
              onChange={(e) => setAngle(e.target.value)}
              placeholder="Anything you want stressed this week — still must stay faithful to the page."
              rows={3}
            />
          </div>

          <Button className="w-full" disabled={busy} onClick={() => void run()}>
            {busy ? (
              <Loader2 className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            Generate deep-insight batch
          </Button>
        </div>

        <div className="space-y-4">
          {!batch ? (
            <div className="rounded-xl bg-surface px-6 py-14 text-center text-sm text-muted shadow-[var(--shadow-border)]">
              Choose a source page and generate. Offline mode still produces a
              full draft from the page argument when the model key is absent.
            </div>
          ) : (
            <>
              {mode && (
                <p className="text-xs text-subtle">
                  Mode: {mode === "model" ? "model + voice profile" : "offline template"}{" "}
                  · review before publishing
                </p>
              )}
              <PostCard title="LinkedIn" body={batch.linkedin} />
              <PostCard
                title="Instagram caption"
                body={`${batch.instagram}\n\n${batch.hashtags.join(" ")}`}
              />
              <PostCard title="Leonardo prompt" body={batch.leonardoPrompt} />
              <PostCard title="WhatsApp Status" body={batch.whatsapp} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function PostCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl bg-surface p-5 shadow-[var(--shadow-border)]">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-display text-lg tracking-tight">{title}</h2>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(body);
              toast.success("Copied");
            } catch {
              toast.error("Could not copy");
            }
          }}
        >
          <Copy className="size-3.5" />
          Copy
        </Button>
      </div>
      <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-fg/90">
        {body}
      </pre>
    </div>
  );
}
