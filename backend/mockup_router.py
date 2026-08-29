"""Pick trade page vs wealth storefront. Client files never become a site."""
from crossover import kind_of, refuse_reason
from trade_page import generate_trade_page
from website_mockup import generate_mockup


def generate_from_client_documents(client_name: str, source_text: str, extra_brief: str = "") -> str:
    blob = f"{client_name}\n{extra_brief}\n{source_text}"
    refuse = refuse_reason(blob)
    if refuse:
        return (
            "<!DOCTYPE html><html lang='en-ZA'><body><p>"
            + refuse
            + "</p></body></html>"
        )
    kind = kind_of(blob)
    if kind == "trade":
        return generate_trade_page(client_name, blob)
    brief = (
        f"Create a professional one-page website mockup for: {client_name}.\n"
        f"{extra_brief}\n"
        "This is the Fortitudo Wealth / practice storefront if the brief says so. "
        "Use Craft thinking: first screen, one primary CTA, omit missing facts. "
        "Do not invent FSP numbers, AUM or testimonials. "
        "Do not use a client's FNA as page copy."
    )
    return generate_mockup(brief, client_context=source_text if kind == "practice" else source_text)
