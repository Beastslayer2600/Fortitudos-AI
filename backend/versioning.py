"""Version + as-of helpers and post-generation span checks."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATE_RE = re.compile(
    r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b"
)
AS_OF_HINT = re.compile(
    r"\b(as at|as of|as-of|on\s+the\s+\d|on\s+20\d{2}|when we (wrote|issued|signed)|advice date|roa date)\b",
    re.I,
)
CHANGE_HINT = re.compile(
    r"\b(what changed|vs previous|versus previous|replacement wording|difference between versions)\b",
    re.I,
)
# What counts as a figure the answer must have got from a page.
#
# Percentages and durations were checked from the start. Money was not — so an
# invented premium, sum assured or fee walked straight into an RoA draft, which
# is the single worst number to be wrong about in a document a client signs.
# Amounts and bare thousands are now checked too.
FIGURE_RE = re.compile(
    r"("
    r"\d+(?:\.\d+)?\s*%"                                   # 75%, 12.5 %
    r"|\bR\s?\d[\d\s,.]*\d(?:\s*(?:m|k|million|billion))?"  # R1 250, R1.2 million
    r"|\bR\s?\d\b"                                          # R5
    r"|\b\d+\s*(?:days?|weeks?|months?|years?)\b"            # 3 months
    r"|\b\d{1,3}(?:[\s,]\d{3})+(?:\.\d+)?\b"               # 1 500 000, 1,250.00
    r")",
    re.I,
)

# "R1,250" in a document and "R1 250" in the answer are the same number. The
# comparison strips both separators so a real figure is not flagged as invented
# over a comma — a grounding check that eats true facts is worse than none.
_SEPARATORS = re.compile(r"[\s,]")


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def today_iso() -> str:
    return date.today().isoformat()


def parse_as_of(question: str, explicit: Optional[str] = None) -> str:
    if explicit:
        m = DATE_RE.search(explicit.replace("/", "-"))
        if m:
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            return f"{y}-{mo:02d}-{d:02d}"
    blob = question or ""
    if AS_OF_HINT.search(blob) or DATE_RE.search(blob):
        m = DATE_RE.search(blob.replace("/", "-"))
        if m:
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            return f"{y}-{mo:02d}-{d:02d}"
    return today_iso()


def query_intent(question: str) -> str:
    q = question or ""
    if CHANGE_HINT.search(q):
        return "change"
    if AS_OF_HINT.search(q) or (
        DATE_RE.search(q) and re.search(r"\b(as at|as of|on|in force|applied)\b", q, re.I)
    ):
        return "content_as_of"
    if re.search(r"\b(which (guides|versions|documents)|list (sources|guides))\b", q, re.I):
        return "list_versions"
    return "content_now"


def in_force(effective_from: str, effective_to: str, as_of: str) -> bool:
    ef = (effective_from or "").strip()
    et = (effective_to or "").strip()
    if ef and as_of < ef:
        return False
    if et and as_of >= et:
        return False
    return True


def guess_meta_from_name(source: str) -> Dict[str, str]:
    stem = Path(source).stem
    product = re.sub(r"[-_]v?\d+.*$", "", stem, flags=re.I)
    product = re.sub(r"[-_]20\d{2}.*$", "", product)
    product_code = (product or stem)[:80]
    version_id = stem[:80]
    effective_from = ""
    m = re.search(r"(20\d{2})[-_](0?[1-9]|1[0-2])(?:[-_](0?[1-9]|[12]\d|3[01]))?", stem)
    if m:
        y, mo = m.group(1), int(m.group(2))
        d = int(m.group(3) or 1)
        effective_from = f"{y}-{mo:02d}-{d:02d}"
    return {
        "product_code": product_code,
        "version_id": version_id,
        "effective_from": effective_from,
        "kind": "versioned",
        "domain": "fa",
    }


def load_sidecar(path: Path) -> Dict[str, str]:
    side = path.with_suffix(".yaml")
    if not side.exists():
        side = path.with_suffix(".yml")
    if not side.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(side.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {}
        out = {}
        for key in (
            "product_code",
            "version_id",
            "effective_from",
            "effective_to",
            "domain",
            "kind",
        ):
            if data.get(key):
                out[key] = str(data[key])
        return out
    except Exception:
        return {}


def span_check(answer: str, context: str) -> Tuple[str, List[str]]:
    if not answer:
        return answer, []
    blob = (context or "").lower()
    blob_compact = _SEPARATORS.sub("", blob)
    flagged: List[str] = []
    out = answer
    for m in FIGURE_RE.finditer(answer):
        token = m.group(0)
        compact = _SEPARATORS.sub("", token.lower())
        if compact in blob_compact or token.lower() in blob:
            continue
        if re.search(r"\[missing|not in the extract|not in the provided", answer, re.I):
            continue
        flagged.append(token)
        out = out.replace(token, "[MISSING — open cited page]", 1)
    if flagged:
        note = (
            "\n\n[SPAN-CHECK] Replaced figure(s) not found in retrieved pages: "
            + ", ".join(flagged)
            + ". Open the cited page before using the number."
        )
        if "[SPAN-CHECK]" not in out:
            out = out.rstrip() + note
    return out, flagged


def product_of(source: str) -> str:
    """The product a source belongs to, with version and date markers stripped.

    `lifestyle_protector_v2` and `lifestyle_protector` are the same product.
    Grouping by this is what lets the desk notice it is holding two versions.
    """
    stem = Path(source or "").stem
    stem = re.sub(r"^(guide|client|learn):", "", stem)
    stem = re.sub(r"[-_\s]v\d+.*$", "", stem, flags=re.I)
    stem = re.sub(r"[-_\s]20\d{2}.*$", "", stem)
    return stem.strip("-_ ").lower()


def version_conflict(results) -> List[str]:
    """Sources in this result set that are rival versions of one product.

    The dangerous retrieval failure is not an irrelevant page — the adviser
    spots that. It is two versions of the same guide where only a figure
    differs, because the answer then looks perfectly normal and cites a real
    page. Returns the conflicting source names, newest-looking last.
    """
    groups: Dict[str, set] = {}
    for row, _score in results or []:
        source = row[1] if len(row) > 1 else ""
        if not source:
            continue
        groups.setdefault(product_of(source), set()).add(source)
    clashes = []
    for _product, sources in sorted(groups.items()):
        if len(sources) > 1:
            clashes.extend(sorted(sources))
    return clashes


def version_note(results) -> str:
    """A line for the adviser when the extracts disagree about their own age.

    Silence here would be the desk choosing a version on the adviser's behalf
    using nothing but word overlap.
    """
    clashes = version_conflict(results)
    if not clashes:
        return ""
    return (
        "\n\n[VERSIONS] These extracts come from more than one version of the "
        "same document: " + ", ".join(clashes) + ". Figures may differ between "
        "them. Open the cited page and confirm which version applies before "
        "using a number."
    )


def snapshot_id(results: List[Tuple[Any, float]]) -> str:
    parts = []
    for row, _score in results:
        source = row[1] if len(row) > 1 else ""
        page = row[2] if len(row) > 2 else ""
        text = row[3] if len(row) > 3 else ""
        parts.append(f"{source}|{page}|{sha256_text(text)[:16]}")
    raw = "\n".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
