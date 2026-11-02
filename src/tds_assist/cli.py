"""Evaluation harness: run the synthetic cases through the pipeline and score them.

Outcomes per case:
  correct  category is acceptable and, where an amount is expected, the TDS matches
  caught   wrong (or no answer), but routed AMBER/RED so a reviewer sees it before payment
  unsafe   wrong and routed GREEN: the failure that matters
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from tds_assist.categories import Category
from tds_assist.corpus import corpus_version
from tds_assist.engine import compute
from tds_assist.ledger import Ledger
from tds_assist.llm import LLM, OpenRouterLLM
from tds_assist.models import InvoiceLine, Vendor
from tds_assist.pipeline import Decision, process
from tds_assist.precedent import PrecedentStore
from tds_assist.rules import RULES_VERSION

DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"


def load_cases(path: Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = []
    for c in raw["cases"]:
        l = c["line"]
        v = l["vendor"]
        line = InvoiceLine(
            id=c["id"],
            vendor=Vendor(v["name"], v["pan"], v.get("transporter_declaration", False)),
            date=date.fromisoformat(l["date"]),
            description=l["description"],
            sac=l["sac"],
            taxable_value=Decimal(l["taxable_value"]),
            gst=Decimal(l["gst"]),
            gst_separate=l["gst_separate"],
            material_value=Decimal(l["material_value"]) if l.get("material_value") else None,
            rent_months=l.get("rent_months", 1),
        )
        cases.append({**c, "line": line})
    return cases


def category_of(d: Decision) -> Category | None:
    if d.audit.get("citation_errors"):
        return None
    if d.classification:
        return d.classification.category
    if d.audit.get("precedent"):
        return Category(d.audit["precedent"]["category"])
    return None


def _audit_category(a: dict) -> Category | None:
    if a.get("citation_errors"):
        return None  # the verifier threw the answer out; it was never the system's suggestion
    if a.get("classification"):
        return Category(a["classification"]["category"])
    if a.get("precedent"):
        return Category(a["precedent"]["category"])
    return None


def _outcome(cat: Category | None, tds, route: str, expected: dict) -> str:
    right = cat is not None and cat.value in expected["acceptable"]
    if right and cat is not Category.NEEDS_INFO and "tds" in expected:
        right = tds is not None and Decimal(tds) == Decimal(expected["tds"])
    if right:
        return "correct"
    return "unsafe" if route == "GREEN" else "caught"


def score(d: Decision, expected: dict) -> str:
    return _outcome(category_of(d), d.computation.tds if d.computation else None, d.route, expected)


def _row(case: dict, audit: dict) -> dict:
    """One results row, built only from the case and its audit record, so `report` can rebuild
    exactly what `eval` wrote."""
    line, exp = case["line"], case["expected"]
    cat = _audit_category(audit)
    cls, comp = audit.get("classification"), audit.get("computation")
    return {
        "id": case["id"], "note": case.get("note", ""), "vendor": line.vendor.name, "date": line.date.isoformat(),
        "description": line.description, "acceptable": exp["acceptable"], "expected_tds": exp.get("tds"),
        "category": cat.value if cat else None,
        "confidence": cls["confidence"] if cls else ("precedent" if audit.get("precedent") else None),
        "route": audit["route"], "reasons": audit["reasons"],
        "section": comp["section_ref"] if comp else None,
        "payment_code": comp["payment_code"] if comp else None,
        "tds": comp["tds"] if comp else None,
        "rationale": cls["rationale"] if cls else "",
        "outcome": _outcome(cat, comp["tds"] if comp else None, audit["route"], exp), "audit": audit,
    }


def run_eval(cases: list[dict], llm: LLM, precedents: PrecedentStore, only: set[str] | None = None) -> list[dict]:
    """Runs every case in `cases`, or only those in `only`. Skipped cases are still booked by the
    simulated reviewer, so a subset sees the same annual aggregates as the full run."""
    ledger = Ledger()
    rows = []
    for c in cases:
        line, exp = c["line"], c["expected"]
        if only is not None and c["id"] not in only:
            if exp.get("post_as"):
                ledger.post(compute(line, Category(exp["post_as"]), ledger))
            continue
        d = process(line, llm, ledger, precedents)
        # Simulated reviewer: books the line under the correct category, whatever the system said,
        # so later lines see the same annual aggregates they would in real books.
        if exp.get("post_as"):
            ledger.post(compute(line, Category(exp["post_as"]), ledger))
        rows.append(_row(c, d.audit))
    return rows


def report(audit_path: Path, cases_path: Path, out_dir: Path) -> dict:
    """Rebuilds results.md (and a normalised audit.jsonl) from an earlier run's audit log."""
    by_id = {c["id"]: c for c in load_cases(cases_path)}
    audits = [json.loads(l) for l in Path(audit_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    missing = [a.get("line_id") for a in audits if a.get("line_id") not in by_id]
    if missing:
        raise ValueError(f"audit lines with no matching case in {cases_path}: {', '.join(map(str, missing))}")
    rows = [_row(by_id[a["line_id"]], a) for a in audits]
    models = sorted({a["model"] for a in audits if a.get("model")})
    return write_results(rows, out_dir, ", ".join(models) or "-")


def _cell(s) -> str:
    return str(s if s is not None else "-").replace("|", "\\|").replace("\n", " ")


def write_results(rows: list[dict], out_dir: Path, model: str) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter(r["outcome"] for r in rows)
    summary = {k: counts.get(k, 0) for k in ("correct", "caught", "unsafe")}
    routes = Counter(r["route"] for r in rows)

    with (out_dir / "audit.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r["audit"], ensure_ascii=False) + "\n")

    corpora = sorted({corpus_version(date.fromisoformat(r["date"])) for r in rows if r["audit"].get("act")})
    md = [
        "# Evaluation results", "",
        f"Model: `{model}`  ",
        f"Rules version: `{RULES_VERSION}`  ",
        f"Corpus: {', '.join(corpora) or '-'}  ",
        f"Cases: {len(rows)} (all synthetic, see `data/cases.json`)", "",
        "| Outcome | Count |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in summary.items()], "",
        "Routes: " + ", ".join(f"{k} {routes.get(k, 0)}" for k in ("GREEN", "AMBER", "RED")), "",
        "| Case | Description | Acceptable | Got | Confidence | Route | Section | TDS (got / expected) | Outcome |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append("| " + " | ".join(_cell(x) for x in (
            r["id"], r["description"], ", ".join(r["acceptable"]), r["category"], r["confidence"], r["route"],
            r["section"], f"{_cell(r['tds'])} / {_cell(r['expected_tds'])}", r["outcome"])) + " |")
    md += ["", "## Every case, with the system's reasons", ""]
    for r in rows:
        md += [f"### {r['id']}: {r['outcome']} ({r['route']})", "",
               f"- Invoice: {r['vendor']}, {r['date']}: {r['description']}",
               f"- Why this case: {r['note']}",
               f"- Got: {_cell(r['category'])}, confidence {_cell(r['confidence'])}"]
        if r["rationale"]:
            md.append(f"- Model rationale: {r['rationale']}")
        md += [f"- Router: {reason}" for reason in r["reasons"]]
        md.append("")
    (out_dir / "results.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tds_assist")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval", help="run the synthetic cases and write eval/results.md")
    e.add_argument("--model", default=DEFAULT_MODEL)
    e.add_argument("--cases", type=Path, default=Path("data/cases.json"))
    e.add_argument("--precedents", type=Path, default=Path("data/precedents.json"))
    e.add_argument("--out", type=Path, default=Path("eval"))
    e.add_argument("--cache", type=Path, default=Path("eval/cache"))
    e.add_argument("--only", help="comma-separated case ids to run, e.g. C01,C11 (default: all)")
    r = sub.add_parser("report", help="rebuild results.md from an earlier run's audit.jsonl (no model calls)")
    r.add_argument("--audit", type=Path, default=Path("eval/audit.jsonl"))
    r.add_argument("--cases", type=Path, default=Path("data/cases.json"))
    r.add_argument("--out", type=Path, default=Path("eval"))
    args = p.parse_args(argv)

    if args.cmd == "report":
        if not args.audit.exists():
            p.error(f"no audit log at {args.audit}; run `eval` first")
        try:
            summary = report(args.audit, args.cases, args.out)
        except ValueError as err:
            p.error(str(err))
        print(f"{summary}  ->  {args.out / 'results.md'}")
        return 0

    cases = load_cases(args.cases)
    wanted = None
    if args.only:
        wanted = {i.strip().upper() for i in args.only.split(",") if i.strip()}
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            p.error(f"unknown case ids: {', '.join(sorted(unknown))}")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("warning: OPENROUTER_API_KEY is not set (use `export`); only cached responses will be used, "
              "other lines route RED", file=sys.stderr)
    llm = OpenRouterLLM(args.model, key, args.cache)
    rows = run_eval(cases, llm, PrecedentStore(args.precedents), wanted)
    summary = write_results(rows, args.out, args.model)
    for r in rows:
        print(f"{r['id']}  {r['route']:<5}  {_cell(r['category']):<20}  tds {_cell(r['tds']):>6}  {r['outcome']}")
    print(f"\n{summary}  ->  {args.out / 'results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
