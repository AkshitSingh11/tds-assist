# Evaluation results

Model: `nvidia/nemotron-3-ultra-550b-a55b:free`  
Rules version: `2026-11-01.1`  
Corpus: ITA1961@2026-11-01, ITA2025@2026-11-01  
Cases: 24 (all synthetic, see `data/cases.json`)

| Outcome | Count |
|---|---|
| correct | 18 |
| caught | 5 |
| unsafe | 1 |

Routes: GREEN 17, AMBER 2, RED 5

| Case | Description | Acceptable | Got | Confidence | Route | Section | TDS (got / expected) | Outcome |
|---|---|---|---|---|---|---|---|---|
| C01 | Statutory audit fee FY 2025-26 | PROFESSIONAL_FEES | PROFESSIONAL_FEES | high | GREEN | 393(1) Table Sl. No. 6(iii)(a) | 12000 / 12000 | correct |
| C02 | Tax audit and return filing fee FY 2025-26 | PROFESSIONAL_FEES | PROFESSIONAL_FEES | precedent | GREEN | 393(1) Table Sl. No. 6(iii)(a) | 4000 / 4000 | correct |
| C03 | Monthly retainer - legal advisory, May 2026 | PROFESSIONAL_FEES | - | - | RED | - | - / 6000 | caught |
| C04 | Supply of security guards and housekeeping staff - May 2026 (12 personnel) | CONTRACT_WORK | CONTRACT_WORK | high | GREEN | 393(1) Table Sl. No. 6(i).D(b) | 7000 / 7000 | correct |
| C05 | Rent for office premises, 3rd floor, Indiranagar - April 2026 | RENT_LAND_BUILDING | RENT_LAND_BUILDING | high | GREEN | 393(1) Table Sl. No. 2(ii)(b) | 18000 / 18000 | correct |
| C06 | Monthly hire charges - 3 tonne diesel forklift, June 2026 (equipment only; operator and fuel by customer) | RENT_PLANT_MACHINERY | RENT_PLANT_MACHINERY | high | GREEN | 393(1) Table Sl. No. 2(ii)(a) | 1500 / 1500 | correct |
| C07 | Hire of 25 tonne mobile crane with operator and fuel, 8 days, for roof truss installation at Bhiwandi warehouse | CONTRACT_WORK, NEEDS_INFO | - | high | RED | - | - / 1920 | caught |
| C08 | Cloud hosting charges - June 2026: 4 virtual servers, 2 TB storage, bandwidth (self-service, pay-as-you-go) | NEEDS_INFO | - | medium | RED | - | - / - | caught |
| C09 | Annual maintenance contract FY 2026-27 - preventive maintenance and on-call repair of 6 rack servers (parts billed separately) | CONTRACT_WORK, NEEDS_INFO | - | medium | RED | - | - / 4800 | caught |
| C10 | Commission @ 2% on sales booked in Q1 FY 2026-27 under sales agency agreement | COMMISSION | COMMISSION | high | GREEN | 393(1) Table Sl. No. 1(ii) | 1280 / 1280 | correct |
| C11 | Design and release of newspaper advertisements - Diwali campaign (media cost and creative) | CONTRACT_WORK, NEEDS_INFO | PROFESSIONAL_FEES | high | GREEN | 393(1) Table Sl. No. 6(iii)(a) | 50000 / 10000 | unsafe |
| C12 | Freight charges - 3 truckloads Bhiwandi to Pune, LR nos. 4411-4413 | CONTRACT_WORK | CONTRACT_WORK | high | GREEN | 393(1) Table Sl. No. 6(i).D(a) | 0 / 0 | correct |
| C13 | Dell Latitude laptops x 20 (HSN 8471) | GOODS_PURCHASE | GOODS_PURCHASE | high | GREEN | 393(1) Table Sl. No. 8(ii) | 0 / 0 | correct |
| C14 | Outdoor catering for annual offsite, 120 persons, 2 days | CONTRACT_WORK | CONTRACT_WORK | high | GREEN | 393(1) Table Sl. No. 6(i).D(a) | 450 / 450 | correct |
| C15 | Electrical repair and maintenance work at Bhiwandi warehouse - May 2026 | CONTRACT_WORK | CONTRACT_WORK | high | GREEN | 393(1) Table Sl. No. 6(i).D(b) | 0 / 0 | correct |
| C16 | Electrical repair and maintenance work at Bhiwandi warehouse - June 2026 | CONTRACT_WORK | CONTRACT_WORK | high | GREEN | 393(1) Table Sl. No. 6(i).D(b) | 0 / 0 | correct |
| C17 | Electrical repair and maintenance work at Bhiwandi warehouse - July 2026 | CONTRACT_WORK | CONTRACT_WORK | high | GREEN | 393(1) Table Sl. No. 6(i).D(b) | 0 / 0 | correct |
| C18 | Electrical repair and maintenance work at Bhiwandi warehouse - August 2026 | CONTRACT_WORK | CONTRACT_WORK | high | GREEN | 393(1) Table Sl. No. 6(i).D(b) | 2240 / 2240 | correct |
| C19 | Annual health check-up camp for employees - doctor's consultation fees | PROFESSIONAL_FEES | PROFESSIONAL_FEES | high | AMBER | 393(1) Table Sl. No. 6(iii)(a) | 12000 / 12000 | correct |
| C20 | Architectural drawings for warehouse extension - stage 1 (concept design) | PROFESSIONAL_FEES | PROFESSIONAL_FEES | high | GREEN | 194J(1)(a) | 8000 / 8000 | correct |
| C21 | Architectural drawings for warehouse extension - stage 2 (working drawings) | PROFESSIONAL_FEES | PROFESSIONAL_FEES | high | GREEN | 393(1) Table Sl. No. 6(iii)(a) | 8000 / 8000 | correct |
| C22 | Services as per agreement dated 01.04.2026 - Q1 charges | NEEDS_INFO | NEEDS_INFO | low | RED | - | - / - | correct |
| C23 | Sitting fees for board meeting held on 12 August 2026 | DIRECTOR_FEES | DIRECTOR_FEES | high | GREEN | 393(1) Table Sl. No. 6(iii)(c) | 2000 / 2000 | correct |
| C24 | Printing of 10,000 product brochures, A4, 4-colour, as per artwork supplied by us | NEEDS_INFO | CONTRACT_WORK | medium | AMBER | 393(1) Table Sl. No. 6(i).D(b) | 2200 / - | caught |

