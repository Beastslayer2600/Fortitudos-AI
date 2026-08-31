import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { test } from "node:test";

const read = (p: string) => readFileSync(p, "utf8");
const sourceFiles = () =>
  execFileSync("git", ["ls-files", "src/**/*.ts", "src/**/*.tsx"], { encoding: "utf8" })
    .split("\n")
    .filter(Boolean)
    .filter((f) => !f.endsWith(".test.ts"));

/**
 * Craft leads are shop owners the studio sells pages to. FA clients are advice
 * clients under FAIS. They share a desk and must not share a record.
 */
test("the two ledgers use different storage keys", () => {
  const craftKey = read("src/lib/craft-ledger.ts").match(/const KEY = "([^"]+)"/)?.[1];
  const faKey = read("src/lib/store.ts").match(/name:\s*"([^"]+)"/)?.[1];
  assert.ok(craftKey, "craft ledger key not found");
  assert.ok(faKey, "FA store key not found");
  assert.notEqual(craftKey, faKey);
});

/**
 * This used to assert that no module *imported* both sides. The chat-first work
 * satisfied that by taking the FA clients as a function parameter instead —
 * ops-brief.ts reads the Craft ledger directly and receives clients as an
 * argument, so the letter passed while the spirit did not.
 *
 * The invariant that actually matters is not "no module sees both". A daily
 * brief legitimately shows a lead to chase beside a client whose FNA is due.
 * It is that the two never become one record: no item carries both identities,
 * nothing crosses from one ledger into the other, and a lead never reaches the
 * client vault. That is what these check.
 */
/**
 * desk-agent.ts dispatches every action, so it necessarily touches both
 * ledgers — that is what a dispatcher is. The invariant is per *action*: no
 * single handler may write to both, because that handler would be the seam
 * where a lead becomes a client or the reverse.
 */
function actionBlocks(): Record<string, string> {
  const src = read("src/lib/desk-agent.ts");
  const marks = [...src.matchAll(/action\.type === "(\w+)"/g)];
  const out: Record<string, string> = {};
  marks.forEach((m, i) => {
    const end = i + 1 < marks.length ? marks[i + 1].index! : src.length;
    out[m[1]] = src.slice(m.index!, end);
  });
  return out;
}

test("no single action writes to both ledgers", () => {
  const offenders = Object.entries(actionBlocks())
    .filter(([, block]) => {
      const craft = /saveLedger\s*\(/.test(block);
      const fa = /addDocument\s*\(|fileClientDoc\s*\(|addNote\s*\(/.test(block);
      return craft && fa;
    })
    .map(([name]) => name);
  assert.deepEqual(offenders, [], `these actions bridge the ledgers: ${offenders.join(", ")}`);
});

test("no module outside the dispatcher writes to both ledgers", () => {
  const offenders = sourceFiles()
    .filter((f) => f !== "src/lib/desk-agent.ts")
    .filter((file) => {
      const src = read(file);
      const craft = /saveLedger\s*\(/.test(src);
      const fa = /addDocument\s*\(|fileClientDoc\s*\(|addNote\s*\(/.test(src);
      return craft && fa;
    });
  assert.deepEqual(offenders, [], `these write to both ledgers: ${offenders.join(", ")}`);
});

test("a brief item carries one identity, never both", () => {
  const src = read("src/lib/ops-brief.ts");
  // Each item is built from exactly one source; an item holding a lead id and a
  // client id would be the moment the two businesses merged into one record.
  assert.doesNotMatch(src, /clientId.*lead\.id|lead\.id.*clientId/s);
  assert.match(src, /id: `lead-\$\{/, "leads are namespaced");
  assert.match(src, /id: `client-\$\{/, "clients are namespaced");
});

test("nothing filed as a Craft lead can carry client-file language", () => {
  const agent = read("src/lib/desk-agent.ts");
  const i = agent.indexOf('action.type === "intake_lead"');
  assert.notEqual(i, -1, "intake_lead is gone — re-point this test");
  const block = agent.slice(i, agent.indexOf("saveLedger", i));
  assert.match(block, /clientFileLanguage/, "a lead reaches the ledger unguarded");
});

test("an unlabelled follow-up never lands on a client file", () => {
  const agent = read("src/lib/desk-agent.ts");
  const i = agent.indexOf('action.type === "schedule_followup"');
  const block = agent.slice(i, agent.indexOf("intake_lead", i));
  // `action.line || "fa"` would fuzzy-match a shop owner onto an advice client.
  assert.doesNotMatch(block, /action\.line \|\| "fa"/, "follow-ups still default to the FA side");
  assert.match(block, /line === "fa"/, "the FA path should still be explicit");
});

test("only an FNA action writes the FNA draft", () => {
  // Ops chatter goes to `output`; `fnaMarkdown` is the client's draft and
  // chat.tsx offers to save that onto the client file. Any other action
  // writing it puts non-client content into a regulated record.
  const blocks = actionBlocks();
  const writers = Object.entries(blocks)
    .filter(([, block]) => /fnaMarkdown\s*=/.test(block))
    .map(([name]) => name)
    .sort();
  assert.deepEqual(writers, ["save_fna_note", "upsert_fna_facts"]);
});

test("the ops actions write to the output channel instead", () => {
  const blocks = actionBlocks();
  for (const name of ["list_today", "schedule_followup", "create_invoice"]) {
    assert.ok(blocks[name], `${name} is gone — re-point this test`);
    assert.doesNotMatch(blocks[name], /fnaMarkdown\s*=/, `${name} writes the FNA draft`);
  }
});

test("the chat only offers to save a real FNA draft", () => {
  const chat = read("src/routes/chat.tsx");
  const i = chat.indexOf("setLastPrep({");
  const block = chat.slice(Math.max(0, i - 300), i + 300);
  assert.match(block, /applied\.fnaMarkdown/);
  assert.doesNotMatch(block, /applied\.output/, "ops output is saveable as a client note");
});

test("the Craft desk never posts a lead to the client vault", () => {
  const craft = read("src/craft/CraftApp.tsx");
  assert.doesNotMatch(craft, /fileClientDoc|\/api\/clients/);
});
