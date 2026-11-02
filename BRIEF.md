# TDS on vendor invoices: let the AI read, let code count, let a human sign

**Jurisdiction:** India. The payer is a company and payees are resident. The prototype covers the Income-tax Act 1961 (FY 2025-26) and the Income-tax Act 2025 (in force from 1 April 2026), and picks between them by invoice date. All invoices, vendors and PANs are synthetic. The code and how to run it are in the [README](README.md), and the full reasoning behind every section below is in [DESIGN.md](DESIGN.md).

**What a user sees.** An accounts-payable (AP) accountant enters one invoice line:

> SecureServ Facility Services Pvt Ltd (a company), 1 June 2026: *"Supply of security guards and housekeeping staff – May 2026 (12 personnel)"*, ₹3,50,000 + GST ₹63,000.

The tool answers:

> **Contract work, s.393(1) Table Sl. No. 6(i), payment code 1024. Deduct ₹7,000** (2% of ₹3,50,000; GST is excluded because the invoice shows it separately). Route **GREEN**.
> Why: *"Any sum for carrying out any work (including supply of labour for carrying out any work) in pursuance of a contract…"*, quoted from the Act in force on that date.

The accountant confirms the answer, or overrides it and records why. The trap here is the technical-fees definition, whose "provision of services of technical or other personnel" points to 10%, which would be ₹35,000. The answer above is the model's real output from the recorded run.

## 1. The area, and what surprised me

I looked for places where finance teams read text and then apply rules by hand. TDS on vendor payments came out on top: it is high-volume, every Indian company does it, and the cost of a mistake falls on the payer. Four things surprised me:

1. **The law changed on 1 April 2026.** Sections 194C, 194J, 194-I and 194H, the numbers every accountant and every LLM knows, became rows of a single table in s.393(1), each with a new payment code. The *categories* ("work", "professional services", "rent") kept almost the same definitions. That shaped the design: **the AI decides only what is stable (the nature of the payment); code decides everything that changed (section, rate, code, threshold), keyed by date.**
2. **Public statute websites are stale.** The consolidated 1961 text online still shows a ₹20,000 threshold for s.194J; it has been ₹50,000 since the Finance Act 2025. Rates therefore come from a reviewed, dated table, and statute text is used only for definitions.
3. **One invoice can be taxed because of other invoices.** Four ₹28,000 repair bills give no TDS, no TDS, no TDS, and then ₹2,240. The fourth bill pushes the year's total over ₹1 lakh, so tax is due on all four. No per-invoice classifier can get this right; it needs a ledger.
4. **The statute contradicts itself.** Advertising appears in the definition of *work* (2%) and in the list of *professions* (10%), and "work" then excludes professional fees. CBDT's position is 2% for an agency releasing ads. The text alone cannot settle it.

## 2. The problem

| | |
|---|---|
| **Who** | The AP accountant who books vendor invoices, and the tax manager or CA who reviews TDS before the monthly deposit and the quarterly return. |
| **Task** | For each invoice line, decide the nature of the payment. Then work out the section, payment code, rate, base (GST excluded when shown separately) and amount, given the vendor's PAN status and payments so far this year. |
| **How often** | Every vendor invoice, every month. Repeat vendors are easy; the cost sits in new vendors, mixed services and vague descriptions. |
| **What it costs today** | Expert time per line, plus errors in both directions. Under-deducting makes the company liable for the tax, 1–1.5% interest a month and a 30% disallowance of the expense: on a ₹10 lakh contract wrongly treated as exempt, that is about ₹95,000 plus interest. Over-deducting (10% instead of 2%) locks up ₹80,000 of the vendor's cash. |

**Why now.** Since April 2026 every vendor master has had to be remapped to new table rows and codes. Models trained on pre-2026 text still answer "194J".

**Out of scope:** non-residents, salary, TCS, GST-TDS, lower-deduction certificates, interest, dividends, return filing, and payers who are individuals.

## 3. Why AI, and why so little of it

A lookup on vendor or SAC (the GST service code) handles the repeat majority, and the design keeps it as a precedent store. Lookups fail on the rest:

- **SAC codes don't carry the legal distinction.** For example, crane hire with an operator is usually a works contract, and bare hire is rent.
- **Vendors describe the same service in many ways.** "Manpower supply", "deployment of guards" and "housekeeping staff" are all supply of labour.
- **The most valuable answer is often "the invoice doesn't say".** Printing to our design is work if the printer uses our paper, and a sale if it uses its own.

Reading a free-text line against legal definitions is a language task. Nothing after it is.

## 4. The design

