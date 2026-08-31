import assert from "node:assert/strict";
import { test } from "node:test";
import { buildOpsBrief, briefToChatLines } from "./ops-brief.ts";
import type { Client, DramaSession, DropItem } from "./types.ts";

const client = (id: string, name: string, status: string) =>
  ({ id, name, status }) as Client;

const base = {
  clients: [] as Client[],
  sessions: [] as DramaSession[],
  dropItems: [] as DropItem[],
};

test("an empty desk says so rather than inventing work", () => {
  const brief = buildOpsBrief(base);
  assert.equal(brief.items.length, 0);
  assert.match(brief.summary, /Desk is clear/);
});

test("clients mid-intake surface, settled ones do not", () => {
  const brief = buildOpsBrief({
    ...base,
    clients: [
      client("c1", "Botha", "FNA"),
      client("c2", "Naidoo", "Intake"),
      client("c3", "Older", "Complete"),
    ],
  });
  const names = brief.items.map((i) => i.title);
  assert.ok(names.includes("Botha"));
  assert.ok(names.includes("Naidoo"));
  assert.ok(!names.includes("Older"));
});

test("an FNA client is today's work, an intake is soon", () => {
  const brief = buildOpsBrief({ ...base, clients: [client("c1", "Botha", "FNA")] });
  assert.equal(brief.items[0].urgency, "today");
});

test("every item is namespaced by which ledger it came from", () => {
  // A brief may show both businesses. No item may belong to both.
  const brief = buildOpsBrief({
    ...base,
    clients: [client("c1", "Botha", "FNA")],
    extras: [{ id: "lead-x", kind: "lead", title: "Joe Plumbing", urgency: "soon" }],
  });
  for (const item of brief.items) {
    assert.match(item.id, /^(client|lead|mockup|drama|drop|meeting|invoice|followup)-/, item.id);
  }
  const ids = brief.items.map((i) => i.id);
  assert.equal(new Set(ids).size, ids.length, "duplicate ids in the brief");
});

test("a client item never carries a lead id and vice versa", () => {
  const brief = buildOpsBrief({ ...base, clients: [client("c1", "Botha", "FNA")] });
  const item = brief.items.find((i) => i.kind === "client");
  assert.ok(item);
  assert.equal(item!.id, "client-c1");
  assert.match(item!.href ?? "", /^\/clients\//);
});

test("the chat rendering lists every item it was given", () => {
  const brief = buildOpsBrief({
    ...base,
    clients: [client("c1", "Botha", "FNA"), client("c2", "Naidoo", "Intake")],
  });
  const text = briefToChatLines(brief);
  assert.ok(text.includes("Botha"));
  assert.ok(text.includes("Naidoo"));
  assert.equal(text.split("\n").filter((l) => l.startsWith("•")).length, brief.items.length);
});

test("the summary counts what is actually due today", () => {
  const brief = buildOpsBrief({
    ...base,
    clients: [client("c1", "A", "FNA"), client("c2", "B", "Intake")],
  });
  assert.match(brief.summary, /2 open items/);
  assert.match(brief.summary, /1 for today/);
});
