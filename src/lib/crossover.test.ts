import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { CLIENT_FILE, clientFileLanguage, mayBeCraftLead, PRACTICE } from "./crossover.ts";

const py = readFileSync("backend/crossover.py", "utf8");

test("every client-file phrase the backend refuses is refused here too", () => {
  for (const phrase of ["fna", "record of advice", "needs analysis", "client file",
                        "policy number", "id number"]) {
    assert.ok(py.includes(phrase), `crossover.py no longer lists ${phrase}`);
    assert.match(`a brief mentioning ${phrase} here`, CLIENT_FILE, phrase);
  }
});

test("the practice pattern still matches what the backend matches", () => {
  for (const phrase of ["fortitudo wealth", "practice storefront", "adviser website"]) {
    assert.ok(py.includes(phrase), `crossover.py no longer lists ${phrase}`);
    assert.match(`about ${phrase} today`, PRACTICE, phrase);
  }
});

test("a real lead brief is allowed through", () => {
  for (const brief of [
    "Geyser repairs and burst pipes in Kempton Park. Phone 011 975 1234.",
    "Bakery in Benoni, open mornings, sourdough and pies.",
    "Panel beater, Boksburg, insurance work welcome.",
    "Salon in Edenvale, Saturday appointments.",
  ]) {
    assert.ok(mayBeCraftLead(brief), brief);
  }
});

test("a brief carrying client-file language is refused, and says why", () => {
  for (const [brief, why] of [
    ["record of advice for the shop owner", "record of advice"],
    ["her FNA says she needs more cover", "fna"],
    ["the client file says he wants a website", "client file"],
    ["policy number 12345 — build him a page", "policy number"],
  ] as const) {
    assert.equal(clientFileLanguage(brief), why, brief);
    assert.ok(!mayBeCraftLead(brief), brief);
  }
});

test("a bare SA ID number is caught even without the words", () => {
  assert.equal(clientFileLanguage("owner 8001015009087 wants a page"), "an ID number");
  assert.equal(clientFileLanguage("800101 5009 087"), "an ID number");
});

test("a phone number is not mistaken for an ID number", () => {
  // 10 digits, not 13 — the guard must not refuse every brief with a number.
  assert.ok(mayBeCraftLead("Call 011 975 1234 for geyser repairs"));
  assert.ok(mayBeCraftLead("+27 82 555 9000 panel beater Boksburg"));
});

test("intake_lead applies the guard", () => {
  const src = readFileSync("src/lib/desk-agent.ts", "utf8");
  const i = src.indexOf('action.type === "intake_lead"');
  assert.notEqual(i, -1);
  const block = src.slice(i, src.indexOf("saveLedger", i));
  assert.match(block, /clientFileLanguage/, "intake_lead writes to the ledger unguarded");
});
