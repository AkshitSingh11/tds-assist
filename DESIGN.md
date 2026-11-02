# Design notes: TDS on vendor invoices

**In one paragraph.** Every Indian company must withhold tax (TDS) from most vendor payments, at a rate set by the *nature* of the payment: contract work, professional fees, rent, commission and so on. Deciding the nature means reading a free-text invoice line against legal definitions, which is a reading job. Everything after that (section, rate, threshold, payment code, amount) is arithmetic on a rules table that changed completely on 1 April 2026. The prototype splits the job along that line. One LLM call picks the category and must quote the statute words it relied on. Code checks the quote, applies dated rules and the vendor's year-to-date ledger, and routes every line GREEN, AMBER or RED to a human who approves it.

**What a user sees.** An AP accountant enters one invoice line:

> SecureServ Facility Services Pvt Ltd (PAN …C…), 1 June 2026: *"Supply of security guards and housekeeping staff – May 2026 (12 personnel)"*, ₹3,50,000 + GST ₹63,000.

The tool answers:

> **Contract work, s.393(1) Table Sl. No. 6(i), payment code 1024. Deduct ₹7,000** (2% of ₹3,50,000; GST excluded because it is shown separately). Route GREEN.
> Why: *"Any sum for carrying out any work (including supply of labour for carrying out any work) in pursuance of a contract…"*, quoted from the Act in force on that date.

The accountant confirms it, or overrides it and records why. Without the tool they work this out by hand, and the trap is that "provision of services of technical or other personnel" in the technical-fees definition points to 10%, and ₹35,000. This is the model's actual answer from the recorded run; [README](README.md#one-invoice-end-to-end) walks through every step.

**Jurisdiction:** India. The payer is a company; payees are resident. The prototype covers both the Income-tax Act 1961 (FY 2025-26) and the Income-tax Act 2025 (in force from 1 April 2026), choosing between them by invoice date. All invoices, vendors and PANs are synthetic. The code is in this repository; see the [README](README.md).

---

## 1. The area, and what surprised me

I started from "where do finance teams read text and then apply rules by hand?" TDS on vendor payments came out on top. It is high-volume, every company in India does it, and a mistake costs the *payer*, not the vendor.

Four things surprised me.

**1. The law changed under everyone's feet on 1 April 2026.** The Income-tax Act 2025 replaced the 1961 Act. Sections 194C, 194J, 194H, 194-I and 194Q, the numbers every accountant and every LLM knows, are now rows of one table in s.393(1), each with a new payment code. But the *categories* barely moved: "work", "professional services", "rent" and "commission or brokerage" are defined in almost the same words in s.402. That one observation shaped the design:

> **The AI decides only what is stable: the nature of the payment. Code decides everything that changed (section, rate, code, threshold), keyed by date.**

**2. Public statute websites are stale.** The consolidated 1961 text on Indian Kanoon still shows a ₹20,000 threshold for s.194J; the Finance Act 2025 raised it to ₹50,000. A system that reads rates from "the statute" on a public website would compute wrong amounts *with a correct-looking citation*. So rates come from a reviewed, dated rules table, and statute text is used only for definitions.

**3. One invoice can be taxed because of other invoices.** A contract payment is taxed if the bill exceeds ₹30,000, *or* if the vendor's total for the year crosses ₹1,00,000. In that case the bill that crosses the line carries tax on every earlier untaxed bill too. Four ₹28,000 repair bills give no TDS, no TDS, no TDS, and then ₹2,240 (2% of ₹1,12,000). No classifier that looks at one invoice at a time, however smart, can get this right. It needs a ledger.

**4. The statute contradicts itself on ordinary invoices.** "Advertising" appears in the definition of *work* (2%) and in the list of *professions* (10%). The 2025 Act then says "work" excludes any sum covered by the professional and technical fees row (s.402(47)(B)). Read literally, an ad agency's whole bill is 10%. CBDT's long-standing position (Circular 715) is 2% for an agency releasing ads. The text alone cannot settle this, so the system has to know when to stop and ask.

## 2. The problem