## Every case, with the system's reasons

### C01: correct (GREEN)

- Invoice: Rao & Co, Chartered Accountants, 2026-06-10: Statutory audit fee FY 2025-26
- Why this case: Plain professional fee. GST shown separately, so excluded from base.
- Got: PROFESSIONAL_FEES, confidence high
- Model rationale: The invoice is for statutory audit fees from a Chartered Accountant firm, which squarely falls under 'profession of accountancy' as defined in Section 402(28) and attracts TDS under Section 393(1) Table Sl. No. 6(iii) for fees for professional services.

### C02: correct (GREEN)

- Invoice: Rao & Co, Chartered Accountants, 2026-07-15: Tax audit and return filing fee FY 2025-26
- Why this case: Same vendor as C01, tax-preparation SAC. A reviewer decided this (PAN, SAC) pair last year, so no LLM call. Aggregate with C01 is past 50,000.
- Got: PROFESSIONAL_FEES, confidence precedent
- Router: Precedent: PROFESSIONAL_FEES decided by Tax reviewer (synthetic) on 2025-11-20

### C03: caught (RED)

- Invoice: Adv. Meera Iyer, 2026-05-05: Monthly retainer - legal advisory, May 2026
- Why this case: Advocate. GST is under reverse charge, so the invoice carries none.
- Got: -, confidence -
- Router: Unparseable LLM answer: No JSON object with a 'category' field in the response

### C04: correct (GREEN)

- Invoice: SecureServ Facility Services Pvt Ltd, 2026-06-01: Supply of security guards and housekeeping staff - May 2026 (12 personnel)
- Why this case: Manpower supply is 'supply of labour' under the definition of work. A model may be drawn to 'provision of services of technical or other personnel' in the technical-services definition; that would be wrong here.
- Got: CONTRACT_WORK, confidence high
- Model rationale: The invoice describes supply of security guards and housekeeping staff, which is a supply of labour for carrying out work under a contract. This falls directly under Section 393(1) Table Sl. No. 6(i) covering payments to contractors for carrying out any work including supply of labour.

### C05: correct (GREEN)

- Invoice: Suresh Kumar, 2026-04-05: Rent for office premises, 3rd floor, Indiranagar - April 2026
- Why this case: Office rent above 50,000 a month.
- Got: RENT_LAND_BUILDING, confidence high
- Model rationale: The invoice explicitly states 'Rent for office premises', which is a building; the statute defines rent for building as falling under the land/building rent category.

