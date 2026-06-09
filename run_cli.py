from __future__ import annotations

import argparse
from pathlib import Path

from core.business_logic import (
    SelectedLine,
    extract_products,
    full_report,
    margin_analysis,
    product_comparison,
    production_optimization,
    render_invoice_or_quote,
    schema_report,
)
from core.excel_reader import read_workbook
from core.llm import OllamaClient
from core.schema_mapper import safe_number


def make_llm(args):
    if not args.ai:
        return None
    return OllamaClient(model=args.model, base_url=args.ollama_url)


def interactive_document(workbook, document_type: str, currency: str, llm):
    products = extract_products(workbook)
    if not products:
        raise SystemExit("No products/items detected for invoice/quotation.")
    print("\nDetected products/items:")
    for p in products[:80]:
        price = p.unit_price if p.unit_price == p.unit_price else p.total_cost() * 1.3
        print(f"  {p.id:>3} | {p.display_name()[:55]:55} | price {price:.2f} | cost {p.total_cost():.2f} | loc {p.location}")
    print("\nEnter selections as id:qty,id:qty (example: 0:10,4:2).")
    raw = input("Selection: ").strip()
    by_id = {p.id: p for p in products}
    lines = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            pid, qty = part.split(":", 1)
        else:
            pid, qty = part, "1"
        p = by_id.get(pid.strip())
        if p:
            lines.append(SelectedLine(product=p, quantity=safe_number(qty, 1.0)))
    if not lines:
        raise SystemExit("No valid lines selected.")
    company = input("Company name [Your Company]: ").strip() or "Your Company"
    customer = input("Customer name [Customer]: ").strip() or "Customer"
    tax = safe_number(input("Tax/VAT % [21]: ").strip() or "21", 21.0)
    out = Path("generated") / f"{document_type}_cli.html"
    render_invoice_or_quote(document_type, lines, company=company, customer=customer, tax_rate=tax, currency=currency, output_path=str(out))
    print(f"Generated {out.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Local Business AI Tool CLI: Excel/CSV to HTML outputs")
    parser.add_argument("file", help="Path to .xlsx/.xlsm/.xls/.csv workbook")
    parser.add_argument("--output", choices=["invoice", "quotation", "full_report", "margin_analysis", "production_optimization", "product_comparison", "schema_report"], default="full_report")
    parser.add_argument("--currency", default="€")
    parser.add_argument("--ai", action="store_true", help="Use local Ollama model for narrative insights")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--out", default="", help="Output HTML path. Defaults to generated/<output>.html")
    args = parser.parse_args()

    workbook = read_workbook(args.file)
    if workbook.errors:
        print("Read warnings/errors:")
        for err in workbook.errors:
            print(" -", err)
    if not workbook.tables:
        raise SystemExit("No readable tables found.")

    Path("generated").mkdir(exist_ok=True)
    llm = make_llm(args)
    if args.output in {"invoice", "quotation"}:
        interactive_document(workbook, args.output, args.currency, llm)
        return

    out = args.out or str(Path("generated") / f"{args.output}.html")
    if args.output == "margin_analysis":
        margin_analysis(workbook, args.currency, llm=llm, output_path=out)
    elif args.output == "production_optimization":
        production_optimization(workbook, args.currency, llm=llm, output_path=out)
    elif args.output == "product_comparison":
        product_comparison(workbook, args.currency, llm=llm, output_path=out)
    elif args.output == "schema_report":
        schema_report(workbook, args.currency, llm=llm, output_path=out)
    else:
        full_report(workbook, args.currency, llm=llm, output_path=out)
    print(f"Generated {Path(out).resolve()}")


if __name__ == "__main__":
    main()
