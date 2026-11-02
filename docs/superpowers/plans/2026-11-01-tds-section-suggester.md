# TDS Section Suggester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For each vendor invoice line booked by an Indian company, suggest the TDS category, the section in force on the invoice date, and the exact TDS amount, with every output traceable to statute text and every line routed to a human.

**Architecture:** The LLM answers only one question: which nature-of-payment category applies, chosen from a fixed list, with verbatim quotes from the statute text in force on the invoice date. Plain code does everything that has to be exact: identifying the payee type from the PAN, mapping category to section/rate/code by date, thresholds against a per-vendor ledger for the year, the GST and material exclusions, and the no-PAN rate. A citation verifier and a router decide how much human attention each line needs. A precedent store, keyed by (PAN, SAC), records human decisions.

**Tech Stack:** Python 3.13, standard library only at runtime (urllib for OpenRouter); pytest via `uv run --with pytest`.

**Spec:** The approved design is in the conversation log (no separate spec file). Its points are restated under Global Constraints.

## Global Constraints

- Jurisdiction: India. Payer is always a company, so it is both a "specified person" (s.402(37)) and a "designated person" (s.402(11)). Payees are residents only.
- Invoices dated **on or after 2026-04-01** fall under Income-tax Act 2025 s.393(1). Invoices dated **before** that fall under Income-tax Act 1961 (194C/194J/194H/194I/194Q). Tax year runs 1 Apr – 31 Mar.
- The LLM never outputs a rate, an amount, or a section number. Categories: `CONTRACT_WORK, PROFESSIONAL_FEES, TECHNICAL_FEES, DIRECTOR_FEES, COMMISSION, RENT_LAND_BUILDING, RENT_PLANT_MACHINERY, GOODS_PURCHASE, NEEDS_INFO`.
- Money is `Decimal`. TDS is rounded to the nearest rupee, half-up (an assumption, noted in the README).
- Rates and thresholds: contractor 1% (individual/HUF) or 2% (others), with ₹30,000 single and ₹1,00,000 aggregate; professional 10% and technical 2%, ₹50,000 aggregate; director fees 10%, nil threshold; commission 2%, ₹20,000; rent of land/building 10% and plant/machinery 2%, ₹50,000 per month; goods 0.1% on the amount above ₹50,00,000 (aggregate per vendor per year). With no PAN: the higher of the rate and 20% (5% for goods). The same rates apply in FY 2025-26 under the 1961 Act.
- No real client data. Every test case is synthetic and labelled `"synthetic": true`.
- Every statute chunk stores `source_url` and `retrieved_on`.

## Review Focus

1. **The LLM returns non-JSON or prose wrapped around the JSON:** parse the first JSON object; if that fails, route RED with reason `llm_parse_error` and never crash. Test: `test_parse_handles_prose_wrapped_json`, `test_parse_garbage_routes_red`.
2. **The LLM cites a clause that isn't in force on the invoice date** (for example a 2025-Act clause for a March 2026 invoice): the verifier rejects it. Test: `test_citation_from_wrong_act_rejected`.
3. **Malformed or missing PAN:** treated as `NO_PAN`, 20% applied, routed AMBER. Test: `test_malformed_pan_is_no_pan`.
4. **The aggregate threshold is crossed mid-year:** catch-up TDS on earlier untaxed payments in the same rule group. Test: `test_contract_aggregate_crossing_catches_up`.
5. **OpenRouter returns HTTP 429:** retry with backoff (3 attempts), then raise `LLMUnavailable`, which the pipeline routes RED. Test: `test_llm_unavailable_routes_red`.

---

### Task 1: Statute corpus, categories, PAN facts, rules table

**Files:**
- Create: `src/tds_assist/{__init__,categories,pan,corpus,rules}.py`, `src/tds_assist/corpus/ita2025.json`, `src/tds_assist/corpus/ita1961.json`, `pyproject.toml`
- Test: `tests/test_rules.py`

