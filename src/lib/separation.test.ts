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

test("no module reads both the Craft ledger and the FA client store", () => {
  const offenders = sourceFiles().filter((file) => {
    const src = read(file);
    const craft = /craft-ledger|from "@\/lib\/craft"/.test(src);
    const fa = /from "@\/lib\/store"|useFortitudo/.test(src);
    return craft && fa;
  });
  assert.deepEqual(offenders, [], `these bridge the two ledgers: ${offenders.join(", ")}`);
});

test("the Craft desk never posts a lead to the client vault", () => {
  const craft = read("src/craft/CraftApp.tsx");
  assert.doesNotMatch(craft, /fileClientDoc|\/api\/clients/);
});
