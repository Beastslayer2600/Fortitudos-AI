import assert from "node:assert/strict";
import { test } from "node:test";
import { project } from "./projections.ts";
import type { ProjectionInputs } from "./types.ts";

const inputs = (over: Partial<ProjectionInputs> = {}): ProjectionInputs => ({
  currentValue: 0, monthlyContribution: 0, lumpSum: 100000, years: 10,
  growthRate: 10, adviceFee: 1, unitPrice: 0, unitsHeld: 0, ...over,
});

// Pinned to backend/app.py's projection(): the fee divides the growth factor.
// Subtracting it from the rate gives 236736.37 and the two surfaces disagree.
test("the advice fee divides the growth factor, as the backend does", () => {
  const out = project(inputs());
  assert.ok(Math.abs(out.projectedValue - 234808.1212961) < 0.01, String(out.projectedValue));
  assert.ok(Math.abs(out.netGrowthRate - 8.910891089) < 1e-6, String(out.netGrowthRate));
});

test("a zero fee leaves gross growth untouched", () => {
  const out = project(inputs({ adviceFee: 0 }));
  assert.ok(Math.abs(out.projectedValue - 100000 * Math.pow(1.1, 10)) < 0.01);
  assert.ok(Math.abs(out.feesRand) < 0.01);
});

test("a catastrophic growth rate does not produce NaN", () => {
  for (const growthRate of [-100, -250]) {
    const out = project(inputs({ growthRate }));
    assert.ok(Number.isFinite(out.projectedValue), `growthRate ${growthRate}`);
    assert.ok(Number.isFinite(out.netGrowthRate), `growthRate ${growthRate}`);
  }
});

test("monthly contributions accumulate without a lump sum", () => {
  const out = project(inputs({ lumpSum: 0, monthlyContribution: 1000 }));
  assert.ok(Number.isFinite(out.projectedValue));
  assert.equal(out.contributions, 1000 * 120);
  assert.ok(out.projectedValue > out.contributions, "growth should exceed contributions");
});
