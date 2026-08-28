import { useEffect, useState, type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  BookOpen,
  FolderOpen,
  Inbox,
  LayoutGrid,
  Menu,
  MessageSquareText,
  MessagesSquare,
  Sparkles,
  Theater,
  Users,
} from "lucide-react";
import { Mark } from "@/components/mark";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useFortitudo } from "@/lib/store";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Desk", icon: LayoutGrid, exact: true },
  { to: "/chat", label: "Chat", icon: MessagesSquare },
  { to: "/ask", label: "Ask the index", icon: MessageSquareText },
  { to: "/library", label: "Library", icon: BookOpen },
  { to: "/clients", label: "Clients", icon: Users },
  { to: "/dropzone", label: "Drop zone", icon: Inbox },
  { to: "/social", label: "Social Studio", icon: Sparkles },
  { to: "/adjudication", label: "Adjudication", icon: Theater },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [open, setOpen] = useState(false);

  useEffect(() => {
    void Promise.resolve(useFortitudo.persist.rehydrate()).then(() => {
      useFortitudo.getState().setHydrated(true);
    });
  }, []);

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-fg focus:px-3 focus:py-2 focus:text-bg"
      >
        Skip to content
      </a>
      <div className="flex min-h-dvh">
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-border bg-surface md:flex">
          <NavBody pathname={pathname} />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 items-center gap-3 border-b border-border px-4 md:hidden">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Open menu">
                  <Menu />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0">
                <NavBody pathname={pathname} onNavigate={() => setOpen(false)} />
              </SheetContent>
            </Sheet>
            <Link to="/" className="flex items-center gap-2 text-fg">
              <Mark className="size-6" />
              <span className="font-display text-lg tracking-tight">Fortitudo</span>
            </Link>
          </header>
          <main id="main" className="min-w-0 flex-1">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}

function NavBody({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <Link
        to="/"
        onClick={onNavigate}
        className="flex items-center gap-3 px-5 pt-6 pb-5"
      >
        <Mark className="size-8 text-accent" />
        <div>
          <div className="font-display text-lg leading-tight tracking-tight">
            Fortitudo
          </div>
          <div className="text-[11px] tracking-[0.18em] text-muted uppercase">
            AI workspace
          </div>
        </div>
      </Link>
      <nav className="flex flex-1 flex-col gap-0.5 px-3">
        <p className="px-2 pt-2 pb-1 text-[10px] tracking-[0.2em] text-subtle uppercase">
          Adviser
        </p>
        {NAV.slice(0, 7).map((item) => (
          <NavLink
            key={item.to}
            item={item}
            pathname={pathname}
            onNavigate={onNavigate}
          />
        ))}
        <p className="px-2 pt-5 pb-1 text-[10px] tracking-[0.2em] text-subtle uppercase">
          Studio
        </p>
        {NAV.slice(7).map((item) => (
          <NavLink
            key={item.to}
            item={item}
            pathname={pathname}
            onNavigate={onNavigate}
          />
        ))}
      </nav>
      <div className="border-t border-border px-5 py-4 text-[11px] leading-relaxed text-subtle">
        Fast index, not an authority. Advice remains yours under FAIS.
        <a
          href="https://wa.me/27773866299"
          className="mt-2 flex items-center gap-1.5 text-muted hover:text-fg"
        >
          <FolderOpen className="size-3" />
          Fortitudo Studios
        </a>
      </div>
    </div>
  );
}

function NavLink({
  item,
  pathname,
  onNavigate,
}: {
  item: (typeof NAV)[number];
  pathname: string;
  onNavigate?: () => void;
}) {
  const active = item.exact
    ? pathname === item.to
    : pathname === item.to || pathname.startsWith(`${item.to}/`);
  const Icon = item.icon;
  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      className={cn(
        "flex h-11 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors duration-150",
        active ? "bg-elevated text-fg" : "text-muted hover:bg-elevated/60 hover:text-fg",
      )}
    >
      <Icon className="size-4" />
      {item.label}
    </Link>
  );
}
