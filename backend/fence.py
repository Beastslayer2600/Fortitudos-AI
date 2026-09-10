"""The ring-fence: proof that the shared code states nobody's identity.

The plan's rule is that a generic core is shared and the employer-specific
part never is. A one-time sweep through the files does not deliver that. The
strings come back — a name typed into a default, a product named in a comment,
an FSP number in a prompt someone was improving — and each one arrives looking
like a small convenience rather than like the thing that contaminates the
shared codebase.

So the fence is a check that runs, not a tidy-up that happened.

It reads the identity the desk is actually configured with and looks for those
exact values in the shared source. Not a fixed blocklist of one person's
details: a blocklist protects whoever wrote it and nobody else, and the next
adviser's name would sail through. What is forbidden is *the configured
identity appearing in shared code*, whoever's it is.

Three kinds of file, three rules:

  shared      Source that is meant to be handed over. No configured identity
              value may appear in it, and no employer or product name.
  local       Content that is the adviser's own — filed lessons, brand notes,
              product literature. Not fenced, and not shareable either; it is
              listed so that "what would I have to remove" has an answer.
  identity    This module and its data. Identity is expected here.

The fence is deliberately not clever about it. A string match on the values in
front of it, reported with file and line, so a person can look.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent

# Source that is meant to be shareable. Anything not listed here is not
# checked, so the list is the claim: these are the trees that must be clean.
SHARED_TREES = ("backend", "src", "scripts")

SHARED_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css"}

# Content that belongs to the adviser, not to the codebase. Excluded from the
# fence because it is not shared — and reported separately, because "this is
# what would have to come out" is the question the fence is really answering.
LOCAL_TREES = (
    "backend/docs/learn",
    "backend/docs/clients",
    "backend/data",
)

# Files that hold identity by design.
IDENTITY_FILES = (
    "backend/identity.py",
    "backend/fence.py",
    "backend/model/Modelfile",
)

# Names that are employer or product material wherever they appear in shared
# code. Unlike the configured identity, these cannot be read from settings —
# an employer's name is not one of the desk's own facts.
FORBIDDEN_IN_SHARED = (
    "Liberty Group",
    "Liberty Learning",
    "Lifestyle Protector",
)

# Identity fields worth fencing. Fields with generic defaults are still listed:
# the default is skipped in fenced_values(), so what gets searched for is the
# real value once somebody sets one. `city` is left out because a city name is
# not identifying on its own and matches ordinary prose.
FENCED_FIELDS = ("adviser_name", "fsp_name", "fsp_number", "practice_name",
                 "studio_name", "studio_site", "studio_email", "contact_phone",
                 "sample_product")

# A value has to be distinctive enough that finding it means something. "5" as
# an FSP number would match every line with a five in it.
MIN_VALUE_LENGTH = 4

# A run of digits long enough to be a phone number rather than a coincidence.
# Below this, stripping punctuation and comparing digits matches version
# strings, ports and array indices.
MIN_DIGIT_RUN = 9


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


@dataclass
class Breach:
    path: str
    line: int
    value: str
    why: str
    text: str = ""


@dataclass
class Report:
    breaches: List[Breach] = field(default_factory=list)
    checked: int = 0
    local_files: List[str] = field(default_factory=list)
    fenced_values: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.breaches


def _is_local(rel: str) -> bool:
    return any(rel == t or rel.startswith(t + "/") for t in LOCAL_TREES)


def _is_identity(rel: str) -> bool:
    return rel in IDENTITY_FILES


def shared_files() -> List[Path]:
    out = []
    for tree in SHARED_TREES:
        base = ROOT / tree
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in SHARED_SUFFIXES:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if "node_modules" in rel or "/.venv/" in rel or "__pycache__" in rel:
                continue
            if _is_local(rel) or _is_identity(rel):
                continue
            out.append(path)
    return out


def local_files() -> List[str]:
    out = []
    for tree in LOCAL_TREES:
        base = ROOT / tree
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                out.append(path.relative_to(ROOT).as_posix())
    return out


def fenced_values() -> List[Tuple[str, str]]:
    """(value, why) for each configured identity value worth searching for.

    A value equal to the shipped default is skipped. The defaults are generic
    by design — "the studio", "the practice" — so fencing them matches ordinary
    prose and reports the absence of identity as a breach, which is the one
    result that would make people stop running this.
    """
    import identity

    ident = identity.load(refresh=True)
    blank = identity.Identity()
    out: List[Tuple[str, str]] = []
    for name in FENCED_FIELDS:
        value = (getattr(ident, name, "") or "").strip()
        if value == (getattr(blank, name, "") or "").strip():
            continue
        if len(value) >= MIN_VALUE_LENGTH:
            out.append((value, f"configured {name}"))
    for name in FORBIDDEN_IN_SHARED:
        out.append((name, "employer or product material"))
    return out


def check(extra: Sequence[str] = ()) -> Report:
    """Look for the configured identity in code that is meant to be shared."""
    rep = Report()
    values = fenced_values() + [(v, "named on the command line") for v in extra
                                if len(v) >= MIN_VALUE_LENGTH]
    rep.fenced_values = [v for v, _ in values]
    rep.local_files = local_files()
    if not values:
        return rep

    for path in shared_files():
        rep.checked += 1
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lowered = text.lower()
        for value, why in values:
            # A phone number is the same fact written several ways. The first
            # version of this compared literal text only, and missed a
            # hardcoded wa.me link because the configured number carries
            # spaces and a plus while the URL is bare digits.
            digits = _digits(value)
            hunting_digits = len(digits) >= MIN_DIGIT_RUN
            if value.lower() not in lowered and not (
                    hunting_digits and digits in _digits(text)):
                continue
            for n, line in enumerate(text.splitlines(), start=1):
                hit = value.lower() in line.lower() or (
                    hunting_digits and digits in _digits(line))
                if hit:
                    rep.breaches.append(Breach(path=rel, line=n, value=value,
                                               why=why, text=line.strip()[:120]))
    return rep


def render(rep: Report) -> str:
    lines = ["Ring-fence — is the shared code free of this desk's identity?",
             "=" * 62,
             f"  {rep.checked} shared source files checked"]
    if not rep.fenced_values:
        lines.append("")
        lines.append("  Nothing to check for: no identity is configured, and")
        lines.append("  the fence has nothing to look for. This is not a pass —")
        lines.append("  configure identity.json, then run it again.")
        return "\n".join(lines) + "\n"

    lines.append(f"  looking for {len(rep.fenced_values)} value(s)")
    if rep.ok:
        lines.append("")
        lines.append("  CLEAN — no configured identity found in shared code.")
    else:
        lines.append("")
        by_file: Dict[str, List[Breach]] = {}
        for b in rep.breaches:
            by_file.setdefault(b.path, []).append(b)
        lines.append(f"  {len(rep.breaches)} breach(es) in {len(by_file)} file(s):")
        for path, items in sorted(by_file.items()):
            lines.append(f"\n  {path}")
            for b in items[:8]:
                lines.append(f"    {b.line:>5}  {b.why}: {b.value}")
                lines.append(f"           {b.text}")
            if len(items) > 8:
                lines.append(f"    ... and {len(items) - 8} more")
    if rep.local_files:
        lines.append("")
        lines.append(f"  {len(rep.local_files)} file(s) are the adviser's own content and are")
        lines.append("  not fenced. They are also not shareable — this is the list")
        lines.append("  of what would have to come out:")
        for rel in rep.local_files[:10]:
            lines.append(f"    {rel}")
        if len(rep.local_files) > 10:
            lines.append(f"    ... and {len(rep.local_files) - 10} more")
    return "\n".join(lines) + "\n"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="Check that shared code states nobody's identity.")
    ap.add_argument("--also", action="append", default=[],
                    help="an extra value to search for (repeatable)")
    args = ap.parse_args()
    rep = check(args.also)
    print(render(rep))
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