| | |
|---|---|
| **Who** | The accounts-payable (AP) accountant who books vendor invoices, and the tax manager or external CA who reviews TDS before the monthly deposit (due on the 7th of the next month) and the quarterly return. |
| **Task** | For each invoice line: decide the nature of the payment, then the section, payment code, rate, taxable base (GST excluded when shown separately) and amount. This must take into account the vendor's PAN status and payments so far this year. |
| **How often** | Every vendor invoice, every month. Most lines are repeat vendors billing the same thing, which is easy. The cost is in the long tail of new vendors, mixed services and vague descriptions. |
| **What it costs today** | The accountant's and reviewer's time per line, plus the cost of errors. |

**Cost of an error.** Under the 1961 Act (the 2025 Act carries equivalent provisions), a payer that fails to deduct:

- is an *assessee in default* for the tax itself (s.201);
- pays interest of 1% a month until deduction, or 1.5% a month if tax was deducted but not deposited (s.201(1A));
- loses 30% of the expense as a deduction until the TDS is paid (s.40(a)(ia)).

*Worked example (synthetic):* a ₹10 lakh annual maintenance contract treated as exempt instead of 2% costs:

- ₹20,000 of tax paid out of the company's own pocket, plus interest;
- ₹3 lakh of disallowed expense, roughly ₹75,000 of extra tax that year at a 25% rate.

Over-deducting also costs money: 10% instead of 2% on the same contract locks up ₹80,000 of the vendor's cash until they get a refund.

**Why now.** In April 2026 every company had to remap its vendor master from old sections to new table rows and payment codes. LLMs trained on pre-2026 text answer "194J". Any tool that hard-codes "this vendor → 194J", or trusts a model's memory of the law, breaks exactly now.

**Out of scope.** The prototype does not cover:

- non-residents (treaty questions) and salary;
- TCS, GST-TDS, lower-deduction certificates, interest and dividends;
- filing returns, and payers who are individuals.

## 3. Why AI at all, and why so little of it

The obvious non-AI approach is a lookup on the vendor or the GST service code (SAC). It covers the easy majority, and the design keeps it: past reviewer decisions keyed by (PAN, SAC) skip the model entirely. But lookups cannot handle what remains:

- **Codes don't carry the legal distinction.** SAC 997319 covers bare equipment hire (rent at 2% above ₹50,000 a month) and hire *with an operator* (usually a works contract). The deciding fact is in the description, not the code. Goods invoices often carry no SAC at all.
- **Descriptions are written by vendors, in their own words.** "Manpower supply", "deployment of guards" and "housekeeping staff" are all supply of labour, which is *work* at 2%. "Provision of technical personnel" points to technical services, at a different section and code. A keyword list that tells these apart ends up as an unmaintainable rulebook of exceptions.
- **The valuable output is often "I don't know".** "Printing of brochures to our design" is work if the printer uses our paper and a sale if it uses its own. A good reviewer spots that the invoice doesn't say, and asks. Rules can't flag a question nobody wrote a rule for.

So AI is used for exactly one thing: reading the line and the definitions, and naming the category, or naming the missing fact. It never touches rates, thresholds or amounts.

## 4. The design

### 4.1 Architecture: who does what

