import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FolderSync, Loader2, Plus, Users } from "lucide-react";
import { toast } from "sonner";
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
import { useFortitudo } from "@/lib/store";
import { syncWerkClients } from "@/lib/sync-werk-clients";
import { CLIENT_STATUSES, type ClientStatus } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export const Route = createFileRoute("/clients/")({ component: ClientsPage });

function ClientsPage() {
  const clients = useFortitudo((s) => s.clients);
  const documents = useFortitudo((s) => s.documents);
  const hydrated = useFortitudo((s) => s.hydrated);
  const mergeFromDisk = useFortitudo((s) => s.mergeFromDisk);
  const lastDiskSyncAt = useFortitudo((s) => s.lastDiskSyncAt);
  const lastDiskSyncRoot = useFortitudo((s) => s.lastDiskSyncRoot);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<ClientStatus | "All">("All");
  const [syncing, setSyncing] = useState(false);
  const autoSynced = useRef(false);

  async function runSync(silent = false) {
    setSyncing(true);
    try {
      const result = await syncWerkClients();
      if (!result.ok) {
        if (!silent) toast.error(result.error);
        return;
      }
      const stats = mergeFromDisk(result.clients, result.root);
      if (!silent) {
        toast.success(
          `Synced ${result.clientCount} folders from ${result.root}`,
          {
            description: `+${stats.addedClients} clients · +${stats.addedDocuments} documents`,
          },
        );
      } else if (stats.addedClients > 0 || stats.addedDocuments > 0) {
        toast.message("Pulled FA clients from disk",
          {
            description: `${result.root} · +${stats.addedClients} clients · +${stats.addedDocuments} docs`,
          },
        );
      }
    } catch (err) {
      if (!silent) {
        toast.error(err instanceof Error ? err.message : "Sync failed");
      }
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    if (!hydrated || autoSynced.current) return;
    autoSynced.current = true;
    void runSync(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return clients.filter((c) => {
      if (statusFilter !== "All" && c.status !== statusFilter) return false;
      if (!needle) return true;
      return (
        c.name.toLowerCase().includes(needle) ||
        c.email.toLowerCase().includes(needle) ||
        c.phone.toLowerCase().includes(needle)
      );
    });
  }, [clients, q, statusFilter]);

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-10 md:py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] tracking-[0.22em] text-muted uppercase">
            Records
          </p>
          <h1 className="mt-2 font-display text-3xl tracking-tight md:text-4xl">
            Clients
          </h1>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Auto-pulls FA client folders from{" "}
            <span className="text-fg/80">C:\Werk\Clients</span> when the desk
            runs locally. Each subfolder becomes a client; files are filed by
            name/folder (FICA, FNA, Quote, …).
          </p>
          {lastDiskSyncAt && (
            <p className="mt-2 text-xs text-subtle">
              Last sync {formatDate(lastDiskSyncAt)}
              {lastDiskSyncRoot ? ` · ${lastDiskSyncRoot}` : ""}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={syncing}
            onClick={() => void runSync(false)}
          >
            {syncing ? (
              <Loader2 className="animate-spin" />
            ) : (
              <FolderSync />
            )}
            Sync from disk
          </Button>
          <Button onClick={() => setOpen(true)}>
            <Plus />
            New client
          </Button>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name, email, phone"
          aria-label="Search clients"
          className="max-w-xs"
        />
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as ClientStatus | "All")}
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All">All statuses</SelectItem>
            {CLIENT_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {filtered.length === 0 ? (
        <div className="mt-10 rounded-xl bg-surface px-6 py-14 text-center shadow-[var(--shadow-border)]">
          <Users className="mx-auto size-8 text-muted" />
          <p className="mt-4 font-display text-xl tracking-tight">
            {clients.length === 0 ? "No clients yet" : "No matches"}
          </p>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
            {clients.length === 0
              ? "Put one folder per client under C:\\Werk\\Clients, then Sync from disk — or create a client here."
              : "Try a different name or clear the status filter."}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Button
              variant="outline"
              disabled={syncing}
              onClick={() => void runSync(false)}
            >
              {syncing ? (
                <Loader2 className="animate-spin" />
              ) : (
                <FolderSync />
              )}
              Sync from disk
            </Button>
            {clients.length === 0 && (
              <Button onClick={() => setOpen(true)}>
                <Plus />
                New client
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-6 overflow-hidden rounded-xl bg-surface shadow-[var(--shadow-border)]">
          <table className="w-full text-left text-sm">
            <thead className="text-[11px] tracking-[0.14em] text-subtle uppercase">
              <tr className="border-b border-border">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="hidden px-4 py-3 font-medium sm:table-cell">
                  Status
                </th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">
                  Docs
                </th>
                <th className="px-4 py-3 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => {
                const count = documents.filter((d) => d.clientId === c.id)
                  .length;
                return (
                  <tr
                    key={c.id}
                    className="border-b border-border last:border-0"
                  >
                    <td className="px-4 py-3">
                      <Link
                        to="/clients/$clientId"
                        params={{ clientId: c.id }}
                        className="hover:text-accent"
                      >
                        {c.name}
                      </Link>
                      <div className="text-xs text-subtle sm:hidden">
                        {c.status}
                      </div>
                    </td>
                    <td className="hidden px-4 py-3 text-muted sm:table-cell">
                      {c.status}
                    </td>
                    <td className="hidden px-4 py-3 tabular-nums text-muted md:table-cell">
                      {count}
                    </td>
                    <td className="px-4 py-3 text-subtle">
                      {formatDate(c.updatedAt)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <NewClientDialog open={open} onOpenChange={setOpen} />
    </div>
  );
}

function NewClientDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const addClient = useFortitudo((s) => s.addClient);
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState<ClientStatus>("Intake");

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const id = addClient({ name, email, phone, status });
    onOpenChange(false);
    setName("");
    setEmail("");
    setPhone("");
    setStatus("Intake");
    void navigate({ to: "/clients/$clientId", params: { clientId: id } });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New client</DialogTitle>
          <DialogDescription>
            A folder-style record. Prefer folders under C:\Werk\Clients for the
            live FA desk; this form is for quick in-browser records.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-3" onSubmit={submit}>
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone</Label>
            <Input
              id="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Status</Label>
            <Select
              value={status}
              onValueChange={(v) => setStatus(v as ClientStatus)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CLIENT_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" className="mt-2 w-full">
            Create
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
