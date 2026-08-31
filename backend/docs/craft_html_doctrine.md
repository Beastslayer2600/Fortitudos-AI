# Craft HTML doctrine

This is for when the model writes the page itself (`html_author`), not when it
writes a spec for the renderer (`design_reason`). Both exist. The renderer
cannot state a fact it was not given, because it never writes free text. When
you write the document you can write anything — so the page is gated before a
shop owner ever sees it, and a page that fails the gate is thrown away.

Everything below is what the gate actually checks. It is not style advice.

## The page is refused if

- **It is not a whole document.** `<!doctype html>` through `</html>`, with a
  `<body>`. A page cut off mid-tag is the most common failure by far. Finish
  the document; a shorter complete page beats an elaborate truncated one.
- **It carries code.** No `<script>`, no `<iframe>`, no `<form>`, no `onclick`
  or any `on*` attribute, no `javascript:` URL. A shop page needs none of it.
- **It states a number that was not in the brief.** A phone number, an opening
  time, a price, a percentage or a year. Not "similar to" the brief — in it.
  If the brief has no hours, write `[HOURS]`. If it has no phone, `[PHONE]`.
  A placeholder is correct. A plausible guess is a lie about a real business.
- **It makes an unearned claim.** "24/7", "always open", "award-winning",
  "best in", "#1", "guaranteed", "5-star", any testimonial. These are the
  reflex phrases for a trade page and they are all inventions unless the owner
  said them.
- **It does not admit what it is.** While it is a mockup it carries the
  `INTERNAL MOCKUP` comment, `noindex`, and a visible line saying it is not
  live. That is what makes it safe to send to a stranger for review.

## What to build

One file. All CSS in a single `<style>` in the head. No external stylesheet,
font, image or script — none of them will load.

The first screen, before any scroll, is: the trade, the suburb, and a
tap-to-call link. Everything else is below that.

Then: what they do, contact details, footer. A sticky Call/WhatsApp bar on
small screens, hidden in `@media print` so the flyer version is clean.

## Writing the copy

- Headline is job + suburb. "Burst pipe in Kempton Park — call Joe", not
  "Quality you can trust".
- Emergency trades (plumber, electrician, geyser, locksmith) open panic-calm:
  the problem named, the number huge. Appointment trades (salon, cafe, bakery)
  open with place and hours.
- South African English. Rand. Short sentences. Grade 6 reading level.
- Omit a section you have no facts for. An absent address section is honest; a
  vague one is filler.

## On design

Earlier doctrine said type and colour belong to the renderer and HTML was not
your job. That was true when the model only produced a spec. When you are
authoring the document, the CSS is yours: choose the type scale, the colour,
the spacing. The constraint is not "do not design" — it is "do not invent
facts". Design freely. State nothing you were not told.
