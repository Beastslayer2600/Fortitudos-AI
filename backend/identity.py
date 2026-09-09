"""Who this desk belongs to — loaded, never hardcoded.

The desk currently states its own identity in about fifteen files: an FSP
number in the advice room's system prompt, an adviser's name in the RoA
defaults, a studio name and phone number in the outreach copy, a product name
in a doctrine comment. Each one was correct when it was written and each one is
now a fact about one person baked into shared code.

That matters for a specific reason. The plan for this codebase is that a
generic core is shared and the employer-specific part never is. An FSP number
compiled into `expert_route.py` means the core cannot be handed to anybody
without handing over the identity too, and — more seriously — a product name
compiled into the code is the thin end of employer material living in a
repository that is meant to be provably clean of it.

So identity is data.

**Defaults are deliberately blank or generic.** Not a placeholder that looks
like a real FSP number — a desk that ships with `FSP 00000` will eventually put
that on a document. Where a field is unset, the code that uses it must omit the
claim rather than invent one, which is the same rule the whole desk already
follows about facts it does not have.

**Real values live outside the repository**, in `identity.json` beside the
vault, or in the environment. The file is in .gitignore for the same reason the
client vault is: the thing that stops employer material reaching a public
remote is that it is not in the working tree to begin with.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, Optional

from config import DATA_ROOT

IDENTITY_FILE = Path(os.environ.get("FORTITUDO_IDENTITY_FILE")
                     or (DATA_ROOT / "identity.json"))

# Every field maps to one environment variable, so a desk can be configured
# without a file at all — which is what a container or a colleague's machine
# will want.
ENV_PREFIX = "FORTITUDO_ID_"


@dataclass(frozen=True)
class Identity:
    """The desk's own facts. Empty means "not stated", never "make one up"."""

    # The person giving advice, and the licence they give it under.
    adviser_name: str = ""
    fsp_name: str = ""
    fsp_number: str = ""

    # The advisory practice, as it appears on a document or a storefront.
    practice_name: str = "the practice"

    # The web studio side of the business. Separate on purpose: Craft is not
    # regulated work and must not borrow the advisory licence's identity.
    studio_name: str = "the studio"
    studio_site: str = ""
    studio_email: str = ""

    contact_phone: str = ""
    city: str = "Gauteng"

    # A product the desk knows about by name, used only in examples and
    # doctrine. Naming an employer's product in shared code is exactly the
    # leak this module exists to close.
    sample_product: str = ""

    @property
    def licence_line(self) -> str:
        """"Name (FSP 1234)" — or as much of it as is actually known.

        Assembled rather than stored, so a half-configured desk states half a
        fact instead of a malformed whole one.
        """
        who = self.adviser_name.strip()
        body = self.fsp_name.strip()
        num = self.fsp_number.strip()
        licence = " ".join(p for p in (body, f"FSP {num}" if num else "") if p)
        if who and licence:
            return f"{who} ({licence})"
        return who or licence

    @property
    def configured(self) -> bool:
        """Whether anyone has told this desk who it belongs to."""
        return bool(self.adviser_name or self.fsp_number or self.fsp_name)

    def missing(self) -> list:
        """The identity fields a regulated document would need and lacks."""
        return [name for name in ("adviser_name", "fsp_name", "fsp_number")
                if not getattr(self, name).strip()]

    def as_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["licence_line"] = self.licence_line
        out["configured"] = self.configured
        return out


_FIELDS = {f.name for f in fields(Identity)}
_CACHE: Optional[Identity] = None


def _from_file() -> Dict[str, str]:
    try:
        raw = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    # Unknown keys are ignored rather than raising: an identity file written
    # for a later version of the desk must not stop this one starting.
    return {k: str(v) for k, v in raw.items() if k in _FIELDS and v is not None}


def _from_env() -> Dict[str, str]:
    out = {}
    for name in _FIELDS:
        value = os.environ.get(ENV_PREFIX + name.upper())
        if value is not None and value.strip():
            out[name] = value.strip()
    return out


def load(refresh: bool = False) -> Identity:
    """The desk's identity. Environment wins over file, file over defaults."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    values = {**_from_file(), **_from_env()}
    _CACHE = Identity(**values)
    return _CACHE


def reset() -> None:
    """Drop the cache. For tests, and for a desk reconfigured while running."""
    global _CACHE
    _CACHE = None


def evidence_engine_line() -> str:
    """The advice room's opening line about whose evidence engine this is.

    Where nothing has been configured it says what it can stand behind —
    that it is an evidence engine — and claims no licence. Stating an FSP
    number the desk was never given would be inventing the one fact a reader
    is most entitled to rely on.
    """
    who = load().licence_line
    return (f"You are an evidence engine for {who}."
            if who else "You are an evidence engine for a financial adviser.")


def render(ident: Optional[Identity] = None) -> str:
    ident = ident or load()
    lines = ["Desk identity", "=" * 46]
    for name in sorted(_FIELDS):
        value = getattr(ident, name) or "(not set)"
        lines.append(f"  {name:<16} {value}")
    lines.append("-" * 46)
    lines.append(f"  licence line     {ident.licence_line or '(not set)'}")
    if not ident.configured:
        lines.append("")
        lines.append(f"  Nothing configured. Write {IDENTITY_FILE}, or set")
        lines.append(f"  {ENV_PREFIX}ADVISER_NAME and friends.")
    elif ident.missing():
        lines.append("")
        lines.append("  Missing for a regulated document: "
                     + ", ".join(ident.missing()))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render())
