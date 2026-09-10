"""Where the data physically is, answered from the configuration rather than asserted.

POPIA s72 governs sending personal information across the border. The desk's
answer is meant to be its easiest win — everything is on the adviser's own
machine — and an easy win stated as a sentence in a document is worth very
little. "We are fully local" is what every vendor says.

So this reports, from the running configuration:

  storage    every directory and database the desk writes to, and whether it
             sits under the data root
  compute    every job, the host it resolves to, and whether that host is on
             this machine
  outbound   every external endpoint reachable from the source, found by
             reading the source rather than from a list somebody maintains

The third one is the point. A residency claim decays: someone adds a font, a
map tile, an analytics beacon, a QR service, and the claim quietly stops being
true while the document still says it is. Reading the source each time means
the answer is current or it fails.

Two things this deliberately does not do. It does not check that the *disk* is
encrypted — that is the operating system's job and the desk cannot verify it
honestly. And it does not follow what a *generated page* loads once a browser
opens it, beyond naming the endpoints baked into it: the desk does not fetch
those, the viewer does, which is a different disclosure and is reported as one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent

# Hosts that are this machine. Anything else is somewhere else, including a
# machine on the same desk — a second PC on the LAN is still a network hop and
# still a decision somebody made.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "0.0.0.0"}

# A URL in the source that the DESK itself calls, versus one it merely writes
# into a page for a browser to fetch later. Different disclosures.
FETCHED_BY_THE_DESK = "the desk calls this"
EMBEDDED_IN_OUTPUT = "written into a generated page; the viewer's browser calls it"
# A link on a generated page. Nothing is fetched unless a human clicks it, and
# what reaches the far end is a shop's public details, never client data.
LINKED_FOR_A_HUMAN = "a link on a generated page; only a visitor who clicks it"
# A vocabulary identifier in JSON-LD. It looks like a URL and is never resolved
# by anything — reporting it as egress would be wrong.
NEVER_RESOLVED = "a JSON-LD vocabulary identifier; never fetched by anyone"

# Where each known external endpoint comes from, so the report can say what it
# is for rather than only that it exists. An endpoint not listed here is still
# reported — as unclassified, which is the case worth noticing.
KNOWN = {
    "api.qrserver.com": ("QR image for a printed flyer", FETCHED_BY_THE_DESK),
    "fonts.googleapis.com": ("web font on a generated page", EMBEDDED_IN_OUTPUT),
    "fonts.gstatic.com": ("web font on a generated page", EMBEDDED_IN_OUTPUT),
    "maps.google.com": ("directions link on a shop page", LINKED_FOR_A_HUMAN),
    "wa.me": ("WhatsApp link on a shop page", LINKED_FOR_A_HUMAN),
    "schema.org": ("structured-data vocabulary", NEVER_RESOLVED),
}

URL_RE = re.compile(r"https?://([A-Za-z0-9._-]+)")

SOURCE_SUFFIXES = {".py", ".html"}


@dataclass
class Store:
    name: str
    path: str
    kind: str
    exists: bool = False
    under_data_root: bool = True
    holds_personal_data: bool = False


@dataclass
class Hop:
    job: str
    host: str
    local: bool
    carries_client_data: bool
    why: str = ""


@dataclass
class External:
    host: str
    where: List[str] = field(default_factory=list)
    purpose: str = ""
    who_calls: str = ""

    @property
    def classified(self) -> bool:
        return bool(self.purpose)


@dataclass
class Report:
    data_root: str = ""
    stores: List[Store] = field(default_factory=list)
    hops: List[Hop] = field(default_factory=list)
    external: List[External] = field(default_factory=list)

    @property
    def stray_stores(self) -> List[Store]:
        """Anything holding personal data outside the data root.

        The data root is the thing an adviser backs up, encrypts and can point
        at when asked where the client information lives. A store outside it is
        personal information in a place nobody is thinking about.
        """
        return [s for s in self.stores
                if s.holds_personal_data and not s.under_data_root]

    @property
    def remote_hops(self) -> List[Hop]:
        return [h for h in self.hops if not h.local]

    @property
    def unclassified(self) -> List[External]:
        return [e for e in self.external if not e.classified]

    @property
    def ok(self) -> bool:
        return not (self.stray_stores or self.remote_hops or self.unclassified)


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def stores() -> Tuple[List[Store], Path]:
    """Every place the desk writes, and whether it holds personal information."""
    import config

    root = Path(config.DATA_ROOT)
    found: List[Store] = []

    def add(name, path, kind, personal):
        p = Path(path)
        found.append(Store(name=name, path=str(p), kind=kind, exists=p.exists(),
                           under_data_root=_under(p, root),
                           holds_personal_data=personal))

    add("product index", config.DB_PATH, "sqlite",
        True)   # holds the extracted text of client documents too
    add("product documents", config.DOCS_DIR, "directory", False)
    add("generated mockups", config.MOCKS_DIR, "directory", False)

    import client_store
    add("client vault", client_store.CLIENTS_DIR, "directory", True)
    add("client records", client_store.CLIENT_DB, "sqlite", True)

    import answer_log, doc_register, desk_users, retention, identity, desk_auth
    add("answer log", answer_log.LOG_DB, "sqlite", True)
    add("document register", doc_register.REGISTER_DB, "sqlite", False)
    add("user directory", desk_users.USERS_DB, "sqlite", True)
    add("erasure receipts", retention.ERASURE_LOG, "sqlite", False)
    add("desk identity", identity.IDENTITY_FILE, "json", False)
    add("desk token", desk_auth.TOKEN_FILE, "secret", False)

    try:
        import sort_engine
        add("drop zone", sort_engine.DROP_ZONE, "directory", True)
        add("review area", sort_engine.REVIEW_ZONE, "directory", True)
    except Exception:
        pass
    return found, root


def is_local_host(host: str) -> bool:
    from compute import is_local
    return is_local(host)


def hops() -> List[Hop]:
    """Every job, and the machine its model work goes to."""
    import compute
    from llm import OLLAMA_HOST

    out = []
    for plan in compute.plans(OLLAMA_HOST):
        out.append(Hop(job=plan.job, host=plan.host,
                       local=is_local_host(plan.host),
                       carries_client_data=plan.carries_client_data,
                       why=plan.why))
    return out


def external(paths: Optional[Sequence[Path]] = None) -> List[External]:
    """Every external host named in the source.

    Read from the source rather than from a maintained list, because a
    maintained list is exactly what goes stale the week somebody adds a font.
    """
    if paths is None:
        paths = [p for p in sorted(ROOT.rglob("*"))
                 if p.is_file() and p.suffix in SOURCE_SUFFIXES
                 and "__pycache__" not in p.as_posix()
                 # Test and evaluation files name hosts in order to check this
                 # scan. Reading them would make every fixture a finding.
                 and not p.name.startswith("test_")
                 and p.name not in ("eval_desk.py",)]
    seen: Dict[str, External] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for host in set(URL_RE.findall(text)):
            if host in LOCAL_HOSTS or host.endswith(".local"):
                continue
            if _looks_like_a_placeholder(host):
                continue
            entry = seen.setdefault(host, External(host=host))
            try:
                rel = path.relative_to(ROOT).as_posix()
            except ValueError:
                rel = path.as_posix()
            if rel not in entry.where:
                entry.where.append(rel)
    for host, entry in seen.items():
        if host in KNOWN:
            entry.purpose, entry.who_calls = KNOWN[host]
    return [seen[h] for h in sorted(seen)]


def _looks_like_a_placeholder(host: str) -> bool:
    """Example hosts in docstrings and error messages are not real egress."""
    return (host.endswith((".example", ".example.com", ".example.net",
                           ".invalid", ".test"))
            or host in {"your-host", "example.com"}
            # A LAN address is a real hop and is reported by hops(), not here;
            # naming it in a comment about configuration is not egress.
            or re.fullmatch(r"192\.168\.\d+\.\d+", host) is not None
            or re.fullmatch(r"10\.\d+\.\d+\.\d+", host) is not None)


def check() -> Report:
    found, root = stores()
    return Report(data_root=str(root), stores=found, hops=hops(),
                  external=external())


def render(rep: Optional[Report] = None) -> str:
    rep = rep or check()
    lines = ["Data residency — where this desk's information actually is",
             "=" * 62, f"  data root   {rep.data_root}", "", "  Storage"]
    for s in rep.stores:
        # Only personal data outside the root is a problem. A directory of
        # product PDFs or public mockups living in the repo is where it is
        # meant to be, and marking it would teach the reader to ignore marks.
        problem = s.holds_personal_data and not s.under_data_root
        mark = "!!" if problem else "  "
        tag = "personal data" if s.holds_personal_data else ""
        here = "" if s.exists else "  (not created yet)"
        where = "" if s.under_data_root else "  [outside the data root]"
        lines.append(f"  {mark} {s.name:<20} {s.kind:<10} {tag}{here}{where}")
        if not s.under_data_root:
            lines.append(f"       {s.path}")

    lines += ["", "  Compute"]
    for h in rep.hops:
        mark = "  " if h.local else "!!"
        where = "this machine" if h.local else h.host
        lines.append(f"  {mark} {h.job:<20} {where}")

    lines += ["", "  Outbound"]
    if not rep.external:
        lines.append("     nothing — no external host appears in the source")
    for e in rep.external:
        mark = "  " if e.classified else "??"
        lines.append(f"  {mark} {e.host}")
        lines.append(f"       {e.purpose or 'UNCLASSIFIED — what is this for?'}")
        if e.who_calls:
            lines.append(f"       {e.who_calls}")
        lines.append(f"       {', '.join(e.where[:3])}")

    lines += ["", "-" * 62]
    if rep.ok:
        lines.append("  Every store holding personal data is under the data root,")
        lines.append("  every job runs on this machine, and every external host")
        lines.append("  in the source is a known one.")
    else:
        for s in rep.stray_stores:
            lines.append(f"  PERSONAL DATA OUTSIDE THE DATA ROOT: {s.name}")
            lines.append(f"    {s.path}")
            lines.append(f"    Move it under {rep.data_root} and point "
                         "FORTITUDO_INDEX_DB at the new path, or delete it and")
            lines.append("    re-run ingest. A fresh install already puts it there.")
        for h in rep.remote_hops:
            lines.append(f"  WORK LEAVES THIS MACHINE: {h.job} -> {h.host}")
        for e in rep.unclassified:
            lines.append(f"  UNKNOWN EXTERNAL HOST: {e.host} in {', '.join(e.where[:2])}")
    lines.append("")
    lines.append("  This does not check that the disk is encrypted. That is the")
    lines.append("  operating system's job and the desk cannot verify it honestly.")
    return "\n".join(lines) + "\n"


def main() -> int:
    rep = check()
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
