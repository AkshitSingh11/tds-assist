import io
import json
import urllib.error
from datetime import date
from decimal import Decimal

import pytest

from tds_assist.categories import Category
from tds_assist.classifier import Citation, Classification, ParseError, build_messages, parse, verify
from tds_assist.corpus import load_corpus
from tds_assist.llm import LLMUnavailable, OpenRouterLLM
from tds_assist.models import InvoiceLine, Vendor

AFTER = load_corpus(date(2026, 6, 1))
BEFORE = load_corpus(date(2026, 3, 1))

LINE = InvoiceLine(
    id="L1", vendor=Vendor("Rao & Co, Chartered Accountants", "AAAFR1234M"), date=date(2026, 6, 1),
    description="Statutory audit fee FY 2025-26", sac="998221",
    taxable_value=Decimal("120000"), gst=Decimal("21600"), gst_separate=True,
)

GOOD = {
    "category": "PROFESSIONAL_FEES",
    "citations": [{"chunk_id": "2025:402(28)", "quote": "the profession of accountancy"}],
    "missing_facts": [],
    "confidence": "high",
    "rationale": "Audit is accountancy.",
}


def cls(category, citations, missing=(), confidence="high"):
    return Classification(Category(category), [Citation(c, q) for c, q in citations], list(missing), confidence, "")


def test_corpus_chunks_declare_supported_categories():
    by_id = {c.id: c for c in AFTER}
    assert "PROFESSIONAL_FEES" in by_id["2025:402(28)"].supports
    assert by_id["2025:393(1)"].supports == ()


def test_parse_valid_json():
    c = parse(json.dumps(GOOD))
    assert c.category is Category.PROFESSIONAL_FEES
    assert c.citations == [Citation("2025:402(28)", "the profession of accountancy")]
    assert c.confidence == "high"


def test_parse_handles_prose_wrapped_json():
    raw = "Sure, here is my answer:\n```json\n" + json.dumps(GOOD) + "\n```\nHope that helps."
    assert parse(raw).category is Category.PROFESSIONAL_FEES


def test_parse_garbage_raises():
    with pytest.raises(ParseError):
        parse("I think this is professional fees.")


def test_unknown_category_raises():
    with pytest.raises(ParseError):
        parse(json.dumps({**GOOD, "category": "SECTION_194J"}))


def test_bad_confidence_raises():
    with pytest.raises(ParseError):
        parse(json.dumps({**GOOD, "confidence": "certain"}))


def test_verify_accepts_exact_quote():
    assert verify(cls("PROFESSIONAL_FEES", [("2025:402(28)", "the profession of accountancy")]), AFTER) == []


def test_verify_tolerates_whitespace_case_and_quote_style():
    c = cls("CONTRACT_WORK", [("2025:402(47)", "“WORK”  shall include—(a) advertising")])
    assert verify(c, AFTER) == []


def test_verify_rejects_fabricated_quote():
    errs = verify(cls("PROFESSIONAL_FEES", [("2025:402(28)", "services of a software engineer")]), AFTER)
    assert errs and "not found" in errs[0]


def test_verify_rejects_too_short_quote():
    errs = verify(cls("PROFESSIONAL_FEES", [("2025:402(28)", "accountancy")]), AFTER)
    assert errs


def test_citation_from_wrong_act_rejected():
    errs = verify(cls("PROFESSIONAL_FEES", [("2025:402(28)", "the profession of accountancy")]), BEFORE)
    assert errs and "not in force" in errs[0]


def test_verify_requires_a_supporting_clause():
    c = cls("PROFESSIONAL_FEES", [("2025:402(29)", "any lease, sub-lease, tenancy")])
    errs = verify(c, AFTER)
    assert any("supports" in e for e in errs)


def test_verify_requires_citation_unless_needs_info():
    assert verify(cls("PROFESSIONAL_FEES", []), AFTER)
    assert verify(cls("NEEDS_INFO", [], missing=["contract terms"]), AFTER) == []


def test_needs_info_must_name_missing_facts():
    assert verify(cls("NEEDS_INFO", []), AFTER)