**Interfaces (produces):**
- `Category(str, Enum)` with the 9 members above.
- `PayeeKind(str, Enum)`: `INDIVIDUAL, HUF, COMPANY, FIRM, OTHER, NO_PAN`; `payee_kind(pan: str | None) -> PayeeKind`. Regex `^[A-Z]{5}[0-9]{4}[A-Z]$`, kind from the 4th character (P, H, C, F, otherwise OTHER).
- `Chunk` dataclass `(id, act, ref, text, source_url, retrieved_on)`; `load_corpus(on: date) -> list[Chunk]` returns only the Act in force on that date.
- `Rule` dataclass `(act, category, section_ref, payment_code, rate, no_pan_rate, threshold_single, threshold_aggregate, threshold_basis: "year"|"month"|"none"|"excess", chunk_id, group)`; `lookup_rule(category, payee: PayeeKind, on: date) -> Rule | None`. `group` names the threshold-aggregation bucket (for example `"6(i)"`, `"194C"`).
- `ACT_2025_FROM = date(2026, 4, 1)`; `tax_year(d: date) -> str` (e.g. `"2026-27"`).

- [ ] Write tests: `payee_kind("AABCT1234F") == COMPANY`, `payee_kind("ABCPK1234L") == INDIVIDUAL`, `payee_kind("bad") == NO_PAN`, `payee_kind(None) == NO_PAN`; `lookup_rule(PROFESSIONAL_FEES, FIRM, date(2026,5,1)).section_ref` contains `"393(1)"` and `payment_code == "1027"`; the same lookup on `date(2026,3,15)` gives `"194J(b)"`; `lookup_rule(CONTRACT_WORK, INDIVIDUAL, ...).rate == Decimal("0.01")`; `load_corpus(date(2026,3,1))` contains no `ita2025` chunk.
- [ ] Run them and confirm they fail; implement; run them and confirm they pass; commit.

### Task 2: Ledger and TDS engine

**Files:** Create `src/tds_assist/{models,ledger,engine}.py`; Test `tests/test_engine.py`

**Interfaces:**
- `Vendor(name, pan: str | None, transporter_declaration: bool = False)`; `InvoiceLine(id, vendor: Vendor, date, description, sac: str | None, taxable_value: Decimal, gst: Decimal, gst_separate: bool, material_value: Decimal | None = None, rent_months: int = 1)`.
- `Ledger.prior(vendor_key, group, tax_year) -> (gross: Decimal, untaxed: Decimal)`; `Ledger.record(vendor_key, group, tax_year, amount, taxed: bool)`.
- `compute(line, category, ledger) -> Computation(applies: bool, act, section_ref, payment_code, rate, base, tds: Decimal, trace: list[str])`. `NEEDS_INFO` raises `ValueError`.
- Base calculation: `taxable_value` if `gst_separate`, otherwise `taxable_value + gst`. Subtract `material_value` for CONTRACT_WORK when it is given. Rent thresholds are tested on `base / rent_months`. Contract work with `transporter_declaration` and a valid PAN gives `applies=False`. Catch-up: when the aggregate threshold is first crossed, base += prior untaxed.

- [ ] Tests (values exact):
  - `test_gst_excluded_when_separate`: professional fee ₹1,20,000 + GST ₹21,600 separate → tds 12000.
  - `test_contract_single_below_threshold_no_tds`: ₹25,000 → applies False.
  - `test_contract_aggregate_crossing_catches_up`: 5 × ₹25,000 to a company contractor → TDS on the 5th line is 2% of 1,25,000 = 2500.
  - `test_no_pan_twenty_percent`: technical fee ₹60,000 → 12000.
  - `test_rent_monthly_threshold`: ₹1,50,000 for 3 months → applies False; ₹1,80,000 for 1 month → 18000.
  - `test_material_excluded`: contract ₹2,00,000 with material ₹1,20,000 → base 80000, tds 1600.
  - `test_director_fee_nil_threshold`: ₹10,000 → 1000.
  - `test_transporter_declaration_exempt`.
  - `test_malformed_pan_is_no_pan`.
  - `test_goods_excess_only`: an aggregate of ₹60,00,000 → base 10,00,000, tds 1000.
