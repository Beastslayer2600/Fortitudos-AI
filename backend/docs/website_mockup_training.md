# Client Website Mockup — Training Notes (Fortitudo AI)

Use these rules whenever you generate a client website mockup or practice storefront.

## Research summary (2025–2026 advisor / professional-services sites)

Conversion reality:
- Unoptimized advisor sites convert ~0.5–1.5%. Optimized trust-first pages reach ~3–8%.
- Trust is the #1 driver: credentials, specificity, privacy language, single clear CTA.
- Mobile-first; copy at roughly Grade 5–7 reading level for scanning.
- One primary CTA above the fold; repeat it once mid-page and once at the end.
- Contact details visible early (phone / email in header), not buried.

Winning one-page architecture (in order):
1. **Header** — name/practice, phone, email, primary CTA button
2. **Hero** — outcome-focused headline for a *specific* audience (not “We are financial advisors”)
3. **Trust strip** — 3–4 concrete signals (years, specialism, offline/privacy, language, regulator stance)
4. **Who this is for** — 2–3 client profiles in plain language
5. **Problems we solve** — named pains, not product lists
6. **How we work** — 3–4 step process (assessment → plan → implement → review)
7. **Proof / method** — evidence style: technical precision, cited product wording, privacy-first local AI if Fortitudo Wealth
8. **Offer / packages** — clear scope and next step (no fake testimonials)
9. **FAQ** — 4 short answers (fees, privacy, what happens after contact, fit)
10. **Final CTA** — book / call / WhatsApp
11. **Footer** — legal line, privacy, no link farms

Headline formula:
- Bad: “John Smith — Financial Advisor”
- Good: “Turn your 50s savings into a clear retirement income plan”
- Good: “Structure risk cover so waiting periods and definitions do not surprise your family”

Copy rules:
- Specific over vague (“14-day survival period” style precision when true; never invent figures)
- No fabricated client counts, AUM, awards, or testimonials
- Prefer “you” language; short paragraphs; scannable subheads
- Privacy near forms: “We use your details only to respond. No sharing. No newsletter unless you ask.”
- South Africa: FICA, FAIS/FSP language only if the brief supplies it; never invent licence numbers

Visual system (mockup HTML):
- Dark ink + cream + gold accent (Fortitudo family) OR client brand colours if supplied
- Generous whitespace, max content width ~720–1100px
- System fonts stack with one display serif for H1 if elegant positioning
- No stock-photo dependency; CSS gradients and geometry are fine for mockups
- Single column on mobile; sticky or simple top bar

Output format for Fortitudo AI:
- Return **one complete HTML document** (`<!DOCTYPE html>…</html>`)
- Inline CSS in `<style>` (no external dependencies except optional Google fonts)
- Placeholder contact fields clearly marked if unknown: `[PHONE]`, `[EMAIL]`
- Mark top of file with HTML comment: `<!-- INTERNAL MOCKUP — adviser review required; not live -->`
