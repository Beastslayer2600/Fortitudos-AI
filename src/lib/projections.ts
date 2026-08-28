import type { ProjectionInputs, ProjectionSummary } from "./types";

export const emptyProjectionInputs = (): ProjectionInputs => ({
  currentValue: 250000,
  monthlyContribution: 2500,
  lumpSum: 0,
  years: 10,
  growthRate: 9,
  adviceFee: 0.75,
  unitPrice: 12.5,
  unitsHeld: 0,
});

export function project(inputs: ProjectionInputs): ProjectionSummary {
  const unitsValue =
    inputs.unitsHeld > 0 && inputs.unitPrice > 0
      ? inputs.unitsHeld * inputs.unitPrice
      : 0;
  const openingValue = Math.max(inputs.currentValue, unitsValue) + inputs.lumpSum;
  const gross = inputs.growthRate / 100;
  const fee = Math.max(0, inputs.adviceFee) / 100;
  const net = gross - fee;
  const years = Math.max(0, inputs.years);
  const monthly = Math.max(0, inputs.monthlyContribution);

  const monthlyRate = Math.pow(1 + net, 1 / 12) - 1;
  const months = Math.round(years * 12);

  const grownOpening = openingValue * Math.pow(1 + net, years);
  let annuity = 0;
  if (months > 0 && monthly > 0) {
    if (Math.abs(monthlyRate) < 1e-9) {
      annuity = monthly * months;
    } else {
      annuity = monthly * ((Math.pow(1 + monthlyRate, months) - 1) / monthlyRate);
    }
  }

  const projectedValue = grownOpening + annuity;
  const contributions = openingValue + monthly * months;
  const growthRand = projectedValue - contributions;
  const grossProjected =
    openingValue * Math.pow(1 + gross, years) +
    (months > 0 && monthly > 0
      ? monthly *
        ((Math.pow(1 + (Math.pow(1 + gross, 1 / 12) - 1), months) - 1) /
          (Math.pow(1 + gross, 1 / 12) - 1))
      : 0);
  const feesRand = Math.max(0, grossProjected - projectedValue);

  return {
    openingValue,
    netGrowthRate: net * 100,
    projectedValue,
    contributions,
    growthRand,
    feesRand,
  };
}

export function zar(n: number) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 0,
  }).format(n);
}
