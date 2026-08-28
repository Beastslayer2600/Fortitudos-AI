export type ProductPage = {
  source: string;
  page: number;
  title: string;
  text: string;
};

const SOURCE = "Fortitudo Lifestyle Protector — sample guide";

function p(page: number, title: string, text: string): ProductPage {
  return { source: SOURCE, page, title, text: text.trim() };
}

/**
 * Original sample corpus for the adviser desk. Wording is invented for demo
 * retrieval — not a licensed product guide. Real PDFs stay on the local
 * machine in the desktop build.
 */
export const PAGES: ProductPage[] = [
  p(
    1,
    "How to use this guide",
    `Fortitudo Lifestyle Protector is a sample living-benefits product used to
demonstrate the adviser workspace. It is not a real policy and must not be
quoted to a client as a market product.

The index stores each page whole. Benefit matrices span a page; splitting them
into paragraphs destroys row/column meaning. When you ask a question, the
workspace retrieves the most relevant pages and answers only from those extracts.

You remain responsible under FAIS for advice given under your licence. This
tool is a fast index, not an authority.`,
  ),
  p(
    4,
    "Waiting periods — overview",
    `Waiting period means the time that must elapse after the start date (or after
an increase in cover) before a claim event can give rise to a benefit.

[TABLE]
Event class | Standard waiting period | After reinstatement | Notes
Cancer (invasive) | 3 months | 6 months | In situ / stage 0 treated under early-cancer scale
Heart attack | 3 months | 6 months | Survival period also applies
Stroke | 3 months | 6 months | Functional deficit must persist 30 days
Blindness / visual | 3 months | 6 months | Irreversible, as defined
Hearing loss / deafness | 6 months | 12 months | Includes otosclerosis pathway
Kidney failure | 3 months | 6 months | Permanent dialysis or transplant
Paralysis / loss of use | 3 months | 6 months | Confirmed by specialist
Occupational disability | 6 months | 12 months | Own-occupation definition
Child benefits | Same as adult class | Same | Child waiting period cannot be shorter

A waiting period does not apply to accidental injury that first occurs after
the start date, except where the table states otherwise.

If the extracts do not name a waiting period for the event asked, do not infer
one from a neighbouring row.`,
  ),
  p(
    5,
    "Survival period",
    `A survival period is the number of days the life assured must survive after
the claim event before the benefit becomes payable.

[TABLE]
Event | Survival period
Heart attack | 14 days
Stroke | 14 days
Cancer (invasive) | None, once diagnosis is histologically confirmed
Blindness | 30 days after the date irreversibility is certified
Hearing loss | 30 days after the audiometry that meets the definition
Paralysis | 90 days of continuous loss of use
Occupational disability | 26 weeks (linked to the waiting / deferred period)

If the life assured dies during the survival period, the living-benefit is not
paid. A separate life cover, if in force, is assessed on its own terms.

Do not treat the survival period as a waiting period. They run on different
clocks.`,
  ),
  p(
    12,
    "Cancer — benefit scale",
    `Cancer benefits are paid as a percentage of the living-benefit sum assured
in force on the date of diagnosis, after the waiting period.

[TABLE]
Severity | Definition (summary) | % of sum assured
A — Early / in situ | Carcinoma in situ, or stage 0, surgically treated | 15%
B — Localised invasive | Invasive malignancy confined to organ of origin, stage I | 50%
C — Regional | Spread to regional lymph nodes, stage II–III | 75%
D — Advanced | Distant metastases or specified blood cancers meeting the advanced definition | 100%

Skin cancers other than malignant melanoma are excluded unless they have
invaded beyond the dermis as defined on page 38.

A partial payment under A or B reduces the remaining sum assured. A later
claim for a different primary site is assessed on the reduced cover unless
the reinstatement option was selected.

Quote percentages verbatim. Do not average adjacent rows.`,
  ),
  p(
    18,
    "Heart attack and stroke",
    `Heart attack means death of heart muscle due to obstruction of blood flow,
evidenced by a typical rise and fall of cardiac biomarkers together with
one of: new Q waves, imaging evidence of new loss of viable myocardium, or
a coronary occlusion documented on angiogram.

[TABLE]
Heart attack severity | Evidence | % of sum assured
Mild | Biomarker rise with no new Q waves and LVEF ≥ 50% at 30 days | 25%
Moderate | New Q waves or LVEF 35–49% | 50%
Severe | LVEF below 35%, or cardiogenic shock, or specified intervention list | 100%

Stroke means infarction of brain tissue or intracranial haemorrhage resulting
in a measurable neurological deficit that persists for at least 30 days.

[TABLE]
Stroke severity | Functional outcome at 30 days | % of sum assured
Mild | NIHSS 1–4, independent in ADLs | 25%
Moderate | NIHSS 5–14, or assistance required in one or more ADLs | 50%
Severe | NIHSS 15+, or permanent paralysis of two or more limbs | 100%

Transient ischaemic attack is not a stroke under this definition.
Waiting period: 3 months (page 4). Survival period: 14 days (page 5).`,
  ),
  p(
    22,
    "Blindness and visual impairment",
    `Visual benefits are assessed on best-corrected visual acuity in both eyes,
certified by an ophthalmologist.

[TABLE]
Definition | Snellen (or equivalent) | % of sum assured
Total blindness | 3/60 or worse in the better eye, irreversible | 100%
Severe visual impairment | 6/60 or worse in the better eye, irreversible | 75%
Hemianopia | Complete homonymous hemianopia, irreversible | 50%
Loss of one eye | Anatomical loss or 3/60 or worse in one eye, other eye better than 6/18 | 30%

Total blindness under Fortitudo Lifestyle Protector (and under the sample
wording that advisers often search as “Living Lifestyle”) pays 100% of the
living-benefit sum assured once irreversibility is certified and the 30-day
survival period has elapsed.

Waiting period: 3 months (page 4).
Reversible conditions, uncorrected refractive error, and night blindness
without the acuity thresholds are not claims.`,
  ),
  p(
    24,
    "Hearing loss, deafness and otosclerosis",
    `Hearing benefits use pure-tone average (PTA) at 500, 1000, 2000 and 4000 Hz,
best-aided, certified by an audiologist and ENT specialist.

[TABLE]
Definition | PTA in better ear | % of sum assured | Waiting period
Profound deafness | 90 dB or worse | 100% | 6 months
Severe hearing loss | 70 dB or worse | 50% | 6 months
Moderate-severe, both ears | 55 dB or worse in each ear | 25% | 6 months
Otosclerosis — operated | Confirmed otosclerosis treated by stapedectomy or equivalent, residual PTA 55 dB or worse in the better ear | 25% | 6 months
Otosclerosis — inoperable | Confirmed otosclerosis, surgery medically contraindicated, PTA 70 dB or worse | 50% | 6 months

The waiting period that applies to hearing loss under this Lifestyle
Protector wording is 6 months from the start date, and 12 months after
reinstatement (see page 4). Accidental binaural deafness from a single
event after the start date has no waiting period.

Hearing loss that is improved to better than the table threshold with a
hearing aid is assessed on the aided PTA. Cochlear implant in both ears
that still leaves PTA at or worse than 90 dB is treated as profound
deafness.

Do not infer a percentage that is not in this table.`,
  ),
  p(
    28,
    "Paralysis and loss of use",
    `Paralysis means complete and irreversible loss of use of the affected limbs,
certified by a neurologist, persisting for the survival period on page 5.

[TABLE]
Event | Definition | % of sum assured
Quadriplegia | Loss of use of both arms and both legs | 100%
Paraplegia | Loss of use of both legs | 100%
Hemiplegia | Loss of use of arm and leg on the same side | 75%
Loss of use of two limbs | Any two limbs, not hemiplegia | 75%
Loss of use of one limb | One arm or one leg | 50%
Loss of use of a hand or foot | Complete loss of use | 25%

Waiting period: 3 months. Survival period: 90 days of continuous loss of use.
Partial weakness, pain, or restriction of movement that is not complete loss
of use does not meet the definition.`,
  ),
  p(
    31,
    "Kidney and major organ failure",
    `[TABLE]
Organ | Definition | % of sum assured | Waiting period
Kidney | End-stage renal failure requiring permanent dialysis or transplant | 100% | 3 months
Liver | End-stage liver failure with irreversible cirrhosis meeting the specified lab and clinical criteria | 100% | 3 months
Lung | Permanent FEV1 below 30% predicted, or transplant listed | 100% | 3 months
Heart | NYHA class IV despite optimal therapy, or transplant listed | 100% | 3 months

A successful transplant pays the same percentage as the failure that
indicated it. A claim cannot be paid twice for failure and transplant of
the same organ.`,
  ),
  p(
    36,
    "Occupational disability",
    `Own-occupation disability means that, solely because of illness or injury,
the life assured is totally unable to perform the material and substantial
duties of their own occupation, and is not working in any other occupation.

[TABLE]
Tier | Definition | % of sum assured | Deferred period
Own occupation — total | Unable to perform own occupation, 26 weeks continuous | 100% of the disability sum assured | 6 months
Own occupation — partial | Able to work in own occupation at reduced capacity, income reduced by 40% or more | 50% | 6 months
Any occupation | Unable to perform any occupation reasonably suited by education, training or experience | 100% (if selected) | 6 months

The waiting period for occupational disability is 6 months (page 4).
Medical reports must address functional capacity, not diagnosis alone.`,
  ),
  p(
    38,
    "Exclusions",
    `No living benefit is payable if the claim event is caused directly or
indirectly by any of the following:

- Intentional self-inflicted injury
- Participation in a criminal act
- War, civil commotion, or terrorism, unless the life assured is a
  non-combatant civilian
- Alcohol or drug use above the legal driving limit at the time of an
  accident, unless prescribed and taken as directed
- A pre-existing condition not disclosed as required at application
- Cosmetic or elective procedures
- Non-melanoma skin cancer that has not invaded beyond the dermis
- Transient ischaemic attack
- Reversible visual or hearing loss

HIV is not an automatic exclusion. AIDS-defining conditions are assessed
against the relevant event definition.

If a row in a benefit table conflicts with this exclusions page, the
exclusion prevails. Cite both pages.`,
  ),
  p(
    41,
    "Benefit payment rules",
    `The living-benefit sum assured is the amount in force on the date of the
claim event, after any waiting-period increase rules.

Partial payments reduce remaining cover. The policy may continue with the
reduced sum assured. A 100% payment ends the living-benefit section.

Accelerated benefits reduce any linked life cover by the same rand amount
unless stand-alone living cover was selected.

Claims must be notified within 6 months of the event, with the medical
reports listed on page 44. Late notification is considered if the delay
was outside the claimant’s control.

All percentages in this guide are of the living-benefit sum assured unless
a table says otherwise.`,
  ),
  p(
    44,
    "Claims — documents required",
    `[TABLE]
Event class | Minimum reports
Cancer | Histology, staging, treating oncologist report
Heart attack | Troponin series, ECG, echocardiogram at 30 days
Stroke | CT or MRI, neurologist report at 30 days, ADL assessment
Blindness | Ophthalmologist certificate with best-corrected acuity
Hearing loss / otosclerosis | Audiogram (PTA), ENT report, operative notes if any
Paralysis | Neurologist report covering 90 days of continuous loss of use
Kidney | Nephrologist report, dialysis records or transplant listing
Occupational disability | Occupational medical, job description, sick-leave record

The adviser should not submit a claim file that is missing the minimum
report for the event class. This page is a checklist, not a medical opinion.`,
  ),
  p(
    48,
    "Definitions — selected terms",
    `Irreversible means that, in the opinion of a specialist, no further
improvement is expected with treatment that is reasonable and available
in South Africa.

Best-corrected means after spectacles, contact lenses, or a hearing aid
as applicable.

Material and substantial duties means the duties that cannot be omitted
without changing the character of the occupation.

Start date means the date cover incepts, or the date of an increase for
the increased portion only.

Otosclerosis means a confirmed bony fixation of the stapes, diagnosed by
an ENT specialist, with or without surgical treatment.

These definitions apply across the guide. A table row does not override a
definition unless it says so explicitly.`,
  ),
  p(
    52,
    "Child benefits",
    `Child living cover, if selected, follows the same event definitions as
the adult tables, with these limits:

[TABLE]
Item | Rule
Maximum child sum assured | 25% of the adult living-benefit, capped as per the quote
Waiting period | Same as the adult event class (page 4)
Survival period | Same as the adult event class (page 5)
Number of children | Named children, or all children of the life assured if the family option is in force
Age limit | Cover ends at the child’s 21st birthday, or 26th if in full-time study

A child claim does not reduce the adult sum assured.
Congenital conditions diagnosed before the start date are excluded.`,
  ),
];

export const SAMPLE_QUESTIONS = [
  "What waiting period applies to hearing loss?",
  "What does Lifestyle Protector pay for total blindness?",
  "Is otosclerosis covered, and at what severity?",
  "What is the survival period for a heart attack claim?",
  "List the standard exclusions.",
];
