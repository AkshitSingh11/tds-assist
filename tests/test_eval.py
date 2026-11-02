import json
from decimal import Decimal
from pathlib import Path

from tds_assist.categories import Category
from tds_assist.cli import load_cases, run_eval, score, write_results
from tds_assist.pan import PayeeKind, payee_kind
from tds_assist.pipeline import Decision
from tds_assist.precedent import PrecedentStore

ROOT = Path(__file__).resolve().parents[1]

CONTRACT = json.dumps({
    "category": "CONTRACT_WORK",
    "citations": [{"chunk_id": "2025:393(1)T6(i)", "quote": "Any sum for carrying out any work"}],
    "missing_facts": [], "confidence": "high", "rationale": "repair work",
})


class FakeLLM:
    model = "fake/model"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, messages):
        return self.reply


def decision(route, category=None, tds=None):
    from types import SimpleNamespace
    cls = SimpleNamespace(category=Category(category)) if category else None
    comp = SimpleNamespace(tds=Decimal(tds)) if tds is not None else None
    return Decision("X", route, [], cls, comp, {"precedent": None})


def test_score_outcomes():
    exp = {"acceptable": ["CONTRACT_WORK", "NEEDS_INFO"], "tds": "1920"}
    assert score(decision("GREEN", "CONTRACT_WORK", "1920"), exp) == "correct"
    assert score(decision("RED", "NEEDS_INFO"), exp) == "correct"
    assert score(decision("GREEN", "CONTRACT_WORK", "960"), exp) == "unsafe"  # right category, wrong amount
    assert score(decision("GREEN", "PROFESSIONAL_FEES", "9600"), exp) == "unsafe"
    assert score(decision("AMBER", "PROFESSIONAL_FEES", "9600"), exp) == "caught"
    assert score(decision("RED"), exp) == "caught"  # LLM down / unparseable: no answer, but stopped


def test_cases_file_is_synthetic_and_well_formed():
    cases = load_cases(ROOT / "data" / "cases.json")
    assert len(cases) >= 10
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["synthetic"] is True
        assert all(Category(a) for a in c["expected"]["acceptable"])
        if c["line"].vendor.pan is not None:
            assert payee_kind(c["line"].vendor.pan) is not PayeeKind.NO_PAN, c["id"]
        if "tds" in c["expected"]:
            assert "post_as" in c["expected"], c["id"]


def test_eval_posts_reviewer_category_so_aggregate_catch_up_happens(tmp_path):
    cases = [c for c in load_cases(ROOT / "data" / "cases.json") if c["id"] in ("C15", "C16", "C17", "C18")]
    rows = run_eval(cases, FakeLLM(CONTRACT), PrecedentStore(tmp_path / "none.json"))
    assert [r["tds"] for r in rows] == ["0", "0", "0", "2240"]
    assert all(r["outcome"] == "correct" for r in rows)


def test_write_results_produces_markdown_and_jsonl(tmp_path):
    cases = [c for c in load_cases(ROOT / "data" / "cases.json") if c["id"] in ("C15", "C22")]
    rows = run_eval(cases, FakeLLM(CONTRACT), PrecedentStore(tmp_path / "none.json"))
    summary = write_results(rows, tmp_path, model="fake/model")
    assert summary == {"correct": 1, "caught": 0, "unsafe": 1}  # C22 should have been NEEDS_INFO
    md = (tmp_path / "results.md").read_text()
    assert "C22" in md and "unsafe" in md
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["line_id"] == "C15"


def test_score_ignores_answer_rejected_by_verifier():
    d = decision("RED", "NEEDS_INFO")
    d.audit["citation_errors"] = ["NEEDS_INFO without any missing facts named"]
    assert score(d, {"acceptable": ["NEEDS_INFO"]}) == "caught"


def test_engine_reproduces_every_hand_computed_amount():
    """The expected amounts in cases.json were worked out by hand from the Acts. Given the
    reviewer's category, in case order on one ledger, the engine must arrive at each of them."""
    from tds_assist.engine import compute
    from tds_assist.ledger import Ledger
    ledger, mismatches = Ledger(), []
    for c in load_cases(ROOT / "data" / "cases.json"):
        exp = c["expected"]
        if "post_as" not in exp:
            continue
        comp = compute(c["line"], Category(exp["post_as"]), ledger)
        ledger.post(comp)
        if comp.tds != Decimal(exp["tds"]):
            mismatches.append((c["id"], exp["tds"], str(comp.tds)))
    assert mismatches == []


def test_cli_only_runs_selected_cases_and_warns_without_key(tmp_path, monkeypatch, capsys):
    from tds_assist.cli import main
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    main(["eval", "--only", "C02, c01", "--out", str(tmp_path), "--cache", str(tmp_path / "cache")])
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert [json.loads(l)["line_id"] for l in lines] == ["C01", "C02"]  # case order, not argument order
    assert "OPENROUTER_API_KEY is not set" in capsys.readouterr().err


def test_cli_only_rejects_unknown_case_ids(tmp_path):
    import pytest
    from tds_assist.cli import main
    with pytest.raises(SystemExit):
        main(["eval", "--only", "C99", "--out", str(tmp_path), "--cache", str(tmp_path / "cache")])


def test_subset_still_books_skipped_cases_so_aggregates_hold(tmp_path):
    cases = load_cases(ROOT / "data" / "cases.json")
    llm = FakeLLM(CONTRACT)
    llm.calls = 0
    orig = llm.complete
    llm.complete = lambda m: (setattr(llm, "calls", llm.calls + 1), orig(m))[1]
    rows = run_eval(cases, llm, PrecedentStore(tmp_path / "none.json"), only={"C18"})
    assert [r["id"] for r in rows] == ["C18"]
    assert rows[0]["tds"] == "2240" and llm.calls == 1


def test_report_rebuilds_identical_results_from_audit(tmp_path):
    from tds_assist.cli import report
    cases = [c for c in load_cases(ROOT / "data" / "cases.json") if c["id"] in ("C01", "C02", "C15", "C22")]
    rows = run_eval(cases, FakeLLM(CONTRACT), PrecedentStore(ROOT / "data" / "precedents.json"))
    write_results(rows, tmp_path / "run", model="fake/model")
    summary = report(tmp_path / "run" / "audit.jsonl", ROOT / "data" / "cases.json", tmp_path / "again")
    assert summary == {"correct": 2, "caught": 0, "unsafe": 2}
    assert (tmp_path / "again" / "results.md").read_text() == (tmp_path / "run" / "results.md").read_text()


def test_report_rejects_audit_line_without_a_case(tmp_path):
    import pytest
    from tds_assist.cli import report
    (tmp_path / "audit.jsonl").write_text(json.dumps({"line_id": "C99"}) + "\n")
    with pytest.raises(ValueError, match="C99"):
        report(tmp_path / "audit.jsonl", ROOT / "data" / "cases.json", tmp_path)


def test_cli_report_command(tmp_path):
    from tds_assist.cli import main
    rows = run_eval([c for c in load_cases(ROOT / "data" / "cases.json") if c["id"] == "C15"],
                    FakeLLM(CONTRACT), PrecedentStore(tmp_path / "none.json"))
    write_results(rows, tmp_path, model="fake/model")
    (tmp_path / "results.md").unlink()
    assert main(["report", "--audit", str(tmp_path / "audit.jsonl"), "--out", str(tmp_path)]) == 0
    assert "C15" in (tmp_path / "results.md").read_text()
