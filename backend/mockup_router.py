"""Pick trade page vs wealth storefront. Client files never become a site."""
from crossover import kind_of, refuse_reason
from design_reason import design_and_render
from website_mockup import generate_mockup


def generate_from_client_documents(client_name: str, source_text: str, extra_brief: str = "") -> str:
    blob = f"{client_name}\n{extra_brief}\n{source_text}"
    refuse = refuse_reason(blob)
    if refuse:
        # Raise rather than render: a refusal page filed in the client folder
        # would look like a mockup someone could hand over.
        raise ValueError(refuse)
    kind = kind_of(blob)
    if kind == "trade":
        # Through the design reasoner, not the bare renderer: it decides the
        # headline, intent and what to omit, and falls back to a deterministic
        # spec when no model is running.
        return design_and_render(client_name, blob)["page"]
    brief = (
        f"Create a professional one-page website mockup for: {client_name}.\n"
        f"{extra_brief}\n"
        "This is the Fortitudo Wealth / practice storefront if the brief says so. "
        "Use Craft thinking: first screen, one primary CTA, omit missing facts. "
        "Do not invent FSP numbers, AUM or testimonials. "
        "Do not use a client's FNA as page copy."
    )
    # Only the practice storefront may draw on the filed text.
    return generate_mockup(brief, client_context=source_text if kind == "practice" else "")
