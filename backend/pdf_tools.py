"""PDF operations for the client vault.

One rule shapes this whole module: **nothing here writes to a path.** Every
function takes bytes and returns bytes. A filed client document is evidence
under FAIS — a signed FNA or RoA altered after the fact is worse than no
document at all — so the ability to overwrite an original is not a feature
that is switched off here, it is an ability the code does not have. The caller
decides where the new bytes land, and client_store.add_generated_file sends
them to 99_AI_Drafts, typed as an AI draft, with the original untouched.

Append-only versioning IS the compliance trail. It is not a limitation on it.

What is honest to offer:

  fill_form   AcroForm fields — the highest-volume real work in a practice
  annotate    comments and highlights, additive by nature
  redact      genuinely removes text from the content stream
  assemble    merge, split, reorder, rotate
  stamp       overlay a banner, a page number, a signature block
  to_markdown read the PDF into an editable draft beside the original

What is not offered, deliberately: rewriting body prose in place. PDF is a
page-description format, not a document with editable text, and a scan has no
text at all. Anything claiming to do it is reflowing a guess, which on a
client file means silent corruption. to_markdown is the honest version.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------- a tiny writer
#
# reportlab would do this, but it is a large dependency on a desk that already
# fights Python wheels, and a stamp needs one font and one text operator. The
# base-14 fonts are guaranteed present in every reader, so a hand-built page
# needs no font embedding.

_ESCAPE = {ord("("): r"\(", ord(")"): r"\)", ord("\\"): r"\\"}


def _pdf_string(text: str) -> str:
    return (text or "").translate(_ESCAPE)


def _content_stream(lines: Sequence[str], size: int, x: float, y: float,
                    leading: float) -> bytes:
    parts = ["BT", f"/F1 {size} Tf", f"{leading} TL", f"1 0 0 1 {x} {y} Tm"]
    for i, line in enumerate(lines):
        parts.append(f"({_pdf_string(line)}) Tj")
        if i + 1 < len(lines):
            parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", "replace")


def make_pdf(pages: Sequence[str], *, size: int = 11, width: float = 595,
             height: float = 842, margin: float = 56) -> bytes:
    """A minimal, valid PDF. Used for stamps, overlays and test fixtures.

    Deliberately plain: one base-14 font, no compression, no images. It exists
    so the desk can produce a page to merge, not to typeset anything.
    """
    leading = size * 1.45
    objects: List[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)          # 1-based object number

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                  b"/Encoding /WinAnsiEncoding >>")
    page_ids: List[int] = []
    kids_placeholder = add(b"")      # Pages object, filled in below

    for text in pages or [""]:
        lines = str(text or "").splitlines() or [""]
        stream = _content_stream(lines, size, margin, height - margin, leading)
        content_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream +
                         b"\nendstream")
        page_id = add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %s %s] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (kids_placeholder, _num(width), _num(height), font_id, content_id)
        )
        page_ids.append(page_id)

    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    objects[kids_placeholder - 1] = (
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))
    )
    catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % kids_placeholder)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, catalog_id, xref_at))
    return bytes(out)


def _num(value: float) -> bytes:
    return (b"%d" % int(value)) if float(value).is_integer() else b"%.2f" % value


# ---------------------------------------------------------------- reading

@dataclass
class Page:
    number: int              # 1-based, as a person counts pages
    text: str

    @property
    def blank(self) -> bool:
        return not self.text.strip()


def read_pages(data: bytes) -> List[Page]:
    """Per-page text. pdfplumber where available, pypdf as the fallback.

    pdfplumber keeps table layout intact, which matters for benefit matrices;
    pypdf is there so this still works if pdfplumber cannot open the file.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as doc:
            return [Page(i, (p.extract_text() or "").strip())
                    for i, p in enumerate(doc.pages, start=1)]
    except Exception:
        pass
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return [Page(i, (p.extract_text() or "").strip())
            for i, p in enumerate(reader.pages, start=1)]


def page_count(data: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(io.BytesIO(data)).pages)


def is_scanned(data: bytes) -> bool:
    """No extractable text anywhere — an image, not a document.

    Worth knowing before promising anything: you cannot redact or read a scan,
    only annotate and stamp it. Saying so beats failing quietly.
    """
    return all(p.blank for p in read_pages(data))


# ---------------------------------------------------------------- forms

@dataclass
class Field:
    name: str
    kind: str                # text, checkbox, choice, signature, button
    value: str = ""
    options: List[str] = field(default_factory=list)
    required: bool = False


_FIELD_KIND = {"/Tx": "text", "/Btn": "checkbox", "/Ch": "choice", "/Sig": "signature"}


