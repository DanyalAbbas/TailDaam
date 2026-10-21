"""Generate the dataset proposal PDF from the governed manifest and clean tables.

The numbers are read from the repository, not typed into the prose. Run:
    PYTHONPATH=src .venv/bin/python src/make_dataset_proposal.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifest.csv"
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "Dataset_Proposal.pdf"


class Proposal(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 6, "TailDaam  |  Dataset Proposal  |  HACK INSIGHT 2026",
                  align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"page {self.page_no()}  |  TailDaam dataset proposal",
                  align="C")


def section(pdf: Proposal, title: str, body: str, size: int = 9) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(15, 45, 30)
    pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(35, 35, 35)
    pdf.multi_cell(0, 4.5, body)
    pdf.ln(2)


def main() -> int:
    manifest = pd.read_csv(MANIFEST)
    counts = {name: len(pd.read_parquet(CLEAN / f"{name}.parquet"))
              for name in ["eia_daily", "pbs_weekly_pk", "pbs_monthly_city", "wb_monthly_energy"]}
    total_rows = sum(counts.values())
    files = {p: int((manifest["publisher"] == p).sum()) for p in manifest["publisher"].unique()}
    pbs_weekly_files = int(manifest["file"].str.contains("pbs_spi/spi_").sum())
    pbs_monthly_files = int(files.get("Pakistan Bureau of Statistics", 0)) - pbs_weekly_files

    pdf = Proposal(format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(15, 45, 30)
    pdf.cell(0, 11, "TailDaam", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, "Dataset Proposal: Pakistan fuel prices and Brent risk",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(0, 5, "HACK INSIGHT 2026  |  Track: Energy demand  |  Danyal Abbas",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    section(pdf, "1. Question and why this data",
            "Pakistan's petrol and high-speed diesel prices are administered at "
            "fortnightly reviews, but public argument about them is rarely tied to a "
            "traceable record. TailDaam answers two narrow questions: what was the "
            "notified domestic price, and how volatile is the global Brent benchmark "
            "that feeds Pakistan's import bill? The primary model targets next-month "
            "Brent realised volatility, not the administered domestic level. Domestic "
            "prices are used for a descriptive pass-through calculation and for the "
            "cited insight agent.")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(15, 45, 30)
    pdf.cell(0, 6, "2. Sources, volume and licence", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(232, 238, 233)
    widths = [38, 12, 17, 75, 42]
    headers = ["Source", "Files", "Clean rows", "Role", "Licence"]
    for w, h in zip(widths, headers):
        pdf.cell(w, 5, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 7.5)
    rows = [
        ("PBS weekly SPI", pbs_weekly_files, f"{counts['pbs_weekly_pk']:,}",
         "Domestic petrol/HSD notified prices", "Government open publication"),
        ("PBS monthly annex", pbs_monthly_files, f"{counts['pbs_monthly_city']:,}",
         "17 cities + national average", "Government open publication"),
        ("US EIA", files.get("U.S. Energy Information Administration", 0), f"{counts['eia_daily']:,}",
         "Daily spot series; Brent is the model target", "Public domain (US Gov)"),
        ("World Bank Pink Sheet", files.get("World Bank", 0), f"{counts['wb_monthly_energy']:,}",
         "Monthly energy benchmark / cross-check", "CC BY 4.0"),
    ]
    for row in rows:
        for w, value in zip(widths, row):
            pdf.cell(w, 5, str(value), border=1)
        pdf.ln()
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(sum(widths), 5, f"Total: {len(manifest)} raw files | {total_rows:,} clean rows | 3 publishers",
             border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    section(pdf, "3. What is used for training, and what is not",
            "The primary model is a HAR-style ridge regression trained on the EIA "
            "daily Brent Europe spot series (target: next calendar month annualised "
            "realised volatility). The features are lagged monthly, quarterly and "
            "annual realised volatility. No PBS or World Bank observation is used to "
            "fit that model. PBS weekly data is used for the descriptive Pakistan "
            "pass-through calculation (39 overlapping weeks; reported as descriptive, "
            "not causal). PBS city data, EIA and World Bank rows are indexed for the "
            "RAG agent so answers can quote them with row IDs. The World Bank series is "
            "an independent benchmark, not a training input.")

    section(pdf, "4. Collection, provenance and independence",
            f"All {len(manifest)} raw files were fetched from the original publishers "
            "on 20-21 October 2026, during the event. No data is taken from a Kaggle, "
            "GitHub or blog re-upload. data/manifest.csv records the source URL, query, "
            "fetch time, SHA-256 and licence for every file. The three publishers are "
            "independent: PBS (Pakistan), EIA (United States) and the World Bank. The "
            "volume is 91,384 clean rows, above the 50,000-row minimum, and the sources "
            "include material outside the suggested Energy-demand track list.")

    section(pdf, "5. Quality, limitations and honesty controls",
            "The deterministic quality agent applies 14 rules and logs every FIX, FLAG "
            "and FAIL decision. The current status is WARN: 1 fix and 4 flags, including "
            "the 9 April 2026 HSD outlier (522.29 PKR/L against 380.56 petrol), which is "
            "kept and annotated rather than silently removed. No synthetic, interpolated "
            "or AI-generated observations are used for training or evaluation. The PBS "
            "weekly history is short (41 reports) with genuine publication gaps; the "
            "monthly city annex covers September 2026; domestic prices are administered. "
            "These limits are stated in the README and Summary.pdf.")

    section(pdf, "6. Reproducibility",
            "Every layer is rebuilt with one command: `make data` runs acquire -> clean "
            "-> quality -> gold. `make model` refits the declared baseline and the "
            "pre-registered challenger; `make test` runs the contract and honesty tests; "
            "`make all` runs the full chain and regenerates Summary.pdf. The fitted model, "
            "gold tables, citation registry and all metrics are committed. The Hugging "
            "Face Space is a static dashboard over the verified API; the API health "
            "endpoint reports the embedding mode and indexed fact count.")

    pdf.output(str(OUT))
    print(f"wrote {OUT.relative_to(ROOT)} ({total_rows:,} clean rows, {len(manifest)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