### C06: correct (GREEN)

- Invoice: LiftRight Equipment Rentals LLP, 2026-06-30: Monthly hire charges - 3 tonne diesel forklift, June 2026 (equipment only; operator and fuel by customer)
- Why this case: Bare equipment hire, no operator: rent for machinery.
- Got: RENT_PLANT_MACHINERY, confidence high
- Model rationale: The invoice describes monthly hire charges for a forklift (equipment only), which constitutes rent for the use of machinery/plant/equipment under Section 393(1) Table Sl. No. 2 and the definition of rent in Section 402(29).

### C07: caught (RED)

- Invoice: Kumar Cranes, 2026-08-08: Hire of 25 tonne mobile crane with operator and fuel, 8 days, for roof truss installation at Bhiwandi warehouse
- Why this case: Hire with operator and fuel for a specific job is usually treated as a works contract, not rent. The TDS happens to be the same (2%) either way here, but the section and payment code differ.
- Got: -, confidence high
- Model rationale: The invoice describes hire of a mobile crane (machinery/plant/equipment) with operator and fuel for a specific period, which squarely falls under the statutory definition of rent for use of machinery, plant or equipment under Section 402(29) and the corresponding TDS entry in Section 393(1) Table Sl. No. 2(ii)(a).
- Router: Citation check failed: 2025:402(29): quote not found in clause text: 'rent means any payment, by whatever name called, under any lease, sub-lease, tenancy or any other agreement or arrangement for the use of (either separately or together) any— (d) machinery; or (e) plant; or (f) equipment'

### C08: caught (RED)

- Invoice: Nimbus Cloud India Pvt Ltd, 2026-07-01: Cloud hosting charges - June 2026: 4 virtual servers, 2 TB storage, bandwidth (self-service, pay-as-you-go)
- Why this case: Self-service cloud hosting. Practice is split (technical services, rent for equipment, or no TDS as a standard facility) and the statute text alone does not settle it. The only safe answer is escalation.
- Got: -, confidence medium
- Model rationale: The invoice is for cloud hosting charges (virtual servers, storage, bandwidth) on a self-service, pay-as-you-go basis, which constitutes payment for the use of equipment (servers, storage devices) under an arrangement for use. The statute defines rent to include machinery, plant, or equipment, and the TDS table prescribes a 2% rate for such use by a specified person (the payer company).
- Router: Citation check failed: 2025:402(29): quote not found in clause text: 'rent means any payment, by whatever name called, under any lease, sub-lease, tenancy or any other agreement or arrangement for the use of (either separately or together) any—(d) machinery; or (e) plant; or (f) equipment'

### C09: caught (RED)

- Invoice: Byte Care Services Pvt Ltd, 2026-04-20: Annual maintenance contract FY 2026-27 - preventive maintenance and on-call repair of 6 rack servers (parts billed separately)
- Why this case: Repair and maintenance AMC is generally a works contract; technical services at 2% gives the same amount but the wrong section and code.
- Got: -, confidence medium
- Model rationale: The invoice describes preventive maintenance and on-call repair of servers, which constitutes rendering of technical services and provision of technical personnel under Section 9(7)(b). Section 402(47) explicitly excludes sums under Section 393(1) Table Sl. No. 6(iii) (which covers fees for technical services) from the definition of 'work', so this is not CONTRACT_WORK.
- Router: Citation check failed: 2025:9(7)(b): quote not found in clause text: 'fees for technical services means any consideration for the rendering of any managerial technical or consultancy services including the provision of services of technical or other personnel'
- Router: Citation check failed: 2025:402(47): quote not found in clause text: 'but does not include (B) any sum referred to in section 393(1) [Table: Sl. No. 6(iii)]'

### C10: correct (GREEN)

- Invoice: Anil Mehta, 2026-07-10: Commission @ 2% on sales booked in Q1 FY 2026-27 under sales agency agreement
- Why this case: Sales commission to an individual agent.
- Got: COMMISSION, confidence high
- Model rationale: The invoice describes a 2% commission on sales booked under a sales agency agreement, which is a payment for services in the course of selling goods on behalf of the company. This matches the statutory definition of commission or brokerage in section 402(7) and the TDS entry for commission (not insurance) in Table Sl. No. 1(ii) of section 393(1).

