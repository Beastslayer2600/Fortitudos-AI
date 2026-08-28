import { useEffect, useState, type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  BookOpen,
  FolderOpen,
  GraduationCap,
  Hammer,
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
  { to: "/ask", label: "Ask", icon: MessageSquareText },
  { to: "/library", label: "Library", icon: BookOpen },
  { to: "/clients", label: "Clients", icon: Users },
  { to: "/dropzone", label: "Drop", icon: Inbox },
  { to: "/learn", label: "Learn", icon: GraduationCap },
  { to: "/social", label: "Social", icon: Sparkles },
  { to: "/adjudication", label: "Studio", icon: Theater },
  { to: "/craft", label: "Craft", icon: Hammer },
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
      <div className="flex min-h-dvh">
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-border bg-surface/90 md:flex">
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
          <main id="main" className="min-w-0 flex-1 pb-20 md:pb-0">
            {children}
          </main>
          <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] md:hidden">
            {[NAV[0], NAV[1], NAV[6], NAV[9]].map((item) => {
              const active = item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`);
              const Icon = item.icon;
              return (
                <Link key={item.to} to={item.to} className={cn("flex min-h-14 flex-col items-center justify-center gap-1 text-[11px]", active ? "text-accent" : "text-muted")}>
                  <Icon className="size-5" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </div>
  );
}

function NavBody({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <Link to="/" onClick={onNavigate} className="flex items-center gap-3 px-5 pt-6 pb-5">
        <Mark className="size-8 text-accent" />
        <div>
          <div className="font-display text-lg leading-tight tracking-tight">Fortitudo</div>
          <div className="text-[11px] tracking-[0.22em] text-accent uppercase">One workspace</div>
        </div>
      </Link>
      <nav className="flex flex-1 flex-col gap-0.5 px-3">
        {NAV.map((item) => (
          <NavLink key={item.to} item={item} pathname={pathname} onNavigate={onNavigate} />
        ))}
      </nav>
      <div className="border-t border-border px-5 py-4 text-[11px] text-subtle">
        Fast index. Advice remains yours under FAIS.
        <a href="https://wa.me/27773866299" className="mt-2 flex items-center gap-1.5 text-muted">
          <FolderOpen className="size-3" /> Fortitudo Studios
        </a>
      </div>
    </div>
  );
}

function NavLink({ item, pathname, onNavigate }: { item: (typeof NAV)[number]; pathname: string; onNavigate?: () => void }) {
  const active = item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`);
  const Icon = item.icon;
  return (
    <Link to={item.to} onClick={onNavigate} className={cn("flex h-11 items-center gap-2.5 rounded-md px-2.5 text-sm", active ? "bg-elevated text-fg shadow-[0_0_0_1px_rgb(188_164_114_/_40%)]" : "text-muted hover:bg-elevated/60")}>
      <Icon className="size-4" />
      {item.label}
    </Link>
  );
}
