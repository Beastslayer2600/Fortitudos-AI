import assert from "node:assert/strict";
import { test } from "node:test";
import {
  mayContactElectronically,
  mailtoLetter,
  whatsappLink,
  type CraftLead,
} from "./craft.ts";

const lead = (consent: CraftLead["consent"]): CraftLead =>
  ({
    id: "l1", name: "Joe Plumbing", city: "Kempton Park", type: "plumber",
    address: "", phone: "0119751234", website: "", email: "joe@example.com",
    note: "", touch: "untouched", photos: [], savedAt: "", source: "hand", consent,
  }) as CraftLead;

test("a refusal is permanent — no electronic route at all", () => {
  const decision = mayContactElectronically(lead("refused"));
  assert.equal(decision.allowed, false);
  assert.equal(mailtoLetter(lead("refused"), "https://x"), "");
  assert.equal(whatsappLink("0119751234", "Joe", "https://x", "refused"), "");
});

test("one unanswered ask is the only ask", () => {
  assert.equal(mayContactElectronically(lead("asked")).allowed, false);
  assert.equal(mailtoLetter(lead("asked"), "https://x"), "");
  assert.equal(whatsappLink("0119751234", "Joe", "https://x", "asked"), "");
});

test("an unknown contact gets the consent ask, never the pitch", () => {
  const decision = mayContactElectronically(lead("unknown"));
  assert.equal(decision.kind, "ask");
  const wa = decodeURIComponent(whatsappLink("0119751234", "Joe", "https://x", "unknown"));
  assert.match(wa, /Reply YES or NO/);
  assert.doesNotMatch(wa, /I made a mock page/);
});

test("consent and existing-customer both allow the pitch", () => {
  for (const state of ["consented", "customer"] as const) {
    assert.equal(mayContactElectronically(lead(state)).kind, "pitch");
    const wa = decodeURIComponent(whatsappLink("0119751234", "Joe", "https://x", state));
    assert.match(wa, /I made a mock page/);
  }
});
