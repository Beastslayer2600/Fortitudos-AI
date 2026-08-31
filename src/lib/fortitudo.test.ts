import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  ANSWER_SHAPE,
  DOCTRINE,
  expertSystem,
  REFUSE,
  ROLE_BOUNDARY,
  ROOM_IDS,
  STANDARD,
  withIdentity,
} from "./fortitudo.ts";

/**
 * backend/expert_route.py is the source of truth for who the desk is. This file
 * is a transcription of it for the browser half. A transcription that is never
 * checked is a second doctrine waiting to happen, so these tests read the
 * Python and fail when the two disagree.
 */
const expertRoute = readFileSync("backend/expert_route.py", "utf8");
const reason = readFileSync("backend/reason.py", "utf8");

/** Pull the string values out of a `NAME = { "key": "value", ... }` block. */
function pyDict(src: string, name: string): Record<string, string> {
  const start = src.indexOf(`${name} = {`);
  assert.notEqual(start, -1, `${name} not found in the Python`);
  const body = src.slice(start, src.indexOf("\n}", start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/"(\w+)":\s*"([^"]*)"/g)) out[m[1]] = m[2];
  return out;
}

test("the rooms are the same rooms the backend has", () => {
  const py = Object.keys(pyDict(expertRoute, "STANDARD")).sort();
  assert.deepEqual([...ROOM_IDS].sort(), py);
});

test("every room's standard matches expert_route.STANDARD", () => {
  const py = pyDict(expertRoute, "STANDARD");
  for (const room of ROOM_IDS) assert.equal(STANDARD[room], py[room], room);
});

test("every room's refusal matches expert_route.REFUSE", () => {
  const py = pyDict(expertRoute, "REFUSE");
  for (const room of ROOM_IDS) assert.equal(REFUSE[room], py[room], room);
});

test("the doctrine carries each room's reasoning order", () => {
  // reason.DOCTRINE is multi-line and parenthesised, so check the load-bearing
  // line rather than re-parsing Python string concatenation.
  for (const room of ROOM_IDS) {
    assert.match(DOCTRINE[room], /^Room: /, room);
    assert.match(DOCTRINE[room], /\nOrder: /, room);
  }
  assert.ok(reason.includes("DOCTRINE = {"), "reason.py no longer defines DOCTRINE");
});

test("the answer shape is the backend's answer shape", () => {
  for (const heading of ["Take", "Evidence", "Gap", "Next"]) {
    assert.ok(ANSWER_SHAPE.includes(heading), heading);
    assert.ok(reason.includes(heading), `${heading} missing from reason.ANSWER_SHAPE`);
  }
});

test("the FSP boundary is stated verbatim", () => {
  assert.ok(ROLE_BOUNDARY.includes("FSP 2409"));
  assert.ok(ROLE_BOUNDARY.includes("You are not the FSP"));
  assert.ok(expertRoute.includes("FSP 2409"), "expert_route.py no longer states the FSP");
  assert.ok(expertRoute.includes("You are not the FSP"));
});

test("expertSystem names the room the way the backend does", () => {
  for (const room of ROOM_IDS) {
    assert.ok(expertSystem(room).startsWith(`You are Fortitudo AI in the ${room} room.`), room);
  }
  assert.ok(expertRoute.includes("You are Fortitudo AI in the {room} room."));
});

test("an unknown room falls back to Advisor, never to no room", () => {
  for (const bad of ["", "billing", "TOASTER", "../fa"]) {
    assert.ok(expertSystem(bad).startsWith("You are Fortitudo AI in the fa room."), bad);
  }
});

test("withIdentity never drops the task prompt or the boundary", () => {
  const out = withIdentity("craft", "TASK-SENTINEL");
  assert.ok(out.includes("TASK-SENTINEL"));
  assert.ok(out.includes(ROLE_BOUNDARY));
  assert.ok(out.includes(REFUSE.craft));
});

test("no browser AI call goes out without the desk identity", () => {
  // The whole point: a generic assistant answering as the desk was the bug.
  for (const file of ["src/lib/ai.ts", "src/lib/desk-chat-ai.ts"]) {
    const src = readFileSync(file, "utf8");
    assert.match(src, /withIdentity|ROLE_BOUNDARY/, `${file} sends a prompt with no identity`);
  }
});
