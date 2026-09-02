import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

/**
 * The Documents tab used to show the vault and the browser store as two
 * unjoined lists. Someone could believe a document was filed when it existed
 * only in their browser — and a browser-only file is not part of the FAIS
 * record and does not survive clearing site data.
 *
 * These read the route because the component is not exported; what is worth
 * pinning is the invariant, not the markup.
 */
const src = readFileSync("src/routes/clients/$clientId.tsx", "utf8");

test("the two document sources are merged into one list", () => {
  assert.match(src, /function Documents\(/);
  assert.doesNotMatch(src, /function VaultDocuments\(/, "the split list is back");
});

test("only the vault can be labelled as in the client file", () => {
  // A row's `where` comes from which source built it, never from a guess.
  const vaultRow = src.slice(src.indexOf("...vault.map("), src.indexOf("...local"));
  assert.match(vaultRow, /where: "filed"/);
  const localRow = src.slice(src.indexOf("...local"), src.indexOf("];", src.indexOf("...local")));
  assert.match(localRow, /where: "device"/);
  assert.doesNotMatch(localRow, /where: "filed"/, "a browser-only file can be shown as filed");
});

test("a browser-only document says it is not in the client file", () => {
  assert.match(src, /On this device only/);
  assert.match(src, /not in the client&apos;s file on disk/);
});

test("a document already in the vault is not listed twice", () => {
  assert.match(src, /filedNames\.has\(d\.filename\.toLowerCase\(\)\)/);
});

test("only a filed PDF can be opened in the workbench", () => {
  const i = src.indexOf("setOpenId(row.docId)");
  assert.notEqual(i, -1);
  const guard = src.slice(i - 260, i);
  assert.match(guard, /row\.docId !== null/);
  assert.match(guard, /\.pdf/);
});

test("a backend that is down is stated, not silently shown as empty", () => {
  assert.match(src, /backend is not running/);
  assert.match(src, /Only what is held in this browser is shown/);
});