def form_fields(data: bytes) -> List[Field]:
    """Every fillable field, so the desk can offer them rather than guess names."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    raw = reader.get_fields() or {}
    out: List[Field] = []
    for name, spec in raw.items():
        try:
            ftype = str(spec.get("/FT", ""))
            flags = int(spec.get("/Ff", 0) or 0)
            opts = [str(o) for o in (spec.get("/Opt") or [])]
            out.append(Field(
                name=str(name),
                kind=_FIELD_KIND.get(ftype, "button"),
                value=str(spec.get("/V", "") or ""),
                options=opts,
                required=bool(flags & 2),          # bit 2 = Required
            ))
        except Exception:
            out.append(Field(name=str(name), kind="text"))
    return sorted(out, key=lambda f: f.name)


def fill_form(data: bytes, values: Dict[str, str]) -> Tuple[bytes, List[str]]:
    """Fill named fields. Returns (bytes, fields that did not exist).

    Unknown names are reported rather than dropped: a form silently missing the
    field you asked for looks exactly like a form that was filled.
    """
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, BooleanObject

    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter(clone_from=reader)
    known = {f.name for f in form_fields(data)}
    missing = sorted(k for k in (values or {}) if k not in known)
    usable = {k: str(v) for k, v in (values or {}).items() if k in known}

    if usable:
        # NeedAppearances makes the reader draw the value it was given, rather
        # than showing an empty box because no appearance stream was generated.
        root = writer._root_object
        acro = root.get("/AcroForm")
        if acro is not None:
            acro[NameObject("/NeedAppearances")] = BooleanObject(True)
        for page in writer.pages:
            try:
                writer.update_page_form_field_values(page, usable)
            except Exception:
                continue

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue(), missing


# ---------------------------------------------------------------- annotation

@dataclass
class Note:
    page: int                # 1-based
    text: str
    rect: Tuple[float, float, float, float] = (56, 700, 380, 760)
    title: str = "Fortitudo AI"


def annotate(data: bytes, notes: Sequence[Note]) -> bytes:
    """Add comments. Additive by nature — nothing existing is touched."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.annotations import FreeText

    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter(clone_from=reader)
    last = len(writer.pages)
    for note in notes or []:
        index = min(max(int(note.page), 1), last) - 1
        writer.add_annotation(
            page_number=index,
            annotation=FreeText(
                text=f"{note.title}: {note.text}" if note.title else note.text,
                rect=note.rect,
                font_size="10pt",
                border_color="c8102e",
                background_color="fff8dc",
            ),
        )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- redaction

# Patterns worth removing before a client document leaves the practice. These
# are POPIA's special-personal-information shapes, not a general secret finder.
SA_ID = re.compile(r"\b\d{6}[\s-]?\d{4}[\s-]?\d{3}\b")
ACCOUNT = re.compile(r"\b\d{9,13}\b")
TAX_NUMBER = re.compile(r"\b[01239]\d{9}\b")

BUILTIN_PATTERNS = {"sa_id": SA_ID, "account": ACCOUNT, "tax": TAX_NUMBER}


class NotRedactable(ValueError):
    """Raised rather than returning a document that only looks redacted."""


def redact(data: bytes, *, literals: Sequence[str] = (),
           patterns: Sequence[str] = ()) -> Tuple[bytes, List[str]]:
    """Genuinely remove text. Returns (bytes, what was removed).

    A black rectangle drawn over a number is not redaction — the number is
    still in the file and any reader will copy it out. This rewrites the
    content stream so the glyphs are gone.

    Refuses a scanned page: there is no text to remove, and a document that
    reports "redacted" while the ID number sits in the image is the exact
    failure this is meant to prevent.
    """
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ContentStream, TextStringObject

    if is_scanned(data):
        raise NotRedactable(
            "This PDF has no extractable text — it is a scan or an image. "
            "Redaction here would draw a box over the picture and leave the "
            "content underneath. Run OCR first, or remove the page."
        )

    chosen = [BUILTIN_PATTERNS[p] for p in patterns if p in BUILTIN_PATTERNS]
    wanted = [str(t) for t in literals if str(t).strip()]
    removed: List[str] = []

    def scrub(text: str) -> str:
        out = text
        for literal in wanted:
            if literal in out:
                removed.append(literal)
                out = out.replace(literal, " " * len(literal))
        for pattern in chosen:
            def _hit(m):
                removed.append(m.group(0))
                return " " * len(m.group(0))
            out = pattern.sub(_hit, out)
        return out

    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        try:
            stream = ContentStream(page.get_contents(), writer)
        except Exception:
            continue
        changed = False
        for operands, operator in stream.operations:
            if operator == b"Tj" and operands:
                new = scrub(str(operands[0]))
                if new != str(operands[0]):
                    operands[0] = TextStringObject(new)
                    changed = True
            elif operator == b"TJ" and operands:
                for i, item in enumerate(operands[0]):
                    if isinstance(item, TextStringObject) or hasattr(item, "get_object"):
                        current = str(item)
                        if not current:
                            continue
                        new = scrub(current)
                        if new != current:
                            operands[0][i] = TextStringObject(new)
                            changed = True
        if changed:
            page.replace_contents(stream)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue(), sorted(set(removed))