```
 Invoice line ──► [CODE] PAN → payee type
                     │
                     ├─► [CODE] precedent for (PAN, SAC)? ── yes ──────────────────────┐
                     │ no                                                               │
                     ▼                                                                  │
               [AI] one LLM call: description + SAC + the clauses in force that day     │
                     → ONE category, verbatim quotes, missing facts, confidence         │
                     (never sees amounts, never returns a section or rate)              │
                     ▼                                                                  │
               [CODE] citation verifier: quote exists, clause in force, quoted words    │
                     ground THIS category ── any failure → RED                          │
                     ▼                                                                  ▼
               [CODE] rules engine: dated rules table + vendor's annual ledger
                     → section, code, rate, base, TDS, step-by-step trace
                     ▼
               [CODE] router: GREEN (precedent, or high confidence + clean citations)
                              AMBER (lower confidence, open questions, no PAN)
                              RED   (NEEDS_INFO, failed check, bad input, model down)
                     ▼
               [HUMAN] AP reviewer approves GREEN in batches and AMBER line by line;
                       RED goes to the tax manager / CA. Decisions can become precedents.
                     ▼
               [CODE] only approved lines post to the ledger; audit record per line
               [HUMAN] tax manager signs the deposit and return; the company stays accountable
```

**One LLM call, a rules engine and a ledger.** Only one step needs language. The 13 clauses in force (6 under the 1961 Act) fit in the prompt, so there is no retrieval step to miss the right clause. The steps are fixed, so agents add nothing. Retrieval earns its place only once circulars and case law are added.

**Exact vs probabilistic, kept apart by data flow.** The model's output is parsed into an enum and a list of quotes, and anything else is rejected. Amounts are never in the prompt. The engine's inputs are the category and the invoice, never model text, so a model that "decides" the rate is 10% has nowhere to put that decision.

**Where knowledge lives, and when it goes stale.**

| Knowledge | Lives in | When it changes |
|---|---|---|
| What a description means | the model | swap in a better model |
| Legal definitions | `corpus/*.json`: verbatim text, source URL, effective dates | add a dated file; dates outside every range route RED |
| Rates, thresholds, codes | `rules.py`: a dated table, version stamped on every audit record | edit and review it like code each Budget |
| Grey-zone calls | humans, via precedents with name and date | gap: precedents don't yet expire when a definition changes |

The same architect billing in March and April 2026 gets s.194J under the 1961 Act, then s.393(1) code 1027 under the 2025 Act, with no change to the prompt or the model.

**Traceability.** Each line's audit record holds:

- the input;
- the Act and the IDs of the clauses shown to the model;
- the rules version;
- the model and prompt hash;
- the raw answer and any citation errors;
- every computation step;
- the route and its reasons.

The prompt hash names the cached response, so any run can be replayed offline.

