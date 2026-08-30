"""Which mockup a brief may become, and from which side of the desk.

Two businesses share this desk and must not share records:

- **FA clients** are advice clients in the vault, under FAIS. A mockup made
  from a client record can only ever be the practice's own storefront.
- **Craft leads** are shop owners the studio sells pages to. They live in the
  browser ledger and are never filed as clients.

A trade shop is a Craft lead, not an advice client, so a client record may not
produce a trade page — that would mean a plumber had been filed in the vault
to use this feature.
"""
from crossover import CLIENT_FILE, kind_of, refuse_reason
from design_reason import design_and_render
from website_mockup import generate_mockup

TRADE_FROM_CLIENT = (
    "This reads like a shop, not an advice client. A trade page is Craft work: "
    "keep the shop in the Craft ledger. The client vault is for advice clients."
)
CLIENT_FILE_FROM_LEAD = (
    "This reads like a client file. A Craft lead is a shop owner, not an "
    "advice client — do not paste client documents into a lead brief."
)


def generate_for_client(client_name: str, source_text: str, extra_brief: str = "") -> str:
    """Practice storefront from a brief. The filed documents are read to decide
    whether this is allowed at all — they are never page copy.

    `source_text` is classified and then dropped. Nothing from a client's file
    reaches the generator, so an FNA cannot surface as a paragraph on a website
    even when the classifier calls the brief a practice storefront.
    """
    blob = f"{client_name}\n{extra_brief}\n{source_text}"
    refuse = refuse_reason(blob)
    if refuse:
        # Raise rather than render: a refusal page filed in the client folder
        # would look like a mockup someone could hand over.
        raise ValueError(refuse)
    if kind_of(blob) == "trade":
        raise ValueError(TRADE_FROM_CLIENT)
    brief = (
        f"Create a professional one-page website mockup for: {client_name}.\n"
        f"{extra_brief}\n"
        "This is the Fortitudo Wealth / practice storefront. "
        "Use Craft thinking: first screen, one primary CTA, omit missing facts. "
        "Do not invent FSP numbers, AUM or testimonials. "
        "Write from this brief only — no client document text is supplied."
    )
    return generate_mockup(brief)


def generate_for_lead(lead_name: str, brief: str, city: str = "Kempton Park",
                      mock_url: str = "", *, author_html: bool = True) -> dict:
    """A Craft lead's page, flyer and spec. Takes a brief, never a client record.

    `author_html=False` forces the deterministic template — useful when a
    caller wants a page it can predict rather than one the model wrote.
    """
    blob = f"{lead_name}\n{brief}"
    # Stricter than refuse_reason: a lead brief has no business containing
    # client-file language even when it also mentions the practice.
    if CLIENT_FILE.search(blob):
        raise ValueError(CLIENT_FILE_FROM_LEAD)
    # Through the design reasoner, not the bare renderer: it decides the
    # headline, intent and what to omit, and falls back to a deterministic
    # spec when no model is running.
    return design_and_render(lead_name, blob, city=city, mock_url=mock_url,
                             author_html=author_html)