### C11: unsafe (GREEN)

- Invoice: Brightline Media Pvt Ltd, 2026-09-25: Design and release of newspaper advertisements - Diwali campaign (media cost and creative)
- Why this case: Advertising appears in both the definition of work and the list of professions, and s.402(47)(B) excludes from 'work' anything that is a professional fee, so a literal reading pushes the whole invoice to 10%. CBDT's long-standing position (Circular 715) is that payments to an advertising agency for releasing ads are contract work (2%). That circular is not in the corpus, so PROFESSIONAL_FEES (five times the correct deduction) is the trap.
- Got: PROFESSIONAL_FEES, confidence high
- Model rationale: The invoice is for design and release of newspaper advertisements, which constitutes advertising services. Advertising is explicitly listed as a profession under Section 402(28), and fees for professional services are covered under Section 393(1) Table Sl. No. 6(iii). The definition of 'work' in Section 402(47) includes advertising but expressly excludes sums falling under Section 393(1) Table Sl. No. 6(iii) (professional services), so this is not contract work.

### C12: correct (GREEN)

- Invoice: Sharma Roadways, 2026-05-18: Freight charges - 3 truckloads Bhiwandi to Pune, LR nos. 4411-4413
- Why this case: Transporter with a declaration (10 or fewer goods carriages) and PAN on file: contract, but no deduction.
- Got: CONTRACT_WORK, confidence high
- Model rationale: The invoice is for freight charges for road transport of goods (truckloads), which is explicitly included in the statutory definition of "work" under Section 402(47)(c) as carriage of goods by a mode other than railways, making it a payment to a contractor under Section 393(1) Table Sl. No. 6(i).

### C13: correct (GREEN)

- Invoice: Compex Systems Pvt Ltd, 2026-06-15: Dell Latitude laptops x 20 (HSN 8471)
- Why this case: Off-the-shelf goods. Aggregate purchases from this seller are below 50 lakh, so nothing to deduct yet.
- Got: GOODS_PURCHASE, confidence high
- Model rationale: The invoice describes Dell Latitude laptops (HSN 8471), which are standard goods purchased off the shelf with no service element. Section 393(1) Table Sl. No. 8(ii) explicitly covers 'purchase of any goods'.

### C14: correct (GREEN)

- Invoice: Lakshmi Caterers, 2026-10-03: Outdoor catering for annual offsite, 120 persons, 2 days
- Why this case: Catering is named in the definition of work. Individual payee, so 1%.
- Got: CONTRACT_WORK, confidence high
- Model rationale: Outdoor catering is explicitly listed as 'work' under Section 402(47)(d), and payments for carrying out work under a contract are covered by Section 393(1) Table Sl. No. 6(i) for payments to contractors.

### C15: correct (GREEN)

- Invoice: QuickFix Electricals, 2026-05-31: Electrical repair and maintenance work at Bhiwandi warehouse - May 2026
- Why this case: Threshold sequence 1 of 4: 28,000 is below the 30,000 single-payment limit and the aggregate is 28,000.
- Got: CONTRACT_WORK, confidence high
- Model rationale: The invoice describes electrical repair and maintenance work performed at a warehouse, which constitutes carrying out work under a contract. This falls squarely under Section 393(1) Table Sl. No. 6(i) for payments to contractors for carrying out any work, and the inclusive definition of 'work' in Section 402(47) supports this classification.

### C16: correct (GREEN)

- Invoice: QuickFix Electricals, 2026-06-30: Electrical repair and maintenance work at Bhiwandi warehouse - June 2026
- Why this case: Threshold sequence 2 of 4: aggregate 56,000.
- Got: CONTRACT_WORK, confidence high
- Model rationale: The invoice describes electrical repair and maintenance work performed at a warehouse, which is a contract for carrying out work (including supply of labour) and falls squarely under the contractor payment provision in Section 393(1) Table Sl. No. 6(i).

### C17: correct (GREEN)

- Invoice: QuickFix Electricals, 2026-07-31: Electrical repair and maintenance work at Bhiwandi warehouse - July 2026
- Why this case: Threshold sequence 3 of 4: aggregate 84,000.
- Got: CONTRACT_WORK, confidence high
- Model rationale: The invoice describes electrical repair and maintenance work, which constitutes carrying out work under a contract as covered by Section 393(1) Table Sl. No. 6(i) for payments to contractors.

### C18: correct (GREEN)