```
 Invoice line: vendor, PAN, date, description, SAC code, amounts
      │
      ▼
 [CODE]  PAN 4th character → payee type (individual/HUF/company/firm/…; bad or missing → NO_PAN)
      │
      ▼
 [CODE]  Precedent for (PAN, SAC)? ──yes──► category a named reviewer decided earlier ──┐
      │ no                                                                             │
      ▼                                                                                │
 [AI]    One LLM call. Sees: description, SAC, vendor name, and the full text of the   │
         13 (2025 Act) or 6 (1961 Act) clauses in force on the invoice date.           │
         Returns: ONE category + verbatim quotes + missing facts + confidence.         │
         Never sees amounts. Never returns a section or rate.                          │
      │                                                                                │
      ▼                                                                                │
 [CODE]  Citation verifier: each quote is really in that clause; the clause is in      │
         force on that date; the quoted words ground THIS category.  Any fail → RED    │
      │                                                                                ▼
 [CODE]  Rules engine: dated rules table + vendor's annual ledger
         → section, payment code, rate (20% if no PAN), base (GST/material out), TDS, step-by-step trace
      │
      ▼
 [CODE]  Router   GREEN  reviewer precedent, or high confidence with clean citations
                  AMBER  medium/low confidence, open questions, or no PAN
                  RED    NEEDS_INFO, failed citation check, bad input, unparseable answer, model down
      │
      ▼
 [HUMAN] AP reviewer: GREEN approved in a batch, AMBER checked line by line.
         RED goes to the tax manager/CA, who may ask the vendor.
         Each decision can be saved as a precedent under the reviewer's name.
      │
      ▼
 [CODE]  Only approved lines post to the ledger (so only approved amounts count toward thresholds).
         Audit record per line.
 [HUMAN] Tax manager signs off the deposit and the return. The company remains the accountable deductor.
```

### 4.2 One invoice, end to end

Here is case C18, the fourth ₹28,000 bill from QuickFix Electricals: "Electrical repair and maintenance work at Bhiwandi warehouse – August 2026".

1. **PAN.** The 4th character is F, so the payee is a firm and the contract rate is 2%, not the 1% for individuals.
2. **Precedent.** There is none for this (PAN, SAC) pair, so the line goes to the model.
3. **Model.** It sees the description, the SAC (995461) and the 2025 definitions, never the ₹28,000. A good answer is `CONTRACT_WORK`, quoting "Any sum for carrying out any work" from s.393(1) Table Sl. No. 6(i), with high confidence.
4. **Verifier.** The quote is present, in force, and inside the words that ground contract work.
5. **Engine.**
   - GST of ₹5,040 is shown separately, so it is excluded from the base.
   - The bill is ₹28,000, below the ₹30,000 single-bill limit.
   - The ledger holds three approved, untaxed bills, so the year's total is ₹1,12,000, which is over ₹1,00,000.
   - The base is therefore ₹1,12,000. The rate is 2% and the TDS is ₹2,240, under s.393(1) Table Sl. No. 6(i).D(b), code 1024.
   - Each step is written to the trace.
6. **Router.** GREEN.
7. **Human.** The reviewer approves, and only then does the bill post to the ledger.

### 4.3 The architecture questions

**One LLM call, or something bigger?** One call, a rules engine and a ledger. Only one step in this problem is genuinely about language. Everything else is a lookup, a sum or a comparison, where an LLM can only add error.

- **No retrieval index.** The whole corpus in force for a date is 13 clauses (or 6 under the 1961 Act), a few thousand tokens, so the model sees all of it. That removes the "right clause never retrieved" failure for free.
- **No agents.** There is no multi-step plan to make; the steps are fixed and known in advance.
- **When retrieval would earn its place:** once circulars and case law are added and the corpus no longer fits in a prompt.

**Exact vs probabilistic, and how they are kept apart.**

| Probabilistic (model) | Exact (code) |
|---|---|
| Category name, from a closed list of 9 | Payee type from PAN |
| Which statute words to quote | Whether the quote exists, is in force, and grounds that category |
| Confidence and missing facts | Section, payment code, rate, threshold, base, catch-up, rounding |

The boundary is enforced by data flow, not by instructions:

- The model's output is parsed into an enum and a list of quotes. Anything else is rejected.
- Amounts are never in the prompt.
- The engine's inputs are the category and the invoice, never model text.
- A model that "decides" the rate is 10% has nowhere to put that decision.

**Where the knowledge lives, and what happens when it goes stale.**

