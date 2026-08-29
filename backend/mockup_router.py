"""Pick trade page vs wealth mockup. Trades never get Playfair + gold defaults."""
from trade_page import generate_trade_page, is_trade_brief
from website_mockup import generate_mockup


def generate_from_client_documents(client_name: str, source_text: str, extra_brief: str = "") -> str:
    blob = f"{client_name}\n{extra_brief}\n{source_text}"
    if is_trade_brief(blob):
        return generate_trade_page(client_name, blob)
    brief = (
        f"Create a professional one-page website mockup for: {client_name}.\n"
        f"{extra_brief}\n"
        "This is a professional-services / advice practice page only if the "
        "documents say so. Do not invent FSP numbers, AUM or testimonials."
    )
    return generate_mockup(brief, client_context=source_text)
