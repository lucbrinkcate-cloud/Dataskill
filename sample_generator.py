from __future__ import annotations

from pathlib import Path

import pandas as pd


def main():
    out = Path("sample_business_input.xlsx")
    products = pd.DataFrame([
        {"Item Code": "A-100", "Description": "Aluminium Bracket Small", "Product Group": "Brackets", "Sales Price EUR": 18.50, "Material Cost": 5.20, "Direct Labour": 2.10, "Handling / Logistics": 1.10, "Overhead": 1.80, "Annual Demand": 9000, "Plant": "Netherlands"},
        {"Item Code": "A-200", "Description": "Aluminium Bracket Large", "Product Group": "Brackets", "Sales Price EUR": 31.00, "Material Cost": 12.50, "Direct Labour": 4.80, "Handling / Logistics": 2.30, "Overhead": 2.80, "Annual Demand": 5200, "Plant": "Netherlands"},
        {"Item Code": "P-010", "Description": "Plastic Housing Basic", "Product Group": "Housings", "Sales Price EUR": 12.00, "Material Cost": 4.80, "Direct Labour": 1.60, "Handling / Logistics": 1.90, "Overhead": 1.20, "Annual Demand": 20000, "Plant": "Poland"},
        {"Item Code": "P-020", "Description": "Plastic Housing Premium", "Product Group": "Housings", "Sales Price EUR": 22.00, "Material Cost": 7.20, "Direct Labour": 2.90, "Handling / Logistics": 1.70, "Overhead": 1.50, "Annual Demand": 12500, "Plant": "Poland"},
        {"Item Code": "C-300", "Description": "Carbon Cover", "Product Group": "Covers", "Sales Price EUR": 45.00, "Material Cost": 22.00, "Direct Labour": 8.50, "Handling / Logistics": 3.40, "Overhead": 4.20, "Annual Demand": 2600, "Plant": "Portugal"},
    ])
    locations = pd.DataFrame([
        {"Product Code": "A-100", "Product": "Aluminium Bracket Small", "Country": "Netherlands", "Total Unit Cost": 10.20, "Capacity": 7000, "Lead Time Days": 8},
        {"Product Code": "A-100", "Product": "Aluminium Bracket Small", "Country": "Poland", "Total Unit Cost": 8.90, "Capacity": 6000, "Lead Time Days": 14},
        {"Product Code": "A-200", "Product": "Aluminium Bracket Large", "Country": "Netherlands", "Total Unit Cost": 22.40, "Capacity": 3500, "Lead Time Days": 8},
        {"Product Code": "A-200", "Product": "Aluminium Bracket Large", "Country": "Poland", "Total Unit Cost": 19.70, "Capacity": 3000, "Lead Time Days": 14},
        {"Product Code": "P-010", "Product": "Plastic Housing Basic", "Country": "Poland", "Total Unit Cost": 9.50, "Capacity": 25000, "Lead Time Days": 12},
        {"Product Code": "P-010", "Product": "Plastic Housing Basic", "Country": "Portugal", "Total Unit Cost": 10.10, "Capacity": 12000, "Lead Time Days": 16},
        {"Product Code": "C-300", "Product": "Carbon Cover", "Country": "Portugal", "Total Unit Cost": 38.10, "Capacity": 4000, "Lead Time Days": 18},
        {"Product Code": "C-300", "Product": "Carbon Cover", "Country": "Poland", "Total Unit Cost": 36.20, "Capacity": 1000, "Lead Time Days": 15},
    ])
    market = pd.DataFrame([
        {"Competitor": "MarketCo", "Similar Product": "Small aluminium bracket", "Market Price": 19.20, "Region": "EU"},
        {"Competitor": "PartsDirect", "Similar Product": "Large aluminium bracket", "Market Price": 29.80, "Region": "EU"},
        {"Competitor": "HousingPro", "Similar Product": "Plastic enclosure basic", "Market Price": 13.10, "Region": "EU"},
        {"Competitor": "CompositeNow", "Similar Product": "Carbon fibre cover", "Market Price": 49.00, "Region": "EU"},
    ])
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        products.to_excel(writer, sheet_name="Sales Items", index=False)
        locations.to_excel(writer, sheet_name="Production locations", index=False)
        market.to_excel(writer, sheet_name="Market benchmarks", index=False)
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