def test_messages_contain_only_in_force_clauses_and_no_amounts():
    msgs = build_messages(LINE, AFTER)
    text = json.dumps(msgs)
    assert "2025:402(28)" in text and "1961:" not in text
    assert "120000" not in text  # the model is not told the amount; thresholds are code's job


def _fake_opener(responses, calls):
    def opener(req, timeout=None):
        calls.append(req)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": r}}]}).encode())
    return opener


def test_cache_hit_skips_network(tmp_path):
    calls = []
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_fake_opener(["one"], calls), sleep=lambda s: None)
    msgs = [{"role": "user", "content": "hi"}]
    assert llm.complete(msgs) == "one"
    assert llm.complete(msgs) == "one"
    assert len(calls) == 1


def test_retries_on_429_then_succeeds(tmp_path):
    calls = []
    err = urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b""))
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_fake_opener([err, "ok"], calls), sleep=lambda s: None)
    assert llm.complete([{"role": "user", "content": "x"}]) == "ok"
    assert len(calls) == 2


def test_gives_up_after_three_attempts(tmp_path):
    calls = []
    errs = [urllib.error.HTTPError("u", 503, "down", {}, io.BytesIO(b"")) for _ in range(3)]
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_fake_opener(errs, calls), sleep=lambda s: None)
    with pytest.raises(LLMUnavailable):
        llm.complete([{"role": "user", "content": "x"}])
    assert len(calls) == 3


def test_offline_mode_without_key_uses_cache_only(tmp_path):
    calls = []
    llm = OpenRouterLLM("m", None, tmp_path, opener=_fake_opener([], calls), sleep=lambda s: None)
    with pytest.raises(LLMUnavailable):
        llm.complete([{"role": "user", "content": "x"}])
    assert calls == []


# --- final-review fixes -------------------------------------------------------

def test_goods_not_supported_by_quote_from_work_inclusions():
    c = cls("GOODS_PURCHASE", [("2025:402(47)", "advertising; (b) broadcasting and telecasting")])
    assert any("supports" in e for e in verify(c, AFTER))


def test_professional_not_supported_by_technical_rate_text():
    c = cls("PROFESSIONAL_FEES", [("2025:393(1)T6(iii)", "fees for technical services (not being a professional services)")])
    assert any("supports" in e for e in verify(c, AFTER))


def test_rent_land_not_supported_by_machinery_text():
    c = cls("RENT_LAND_BUILDING", [("2025:393(1)T2", "for the use of any machinery or plant or equipment")])
    assert any("supports" in e for e in verify(c, AFTER))


def test_insurance_commission_text_does_not_support_commission():
    c = cls("COMMISSION", [("2025:393(1)T1", "soliciting or procuring insurance business")])
    assert any("supports" in e for e in verify(c, AFTER))


def test_quote_spanning_two_categories_supports_neither():
    q = "(c) land appurtenant to a building (including factory building); or (d) machinery"
    assert verify(cls("RENT_LAND_BUILDING", [("2025:402(29)", q)]), AFTER)
    assert verify(cls("RENT_PLANT_MACHINERY", [("2025:402(29)", q)]), AFTER)


def test_right_category_from_shared_clause_still_supported():
    assert verify(cls("RENT_PLANT_MACHINERY", [("2025:393(1)T2", "for the use of any machinery or plant or equipment")]), AFTER) == []
    assert verify(cls("TECHNICAL_FEES", [("2025:393(1)T6(iii)", "fees for technical services (not being a professional services)")]), AFTER) == []
    assert verify(cls("CONTRACT_WORK", [("2025:402(47)", "advertising; (b) broadcasting and telecasting")]), AFTER) == []
    assert verify(cls("GOODS_PURCHASE", [("2025:402(47)", "by using material purchased from a person, other than such customer")]), AFTER) == []
    assert verify(cls("RENT_LAND_BUILDING", [("1961:194I-Expl(i)", "(b) building (including factory building)")]), BEFORE) == []
    assert verify(cls("PROFESSIONAL_FEES", [("1961:194J-Expl", "the profession of accountancy")]), BEFORE) == []
    assert verify(cls("TECHNICAL_FEES", [("1961:194J-Expl", "\"fees for technical services\" shall have the same meaning")]), BEFORE) == []


