import { nounFor } from "@/lib/craft";

export function TradeObject({
  type,
  name,
  accent = "#c9b496",
}: {
  type: string;
  name: string;
  accent?: string;
}) {
  const noun = nounFor(type, name);
  return (
    <div className="relative grid h-40 w-40 place-items-center [perspective:600px]">
      <div
        className="h-24 w-24 animate-[spin_12s_linear_infinite] rounded-sm"
        style={{
          transformStyle: "preserve-3d",
          background: `linear-gradient(145deg, ${accent}, #1a1612)`,
          boxShadow: `0 18px 40px color-mix(in srgb, ${accent} 35%, transparent)`,
        }}
        aria-hidden
      >
        <span className="sr-only">{noun}</span>
      </div>
      <p className="absolute bottom-1 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{noun}</p>
    </div>
  );
}
