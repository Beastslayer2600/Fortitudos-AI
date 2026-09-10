import assert from "node:assert/strict";
import { test } from "node:test";
import { wrongRateLabel } from "./desk-api.ts";

test("an unmeasured wrong-answer rate never renders as zero", () => {
  // The whole point of the answer log is turning "how often is this wrong"
  // from an estimate into a number. Rendering 0% before anything has been
  // judged would put a number in front of a reader that nobody has earned.
  assert.equal(wrongRateLabel(null), "not measured");
  assert.notEqual(wrongRateLabel(null), "0%");
});

test("a genuine zero is still shown as zero", () => {
  assert.equal(wrongRateLabel(0), "0%");
});

test("a rate is rounded to whole percent", () => {
  assert.equal(wrongRateLabel(0.5), "50%");
  assert.equal(wrongRateLabel(1), "100%");
  assert.equal(wrongRateLabel(1 / 3), "33%");
});
