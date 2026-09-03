/**
 * Mirrors Financial Needs Analysis & Client Intake (fillable PDF, 6 pages).
 * Desk Chat merges chat facts + client file into a working draft — blanks stay blank.
 * Never invent figures. Adviser verifies before the signed FNA / ROA.
 */
import type {
  Client,
  ClientDocument,
  ClientEmail,
  ClientNote,
  ClientProjection,
} from "./types.ts";

export type FnaField = {
  key: string;
  label: string;
  value: string;
  source: "chat" | "file" | "blank";
};

export type FnaSection = {
  id: string;
  title: string;
  fields: FnaField[];
  notes?: string;
};

export type FnaDraft = {
  clientId: string;
  clientName: string;
  meetingType: string;
  meetingDate: string;
  adviserName: string;
  sections: FnaSection[];
  filledCount: number;
  blankCount: number;
  markdown: string;
  rawFacts: string[];
};

const BLANK = "";

function field(
  key: string,
  label: string,
  value: string,
  source: FnaField["source"] = value ? "chat" : "blank",
): FnaField {
  return { key, label, value: value || BLANK, source: value ? source : "blank" };
}

/** Pull key:value and free-form facts from adviser chat text. */
export function extractChatFacts(text: string): Record<string, string> {
  const facts: Record<string, string> = {};
  const lower = text.toLowerCase();

  // key: value or key = value lines
  for (const line of text.split(/\n|;/)) {
    const m = line.match(
      /^\s*([A-Za-z][A-Za-z0-9 /&()%._-]{1,40})\s*[:=]\s*(.+?)\s*$/,
    );
    if (m) {
      facts[normalizeKey(m[1])] = m[2].trim();
    }
  }

  const salary =
    text.match(/net\s*(?:salary|income)\s*(?:of|=|:)?\s*R?\s*([\d\s,]+)/i) ||
    text.match(/earns?\s*R?\s*([\d\s,]+)\s*(?:net|pm|per month)?/i);
  if (salary) facts.net_salary = cleanMoney(salary[1]);

  const gross = text.match(/gross\s*(?:salary|income)\s*(?:of|=|:)?\s*R?\s*([\d\s,]+)/i);
  if (gross) facts.gross_salary = cleanMoney(gross[1]);

  const spouseSalary = text.match(
    /spouse(?:'s)?\s*(?:earns?|income|salary)\s*(?:of|=|:)?\s*R?\s*([\d\s,]+)/i,
  );
  if (spouseSalary) facts.spouse_net_salary = cleanMoney(spouseSalary[1]);

  const kids = text.match(/(\d+)\s*(?:kids|children)/i);
  if (kids) facts.number_of_children = kids[1];

  const retire = text.match(/retir(?:e|ement)\s*(?:at|age)?\s*(\d{2})/i);
  if (retire) facts.target_retirement_age = retire[1];

  const risk = text.match(/\b(cautious|balanced|adventurous)\b/i);
  if (risk) facts.attitude_to_risk = risk[1];

  const id = text.match(/\b(id|id number)\s*[:=]?\s*(\d{6,13})/i);
  if (id) facts.id_number = id[2];

  const dob = text.match(
    /(?:dob|date of birth|born)\s*[:=]?\s*(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|\d{1,2}\s+\w+\s+\d{4})/i,
  );
  if (dob) facts.date_of_birth = dob[1];

  const occ = text.match(/(?:occupation|job)\s*[:=]\s*([^\n;]+)/i);
  if (occ) facts.occupation = occ[1].trim();

  const employer = text.match(/employer\s*[:=]\s*([^\n;]+)/i);
  if (employer) facts.employer = employer[1].trim();

  const address = text.match(/(?:address|lives? (?:at|in))\s*[:=]?\s*([^\n;]{8,})/i);
  if (address) facts.residential_address = address[1].trim();

  if (/first meeting/i.test(lower)) facts.meeting_type = "First meeting";
  else if (/full fna/i.test(lower)) facts.meeting_type = "Full FNA";
  else if (/annual review/i.test(lower)) facts.meeting_type = "Annual review";

  if (/\bsmoker\b/i.test(lower) && !/non[- ]?smoker/i.test(lower))
    facts.smoker = "Yes";
  if (/non[- ]?smoker/i.test(lower)) facts.smoker = "No";

  // Capture long free-text blocks after labels
  const priority = text.match(/priority\s*#?1\s*[:=]\s*([^\n]+)/i);
  if (priority) facts.top_priority_1 = priority[1].trim();

  const goals = text.match(/(?:goals?|objectives?)\s*[:=]\s*([^\n]+)/i);
  if (goals) facts.long_term_goals = goals[1].trim();

  // Keep whole message as discovery note fragment
  if (text.length > 40) facts._chat_blob = text.slice(0, 4000);

  return facts;
}

function normalizeKey(k: string) {
  return k
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function cleanMoney(s: string) {
  return s.replace(/\s/g, "").replace(/,/g, "");
}

function pick(
  facts: Record<string, string>,
  ...keys: string[]
): { value: string; source: FnaField["source"] } {
  for (const k of keys) {
    const v = facts[normalizeKey(k)] ?? facts[k];
    if (v && String(v).trim()) return { value: String(v).trim(), source: "chat" };
  }
  return { value: BLANK, source: "blank" };
}

function fromFile(value: string): { value: string; source: FnaField["source"] } {
  return value?.trim()
    ? { value: value.trim(), source: "file" }
    : { value: BLANK, source: "blank" };
}

function merge(
  chat: { value: string; source: FnaField["source"] },
  file: { value: string; source: FnaField["source"] },
) {
  if (chat.value) return chat;
  return file;
}

export function buildFnaDraft(input: {
  client: Client;
  documents: ClientDocument[];
  notes: ClientNote[];
  emails: ClientEmail[];
  projections: ClientProjection[];
  chatTexts: string[];
  meetingDate?: string;
  adviserName?: string;
}): FnaDraft {
  const facts: Record<string, string> = {};
  for (const t of input.chatTexts) {
    Object.assign(facts, extractChatFacts(t));
  }

  // Mine document / note text lightly
  for (const d of input.documents) {
    if (d.text) Object.assign(facts, extractChatFacts(d.text));
  }
  for (const n of input.notes) {
    Object.assign(facts, extractChatFacts(`${n.title}: ${n.content}`));
  }

  const c = input.client;
  const name = merge(pick(facts, "full_name", "client_name", "name"), fromFile(c.name));
  const email = merge(pick(facts, "email"), fromFile(c.email));
  const mobile = merge(pick(facts, "mobile", "phone", "cell"), fromFile(c.phone));

  const docTypes = new Set(input.documents.map((d) => d.docType));
  const fnaNote = input.notes.find((n) => n.noteType === "FNA");
  const meetingNote = input.notes.find((n) => n.noteType === "Meeting");

  const sections: FnaSection[] = [
    {
      id: "meeting",
      title: "Meeting & adviser details",
      fields: [
        field("client_name", "Client name", name.value, name.source),
        field(
          "meeting_date",
          "Meeting date",
          pick(facts, "meeting_date").value || input.meetingDate || "",
          pick(facts, "meeting_date").value || input.meetingDate ? "chat" : "blank",
        ),
        field(
          "adviser_name",
          "Adviser name",
          pick(facts, "adviser_name").value || input.adviserName || "Gert Fourie",
          pick(facts, "adviser_name").value ? "chat" : "file",
        ),
        field(
          "fsp_rep",
          "FSP / rep no.",
          pick(facts, "fsp", "fsp_rep", "rep_no").value || "Liberty Group Limited FSP 2409",
          pick(facts, "fsp", "fsp_rep").value ? "chat" : "file",
        ),
        field(
          "meeting_type",
          "Meeting type",
          pick(facts, "meeting_type").value ||
            (docTypes.has("Signed FNA") ? "Annual review" : "Full FNA"),
          pick(facts, "meeting_type").value ? "chat" : "file",
        ),
      ],
    },
    {
      id: "1",
      title: "1. Personal details",
      fields: [
        field("full_name", "Full name (client)", name.value, name.source),
        field("spouse_name", "Spouse / partner full name", pick(facts, "spouse_name", "spouse").value),
        field("id_number", "ID number", pick(facts, "id_number", "id").value),
        field("spouse_id", "Spouse ID number", pick(facts, "spouse_id").value),
        field("date_of_birth", "Date of birth", pick(facts, "date_of_birth", "dob").value),
        field("occupation", "Occupation", pick(facts, "occupation", "job").value),
        field("education", "Highest form of education", pick(facts, "education").value),
        field("employer", "Employer", pick(facts, "employer").value),
        field("employment_status", "Employment status", pick(facts, "employment_status").value),
        field("years_employed", "Years employed", pick(facts, "years_employed").value),
        field("email", "Email", email.value, email.source),
        field("mobile", "Mobile", mobile.value, mobile.source),
        field("marital_status", "Marital status & matrimonial regime", pick(facts, "marital_status", "marital").value),
        field("residential_address", "Residential address", pick(facts, "residential_address", "address").value),
        field("tax_residency", "Tax residency / citizenship", pick(facts, "tax_residency").value),
        field("smoker", "Smoker?", pick(facts, "smoker").value),
        field("health_conditions", "Health conditions (client/family)", pick(facts, "health_conditions", "health").value),
        field("dependants", "Dependants (name / DOB / relationship)", pick(facts, "dependants", "dependants_detail").value),
        field("number_of_children", "Number of children", pick(facts, "number_of_children", "children").value),
      ],
      notes: fnaNote ? `From FNA note “${fnaNote.title}”: ${fnaNote.content.slice(0, 400)}` : undefined,
    },
    {
      id: "2",
      title: "2. Monthly income",
      fields: [
        field("net_salary", "Net salary (R) — client", pick(facts, "net_salary", "net_income").value),
        field("spouse_net_salary", "Net salary (R) — spouse", pick(facts, "spouse_net_salary").value),
        field("gross_salary", "Gross salary (R)", pick(facts, "gross_salary").value),
        field("bonus", "Bonus / commission / 13th (R)", pick(facts, "bonus", "commission").value),
        field("business_income", "Business income (R)", pick(facts, "business_income").value),
        field("rental_income", "Rental income (R)", pick(facts, "rental_income").value),
        field("investment_income", "Investment / other income (R)", pick(facts, "investment_income").value),
        field("total_monthly_income", "TOTAL monthly income (R)", pick(facts, "total_monthly_income").value),
        field("marginal_tax", "Marginal tax rate (%)", pick(facts, "marginal_tax", "tax_rate").value),
        field("expected_income_changes", "Expected income changes", pick(facts, "expected_income_changes").value),
      ],
    },
    {
      id: "3",
      title: "3. Monthly expenses (household)",
      fields: [
        field("housing", "Housing: bond/rent (R)", pick(facts, "housing", "bond", "rent").value),
        field("rates", "Rates/levies/utilities (R)", pick(facts, "rates", "utilities").value),
        field("transport", "Transport (R)", pick(facts, "transport").value),
        field("groceries", "Groceries/household (R)", pick(facts, "groceries").value),
        field("school_fees", "School/tertiary fees (R)", pick(facts, "school_fees").value),
        field("medical_aid_expense", "Medical aid (R)", pick(facts, "medical_aid_expense", "medical_aid_premium").value),
        field("insurance_premiums", "Insurance premiums (R)", pick(facts, "insurance_premiums").value),
        field("debt_repayments", "Debt repayments (R)", pick(facts, "debt_repayments").value),
        field("lifestyle", "Lifestyle/other (R)", pick(facts, "lifestyle").value),
        field("current_savings", "Current savings/invest (R)", pick(facts, "current_savings").value),
        field("total_expenses", "TOTAL expenses (R)", pick(facts, "total_expenses").value),
        field("surplus", "Monthly SURPLUS / (SHORTFALL) (R)", pick(facts, "surplus", "shortfall").value),
        field("budget_track", "Do you track / budget spending?", pick(facts, "budget_track").value),
      ],
    },
    {
      id: "4",
      title: "4. Assets",
      fields: [
        field("primary_residence", "Primary residence value (R)", pick(facts, "primary_residence", "home_value").value),
        field("other_property", "Other / investment property (R)", pick(facts, "other_property").value),
        field("vehicles", "Vehicles (R)", pick(facts, "vehicles").value),
        field("cash_savings", "Cash & savings (R)", pick(facts, "cash_savings").value),
        field("unit_trusts", "Unit trusts/shares/ETFs (R)", pick(facts, "unit_trusts", "investments").value),
        field("tfsa", "Endowments/TFSA (R)", pick(facts, "tfsa", "endowments").value),
        field("retirement_funds", "Retirement funds value (R)", pick(facts, "retirement_funds", "ra_value", "current_savings_value").value),
        field("business_interests", "Business interests (R)", pick(facts, "business_interests").value),
        field("total_assets", "TOTAL assets (R)", pick(facts, "total_assets").value),
        field("inheritances", "Expected inheritances or windfalls", pick(facts, "inheritances").value),
      ],
    },
    {
      id: "5",
      title: "5. Liabilities",
      fields: [
        field("home_loan", "Home loan balance (R)", pick(facts, "home_loan", "bond_balance").value),
        field("vehicle_finance", "Vehicle finance (R)", pick(facts, "vehicle_finance").value),
        field("credit_cards", "Credit cards/overdraft (R)", pick(facts, "credit_cards").value),
        field("personal_loans", "Personal loans (R)", pick(facts, "personal_loans").value),
        field("student_loans", "Student loans (R)", pick(facts, "student_loans").value),
        field("sars", "SARS / tax owed (R)", pick(facts, "sars").value),
        field("total_liabilities", "TOTAL liabilities (R)", pick(facts, "total_liabilities").value),
        field("net_worth", "NET WORTH (R)", pick(facts, "net_worth").value),
        field("surety", "Surety / guarantees signed for others?", pick(facts, "surety").value),
        field("debt_review", "Under debt review / any default?", pick(facts, "debt_review").value),
      ],
    },
    {
      id: "6",
      title: "6. Risk cover — needs analysis",
      fields: [
        field("life_dependants", "Who depends on income / how long / lump sum needed", pick(facts, "life_dependants", "legacy").value),
        field("debts_to_settle", "Debts to settle (R)", pick(facts, "debts_to_settle").value),
        field("lump_sum_needed", "Lump sum needed (R)", pick(facts, "lump_sum_needed").value),
        field("existing_life", "Existing life cover (provider / sum assured)", pick(facts, "existing_life", "life_cover").value),
        field("disability_notes", "Disability — financial impact if permanently disabled", pick(facts, "disability_notes").value),
        field("own_occupation", "Existing definition is own occupation?", pick(facts, "own_occupation").value),
        field("disability_lump", "Disability existing lump sum (R)", pick(facts, "disability_lump").value),
        field("disability_monthly", "Disability monthly benefit (R)", pick(facts, "disability_monthly").value),
        field("income_protection", "Income protection — existing / waiting period", pick(facts, "income_protection").value),
        field("savings_runway", "How many months could savings cover expenses?", pick(facts, "savings_runway").value),
        field("severe_illness", "Severe illness / dread — family history & existing cover", pick(facts, "severe_illness", "dread").value),
        field("funeral", "Funeral cover — self / family / cultural expectations", pick(facts, "funeral").value),
      ],
      notes: input.documents
        .filter((d) => /quote|advice|living|life|disability/i.test(d.filename + d.docType + d.text))
        .map((d) => `${d.docType}: ${d.filename} — ${(d.text || "").slice(0, 200)}`)
        .join(" | ") || undefined,
    },
    {
      id: "7",
      title: "7. Medical & healthcare",
      fields: [
        field("medical_scheme", "Medical aid scheme", pick(facts, "medical_scheme", "medical_aid").value),
        field("medical_plan", "Plan", pick(facts, "medical_plan").value),
        field("gap_cover", "Gap cover in place?", pick(facts, "gap_cover").value),
        field("dependants_covered", "Dependants covered?", pick(facts, "dependants_covered").value),
        field("chronic", "Chronic conditions / anticipated procedures", pick(facts, "chronic", "health_conditions").value),
      ],
    },
    {
      id: "8",
      title: "8. Retirement planning",
      fields: [
        field("target_retirement_age", "Target retirement age", pick(facts, "target_retirement_age", "retire_age").value),
        field("desired_income", "Desired income today (R)", pick(facts, "desired_income").value),
        field("current_retirement_savings", "Current savings value (R)", pick(facts, "current_retirement_savings", "retirement_funds", "ra_value").value),
        field("monthly_contribution", "Monthly contribution (R)", pick(facts, "monthly_contribution", "ra_contribution").value),
        field("debt_free_by_retirement", "Expect to be debt-free by retirement?", pick(facts, "debt_free_by_retirement").value),
        field("other_retirement", "Other expected retirement income / preservation / post-retirement medical", pick(facts, "other_retirement").value),
      ],
      notes: input.projections.length
        ? input.projections
            .map(
              (p) =>
                `${p.name}: current R${p.inputs.currentValue}, monthly R${p.inputs.monthlyContribution}, ${p.inputs.years}y → ~R${Math.round(p.summary.projectedValue)}`,
            )
            .join("; ")
        : undefined,
    },
    {
      id: "9",
      title: "9. Investments & savings goals",
      fields: [
        field("emergency_fund", "Emergency fund (months of expenses)", pick(facts, "emergency_fund").value),
        field("short_term_goals", "Short-term goals (0-2 yrs)", pick(facts, "short_term_goals").value),
        field("medium_term_goals", "Medium-term goals (2-7 yrs)", pick(facts, "medium_term_goals").value),
        field("long_term_goals", "Long-term goals (7+ yrs)", pick(facts, "long_term_goals", "goals").value),
        field("using_tfsa", "Using annual TFSA allowance?", pick(facts, "using_tfsa").value),
        field("lump_sum_invest", "Lump sum to invest (R)", pick(facts, "lump_sum_invest").value),
        field("monthly_capacity", "Monthly capacity (R)", pick(facts, "monthly_capacity", "budget_for_solutions").value),
      ],
    },
    {
      id: "10",
      title: "10. Children's education",
      fields: [
        field("number_of_children", "Number of children", pick(facts, "number_of_children").value),
        field("schooling", "Schooling (public/private)", pick(facts, "schooling").value),
        field("tertiary", "Tertiary path envisaged", pick(facts, "tertiary").value),
        field("saving_education", "Currently saving toward education?", pick(facts, "saving_education").value),
        field("education_if_gone", "How funded if you are not around?", pick(facts, "education_if_gone").value),
      ],
    },
    {
      id: "11",
      title: "11. Estate planning",
      fields: [
        field("will", "Valid, up-to-date will?", pick(facts, "will").value),
        field("executor", "Nominated executor", pick(facts, "executor").value),
        field("estate_duty", "Estate duty & liquidity considered?", pick(facts, "estate_duty").value),
        field("beneficiaries", "Policy beneficiaries up to date?", pick(facts, "beneficiaries").value),
        field("trust", "Trust in place / considered?", pick(facts, "trust").value),
        field("living_will", "Living will / advance directive?", pick(facts, "living_will").value),
        field("poa", "Power of attorney in place?", pick(facts, "poa").value),
        field("estate_notes", "Estate planning notes", pick(facts, "estate_notes").value),
      ],
    },
    {
      id: "12",
      title: "12. Tax",
      fields: [
        field("marginal_tax", "Marginal tax rate (%)", pick(facts, "marginal_tax", "tax_rate").value),
        field("tax_deductible_ra", "Maximising tax-deductible retirement contributions?", pick(facts, "tax_deductible_ra").value),
        field("tfsa_interest", "Using TFSA & interest exemptions?", pick(facts, "tfsa_interest", "using_tfsa").value),
        field("sars_compliant", "Tax-compliant / up to date with SARS?", pick(facts, "sars_compliant").value),
        field("other_tax", "CGT, foreign income, trust income or other", pick(facts, "other_tax").value),
      ],
    },
    {
      id: "13",
      title: "13. Business assurance (if self-employed / owner)",
      fields: [
        field("buy_and_sell", "Buy-and-sell agreement in place & funded?", pick(facts, "buy_and_sell").value),
        field("key_person", "Key-person cover on critical people?", pick(facts, "key_person").value),
        field("contingent_liability", "Contingent liability cover (sureties)?", pick(facts, "contingent_liability").value),
        field("overhead_protection", "Business overhead protection?", pick(facts, "overhead_protection").value),
        field("income_draw", "How is income drawn & succession plan", pick(facts, "income_draw", "succession").value),
      ],
    },
    {
      id: "14",
      title: "14. Risk profile & attitude",
      fields: [
        field("attitude_to_risk", "Attitude to risk", pick(facts, "attitude_to_risk", "risk").value),
        field("drop_20", "Reaction if investment dropped 20% in a year", pick(facts, "drop_20").value),
        field("capital_vs_growth", "Capital protection vs growth; experience; horizon", pick(facts, "capital_vs_growth", "horizon").value),
        field("ethical", "Ethical / religious restrictions (Shariah, ESG)?", pick(facts, "ethical", "shariah", "esg").value),
      ],
    },
    {
      id: "15",
      title: "15. Existing policies & products review",
      fields: [
        field(
          "existing_policies",
          "Provider / type / value / premium / beneficiary",
          pick(facts, "existing_policies").value ||
            input.documents
              .filter((d) => ["Quote", "Advice Report", "ROA"].includes(d.docType))
              .map((d) => `${d.docType}: ${d.filename}`)
              .join("; "),
          pick(facts, "existing_policies").value
            ? "chat"
            : input.documents.some((d) => ["Quote", "Advice Report"].includes(d.docType))
              ? "file"
              : "blank",
        ),
        field("product_gaps", "Products client doesn't understand / unhappy with / gaps", pick(facts, "product_gaps").value),
      ],
    },
    {
      id: "16",
      title: "16. Goals, priorities & discovery",
      fields: [
        field("top_priority_1", "Top priority #1", pick(facts, "top_priority_1", "priority_1").value),
        field("top_priority_2", "Top priority #2", pick(facts, "top_priority_2").value),
        field("top_priority_3", "Top priority #3", pick(facts, "top_priority_3").value),
        field("monthly_budget_solutions", "Monthly budget available for solutions (R)", pick(facts, "monthly_budget_solutions", "monthly_capacity").value),
        field(
          "discovery_notes",
          "Discovery / behavioural notes",
          pick(facts, "discovery_notes").value ||
            meetingNote?.content.slice(0, 500) ||
            facts._chat_blob?.slice(0, 500) ||
            "",
          pick(facts, "discovery_notes").value
            ? "chat"
            : meetingNote || facts._chat_blob
              ? "file"
              : "blank",
        ),
      ],
    },
    {
      id: "17",
      title: "17. First-meeting discussion notes",
      fields: [
        field("why_now", "What made you decide to see an adviser now?", pick(facts, "why_now").value),
        field("if_cant_work", "If you couldn't work tomorrow, what would happen?", pick(facts, "if_cant_work").value),
        field("preferred_channel", "Preferred contact channel", pick(facts, "preferred_channel").value),
        field("review_frequency", "Review frequency", pick(facts, "review_frequency").value),
        field("other_decision_makers", "Others who should be part of decisions", pick(facts, "other_decision_makers").value),
      ],
    },
    {
      id: "18",
      title: "18. Declaration & consent",
      fields: [
        field("fais_disclosure", "FAIS disclosure provided?", pick(facts, "fais_disclosure").value),
        field("popia_consent", "POPIA consent?", pick(facts, "popia_consent").value),
        field("client_signature", "Client signature", ""),
        field("adviser_signature", "Adviser signature", ""),
      ],
      notes: "Leave signatures blank until the live meeting. This draft is not a signed FNA.",
    },
  ];

  let filledCount = 0;
  let blankCount = 0;
  for (const s of sections) {
    for (const f of s.fields) {
      if (f.value) filledCount += 1;
      else blankCount += 1;
    }
  }

  const markdown = renderFnaMarkdown({
    clientName: c.name,
    meetingDate: input.meetingDate || pick(facts, "meeting_date").value,
    sections,
    filledCount,
    blankCount,
  });

  return {
    clientId: c.id,
    clientName: c.name,
    meetingType: pick(facts, "meeting_type").value || "Full FNA",
    meetingDate: input.meetingDate || pick(facts, "meeting_date").value || "",
    adviserName: pick(facts, "adviser_name").value || input.adviserName || "Gert Fourie",
    sections,
    filledCount,
    blankCount,
    markdown,
    rawFacts: Object.entries(facts)
      .filter(([k]) => !k.startsWith("_"))
      .map(([k, v]) => `${k}: ${v}`),
  };
}

function renderFnaMarkdown(input: {
  clientName: string;
  meetingDate: string;
  sections: FnaSection[];
  filledCount: number;
  blankCount: number;
}): string {
  const lines: string[] = [
    `# Financial Needs Analysis & Client Intake — working draft`,
    ``,
    `**Client:** ${input.clientName}`,
    `**Meeting date:** ${input.meetingDate || "[to confirm]"}`,
    `**Filled fields:** ${input.filledCount} · **Still blank:** ${input.blankCount}`,
    ``,
    `_Internal working draft only. Aligns with the Fortitudo FNA Client Intake Form. Verify against payslips, statements and policy schedules. Not advice. Not a signed FNA._`,
    ``,
  ];

  for (const section of input.sections) {
    lines.push(`## ${section.title}`);
    for (const f of section.fields) {
      const tag =
        f.source === "chat" ? "chat" : f.source === "file" ? "file" : "blank";
      const val = f.value || "________________";
      lines.push(`- **${f.label}** [${tag}]: ${val}`);
    }
    if (section.notes) lines.push(`\n_Note: ${section.notes}_`);
    lines.push("");
  }

  lines.push(
    `---`,
    `Transfer completed fields into the fillable PDF. Confirm every number with the client before signing.`,
  );
  return lines.join("\n");
}

export function mergeChatIntoDraft(
  draft: FnaDraft,
  extraChat: string,
  client: Client,
  documents: ClientDocument[],
  notes: ClientNote[],
  emails: ClientEmail[],
  projections: ClientProjection[],
): FnaDraft {
  return buildFnaDraft({
    client,
    documents,
    notes,
    emails,
    projections,
    chatTexts: [...draft.rawFacts, extraChat],
    meetingDate: draft.meetingDate,
    adviserName: draft.adviserName,
  });
}
