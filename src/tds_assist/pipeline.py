"""One invoice line through the whole system: precedent, LLM, verifier, rules engine, router.

Routing:
  RED    no category the system can stand behind (NEEDS_INFO, unparseable or ungrounded
         answer, LLM down, date outside the corpus). Nothing is computed.
  AMBER  a computed suggestion a reviewer must confirm (confidence below high, open
         questions, or no valid PAN).
  GREEN  a reviewer's precedent, or a high-confidence answer whose citations all check out.
Nothing is posted to the ledger here; posting happens once a human approves the line.
"""

import hashlib
import json
from dataclasses import asdict, dataclass

from tds_assist.categories import Category
from tds_assist.classifier import Classification, ParseError, build_messages, parse, verify
from tds_assist.corpus import load_corpus
from tds_assist.engine import Computation, compute
from tds_assist.ledger import Ledger
from tds_assist.llm import LLM, LLMUnavailable
from tds_assist.models import InvoiceLine
from tds_assist.pan import PayeeKind, payee_kind
from tds_assist.precedent import PrecedentStore
from tds_assist.rules import RULES_VERSION

AUDIT_KEYS = ("line_id", "input", "act", "corpus_ids", "rules_version", "model", "prompt_sha256", "raw_llm",
              "classification", "citation_errors", "computation", "computation_trace", "route", "reasons",
              "precedent")


@dataclass
class Decision:
    line_id: str
    route: str
    reasons: list[str]
    classification: Classification | None
    computation: Computation | None
    audit: dict


def _line_json(line: InvoiceLine) -> dict:
    return json.loads(json.dumps(asdict(line), default=str))


def _comp_json(c: Computation) -> dict:
    d = json.loads(json.dumps(asdict(c), default=str))
    d.pop("trace")
    return d


def process(line: InvoiceLine, llm: LLM, ledger: Ledger, precedents: PrecedentStore) -> Decision:
    audit = dict.fromkeys(AUDIT_KEYS)
    audit.update(line_id=line.id, input=_line_json(line), rules_version=RULES_VERSION, model=llm.model,
                 citation_errors=[], computation_trace=[])
    state = {"classification": None}

    def done(route: str, reasons: list[str], computation: Computation | None = None) -> Decision:
        audit.update(route=route, reasons=reasons)
        if computation:
            audit.update(computation=_comp_json(computation), computation_trace=computation.trace)
        return Decision(line.id, route, reasons, state["classification"], computation, audit)

    try:
        return _process(line, llm, ledger, precedents, audit, state, done)
    except Exception as e:  # last resort: an unforeseen failure must stop the line, not the batch
        return done("RED", [f"Internal error, line not processed: {type(e).__name__}: {e}"])


def _process(line, llm, ledger, precedents, audit, state, done) -> Decision:
    try:
        chunks = load_corpus(line.date)
    except ValueError as e:
        return done("RED", [str(e)])
    audit.update(act=chunks[0].act, corpus_ids=[c.id for c in chunks])

    reasons: list[str] = []
    precedent = precedents.lookup(line.vendor.pan, line.sac)
    if precedent:
        audit["precedent"] = {**asdict(precedent), "category": precedent.category.value}
        category = precedent.category
        reasons.append(f"Precedent: {category.value} decided by {precedent.decided_by} on {precedent.decided_on}")
    else:
        messages = build_messages(line, chunks)
        key = getattr(llm, "cache_key", None)
        audit["prompt_sha256"] = key(messages) if key else hashlib.sha256(
            json.dumps(messages, ensure_ascii=False).encode()).hexdigest()
        try:
            raw = llm.complete(messages)
        except LLMUnavailable as e:
            return done("RED", [f"LLM unavailable: {e}"])
        audit["raw_llm"] = raw
        try:
            classification = state["classification"] = parse(raw)
        except ParseError as e:
            return done("RED", [f"Unparseable LLM answer: {e}"])
        audit["classification"] = {**asdict(classification), "category": classification.category.value}
        errors = verify(classification, chunks)
        audit["citation_errors"] = errors
        if errors:
            return done("RED", [f"Citation check failed: {e}" for e in errors])
        if classification.category is Category.NEEDS_INFO:
            return done("RED", ["Needs information: " + "; ".join(classification.missing_facts)])
        category = classification.category
        if classification.confidence != "high":
            reasons.append(f"Model confidence is {classification.confidence}")
        if classification.missing_facts:
            reasons.append("Open questions: " + "; ".join(classification.missing_facts))

    try:
        computation = compute(line, category, ledger)
    except ValueError as e:
        return done("RED", [f"Cannot compute TDS for {category.value} on {line.date.isoformat()}: {e}"])
    if payee_kind(line.vendor.pan) is PayeeKind.NO_PAN:
        reasons.append("No valid PAN on file: higher rate applied, confirm PAN status")

    flagged = [r for r in reasons if not r.startswith("Precedent:")]
    return done("AMBER" if flagged else "GREEN", reasons, computation)