- Invoice: QuickFix Electricals, 2026-08-31: Electrical repair and maintenance work at Bhiwandi warehouse - August 2026
- Why this case: Threshold sequence 4 of 4: aggregate 1,12,000 crosses 1,00,000, so 2% on the whole 1,12,000 including the three earlier untaxed bills.
- Got: CONTRACT_WORK, confidence high
- Model rationale: The invoice describes electrical repair and maintenance work performed at a warehouse, which constitutes carrying out work under a contract and falls squarely under Section 393(1) Table Sl. No. 6(i) for payments to contractors.

### C19: correct (AMBER)

- Invoice: Dr. R. Menon, 2026-08-20: Annual health check-up camp for employees - doctor's consultation fees
- Why this case: Doctor with no PAN on file: professional fees at 20% instead of 10%.
- Got: PROFESSIONAL_FEES, confidence high
- Model rationale: The invoice is for doctor's consultation fees for an employee health check-up camp, which constitutes fees for professional services (medical profession) as defined in section 402(28) and covered under section 393(1) Table Sl. No. 6(iii)(a).
- Router: No valid PAN on file: higher rate applied, confirm PAN status

### C20: correct (GREEN)

- Invoice: Neha Kapoor, Architect, 2026-03-16: Architectural drawings for warehouse extension - stage 1 (concept design)
- Why this case: Transition pair 1 of 2: invoice dated March 2026, so the 1961 Act applies (s.194J(1)(a)) and the model sees only 1961 text.
- Got: PROFESSIONAL_FEES, confidence high
- Model rationale: The invoice is for architectural concept design drawings by an identified architect, which falls squarely under 'professional services' as defined in Section 194J Explanation (a) that explicitly includes the architectural profession.

### C21: correct (GREEN)

- Invoice: Neha Kapoor, Architect, 2026-04-10: Architectural drawings for warehouse extension - stage 2 (working drawings)
- Why this case: Transition pair 2 of 2: same vendor, April 2026, so the 2025 Act (s.393(1) Table Sl. No. 6(iii)(a), code 1027) and a fresh tax-year aggregate.
- Got: PROFESSIONAL_FEES, confidence high
- Model rationale: The invoice is for architectural drawings by an architect, which falls squarely under 'professional services' as defined in section 402(28) covering architectural profession, and TDS applies under section 393(1) Table Sl. No. 6(iii) for fees for professional services.

### C22: correct (RED)

- Invoice: Orbit Solutions Pvt Ltd, 2026-07-05: Services as per agreement dated 01.04.2026 - Q1 charges
- Why this case: No information about what the service is.
- Got: NEEDS_INFO, confidence low
- Model rationale: The invoice description 'Services as per agreement dated 01.04.2026 - Q1 charges' is too generic to determine which statutory category applies; it could fall under contract work, professional fees, technical fees, commission, rent, goods purchase, or director fees depending on the actual services.
- Router: Needs information: Nature of services rendered (e.g., contract work, professional services, technical services, commission, rent, goods purchase); Whether the vendor is a director of the payer company; Whether the agreement involves use of land, building, machinery, plant, equipment, furniture, or fittings; Whether the payment is for purchase of goods exceeding fifty lakh rupees

### C23: correct (GREEN)

- Invoice: Prof. Kavita Rao, 2026-08-12: Sitting fees for board meeting held on 12 August 2026
- Why this case: Sitting fees to a director: 10%, no threshold.
- Got: DIRECTOR_FEES, confidence high
- Model rationale: The invoice describes 'Sitting fees for board meeting' paid to Prof. Kavita Rao, which constitutes fees paid to a director of the company. This falls squarely under the statutory language for director remuneration/fees in Table Sl. No. 6(iii)(c).

### C24: caught (AMBER)

- Invoice: PrintWell Offset, 2026-09-10: Printing of 10,000 product brochures, A4, 4-colour, as per artwork supplied by us
- Why this case: Printing to our design. Under s.402(47)(e) this is work only if the paper is bought from us; if the printer uses its own paper it is a sale. The invoice does not say, so the right answer is to ask.
- Got: CONTRACT_WORK, confidence medium
- Model rationale: The invoice describes printing of product brochures as per customer-supplied artwork, which constitutes "advertising" work under Section 402(47)(a) and therefore falls under payments to contractors for carrying out any work under Section 393(1) Table Sl. No. 6(i).
- Router: Model confidence is medium
