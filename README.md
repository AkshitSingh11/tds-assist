# tds-assist

A prototype that suggests the TDS (tax deducted at source) treatment of a vendor invoice line for an Indian company. The output covers the nature of payment, the section and payment code, the rate and the amount. Every suggestion carries a statute citation and goes to an accounts-payable reviewer. The design and the answers to the assignment questions are in [BRIEF.md](BRIEF.md) (4 pages), with the full reasoning in [DESIGN.md](DESIGN.md).

All data in this repository is public (statute text) or synthetic (invoices, vendors, PANs).

## The problem

Indian companies must withhold income tax from most vendor payments and deposit it with the government. This is TDS. How much to withhold depends on what the payment *is*: a contractor's work is 2% (1% for individuals), a professional's fee 10%, rent of an office 10%, rent of machinery 2%, and goods 0.1% above a threshold. The deposit and the quarterly return also need a section and a payment code. Most of the amount follows mechanically from the category: GST excluded or not, thresholds per bill and per year, a 20% rate when the vendor has no PAN.

The hard part is the category. An accounts-payable clerk sees a vendor name and a one-line description, such as "Supply of security guards and housekeeping staff". They must decide whether that is *work* (2%) or *fees for technical services* (10%), and the statute supports both readings. Errors cost money in both directions:

- **Under-deduct** and the company owes the shortfall, plus interest at 1% to 1.5% a month, and the expense can be disallowed.
- **Over-deduct** and the vendor's cash is locked up until they claim a refund, so they call AP to complain.

Today the clerk decides from memory, from a cheat sheet or by asking the tax team. Usually no record says why.

This tool does the first pass. For each invoice line it suggests the category, the section, the code and the amount. It quotes the statute words that justify the category and shows its arithmetic. Each line is then sent to one of three queues:

- **GREEN:** a quick confirm;
- **AMBER:** review it;
- **RED:** the tool cannot stand behind any answer, and a human must decide.

A human approves every line before payment. The tool does not pay, file or post anything on its own.

### One invoice, end to end

This is case C04 from the evaluation, with the model's actual answer from the recorded run in [eval/audit.jsonl](eval/audit.jsonl).

**Input.** The invoice line, as AP would key it from the bill:

```
Vendor:  SecureServ Facility Services Pvt Ltd     PAN AABCS5678Q
Date:    2026-06-01
Line:    Supply of security guards and housekeeping staff - May 2026 (12 personnel)
SAC:     998525
Amount:  ₹3,50,000 + GST ₹63,000 (shown separately)
```

**1. Payee type, from code.** The 4th character of the PAN is `C`, so the payee is a company. That fixes the rate band before any model is involved.

**2. Category, from the model.** The model sees the description, the SAC and the text of the Income-tax Act 2025, which is in force on 1 June 2026. It never sees the amounts. It returns one category and the exact words it relies on:

```
category:   CONTRACT_WORK      confidence: high
quote 1:    393(1) Table Sl. No. 6(i)
            "Any sum for carrying out any work (including supply of labour for carrying
             out any work) in pursuance of a contract between the contractor and a
             designated person."
quote 2:    402(47), the definition of "work"
rationale:  supply of labour for carrying out work under a contract ...
```

The trap here is the definition of *fees for technical services*, which includes "the provision of services of technical or other personnel". That reading gives 10%, five times the correct deduction. Choosing between the two is where judgment is needed.

**3. Citation check, from code.** Each quote must appear verbatim in the clause the model named. That clause must be in force on the invoice date. The quoted words must be the part of the clause that supports *this* category: words about machinery hire cannot justify rent of a building. Both quotes pass. A made-up or doctored quote sends the line RED.

**4. Amount, from code.** The rules table and the vendor's ledger for the year do the arithmetic. Every step is written down:

```
Payee type COMPANY from PAN; Act ITA2025 applies on 2026-06-01; rule 393(1) Table Sl. No. 6(i).D(b)
GST 63000 shown separately, excluded from base (CBDT Circular 23/2017)
Single 350000 vs 30000; aggregate 350000 (prior 0) vs 100000
TDS = 350000 x 0.02 = 7000
```

**Output.** Route **GREEN**. Section 393(1) Table Sl. No. 6(i), payment code 1024, deduct **₹7,000**. The reviewer sees the suggestion, both quotes and the trace above. Once they approve it, the line is posted to the ledger, where it counts toward the vendor's annual threshold.

Two other cases from the same run show the other outcomes:

- **C22** "Services as per agreement dated 01.04.2026 - Q1 charges". The model answered NEEDS_INFO and listed what it would need to know, starting with the nature of the services. The line went RED and nothing was computed. That is the right outcome: no one could classify this line from the invoice.
- **C11** "Design and release of newspaper advertisements". The model chose professional fees at high confidence: advertising is listed as a profession, and the definition of "work" excludes professional fees. The quotes were genuine, so the line went GREEN with ₹50,000 to deduct. The established treatment is contract work, ₹10,000, but the CBDT circular that says so is not in the corpus. This is the failure the design cannot catch, and it is discussed in [DESIGN.md](DESIGN.md#45-the-weakest-point-and-what-would-break-it).

## Run it

You need Python 3.11+ and [uv](https://docs.astral.sh/uv/). There are no runtime dependencies beyond the standard library.

```bash
# unit tests (no network)
uv run --with pytest pytest -q

# evaluation on the 24 synthetic invoice lines
export OPENROUTER_API_KEY=sk-or-...        # free account at openrouter.ai; `export` matters, see below
uv run python -m tds_assist eval           # writes eval/results.md and eval/audit.jsonl
uv run python -m tds_assist eval --only C01,C11          # a few cases; earlier cases still count toward thresholds
uv run python -m tds_assist eval --model google/gemma-4-31b-it:free   # any OpenRouter model

# rebuild eval/results.md from an existing eval/audit.jsonl (no key, no model calls)
uv run python -m tds_assist report
uv run python -m tds_assist report --audit path/to/audit.jsonl --out path/to/dir
```

`report` scores the recorded answers against `data/cases.json` again and writes `results.md` next to them. Use it to regenerate the summary after a run was interrupted, or after editing the cases' expected answers. It is also the quickest way to read someone else's run.

The key must reach the Python process: `export OPENROUTER_API_KEY=...` or `OPENROUTER_API_KEY=... uv run ...` on one line. `OPENROUTER_API_KEY=...; uv run ...` (with a semicolon) sets a shell variable that `uv` never sees. The CLI warns when no key is set.

Every model response is cached under `eval/cache/`, keyed by the hash of model plus prompt; the same hash is written to each line's audit record. The cache for the recorded run is committed, so `eval` without a key replays it offline. C03 is the exception: the model returned an empty reply, and empty replies are not cached. A prompt that is not in the cache, with no key, routes the line RED ("LLM unavailable") rather than failing.

## Model used

`nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter at temperature 0. The first choice was `google/gemma-4-31b-it:free`, but on 2026-11-01 its shared free pool returned "rate-limited upstream" on every request, so the default moved to the free model that answered. Swap models with `--model`; responses are cached per model. A free account allows 50 requests a day; one full evaluation uses 23 (C02 is decided by a precedent and needs no call). Overloaded-provider errors are retried up to three times.

## What happens to one invoice line

```
PAN ─► payee type (code) ─► precedent for (PAN, SAC)? ── yes ─► reviewer's earlier category
                                   │ no
                                   ▼
          LLM picks ONE category + exact quotes from the statute in force on the invoice date
                                   ▼
          verifier: each quote is really in that clause, the clause is in force, and the quoted words ground the category
                                   ▼
          rules engine: dated rules table + per-vendor annual ledger ─► section, code, rate, base, TDS, trace
                                   ▼
          router: GREEN / AMBER / RED ─► reviewer ─► approved lines posted to the ledger
```

| Module | Role | Exact or probabilistic |
|---|---|---|
| `pan.py` | Payee type from the 4th character of the PAN; malformed or missing PAN means NO_PAN | exact |
| `precedent.py` | Earlier reviewer decisions keyed by (PAN, SAC) | exact (a human made it) |
| `corpus/` | Verbatim definitions and charging text from the Income-tax Act 2025 and 1961, each with source URL and effective dates | data |
| `classifier.py` | Prompt, JSON parsing and citation verifier | the LLM is probabilistic; the parser and verifier are exact |
| `rules.py` | Section, payment code, rate, threshold and no-PAN rate per category, by date | exact, versioned (`RULES_VERSION`) |
| `engine.py`, `ledger.py` | GST and material exclusion, thresholds with annual catch-up, no-PAN rate, transporter exemption, rounding | exact |
| `pipeline.py` | Runs the steps, routes the result and writes the audit record | exact |
| `cli.py` | Evaluation harness | |

The LLM never sees amounts and never outputs a section, rate or amount.

## Examples tested

All 24 lines are synthetic: invented vendors and amounts, and PANs that are format-valid only. The full inputs and expectations are in [data/cases.json](data/cases.json). They are processed in order against one ledger, so earlier bills count toward later bills' annual thresholds.

| Case | What it tests |
|---|---|
| C01 | CA firm audit fee; GST shown separately and excluded |
| C02 | Same vendor, different SAC, with a reviewer precedent, so there is no LLM call |
| C03 | Advocate retainer (individual; GST on reverse charge) |
| C04 | Security and housekeeping manpower: "supply of labour" (work), not "provision of personnel" (technical) |
| C05 | Office rent of ₹1.8 lakh a month |
| C06 | Forklift hire without an operator (rent for machinery) |
| C07 | Crane hire with operator and fuel (usually contract; NEEDS_INFO acceptable) |
| C08 | Self-service cloud hosting (unsettled in practice; the only safe answer is escalation) |
| C09 | Server AMC (contract vs technical services) |
| C10 | Sales commission agent |
| C11 | Advertising agency: in both "work" and "professional services"; the 10% trap |
| C12 | Transporter with a declaration and PAN, so no deduction |
| C13 | Laptops (goods; below the ₹50 lakh aggregate) |
| C14 | Individual caterer at 1% |
| C15–C18 | Four ₹28,000 repair bills: no TDS until the ₹1 lakh aggregate is crossed, then 2% on the full ₹1.12 lakh |
| C19 | Doctor with no PAN on file: 20% instead of 10% |
| C20–C21 | Same architect in March 2026 (1961 Act, s.194J) and April 2026 (2025 Act, s.393, code 1027) |
| C22 | "Services as per agreement", which must be NEEDS_INFO |
| C23 | Director sitting fees (10%, no threshold) |
| C24 | Brochures printed to our design: work or sale depends on whose paper, which the invoice doesn't say |

Each case is scored as follows:

- **correct**: the category is acceptable and the TDS amount matches.
- **caught**: the answer is wrong or missing, but the line was routed AMBER or RED.
- **unsafe**: the answer is wrong and the line was routed GREEN.

## Results

One live run of `nvidia/nemotron-3-ultra-550b-a55b:free` over the 24 synthetic lines. The full table is in [eval/results.md](eval/results.md) and every record in [eval/audit.jsonl](eval/audit.jsonl).

| Outcome | Count | Cases |
|---|---|---|
| correct | 18 | including C04 (manpower supply, the 10% trap avoided), C15–C18 (catch-up to ₹2,240), C19 (no PAN, AMBER at 20%), C20/C21 (Act switch), C22 (NEEDS_INFO) |
| caught | 5 | C03, C07, C08, C09, C24 |
| unsafe | 1 | C11 |

Twenty-four synthetic cases show how the design behaves. They are not an accuracy estimate. What the run shows:

- **The one unsafe line is the predicted one.** On C11 (advertising), the model chose professional fees at high confidence and quoted genuine text, so the line went GREEN with ₹50,000 instead of ₹10,000. An earlier run of the same prompt at temperature 0 answered NEEDS_INFO. So the model is not deterministic even at temperature 0, and a single run says little about one case.
- **C07 and C08 were caught, but partly by luck.** The model chose rent of machinery for both. That is wrong for a crane with an operator and for cloud hosting. The verifier rejected both answers because the model joined parts of the rent definition without marking the cut ("any—(d) machinery", skipping (a)–(c)). Had it quoted exactly, C07 (high confidence) would have gone GREEN with the right amount under the wrong section: a second unsafe line.
- **C09** (server AMC as technical fees, medium confidence) also failed the citation check for a paraphrased quote. Medium confidence would have sent it AMBER anyway.
- **C24** (printing to our design) came back as contract work at medium confidence, so it went AMBER. Only NEEDS_INFO counts as correct.
- **C03** (advocate retainer) got an empty reply from the provider, which routed RED.
- **Every amount the system computed on a correct category matched the hand computation.**

What the unit tests (no network) establish independently of any model:

- Given the reviewer's category, the engine reproduces **all 21** hand-computed TDS amounts in `data/cases.json`, processed in order on one ledger. This includes the C15–C18 catch-up and the C20/C21 Act switch.
- Made-up quotes, quotes from the Act not in force, and real quotes from the wrong part of a shared clause are rejected. For example, the machinery-hire words cannot support 10% rent of a building.
- Every failure goes to RED: model down, non-JSON or wrong-typed answer, unexpected exception, date outside both Acts, negative amounts, rent for zero months.
- `process()` never posts to the ledger; only approved lines count toward thresholds.

The cases predicted to fail, before the run: C11, C04, C08, C24, C07 and C09. Five of the six did; C04 was answered correctly. See [DESIGN.md §6](DESIGN.md#6-evidence).

## Assumptions and limits

- **Scope.** The payer is a company; payees are residents; payment dates fall in FY 2025-26 (1961 Act) or from 1 April 2026 (2025 Act). Out of scope: non-residents, salary, TCS, lower-deduction certificates, GST-TDS, interest, dividends and return filing.
- **Rates and thresholds** come from `rules.py`, not from the statute text. The public consolidated 1961 text still shows outdated thresholds; see the note in `corpus/ita1961.json`.
- **Payment codes** (1023, 1024, 1026, 1027, 1028, 1006, 1008, 1009) are from secondary sources. Code 1031 (goods) was found in only one source and must be checked.
- **The ₹50,000 threshold** for professional and technical fees is applied per category. Whether the 2025 Act intends one combined threshold is an open question.
- **GST** is excluded from the base only when the invoice shows it separately (CBDT Circular 23/2017).
- **Goods (194Q / Sl. No. 8(ii))** applies only if the payer's turnover exceeded ₹10 crore in the previous year; the prototype assumes it did.
- **Rent threshold** (₹50,000 a month) is applied per invoice, dividing by `rent_months`; it does not add up several invoices for the same month.
- **Transporter declaration** is stored on the vendor, not per invoice or per year.
- **Invalid lines** (negative amounts, material above the invoice value, rent for zero months) route RED rather than computing anything. Credit notes are out of scope.
- **Not production code.** There is no ERP integration, authentication or UI. The precedent store and ledger are JSON and in-memory.
