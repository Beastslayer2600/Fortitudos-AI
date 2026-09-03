import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { applyDeskActions, buildContextBlock, type DeskAgentContext, type VaultDocument } from "./desk-agent.ts";
import type { Client } from "./types.ts";

const client = (id: string, name: string) =>
  ({ id, name, status: "FNA", email: "", phone: "" }) as Client;

const doc = (id: number, filename: string, clientId: string): VaultDocument => ({
  id,
  filename,
  docType: "Signed FNA",
  clientId,
});

function ctx(over: Partial<DeskAgentContext> = {}): DeskAgentContext {
  return {
    clients: [client("botha", "Mrs Botha"), client("naidoo", "Mr Naidoo")],
    documents: [],
    notes: [],
    emails: [],
    projections: [],
    activeClientId: "botha",
    fnaFactLines: [],
    recentMessages: [],
    userMessage: "",
    vaultDocuments: [
      doc(1, "signed_fna.pdf", "botha"),
      doc(2, "fica_id.pdf", "botha"),
      doc(9, "naidoo_fna.pdf", "naidoo"),
    ],
    ...over,
  };
}

const mutators = {
  updateClient: () => {},
  addNote: () => {},
  addDocument: () => {},
};

function run(action: Record<string, unknown>, over: Partial<DeskAgentContext> = {}) {
  return applyDeskActions([action as never], ctx(over), mutators as never);
}

test("a document of the active client resolves by id", () => {
  const out = run({ type: "pdf_action", docId: 1, action: "extract" });
  assert.equal(out.pdfRequests?.length, 1);
  assert.equal(out.pdfRequests![0].docId, 1);
  assert.equal(out.pdfRequests![0].clientId, "botha");
});

test("another client's document is never reachable", () => {
  // The whole reason the agent gets ids at all. Doc 9 is Naidoo's.
  const out = run({ type: "pdf_action", docId: 9, action: "extract" });
  assert.equal(out.pdfRequests?.length, 0);
  assert.match(out.applied.join(" "), /no filed document of this client matched/);
});

test("a document that does not exist is refused, not invented", () => {
  const out = run({ type: "pdf_action", docId: 4242, action: "extract" });
  assert.equal(out.pdfRequests?.length, 0);
});

test("nothing happens when no client is open", () => {
  const out = run({ type: "pdf_action", docId: 1, action: "extract" }, { activeClientId: null });
  assert.equal(out.pdfRequests?.length, 0);
  assert.match(out.applied.join(" "), /no client is open/);
});

test("a filename can be used instead of an id", () => {
  const out = run({ type: "pdf_action", filename: "fica", action: "stamp", text: "COPY" });
  assert.equal(out.pdfRequests?.[0].docId, 2);
});

test("an ambiguous filename is refused rather than guessed", () => {
  // Acting on the wrong document of the right client is still wrong.
  const out = run({ type: "pdf_action", filename: ".pdf", action: "extract" });
  assert.equal(out.pdfRequests?.length, 0);
  assert.match(out.applied.join(" "), /matches 2 documents/);
});

test("a filename only matches within the active client", () => {
  const out = run({ type: "pdf_action", filename: "naidoo", action: "extract" });
  assert.equal(out.pdfRequests?.length, 0);
});

test("redact with neither text nor pattern does nothing", () => {
  const out = run({ type: "pdf_action", docId: 1, action: "redact" });
  assert.equal(out.pdfRequests?.length, 0);
  assert.match(out.applied.join(" "), /needs text or a pattern/);
});

test("redact carries the patterns through", () => {
  const out = run({ type: "pdf_action", docId: 1, action: "redact", patterns: ["sa_id"] });
  assert.deepEqual(out.pdfRequests![0].body.patterns, ["sa_id"]);
  assert.equal(out.pdfRequests![0].action, "redact");
});

test("annotate and stamp require their text", () => {
  for (const action of ["annotate", "stamp"]) {
    const out = run({ type: "pdf_action", docId: 1, action });
    assert.equal(out.pdfRequests?.length, 0, action);
  }
});

test("annotate defaults to page 1 and carries the note", () => {
  const out = run({ type: "pdf_action", docId: 1, action: "annotate", text: "check this" });
  assert.deepEqual(out.pdfRequests![0].body.notes, [{ page: 1, text: "check this" }]);
});

test("every request names the client, so the backend can refuse a mismatch", () => {
  const out = run({ type: "pdf_action", docId: 1, action: "extract" });
  assert.equal(out.pdfRequests![0].clientId, "botha");
});

test("a pdf action never writes the FNA draft", () => {
  const out = run({ type: "pdf_action", docId: 1, action: "extract" });
  assert.equal(out.fnaMarkdown, undefined);
});

test("the context lists only the active client's documents", () => {
  const block = buildContextBlock(ctx());
  assert.match(block, /signed_fna\.pdf/);
  assert.match(block, /fica_id\.pdf/);
  assert.doesNotMatch(block, /naidoo_fna\.pdf/, "another client's file is visible to the agent");
});

test("an open document's text reaches the agent", () => {
  const withText = ctx({
    vaultDocuments: [
      { ...doc(1, "signed_fna.pdf", "botha"), pages: [{ page: 1, text: "ID number 8001015009087" }] },
    ],
  });
  const block = buildContextBlock(withText);
  assert.match(block, /OPEN/);
  assert.match(block, /8001015009087/, "the open page text is not in context");
});

test("the agent is told it cannot rewrite PDF prose", () => {
  const src = readFileSync("src/lib/desk-agent.ts", "utf8");
  assert.match(src, /cannot rewrite the words inside a PDF/);
  assert.match(src, /never "redacted the document"/);
});

test("the client scope is sent on every pdf call from the chat", () => {
  const chat = readFileSync("src/routes/chat.tsx", "utf8");
  const i = chat.indexOf("deskApi.pdfAction(");
  assert.notEqual(i, -1, "chat no longer runs pdf requests");
  assert.match(chat.slice(i, i + 220), /req\.clientId/, "pdf call omits the client scope");
});
