import json
from datetime import date
from decimal import Decimal

from tds_assist.categories import Category
from tds_assist.ledger import Ledger
from tds_assist.llm import LLMUnavailable
from tds_assist.models import InvoiceLine, Vendor
from tds_assist.pipeline import AUDIT_KEYS, process
from tds_assist.precedent import Precedent, PrecedentStore

CA = Vendor("Rao & Co, Chartered Accountants", "AAAFR1234M")


def line(vendor=CA, description="Statutory audit fee FY 2025-26", sac="998221", amount="120000", on=date(2026, 6, 10)):
    return InvoiceLine("L1", vendor, on, description, sac, Decimal(amount), Decimal("0"), True)


def answer(category="PROFESSIONAL_FEES", citations=(("2025:402(28)", "the profession of accountancy"),),
           missing=(), confidence="high"):
    return json.dumps({
        "category": category,
        "citations": [{"chunk_id": c, "quote": q} for c, q in citations],
        "missing_facts": list(missing),
        "confidence": confidence,
        "rationale": "test",
    })


class FakeLLM:
    model = "fake/model"

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def store(tmp_path, *precedents):
    s = PrecedentStore(tmp_path / "precedents.json")
    for p in precedents:
        s.add(p)
    return s


def test_precedent_hit_skips_llm(tmp_path):
    s = store(tmp_path, Precedent("AAAFR1234M", "998221", Category.PROFESSIONAL_FEES, "A. Reviewer", "2026-05-01", "audit"))
    llm = FakeLLM(answer())
    d = process(line(), llm, Ledger(), s)
    assert llm.calls == 0
    assert d.route == "GREEN"
    assert d.computation.tds == Decimal("12000")
    assert d.audit["precedent"]["decided_by"] == "A. Reviewer"


def test_precedent_store_persists_and_normalises_pan(tmp_path):
    store(tmp_path, Precedent("AAAFR1234M", "998221", Category.PROFESSIONAL_FEES, "A. Reviewer", "2026-05-01", ""))
    reloaded = PrecedentStore(tmp_path / "precedents.json")
    assert reloaded.lookup(" aaafr1234m ", "998221").category is Category.PROFESSIONAL_FEES
    assert reloaded.lookup("AAAFR1234M", "998222") is None
    assert reloaded.lookup(None, "998221") is None
    assert reloaded.lookup("AAAFR1234M", None) is None


def test_needs_info_routes_red_no_computation(tmp_path):
    llm = FakeLLM(answer("NEEDS_INFO", citations=(), missing=["whose material is used"], confidence="low"))
    d = process(line(description="Services as per agreement"), llm, Ledger(), store(tmp_path))
    assert d.route == "RED"
    assert d.computation is None
    assert any("whose material is used" in r for r in d.reasons)


def test_parse_garbage_routes_red(tmp_path):
    d = process(line(), FakeLLM("This is professional fees, 10%."), Ledger(), store(tmp_path))
    assert d.route == "RED"
    assert d.computation is None
    assert d.audit["raw_llm"] == "This is professional fees, 10%."


def test_llm_unavailable_routes_red(tmp_path):
    d = process(line(), FakeLLM(LLMUnavailable("429")), Ledger(), store(tmp_path))
    assert d.route == "RED"
    assert d.computation is None


def test_fabricated_citation_routes_red(tmp_path):
    llm = FakeLLM(answer(citations=(("2025:402(28)", "services of a software engineer"),)))
    d = process(line(), llm, Ledger(), store(tmp_path))
    assert d.route == "RED"
    assert d.audit["citation_errors"]


def test_high_confidence_grounded_routes_green(tmp_path):
    d = process(line(), FakeLLM(answer()), Ledger(), store(tmp_path))
    assert d.route == "GREEN"
    assert d.classification.category is Category.PROFESSIONAL_FEES
    assert d.computation.tds == Decimal("12000")
    assert d.computation.payment_code == "1027"


def test_medium_confidence_routes_amber_with_computation(tmp_path):
    d = process(line(), FakeLLM(answer(confidence="medium")), Ledger(), store(tmp_path))
    assert d.route == "AMBER"
    assert d.computation.tds == Decimal("12000")


def test_missing_facts_route_amber(tmp_path):
    d = process(line(), FakeLLM(answer(missing=["is the firm a partnership"])), Ledger(), store(tmp_path))
    assert d.route == "AMBER"


def test_no_pan_routes_amber_at_twenty_percent(tmp_path):
    v = Vendor("Dr. R. Menon", None)
    d = process(line(vendor=v, amount="60000"), FakeLLM(answer()), Ledger(), store(tmp_path))
    assert d.route == "AMBER"
    assert d.computation.tds == Decimal("12000")


def test_process_does_not_post_to_ledger(tmp_path):
    ledger = Ledger()
    process(line(), FakeLLM(answer()), ledger, store(tmp_path))
    assert ledger.prior("AAAFR1234M", "PROFESSIONAL_FEES", "2026-27") == (Decimal("0"), Decimal("0"))


def test_date_outside_any_act_routes_red(tmp_path):
    d = process(line(on=date(2024, 6, 1)), FakeLLM(answer()), Ledger(), store(tmp_path))
    assert d.route == "RED"
    assert d.computation is None


def test_audit_has_required_keys(tmp_path):
    d = process(line(), FakeLLM(answer()), Ledger(), store(tmp_path))
    assert set(AUDIT_KEYS) <= set(d.audit)
    assert d.audit["model"] == "fake/model"
    assert d.audit["act"] == "ITA2025"
    assert "2025:402(28)" in d.audit["corpus_ids"]
    assert len(d.audit["prompt_sha256"]) == 64
    assert d.audit["computation_trace"]
    json.dumps(d.audit)  # must be serialisable for the JSONL log


def test_unexpected_llm_exception_routes_red(tmp_path):
    d = process(line(), FakeLLM(RuntimeError("boom")), Ledger(), store(tmp_path))
    assert d.route == "RED" and d.computation is None


def test_wrong_typed_missing_facts_routes_red(tmp_path):
    raw = json.dumps({"category": "NEEDS_INFO", "missing_facts": 5, "confidence": "low"})
    d = process(line(), FakeLLM(raw), Ledger(), store(tmp_path))
    assert d.route == "RED"


def test_invalid_rent_months_routes_red(tmp_path):
    bad = InvoiceLine("L1", CA, date(2026, 6, 10), "Office rent", "997212", Decimal("100000"), Decimal("0"), True,
                      rent_months=0)
    rent = answer("RENT_LAND_BUILDING", citations=(("2025:402(29)", "(b) building (including factory building)"),))
    d = process(bad, FakeLLM(rent), Ledger(), store(tmp_path))
    assert d.route == "RED" and d.computation is None


def test_audit_prompt_hash_is_the_cache_key(tmp_path):
    from tds_assist.llm import OpenRouterLLM
    from tds_assist.classifier import build_messages
    from tds_assist.corpus import load_corpus
    llm = OpenRouterLLM("fake/model", None, tmp_path)
    d = process(line(), llm, Ledger(), store(tmp_path))
    assert d.audit["prompt_sha256"] == llm.cache_key(build_messages(line(), load_corpus(line().date)))