def test_corpus_support_spans_are_verbatim_and_unique():
    from tds_assist.classifier import _norm
    for ch in AFTER + BEFORE:
        for cat, span in ch.spans:
            assert Category(cat)
            if span != "*":
                assert _norm(ch.text).count(_norm(span)) == 1, (ch.id, span)


def test_parse_rejects_non_list_missing_facts():
    with pytest.raises(ParseError):
        parse(json.dumps({**GOOD, "missing_facts": 5}))
    with pytest.raises(ParseError):
        parse(json.dumps({**GOOD, "citations": "the profession of accountancy"}))


def test_parse_treats_string_missing_facts_as_one_fact():
    assert parse(json.dumps({**GOOD, "missing_facts": "whose paper"})).missing_facts == ["whose paper"]


def _raw_opener(bodies, calls):
    def opener(req, timeout=None):
        calls.append(req)
        b = bodies.pop(0)
        if isinstance(b, Exception):
            raise b
        return io.BytesIO(b)
    return opener


def test_non_json_body_and_connection_reset_become_llm_unavailable(tmp_path):
    calls = []
    bodies = [b"<html>bad gateway</html>", ConnectionResetError("reset"), b"[1]"]
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_raw_opener(bodies, calls), sleep=lambda s: None)
    with pytest.raises(LLMUnavailable):
        llm.complete([{"role": "user", "content": "x"}])
    assert len(calls) == 3


def test_non_string_content_is_unavailable(tmp_path):
    body = json.dumps({"choices": [{"message": {"content": [{"type": "text", "text": "hi"}]}}]}).encode()
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_raw_opener([body] * 3, []), sleep=lambda s: None)
    with pytest.raises(LLMUnavailable):
        llm.complete([{"role": "user", "content": "x"}])


def test_empty_answer_is_not_cached(tmp_path):
    calls = []
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_fake_opener(["", "ok"], calls), sleep=lambda s: None)
    msgs = [{"role": "user", "content": "x"}]
    assert llm.complete(msgs) == ""
    assert llm.complete(msgs) == "ok"
    assert len(calls) == 2


def test_quotes_differing_only_in_quote_marks_and_dashes_verify():
    """Both quotes are verbatim from a live Nemotron answer for C01: same words, but the model
    dropped the quotation marks around the defined term and the '––' after 'by way of'."""
    c = Classification(Category.PROFESSIONAL_FEES, [
        Citation("2025:402(28)", "professional services means services rendered by a person in the course of carrying "
                 "on legal, medical, engineering or architectural profession or the profession of accountancy or "
                 "technical consultancy or interior decoration or advertising"),
        Citation("2025:393(1)T6(iii)", "Any sum by way of fees for (a) professional services; or (b) fees for "
                 "technical services; or (c) remuneration or fees or commission by whatever name called"),
    ], [], "high", "")
    assert verify(c, AFTER) == []


def test_punctuation_tolerance_does_not_admit_changed_words():
    c = Classification(Category.PROFESSIONAL_FEES, [
        Citation("2025:402(28)", "professional services means services rendered by a person in the course of software development"),
    ], [], "high", "")
    assert verify(c, AFTER)


def test_upstream_error_inside_200_is_retried(tmp_path):
    calls = []
    overloaded = json.dumps({"error": {"message": "Upstream error: Service temporarily overloaded", "code": 503}}).encode()
    ok = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_raw_opener([overloaded, ok], calls), sleep=lambda s: None)
    assert llm.complete([{"role": "user", "content": "x"}]) == "ok"
    assert len(calls) == 2


def test_client_error_inside_200_is_not_retried(tmp_path):
    calls = []
    bad = json.dumps({"error": {"message": "invalid model", "code": 400}}).encode()
    llm = OpenRouterLLM("m", "k", tmp_path, opener=_raw_opener([bad, bad], calls), sleep=lambda s: None)
    with pytest.raises(LLMUnavailable):
        llm.complete([{"role": "user", "content": "x"}])
    assert len(calls) == 1
