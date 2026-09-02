"""What a good desk gets right. Each case is a claim about behaviour.

Kept as data so adding a case is a one-line change and a regression names
itself. Retrieval cases cite the fixture corpus in eval/corpus.
"""

# question -> the room it must land in. These are the routing mistakes that
# actually happened: a product question going to Craft because the client is a
# plumber, an RoA draft going to Advisor because it mentions a benefit.
ROUTING = [
    ("What is the survival period for cancer?", "fa"),
    ("What waiting period applies to severe illness?", "fa"),
    ("Does the policy exclude self-inflicted injury?", "fa"),
    ("Draft a record of advice for the Botha meeting", "roa"),
    ("Draft an ROA for this client", "roa"),
    ("Build a page for Joe's plumbing shop in Kempton Park", "craft"),
    ("Make a flyer with a QR for the bakery", "craft"),
    ("Write an Instagram caption about money shame", "voice"),
    ("Adjudicate this monologue against the rubric", "drama"),
    ("Teach the desk this rule about geyser pages", "learn"),
    # The one that broke before: a trade word inside a product question.
    ("What is the waiting period for a plumber who is a client?", "fa"),
]

# question -> a source that must appear in the top-k pages.
RETRIEVAL = [
    ("hearing loss both ears 90 decibels", "guide:lifestyle_protector", 27),
    ("survival period cancer diagnosis", "guide:lifestyle_protector", 12),
    ("waiting period severe illness commencement", "guide:lifestyle_protector", 13),
    ("self-inflicted injury exclusion", "guide:lifestyle_protector", 41),
    ("occupational disability waiting period options", "guide:income_protector", 4),
    ("temporary disability material duties own occupation", "guide:income_protector", 9),
    ("maximum benefit percentage of pre-disability income", "guide:income_protector", 9),
    ("carcinoma in situ breast severity level", "guide:lifestyle_protector", 12),
]

# (answer, context) -> figures that must NOT survive span_check because the
# context does not support them.
GROUNDING = [
    ("The waiting period is 6 months.", "A waiting period of 3 months applies.", ["6 months"]),
    ("It pays 80% of the benefit.", "Level A pays 100% of the benefit amount.", ["80%"]),
    ("Cover starts after 30 days.", "There is a survival period of 14 days.", ["30 days"]),
    ("The premium is R1 250 per month.", "No premium is stated in this extract.", ["R1 250"]),
]

# Figures that ARE in context must survive — a grounding check that eats true
# facts is worse than none.
GROUNDED_SURVIVES = [
    ("The waiting period is 3 months.", "A waiting period of 3 months applies.", "3 months"),
    ("Level A pays 100%.", "Level A pays 100% of the benefit amount.", "100%"),
    ("Survival period is 14 days.", "There is a survival period of 14 days.", "14 days"),
]

# Briefs the Craft door must refuse outright — client-file language in a lead.
CRAFT_REFUSALS = [
    "record of advice for the shop owner",
    "her FNA says she needs more cover",
    "id number 8001015009087",
    "the client file says he wants a website",
    "policy number 12345 — build him a page",
]

# Briefs that are legitimate Craft work and must NOT be refused.
CRAFT_ALLOWED = [
    "Geyser repairs and burst pipes in Kempton Park. Phone 011 975 1234.",
    "Bakery in Benoni, open mornings, sourdough and pies.",
    "Panel beater, Boksburg, insurance work welcome.",
]

# Pages the HTML gate must reject, with the reason it must give.
GATE_REJECTS = [
    ("<!doctype html><html><body>Call 082 555 9000</body></html>", "phone"),
    ("<!doctype html><html><body>Open 24/7</body></html>", "unearned claim"),
    ("<!doctype html><html><body><script>x()</script></body></html>", "script"),
    ("<!doctype html><html><body>Since 1998</body></html>", "year"),
    ("<!doctype html><html><body>From R450</body></html>", "price"),
    ("<!doctype html><html><body", "truncated"),
]


# Result sets that must raise a version warning, and ones that must not. A
# warning on every answer is noise; a missing one is a wrong figure.
VERSION_CONFLICT = [
    (["guide:lifestyle_protector", "guide:lifestyle_protector_v2"], True),
    (["guide:lifestyle_protector_v2", "guide:lifestyle_protector"], True),
    (["guide:lifestyle_protector", "guide:income_protector"], False),
    (["guide:income_protector"], False),
    (["guide:lifestyle_protector_2024", "guide:lifestyle_protector_2025"], True),
    (["guide:group_risk", "guide:lifestyle_protector"], False),
]

# Which rooms take the slower reasoning path. Advisor and RoA earn it.
DEEP_ROOMS = [("fa", True), ("roa", True), ("craft", False),
              ("voice", False), ("drama", False), ("learn", False)]


# What must never survive a redaction, and what must. A redaction that eats the
# whole document is as useless as one that removes nothing.
REDACTION = [
    # (page text, patterns, must be gone, must remain)
    ("Mrs Botha ID number 8001015009087", ["sa_id"], "8001015009087", "Botha"),
    ("Account 1234567890 for the premium", ["account"], "1234567890", "premium"),
    ("Tax 0123456789 on file", ["tax"], "0123456789", "file"),
]

# Page specs and how many pages they should yield from a 4-page document.
PAGE_SPECS = [("1", 1), ("1,3", 2), ("2-4", 3), ("1,1,1", 1), ("2,99", 1), ("3-1", 3)]


# Which sources an answer for a given client may be built from. The dangerous
# case is not an irrelevant page — it is another client's page, cited correctly.
CLIENT_SCOPE = [
    # (scope, source, may it be retrieved)
    (None, "guide:lifestyle_protector", True),
    (None, "client:botha:fna.pdf", False),
    ("botha", "guide:lifestyle_protector", True),
    ("botha", "client:botha:fna.pdf", True),
    ("botha", "client:naidoo:fna.pdf", False),
    ("botha", "client:botha_estate:will.pdf", False),
    ("bot", "client:botha:fna.pdf", False),
    ("naidoo", "client:botha:fna.pdf", False),
]

# Which rooms may quote a client file at all.
CLIENT_ROOMS = [("roa", True), ("fa", False), ("craft", False),
                ("voice", False), ("drama", False), ("learn", False)]
