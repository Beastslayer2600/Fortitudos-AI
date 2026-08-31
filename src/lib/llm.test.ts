import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { DEFAULT_MODEL, llmMode, ollamaModel } from "./llm.ts";

/**
 * The desk is local-first and holds client files. `auto` used to fall through
 * to xAI whenever Ollama was down — which meant the prompt left the machine
 * precisely when the local model failed, silently, caller none the wiser.
 */
const src = readFileSync("src/lib/llm.ts", "utf8");

/** The provider selection after the two explicit modes. */
function autoBranch(): string {
  const i = src.indexOf("// auto is local");
  assert.notEqual(i, -1, "the auto branch comment is gone — was it rewritten?");
  return src.slice(i, i + 900);
}

test("auto never reaches the cloud", () => {
  assert.doesNotMatch(autoBranch(), /callXai/, "auto still calls xAI");
});

test("xAI is only reachable by asking for it by name", () => {
  // Skip the declaration; count only call sites.
  const calls = [...src.matchAll(/callXai\(/g)].filter(
    (m) => !/function\s+callXai\($/.test(src.slice(0, m.index! + 8)),
  );
  assert.equal(calls.length, 1, `callXai has ${calls.length} call sites, expected 1`);
  const before = src.slice(0, calls[0].index);
  assert.match(before.slice(-200), /mode === "xai"/, "callXai is not gated on the explicit mode");
});

test("a dead Ollama is an error, not a redirect", () => {
  assert.match(autoBranch(), /ok: false/);
  assert.match(autoBranch(), /provider: "ollama"/);
});

test("the error explains why the configured key was not used", () => {
  assert.match(autoBranch(), /FORTITUDO_LLM=xai/);
});

test("default mode is auto, which is local", () => {
  const prev = process.env.FORTITUDO_LLM;
  delete process.env.FORTITUDO_LLM;
  try {
    assert.equal(llmMode(), "auto");
  } finally {
    if (prev !== undefined) process.env.FORTITUDO_LLM = prev;
  }
});

test("probeLlm never advertises the cloud as preferred under auto", () => {
  const i = src.indexOf("let preferred");
  const block = src
    .slice(i, src.indexOf("return {", i))
    .split("\n")
    .filter((l) => !l.trim().startsWith("//"))       // comments are not behaviour
    .filter((l) => !/mode === "xai"/.test(l))        // the explicit mode is allowed
    .join("\n");
  assert.doesNotMatch(block, /else if \(xaiOk\)/, "auto can still prefer xAI");
});

test("the browser path defaults to the desk's own model", () => {
  const prev = { o: process.env.OLLAMA_MODEL, f: process.env.FORTITUDO_CHAT_MODEL };
  delete process.env.OLLAMA_MODEL;
  delete process.env.FORTITUDO_CHAT_MODEL;
  try {
    assert.equal(ollamaModel(), DEFAULT_MODEL);
    assert.equal(DEFAULT_MODEL, "fortitudo");
  } finally {
    if (prev.o !== undefined) process.env.OLLAMA_MODEL = prev.o;
    if (prev.f !== undefined) process.env.FORTITUDO_CHAT_MODEL = prev.f;
  }
});

test("it honours the same variable the Python desk reads", () => {
  const prev = process.env.FORTITUDO_CHAT_MODEL;
  delete process.env.OLLAMA_MODEL;
  process.env.FORTITUDO_CHAT_MODEL = "qwen2.5-coder:7b";
  try {
    assert.equal(ollamaModel(), "qwen2.5-coder:7b");
  } finally {
    if (prev === undefined) delete process.env.FORTITUDO_CHAT_MODEL;
    else process.env.FORTITUDO_CHAT_MODEL = prev;
  }
});

test("the Python default and the browser default are the same name", () => {
  const py = readFileSync("backend/config.py", "utf8");
  const m = py.match(/CHAT_MODEL = os\.environ\.get\("FORTITUDO_CHAT_MODEL",\s*"([^"]+)"\)/);
  assert.ok(m, "could not read the Python default");
  assert.equal(m[1], DEFAULT_MODEL);
});