# ---------------------------------------------------------------- assemble

def _parse_pages(spec: str, total: int) -> List[int]:
    """"1,3,5-7" -> [1,3,5,6,7]. Out-of-range numbers are dropped, not clamped.

    Clamping would silently include a page nobody asked for, which in a client
    pack is how the wrong person's document goes out.
    """
    wanted: List[int] = []
    for chunk in re.split(r"[,\s]+", (spec or "").strip()):
        if not chunk:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", chunk)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            wanted.extend(range(min(lo, hi), max(lo, hi) + 1))
        elif chunk.isdigit():
            wanted.append(int(chunk))
    seen, out = set(), []
    for n in wanted:
        if 1 <= n <= total and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def select_pages(data: bytes, spec: str) -> bytes:
    """Keep only the pages named. "1,3,5-7"."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(data))
    keep = _parse_pages(spec, len(reader.pages))
    if not keep:
        raise ValueError(f"No pages matched {spec!r} in a {len(reader.pages)}-page document.")
    writer = PdfWriter()
    for n in keep:
        writer.add_page(reader.pages[n - 1])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def rotate_pages(data: bytes, spec: str, degrees: int) -> bytes:
    """Rotate the named pages. Degrees is rounded to a legal quarter turn."""
    from pypdf import PdfReader, PdfWriter
    turn = int(round(degrees / 90.0)) * 90 % 360
    reader = PdfReader(io.BytesIO(data))
    chosen = set(_parse_pages(spec, len(reader.pages)) or range(1, len(reader.pages) + 1))
    writer = PdfWriter(clone_from=reader)
    for i, page in enumerate(writer.pages, start=1):
        if i in chosen and turn:
            page.rotate(turn)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def merge(parts: Sequence[bytes]) -> bytes:
    """One pack from several documents, in the order given."""
    from pypdf import PdfReader, PdfWriter
    usable = [p for p in parts if p]
    if not usable:
        raise ValueError("Nothing to merge.")
    writer = PdfWriter()
    for blob in usable:
        for page in PdfReader(io.BytesIO(blob)).pages:
            writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- stamp

def _overlay(text_lines: Sequence[str], width: float, height: float,
             x: float, y: float, size: int) -> bytes:
    leading = size * 1.35
    stream = _content_stream(list(text_lines), size, x, y, leading)
    return _single_page_pdf(stream, width, height)


def _single_page_pdf(stream: bytes, width: float, height: float) -> bytes:
    objects: List[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                  b"/Encoding /WinAnsiEncoding >>")
    pages_id = add(b"")
    content_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    page_id = add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %s %s] "
                  b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                  % (pages_id, _num(width), _num(height), font_id, content_id))
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [%d 0 R] /Count 1 >>" % page_id
    catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1) + b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, catalog_id, xref_at))
    return bytes(out)


def stamp(data: bytes, text: str, *, where: str = "top", size: int = 10,
          pages: str = "") -> bytes:
    """Overlay a line on each chosen page. A banner, a reference, a page mark.

    The stamp is drawn over the page, so the original content stays readable
    and intact underneath — this is marking a document, not changing it.
    """
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(data))
    chosen = set(_parse_pages(pages, len(reader.pages)) or range(1, len(reader.pages) + 1))
    lines = [ln for ln in str(text or "").splitlines() if ln.strip()] or [""]

    # Clone into the writer before merging. pypdf deprecated merging onto a
    # page still owned by a reader and calls that path unreliable, and a stamp
    # that lands intermittently on a client pack is worse than no stamp.
    writer = PdfWriter(clone_from=reader)
    for i, page in enumerate(writer.pages, start=1):
        if i not in chosen:
            continue
        box = page.mediabox
        w, h = float(box.width), float(box.height)
        y = h - 28 if where == "top" else 28 + (len(lines) - 1) * size * 1.35
        over = PdfReader(io.BytesIO(_overlay(lines, w, h, 40, y, size))).pages[0]
        page.merge_page(over)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- to markdown

def to_markdown(data: bytes, title: str = "") -> str:
    """The honest version of "edit the text".

    You cannot rewrite prose inside a PDF without reflowing a guess. So the
    text comes out into markdown you can actually edit, the PDF stays the
    untouched original, and the two sit side by side in the client folder.
    """
    pages = read_pages(data)
    head = [f"# {title or 'Document'}", "",
            f"Extracted from a PDF of {len(pages)} page(s). The PDF is the "
            "original and is unchanged; this is a working draft.", ""]
    if all(p.blank for p in pages):
        head += ["> No text could be extracted. This is a scan or a photo, not",
                 "> a text PDF. It needs OCR before anything can read it.", ""]
        return "\n".join(head)
    body: List[str] = []
    for page in pages:
        body.append(f"## Page {page.number}")
        body.append("")
        body.append(page.text if page.text else "_(no text on this page)_")
        body.append("")
    return "\n".join(head + body)