| Knowledge | Lives in | When it changes |
|---|---|---|
| What an invoice description *means* | The model | Nothing to update. A better model is a drop-in. |
| Legal definitions ("work", "rent"…) | `corpus/*.json`: verbatim text, source URL, retrieval date, effective dates | Add a file with its own date range. A line dated outside every range routes RED. |
| Sections, rates, thresholds, codes | `rules.py`: an effective-dated table, with `RULES_VERSION` stamped on every audit record | Edited and reviewed like code when a Finance Act passes. Old rows stay for old dates. |
| Tax law in the model's weights | Deliberately unused | The prompt forbids it, and the verifier rejects any citation not in the provided text. |
| Grey-zone calls, vendor facts | Humans, via the precedent store (name and date) | Gap: precedents don't yet expire when a definition they relied on changes. |

**The transition proves it.** The same architect bills in March and in April 2026 (C20, C21):

- March is s.194J(1)(a), under the 1961 Act.
- April is s.393(1) Table Sl. No. 6(iii)(a), code 1027, with a fresh tax-year total.

The model was shown only the Act in force each time. Neither the prompt nor the model changed.

**Traceability.** Each line's audit record holds enough for an auditor to reconstruct the decision without trusting the system:

- the input;
- the Act and the IDs of every clause shown to the model;
- the rules version;
- the model name and prompt hash;
- the raw model answer, and any citation errors;
- the computation with every step (GST excluded, year-to-date total, catch-up, rate, rounding);
- the route and reasons;
- for precedents, who decided and when.

The prompt hash is also the file name of the cached model response, so any reported run can be replayed offline, byte for byte.

### 4.4 Rejected alternatives

| Alternative | Why not |
|---|---|
| One LLM call returning section, rate and amount | Models answer from pre-2026 memory ("194J"), can't see the year's totals, and do arithmetic unreliably. It is the most common design and fails on exactly the April 2026 transition. |
| Rules on SAC code alone | SAC is a GST classification, not a TDS one (see §3). Kept as a precedent key and a hint. |
| RAG over a vector store | It adds a retrieval failure mode to a corpus that fits in the prompt. |
| Fine-tuning | There is no labelled data, and it would bake in law that just changed: the staleness this design exists to avoid. |
| A second "critic" LLM | Another probabilistic opinion at twice the cost. A deterministic verifier plus a human is a stronger check. |
| Letting the model answer "no TDS" | Exemptions (transporter declaration, thresholds) depend on vendor-master and ledger facts, so code applies them. |
| Model outputs section numbers, mapped to categories | The section numbers changed in 2026; categories didn't. Asking for the stable thing is the point. |

### 4.5 The weakest point, and what would break it

**A confident, wrong category backed by a real quote from a clause that genuinely supports it.** Advertising cited to the "professional services" definition passes every mechanical check and routes GREEN at 10%. The verifier proves the citation is *real*, not that the reasoning is *right*. This is the one way the system can be wrong with nothing flagging it. It happened in the live run (§6): C11 went GREEN at ₹50,000 instead of ₹10,000.

Mitigations:

- **Precedents** take recurring vendors out of the model's hands after one human decision.
- **Known grey zones become citable.** Adding CBDT circulars to the corpus as dated sources gives the model and the reviewer the official answer to quote.
- **The tax manager samples GREEN lines.** The evaluation measures *unsafe* (wrong and GREEN) separately, because that is the rate that matters.

Other things that would break it:

- **Vague descriptions.** These correctly route RED, but then the tool saves no time.
- **An over-strict map of which words ground which category.** This sends correct answers to RED. It is a hand-maintained map, tested so that every entry is verbatim and unique, but it is still judgment.
- **A Finance Act change nobody enters in `rules.py`.** The design makes that update one reviewed edit, but someone still has to make it.

## 5. What I added beyond the AI

- **The split itself.** The stable category comes from the AI; the dated rules come from code. That came from reading the two Acts side by side and noticing that the categories survived while the numbers didn't.
- **Distrust of public statute text for rates,** after finding the stale ₹20,000 threshold.
- **A verifier the model cannot argue with.** Each quote must be verbatim, in force on the invoice date, and drawn from the words that ground the chosen category.
  - Several clauses serve more than one category. Rent of machinery (2%) and of land (10%) sit in one row; professional, technical and director fees share another.
  - Quoting the machinery words therefore cannot support 10% rent.
  - A 1961 clause cited for an April 2026 invoice is rejected.