- [ ] Fail, implement, pass, commit.

### Task 3: LLM client, classifier, citation verifier

**Files:** Create `src/tds_assist/{llm,classifier}.py`; Test `tests/test_classifier.py`

**Interfaces:**
- `class LLM(Protocol): model: str; def complete(self, messages: list[dict]) -> str`.
- `OpenRouterLLM(model, api_key, cache_dir: Path)` uses temperature 0, a disk cache keyed by sha256 of `model + json(messages)`, and retries 429/5xx 3× with backoff. It raises `LLMUnavailable`.
- `Citation(chunk_id, quote)`; `Classification(category, citations, missing_facts, confidence: "high"|"medium"|"low", rationale)`.
- `build_messages(line, chunks) -> list[dict]`; `parse(raw: str) -> Classification` (raises `ParseError`); `verify(cls, chunks) -> list[str]` (an empty list means grounded).
- Quotes are compared after collapsing whitespace and ignoring case. A category other than NEEDS_INFO with zero citations is an error.

- [ ] Tests: `test_parse_handles_prose_wrapped_json`, `test_parse_garbage_raises`, `test_verify_accepts_exact_quote`, `test_verify_rejects_fabricated_quote`, `test_citation_from_wrong_act_rejected`, `test_unknown_category_raises`, `test_cache_hit_skips_network` (inject a fake opener).
- [ ] Fail, implement, pass, commit.

### Task 4: Precedents, pipeline, routing, audit log, CLI, evaluation

**Files:** Create `src/tds_assist/{precedent,pipeline,cli,__main__}.py`, `data/cases.json`, `data/precedents.json`; Test `tests/test_pipeline.py`

**Interfaces:**
- `PrecedentStore(path).lookup(pan, sac) -> Precedent | None`, `.add(Precedent(pan, sac, category, decided_by, decided_on, note))`.
- `process(line, llm, ledger, precedents) -> Decision(line_id, route: "GREEN"|"AMBER"|"RED", reasons: list[str], classification, computation | None, audit: dict)`.
- Routing:
  - RED: NEEDS_INFO, parse error, `LLMUnavailable`, or citation errors.
  - AMBER: confidence other than high, missing_facts not empty, NO_PAN, or category in {PROFESSIONAL_FEES, TECHNICAL_FEES} with confidence other than high.
  - GREEN: a precedent hit, or high confidence with no missing facts.
- Audit dict keys: `line_id, input, act, corpus_ids, rules_version, model, prompt_sha256, raw_llm, citation_errors, computation_trace, route, reasons, precedent`.
- CLI: `python -m tds_assist eval [--model M] [--cases data/cases.json]` processes the cases in order with a shared ledger, writes `eval/results.md` and `eval/audit.jsonl`, and prints a summary.
- Eval outcome per case:
  - `correct`: the category is in `expected.acceptable` and the TDS equals `expected.tds` when given.
  - `caught`: wrong, but routed AMBER or RED.
  - `unsafe`: wrong and routed GREEN.

- [ ] Tests (FakeLLM): `test_precedent_hit_skips_llm`, `test_needs_info_routes_red_no_computation`, `test_parse_garbage_routes_red`, `test_llm_unavailable_routes_red`, `test_high_confidence_grounded_routes_green`, `test_audit_has_required_keys`.
- [ ] Write the ~16 synthetic cases.
- [ ] Fail, implement, pass, commit.
- [ ] Live run: `OPENROUTER_API_KEY=… uv run python -m tds_assist eval`. Commit the cache and results.

### Task 5: README and BRIEF

- [ ] `README.md`: how to run, model used, case list, results table copied from `eval/results.md`, assumptions.
- [ ] `BRIEF.md`: ≤4 pages plus a 1-page appendix answering every PDF question. The "What came from you" and "Stand behind without AI" sections are left as marked prompts for the user.