**Weakest point.** A confident, wrong category with a genuine quote from a clause that really does support it. The verifier proves a citation is *real*, not that the reasoning is *right*. This happened in the live run: on C11 (advertising), the model chose professional fees and the line went GREEN at ₹50,000 instead of ₹10,000. Precedents, citable CBDT circulars and sampled review of GREEN lines are the mitigations ([DESIGN §4.5](DESIGN.md#45-the-weakest-point-and-what-would-break-it)).

**Rejected alternatives.**

| Alternative | Why not |
|---|---|
| One LLM call returning section, rate and amount | It answers from pre-2026 memory, can't see the year's totals, and is unreliable at arithmetic. |
| Rules on SAC alone | SAC is a GST classification, not a TDS one. It is kept as a precedent key. |
| RAG / vector store | It adds a retrieval failure to a corpus that fits in the prompt. |
| Fine-tuning | There is no labelled data, and it would bake in law that just changed. |
| A second "critic" LLM | Another probabilistic opinion. A deterministic verifier plus a human is stronger. |

## 5. What I added beyond the AI

- **The split itself:** stable categories come from the AI, dated rules from code. It came from reading the two Acts side by side.
- **Distrust of public statute text for rates,** after finding the stale threshold.
- **A verifier the model cannot argue with.** Several clauses serve two categories (rent of machinery at 2% and of buildings at 10% share one row), so a quote must come from the words that ground *the chosen* category, in the Act in force on the invoice date.
- **Amounts withheld from the model.**
- **Test cases built around traps** rather than easy wins: advertising, manpower supply, printing to specification, the transporter exemption, the Act switch, and the annual catch-up.

## 6. Evidence

I built 24 synthetic lines around known traps and ran them once through `nvidia/nemotron-3-ultra-550b-a55b:free` (free tier, temperature 0). The results were **18 correct, 5 caught (AMBER/RED), 1 unsafe (wrong and GREEN)**. This shows how the design behaves; it is not an accuracy estimate.

- **The unsafe line was the predicted one (C11).** An earlier run of the same prompt answered NEEDS_INFO, so the free model isn't deterministic even at temperature 0.
- **Two "caught" lines were partly luck.** On C07 and C08 the model chose rent of machinery, which is wrong for both. The verifier rejected them only because the model stitched a quote together. With an exact quote, C07 would have gone GREEN with the right amount under the wrong code: a second unsafe line.
- **Wherever the category was right, the amount was right,** including the catch-up (₹2,240) and the Act switch.
- **Unit tests check, independent of any model:**
  - all 21 hand-computed amounts;
  - rejection of fabricated, wrong-Act and wrong-category quotes;
  - every failure mode routing RED.

Per-case detail is in [eval/results.md](eval/results.md) and [DESIGN §6](DESIGN.md#6-evidence).

## 7. Risks

| Risk | How the design handles it |
|---|---|
| **Wrong answers** | Nothing posts without a human. Output is a closed set, checked mechanically. Uncertainty routes AMBER/RED. Amounts never come from the model. *Unsafe* is measured separately from *caught*. |
| **Outdated rules** | Rates live in one dated, versioned table. Statute text carries effective dates, and dates outside every range fail closed. Residual risk: someone must update the table each Budget. |
| **Confidential data** | The model sees only vendor name, description and SAC: no PAN, amounts or bank details. Production needs a no-retention or self-hosted model. The plaintext response cache is for synthetic data only. |
| **Liability** | The company is the deductor and stays accountable. The tool is decision support: it never pays or files. A qualified person approves every line, and grey zones go to the tax manager or CA, whose name is recorded in the audit trail. |
| **Another jurisdiction** | The corpus, the rules table and the payee-type logic change. The architecture, verifier, router and audit record stay. US 1099 and the UK CIS have the same shape. |

## 8. Before spending more time

1. **Measure the precedent hit rate** with a real AP team. If 90% of lines are repeats, the model matters for only 10%.
2. **Get 500 historical lines labelled by a CA** and measure the unsafe rate first.
3. **Add CBDT circulars as dated, citable sources** (Circular 715 first).
4. **Sample each line twice, and accept elided quotes.** Disagreement routes AMBER; quotes elided with "…" are checked fragment by fragment.
5. **Make precedents expire** when the definition they relied on changes.
6. **Resolve the open legal points in `rules.py`:** whether the ₹50,000 threshold is shared between professional and technical fees, the monthly rent aggregation, and payment code 1031.

---

## Appendix: what came from AI, and what came from me

**Where AI helped.** I used Claude Code (Claude Opus) for:

- brainstorming problems;
- researching the 2025 Act, and fetching and checking statute text word for word;
- drafting the design, the code and the tests;
- an independent code review;
- drafting this brief.

Key prompts:

1. *"Which are some of the problems you see in finance side which can be automated / solved via AI-based solutions?"*, then *"suggest more simple ones"*.
2. *"Check the 'Think hard about the architecture part' and based on that, suggest the problems please and how they fit in the assignment."* This reframed the choice around problems that need both an exact part and a probabilistic part.
3. *"Let's go ahead with TDS section classification... create a doc outlining the details of what is built and answer all the questions asked in the PDF."*

**What was rejected or corrected, and how it was caught:**

- **Statute text first written from memory (s.194C).** It differed from the source page. Every clause is now checked by exact substring match against the downloaded text.
- **"194J(b)" used for professional fees.** That is a colloquial label: the clause is s.194J(1)(a), and (b) is technical services. A test pins it.
- **Rates read from statute text.** Rejected after finding the superseded ₹20,000 threshold.
- **Circular 715 paraphrased from memory.** The official source was unreachable, so it was left out rather than invented, and the gap is named as the weakest point.
- **A citation verifier that was too coarse.** Machinery-hire words (2%) could "support" rent of a building (10%). The code review caught it, and each category is now tied to its own words in a shared clause.
- *Before submitting: keep only the corrections you personally caught or drove, and say which.*

**What came from me.** I'm not a tax person, so most of the statute digging was done with the AI. My part was mostly steering and refusing to take things on faith.

- **Choosing the problem.** The first round of ideas felt too broad. I pushed for simpler problems and then deliberately for ones that would stress the *architecture* questions in the brief. TDS was my pick because it has both halves: a judgment call (what *is* this payment?) and arithmetic that has to be exact.
- **Running it myself.** I didn't trust the "it works" summary. I ran the full evaluation and read the audit log line by line, which is how I found every line marked "LLM unavailable". Partly my own fault: I'd set the key with a semicolon instead of `export`. That is now a warning in the CLI and a note in the README, because the next person will make the same mistake.
- **Noticing what was missing.** After the run there was no results file, so I asked for a way to rebuild results from the audit log (`report`). I also realised the docs explained *how* the system works but never *what problem it solves for whom*. That's why the C04 invoice now opens both documents.
- **Keeping it honest.** My one standing rule for the write-up was "no AI slop": crisp, readable, and failures (C11, the C07 near-miss) stated plainly. Free-tier limits meant keeping test runs small. I also caught that the confidential assignment PDF had gone into git, and had it purged from the history. That should have been done on day one.

**One thing I'd stand behind without AI.** Why a classifier alone can never get TDS right. Take four ₹28,000 repair bills from one vendor. Each is under the ₹30,000 single-bill limit, so the first three get no deduction. The fourth takes the year's total to ₹1,12,000, past the ₹1 lakh annual limit. Now tax is due on *all four*, so that bill carries 2% of ₹1,12,000, which is ₹2,240. The answer for invoice four depends on invoices one to three, which no per-invoice model ever sees. That's why the AI only says *what kind* of payment it is, and a ledger plus dated rules in code decide the amount. The same split handles April 2026: the section numbers changed and the categories didn't.