- **Amounts withheld from the model,** so it cannot even attempt the thresholds.
- **Test cases built around known traps** rather than easy wins:
  - advertising;
  - manpower supply vs "provision of personnel";
  - printing to specification;
  - the transporter exemption;
  - the Act transition;
  - aggregate catch-up.

## 6. Evidence

### The live run

One run of `nvidia/nemotron-3-ultra-550b-a55b:free` (free tier, temperature 0) over the 24 synthetic lines. The per-case table is in `eval/results.md`, the full audit records are in `eval/audit.jsonl`, and the cached responses replay offline.

| correct | caught | unsafe |
|---|---|---|
| 18 | 5 | 1 |

These 24 cases were built around traps, so they show how the design behaves. They are not an accuracy estimate. What I take from them:

- **The unsafe line is the one §4.5 predicted.**
  - C11 (advertising): the model chose professional fees at high confidence and quoted genuine text. The line went GREEN at ₹50,000; the established treatment is ₹10,000.
  - No mechanical check could stop it, because the quotes really do support professional fees.
  - The same prompt at temperature 0 answered NEEDS_INFO in an earlier run. So a free-tier model is not deterministic, and one run is one sample.
- **The verifier caught two wrong answers, but for the wrong reason.**
  - On C07 (crane with operator) and C08 (cloud hosting), the model chose rent of machinery. That is wrong for both.
  - Both were rejected because the model stitched parts of the rent definition together without marking the gap. They were not rejected because they were wrong.
  - Had the model quoted exactly, C07 (high confidence) would have gone GREEN. The amount would have been right (₹1,920) but the section and payment code wrong (2(ii)(a), code 1008 instead of 6(i), code 1024): a second unsafe line.
  - The lesson: a strict verifier inflates "caught" in a way that flatters the system. A later version should accept quotes elided with "…" (checking each fragment separately), so that RED means "no grounds" and not "sloppy quoting".
- **C04, the case I expected to fail, was right.** The model chose supply of labour over "provision of personnel", quoting the clause that says so.
- **Confidence did real work.**
  - C09 (AMC as technical fees) and C24 (printing as contract work) were wrong at medium confidence. C24 went AMBER; C09 also failed the citation check.
  - C19 (doctor with no PAN) was right, and still went AMBER, because the 20% rate must be confirmed.
- **C03 failed on infrastructure, not judgment.** The provider returned an empty reply, and the line went RED.
- **Where the category was right, the amount was right, every time.** That includes the catch-up bill (₹2,240) and the March/April Act switch.

Predicted before the run (kept below as written): C11, C04, C08, C24, C07, C09. Five of the six went wrong; C04 did not.

### What is established deterministically

(Unit tests, no network.)

| Claim | How it is checked |
|---|---|
| The engine reproduces all 21 hand-computed TDS amounts in `data/cases.json` | It is given the reviewer's category for each case, processed in order on one ledger. This includes the four-bill catch-up (0, 0, 0, ₹2,240), the 20% no-PAN rate, transporter exemption, goods below ₹50 lakh, and the March/April Act switch. |
| A made-up quote, a quote from the wrong Act, or a real quote from the wrong part of a shared clause is rejected | Verifier tests, including machinery text cited for 10% rent, technical-fee text for professional fees, and insurance-commission text for brokerage. |
| Every failure mode lands on RED, never GREEN | Tests cover: model unreachable, non-JSON reply, wrong-typed fields, an unexpected exception, a date outside both Acts, negative amounts, and rent for zero months. |
| Nothing counts toward thresholds until a human approves | `process()` never writes to the ledger; there is a test for this. |
| With the model down, it fails safe | A no-key run of all 24 lines with an empty cache: 23 RED, 1 GREEN. The GREEN is C02, a reviewer precedent, correct at ₹4,000. Zero unsafe. |
| A run's results can be rebuilt from its audit log alone | `report` re-scores `audit.jsonl` against the cases and reproduces `results.md` byte for byte (tested). |

**Predicted before the run** (left as written, so it can be checked against the results above):

- **C11 (advertising agency).** This is the 10% trap. A literal reading of the text points to professional fees. Only a CONTRACT_WORK or NEEDS_INFO answer is acceptable, and a GREEN 10% answer would be *unsafe*.
- **C04 (manpower supply).** "Provision of services of technical or other personnel" in the technical-services definition is a magnet. The right answer is contract work.
- **C08 (cloud hosting)** and **C24 (printing to our design).** These score correct only as NEEDS_INFO. A model that is eager to help will pick something.
- **C07 and C09 (crane with operator, server AMC).** A wrong category gives the *same* 2% amount but the wrong section and payment code. Scoring counts these as wrong, because the return would be wrong.

## 7. Risks, and how the design handles each

**Wrong answers.**

- Nothing posts without a human.
- Model output is limited to a closed set and checked mechanically.
- Uncertainty routes AMBER or RED, and the model is told to answer NEEDS_INFO rather than guess.
- Amounts are never model output.
- *Unsafe* (wrong and GREEN) is measured separately from *caught*, because a wrong answer that is flagged costs a minute of review, while a wrong answer that isn't flagged costs tax, interest and a disallowance.

**Outdated rules.**

- Rates live in one dated, versioned table.
- Statute text carries effective dates, and dates outside every range fail closed.
- Every audit record names the rules version.
- Residual risk: someone must update the table each Budget. Payment code 1031 (goods) comes from a single secondary source and is flagged as such.

**Confidential data.**

- The model receives the vendor name, the description and the SAC only: no PAN, amounts or bank details.
- The prototype used only synthetic data on a free tier, whose providers may log prompts.
- In production, use an enterprise endpoint with no retention, or a self-hosted model. The prompt is small and the task narrow, so a small local model is plausible.
- The response cache is plaintext. That is fine for synthetic data; it should not be used as-is with real invoices.

**Liability, and keeping a qualified human in the loop.**

- **Who is accountable.** The company is the deductor and remains legally accountable for every rupee withheld, or not withheld. The tool is internal decision support, not tax advice, and it never files or pays anything.
- **Who approves.** A qualified person approves every line. Grey zones go to the tax manager or CA, whose name is recorded in the precedent and the audit trail.
- **Why routing matters.** Routing decides *how much* human attention a line gets, never *whether* it gets any.

**Another jurisdiction.**

- **What changes:** the corpus files, the rules table and the payee-type logic (the PAN 4th-character rule is Indian).
- **What stays:** the architecture, the verifier, the router and the audit record.
- **Why it transfers:** the US 1099 split (non-employee compensation vs rents) and the UK Construction Industry Scheme have the same shape. "What kind of payment is this?" is answered by reading; "what does the law do with it?" is answered by code.

## 8. Before spending more time

1. **Measure the precedent hit rate.** Sit with an AP team for a week and find out what share of lines are repeat (PAN, SAC) pairs. If it's 90%, the LLM matters for 10% of lines and the business case is review time on those. That number decides whether this is worth building.
2. **Get real labels.** Have the company's CA label 500 historical lines, and measure the *unsafe* rate before anything else. 24 synthetic cases show the mechanics, not accuracy.
3. **Add CBDT circulars as citable, dated sources** (Circular 715 on advertising first). Then check whether the advertising and AMC grey zones move from AMBER/RED to correct GREEN.
4. **Run each line more than once, and accept elided quotes.** The C11 flip shows a single sample hides instability. Two calls that disagree should route AMBER. Quotes elided with "…" should be checked fragment by fragment, so that the verifier rejects ungrounded answers and not sloppy quoting.
5. **Make precedents expire.** Store the Act and rules version with each precedent, and re-queue it when a definition it relied on changes.
6. **Resolve the open legal points in `rules.py`:**
   - whether the 2025 Act's ₹50,000 threshold is shared between professional and technical fees;
   - whether the rent threshold should add up all invoices for the same month;
   - payment code 1031.
7. **Only then extend scope:** lower-deduction certificates, non-residents and ERP integration.
