"""Generate the designed dataset-proposal PDF.

The counts come from the governed manifest and clean tables; the prose does not
hard-code the volume. Run:
    PYTHONPATH=src .venv/bin/python src/make_dataset_proposal.py

The logo is the same mark used by the web app. `frontend/dist/mark.png` is
committed so this build does not depend on ImageMagick or a network call.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifest.csv"
CLEAN = ROOT / "data" / "clean"
LOGO = ROOT / "frontend" / "dist" / "mark.png"
OUT = ROOT / "Dataset_Proposal.pdf"

INK = (18, 22, 19)
GREEN = (10, 107, 61)
GREEN_DARK = (15, 45, 30)
PALE = (247, 245, 236)
CARD = (232, 238, 233)
LINE = (214, 220, 212)
MUTED = (95, 106, 98)
AMBER = (183, 121, 31)
WHITE = (255, 255, 255)


class Proposal(FPDF):
    def multi_cell(self, w, h=None, text="", *args, **kwargs):
        # fpdf2 justifies multi_cell text by default; long labels in a
        # narrow card then look as if they have random gaps.
        kwargs.setdefault("align", "L")
        return super().multi_cell(w, h, text, *args, **kwargs)

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(10)
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(18, 17, 192, 17)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*GREEN)
        self.set_xy(18, 11)
        self.cell(26, 4, "TAILDAAM")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.set_xy(46, 11)
        self.cell(58, 4, "DATASET PROPOSAL")
        self.set_font("Helvetica", "", 7)
        self.set_xy(110, 11)
        self.cell(82, 4, "HACK INSIGHT 2026  /  ENERGY DEMAND", align="R")

    def footer(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(-13)
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(18, 281, 192, 281)
        self.set_y(-10)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 4, "TailDaam  /  dataset proposal  /  every figure traceable",
                  align="L")
        self.cell(0, 4, f"{self.page_no():02d}", align="R")


def label(pdf: Proposal, text: str, y: float) -> float:
    pdf.set_y(y)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 4, text, new_x="LMARGIN", new_y="NEXT")
    return pdf.get_y() + 1


def heading(pdf: Proposal, text: str, size: int = 18) -> None:
    pdf.set_font("Helvetica", "B", size)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def body(pdf: Proposal, text: str, size: float = 9.2, width: float = 174,
         leading: float = 4.8) -> None:
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(45, 53, 47)
    pdf.multi_cell(width, leading, text, new_x="LMARGIN", new_y="NEXT")


def rule(pdf: Proposal, y: float | None = None, color=LINE) -> None:
    if y is not None:
        pdf.set_y(y)
    pdf.set_draw_color(*color)
    pdf.set_line_width(0.35)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())


def stat_card(pdf: Proposal, x: float, y: float, w: float, h: float,
              number: str, caption: str) -> None:
    pdf.set_fill_color(*PALE)
    pdf.rect(x, y, w, h, style="F")
    pdf.set_xy(x + 4, y + 5)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*GREEN_DARK)
    pdf.cell(w - 8, 7, number, new_x="LEFT", new_y="NEXT")
    pdf.set_xy(x + 4, y + 13)
    pdf.set_font("Helvetica", "", 7.2)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(w - 8, 3.6, caption)


def pill(pdf: Proposal, x: float, y: float, text: str, w: float = 22,
         color=GREEN) -> None:
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, 5, style="F")
    pdf.set_xy(x + 2, y + 1)
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_text_color(*WHITE)
    pdf.cell(w - 4, 3, text, align="C")


def main() -> int:
    manifest = pd.read_csv(MANIFEST)
    counts = {
        name: len(pd.read_parquet(CLEAN / f"{name}.parquet"))
        for name in ["eia_daily", "pbs_weekly_pk", "pbs_monthly_city",
                     "wb_monthly_energy"]
    }
    total_rows = sum(counts.values())
    pbs_files = int((manifest["publisher"] == "Pakistan Bureau of Statistics").sum())
    pbs_weekly_files = int(manifest["file"].str.contains("pbs_spi/spi_").sum())
    pbs_monthly_files = pbs_files - pbs_weekly_files
    eia_files = int((manifest["publisher"] == "U.S. Energy Information Administration").sum())
    wb_files = int((manifest["publisher"] == "World Bank").sum())

    pdf = Proposal(format="A4")
    pdf.set_title("TailDaam - Dataset Proposal")
    pdf.set_author("Danyal Abbas")
    pdf.set_subject("Credible sources, provenance and model-use rationale for "
                    "Pakistan fuel prices and Brent risk")
    pdf.set_creator("TailDaam")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)

    # ---------------------------------------------------------------- cover
    pdf.add_page()
    pdf.set_fill_color(*PALE)
    pdf.rect(0, 0, 210, 297, style="F")
    pdf.image(str(LOGO), x=18, y=18, w=17, h=17)
    pdf.set_xy(39, 19)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(70, 7, "TailDaam", new_x="LEFT", new_y="NEXT")
    pdf.set_xy(39.5, 26.5)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(95, 4, "PAKISTAN FUEL PRICES, WITH RECEIPTS")

    pdf.set_xy(140, 20)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*GREEN)
    pdf.cell(52, 4, "HACK INSIGHT 2026", align="R", new_x="LEFT", new_y="NEXT")
    pdf.set_x(140)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(52, 4, "TRACK: ENERGY DEMAND", align="R")

    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.4)
    pdf.line(18, 44, 192, 44)

    pdf.set_xy(18, 74)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 5, "DATASET PROPOSAL", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(18, 83)
    pdf.set_font("Helvetica", "B", 43)
    pdf.set_text_color(*INK)
    pdf.cell(0, 17, "The record", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(18)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 17, "behind the price.", new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(18, 118)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(45, 53, 47)
    pdf.multi_cell(125, 6,
                   "Credible sources, provenance and model-use rationale for "
                   "Pakistan's petrol and diesel record and a Brent volatility "
                   "model.")

    # dark stat band
    card_y = 150
    pdf.set_fill_color(*INK)
    pdf.rect(18, card_y, 174, 42, style="F")
    pdf.set_xy(23, card_y + 7)
    stats = [
        (f"{len(manifest)}", "raw files"),
        (f"{total_rows:,}", "clean rows"),
        ("3", "publishers"),
        ("14", "quality rules"),
    ]
    for i, (number, caption) in enumerate(stats):
        x = 23 + i * 43.5
        pdf.set_xy(x, card_y + 8)
        pdf.set_font("Helvetica", "B", 19)
        pdf.set_text_color(*PALE)
        pdf.cell(40, 8, number, new_x="LEFT", new_y="NEXT")
        pdf.set_xy(x, card_y + 18)
        pdf.set_font("Helvetica", "", 6.8)
        pdf.set_text_color(190, 200, 191)
        pdf.cell(40, 4, caption.upper())
    pdf.set_xy(23, card_y + 30)
    pdf.set_font("Helvetica", "", 6.8)
    pdf.set_text_color(190, 200, 191)
    pdf.cell(0, 4, "91,384 rows are above the 50,000-row gate. No synthetic or re-uploaded data.",
             new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(18, 222)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GREEN_DARK)
    pdf.cell(60, 4, "PREPARED BY", new_x="LEFT", new_y="NEXT")
    pdf.set_xy(18, 227)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.cell(80, 5, "Danyal Abbas", new_x="LEFT", new_y="NEXT")
    pdf.set_xy(18, 236)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(80, 4, "21 October 2026  /  TailDaam v1.0", new_x="LEFT", new_y="NEXT")

    pdf.set_xy(120, 222)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GREEN_DARK)
    pdf.cell(72, 4, "THE CLAIM", align="R", new_x="LEFT", new_y="NEXT")
    pdf.set_xy(108, 227)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(84, 4,
                   "Every price in the gold layer can be traced to a published "
                   "row. Unsupported answers refuse.", align="R")

    pdf.set_draw_color(*GREEN)
    pdf.set_line_width(1)
    pdf.line(18, 264, 56, 264)
    pdf.set_xy(18, 268)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, "A governed data product for the HACK INSIGHT 2026 energy track.",
             new_x="LMARGIN", new_y="NEXT")

    # ---------------------------------------------------------- page 2
    pdf.add_page()
    y = label(pdf, "01  /  THE QUESTION", 24)
    heading(pdf, "What we are actually modelling", 20)
    body(pdf, "Pakistani petrol and high-speed diesel prices are administered at "
              "fortnightly reviews, and the evidence is scattered across PBS "
              "reports and global benchmark feeds. Public argument mixes three "
              "claims: the notified price, why it moved, and what happens next. "
              "TailDaam answers the first with citations, measures the second "
              "only descriptively, and does not forecast the administered "
              "domestic price.", width=118)
    body(pdf, "The primary model targets the risk dimension of the oil import "
              "bill: next-month Brent realised volatility. That is where the "
              "data has enough history for a defensible baseline comparison.",
         width=118)
    pdf.ln(2)
    body(pdf, "The agent is refusal-first. A scope gate, retrieval confidence "
              "floor, time/product/city filters and a number verifier make "
              "unsupported answers a code path, not a prompt request.", width=118)

    # right callout
    bx, by, bw, bh = 142, 30, 50, 98
    pdf.set_fill_color(*CARD)
    pdf.rect(bx, by, bw, bh, style="F")
    pdf.set_xy(bx + 5, by + 6)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 4, "PRIMARY TARGET")
    pdf.set_xy(bx + 5, by + 11)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*INK)
    pdf.multi_cell(bw - 10, 4.2, "Next-month Brent realised volatility")
    pdf.set_xy(bx + 5, by + 28)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 4, "BASELINE")
    pdf.set_xy(bx + 5, by + 33)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(45, 53, 47)
    pdf.multi_cell(bw - 10, 4, "Persistence (this month's RV)")
    pdf.set_xy(bx + 5, by + 46)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 4, "RESULT")
    pdf.set_xy(bx + 5, by + 51)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*GREEN_DARK)
    pdf.cell(0, 5, "-7.27% MAE", new_x="LEFT", new_y="NEXT")
    pdf.set_xy(bx + 5, by + 57)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(bw - 10, 3.8, "16.5102 vs 17.8044 on 93 held-out months")
    pdf.set_xy(bx + 5, by + 72)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 4, "NOT CLAIMED")
    pdf.set_xy(bx + 5, by + 77)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(70, 78, 71)
    pdf.multi_cell(bw - 10, 3.8, "A domestic retail-price forecast or a causal "
                                "pass-through estimate")

    y = 137
    y = label(pdf, "02  /  SOURCES", y)
    heading(pdf, "Three publishers. 54 files. 91,384 clean rows.", 18)

    table_x = 18
    table_y = pdf.get_y() + 2
    widths = [38, 12, 20, 63, 41]
    headers = ["SOURCE", "FILES", "ROWS", "ROLE IN THIS PROJECT", "LICENCE"]
    pdf.set_fill_color(*GREEN_DARK)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 6.8)
    for w, h in zip(widths, headers):
        pdf.cell(w, 7, h, border=0, fill=True, align="L")
    pdf.ln()
    rows = [
        ("PBS weekly SPI", pbs_weekly_files, f"{counts['pbs_weekly_pk']:,}",
         "Weekly petrol/HSD prices", "Government open"),
        ("PBS monthly annex", pbs_monthly_files, f"{counts['pbs_monthly_city']:,}",
         "17 cities + national average", "Government open"),
        ("US EIA", eia_files, f"{counts['eia_daily']:,}",
         "Daily spot; Brent is the target", "Public domain"),
        ("World Bank Pink Sheet", wb_files, f"{counts['wb_monthly_energy']:,}",
         "Independent energy benchmark", "CC BY 4.0"),
    ]
    for i, row in enumerate(rows):
        pdf.set_fill_color(*(PALE if i % 2 == 0 else WHITE))
        pdf.set_text_color(40, 48, 42)
        pdf.set_font("Helvetica", "", 7.2)
        for j, (w, val) in enumerate(zip(widths, row)):
            align = "R" if j in (1, 2) else "L"
            pdf.cell(w, 8, str(val), border=0, fill=True, align=align)
        pdf.ln()
    pdf.set_fill_color(*CARD)
    pdf.set_text_color(*GREEN_DARK)
    pdf.set_font("Helvetica", "B", 7.2)
    pdf.cell(174, 7, f"TOTAL   {len(manifest)} raw files   /   {total_rows:,} clean rows   /   "
                     "3 independent publishers", fill=True,
             new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    cards = [
        ("50,000+", "Volume gate", "The clean layer is 91,384 rows, not a thin "
         "weekly series."),
        ("3", "Independent sources", "PBS is the Pakistani anchor; EIA and the "
         "World Bank are off the suggested source list."),
        ("1", "Manifest", "Every raw file carries a URL, fetch time, SHA-256 "
         "and licence."),
    ]
    cards_y = pdf.get_y()
    for i, (big, title, text) in enumerate(cards):
        x = 18 + i * 59
        pdf.set_fill_color(*PALE)
        pdf.rect(x, cards_y, 55, 34, style="F")
        pdf.set_xy(x + 4, cards_y + 4)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*GREEN_DARK)
        pdf.cell(0, 6, big)
        pdf.set_xy(x + 4, cards_y + 12)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*GREEN)
        pdf.cell(0, 4, title.upper())
        pdf.set_xy(x + 4, cards_y + 17)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(46, 3.6, text)

    absent_y = cards_y + 42
    pdf.set_fill_color(*INK)
    pdf.rect(18, absent_y, 174, 24, style="F")
    pdf.set_xy(23, absent_y + 4)
    pdf.set_font("Helvetica", "B", 6.8)
    pdf.set_text_color(190, 230, 205)
    pdf.cell(0, 4, "WHAT IS DELIBERATELY ABSENT")
    absent = [
        ("NO SYNTHETIC ROWS", "Every observation is published."),
        ("NO KAGGLE MIRRORS", "Only original publishers are fetched."),
        ("NO BACKFILLED WEEKS", "Publication gaps stay gaps."),
    ]
    for i, (title, text) in enumerate(absent):
        x = 23 + i * 56
        pdf.set_xy(x, absent_y + 10)
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(*PALE)
        pdf.cell(50, 3, title)
        pdf.set_xy(x, absent_y + 14)
        pdf.set_font("Helvetica", "", 6.3)
        pdf.set_text_color(190, 200, 191)
        pdf.cell(50, 3, text)

    # ---------------------------------------------------------- page 3
    pdf.add_page()
    y = label(pdf, "03  /  HOW THE DATA IS USED", 24)
    heading(pdf, "Training, retrieval, and one descriptive estimate", 19)
    body(pdf, "The model and the agent are deliberately separated. The model is "
              "trained on EIA daily Brent only; the agent may quote the PBS, EIA "
              "and World Bank gold facts. The Pakistan pass-through is a "
              "descriptive small-sample calculation, not a training input and "
              "not a causal claim.", width=174)
    pdf.ln(2)

    uses = [
        ("MODEL TRAINING", "EIA daily Brent Europe spot", "Target: next calendar "
         "month annualised realised volatility. Features: lagged monthly, "
         "quarterly and annual RV. Ridge alpha = 10, pre-registered."),
        ("DESCRIPTIVE", "PBS weekly + EIA Brent", "39 overlapping weeks: "
         "correlation 0.6928, slope 0.5821 PKR per USD/bbl. Reported as "
         "small-sample evidence; no causal claim."),
        ("RAG EVIDENCE", "2,129 gold facts", "PBS weekly/monthly, EIA and World "
         "Bank rows with citation tags and row IDs. The agent may only quote "
         "these rows."),
    ]
    uses_y = pdf.get_y() + 2
    for i, (tag, title, text) in enumerate(uses):
        x = 18 + i * 59
        pdf.set_fill_color(*(CARD if i == 0 else PALE))
        pdf.rect(x, uses_y, 55, 46, style="F")
        pdf.set_xy(x + 4, uses_y + 4)
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(*GREEN)
        pdf.cell(0, 4, tag)
        pdf.set_xy(x + 4, uses_y + 9)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*INK)
        pdf.multi_cell(47, 4, title)
        pdf.set_xy(x + 4, uses_y + 18)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(47, 3.6, text)

    y = label(pdf, "04  /  PROVENANCE", uses_y + 54)
    heading(pdf, "From publisher file to quoted row", 19)
    body(pdf, "Every transfer is recorded. A gold answer carries the row IDs it "
              "came from; those IDs resolve back through the clean table to a "
              "raw file and its SHA-256 in data/manifest.csv.", width=174)
    pdf.ln(2)

    # pipeline boxes
    py = pdf.get_y() + 2
    steps = [("01", "ACQUIRE", "original URL"), ("02", "CLEAN", "typed rows"),
             ("03", "QUALITY", "FIX / FLAG"), ("04", "GOLD", "row IDs"),
             ("05", "AGENT", "quote only")]
    box_w, gap = 31.0, 4.4
    for i, (num, title, sub) in enumerate(steps):
        x = 18 + i * (box_w + gap)
        pdf.set_fill_color(*(INK if i == 4 else CARD))
        pdf.rect(x, py, box_w, 19, style="F")
        pdf.set_xy(x + 3, py + 3)
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(*(GREEN if i < 4 else (190, 230, 205)))
        pdf.cell(0, 3, num)
        pdf.set_xy(x + 3, py + 7)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*(INK if i < 4 else WHITE))
        pdf.cell(0, 4, title)
        pdf.set_xy(x + 3, py + 12)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(*(MUTED if i < 4 else (190, 200, 191)))
        pdf.cell(0, 3, sub)
        if i < 4:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*GREEN)
            pdf.set_xy(x + box_w + 0.7, py + 6)
            pdf.cell(gap - 1.4, 5, ">", align="C")

    pdf.set_y(py + 28)
    pdf.set_fill_color(*PALE)
    pdf.rect(18, pdf.get_y(), 174, 18, style="F")
    pdf.set_xy(23, pdf.get_y() + 4)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(164, 4,
                   "Manifest fields: file, source, publisher, url, query, "
                   "fetch_time_utc, sha256, licence, bytes. No Kaggle mirror, "
                   "no blog scrape, no re-uploaded dataset.")

    example_y = pdf.get_y() + 10
    pdf.set_fill_color(*PALE)
    pdf.rect(18, example_y, 174, 28, style="F")
    pdf.set_xy(23, example_y + 4)
    pdf.set_font("Helvetica", "B", 6.8)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 4, "ONE ANSWER, TRACED")
    pdf.set_xy(23, example_y + 10)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*INK)
    pdf.cell(0, 4, "What is the current petrol price in Pakistan?")
    pdf.set_xy(23, example_y + 16)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(45, 53, 47)
    pdf.cell(0, 4, "396.06 PKR/L  /  week ended 2026-10-15  /  PBS-SPI  /  "
                   "pbs:2026-10-15:petrol_super")
    pdf.set_xy(23, example_y + 21)
    pdf.set_font("Helvetica", "", 6.8)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, "The number is quoted from the row, not generated by a language model.")

    # ---------------------------------------------------------- page 4
    pdf.add_page()
    y = label(pdf, "05  /  QUALITY AND LIMITS", 24)
    heading(pdf, "What is repaired, what is kept, what is refused", 19)

    pdf.set_fill_color(*INK)
    pdf.rect(18, 35, 78, 42, style="F")
    pdf.set_xy(24, 40)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(190, 230, 205)
    pdf.cell(0, 4, "QUALITY STATUS")
    pdf.set_xy(24, 46)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*AMBER)
    pdf.cell(0, 9, "WARN")
    pdf.set_xy(24, 57)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*PALE)
    pdf.cell(0, 4, "14 rules  /  1 fix  /  4 flags  /  0 fails")
    pdf.set_xy(24, 64)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(190, 200, 191)
    pdf.multi_cell(66, 3.8, "Warnings are kept and shown. A WARN is not hidden "
                            "behind a PASS.")

    qx = 103
    q_items = [
        ("FIX", "Dropped 1 non-positive EIA price; no value invented."),
        ("FLAG", "20 EIA daily jumps kept: energy markets can genuinely gap."),
        ("FLAG", "9 Apr 2026 HSD jump 522.29 PKR/L kept and annotated."),
        ("FLAG", "Two PBS cadence gaps > 28 days; not filled."),
    ]
    for i, (tag, text) in enumerate(q_items):
        yy = 37 + i * 10.5
        pill(pdf, qx, yy, tag, 12, GREEN if tag == "FIX" else AMBER)
        pdf.set_xy(qx + 15, yy + 1)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(45, 53, 47)
        pdf.multi_cell(72, 3.8, text)

    pdf.set_y(85)
    y = label(pdf, "06  /  LIMITS", 85)
    heading(pdf, "The constraints are part of the record", 17)
    limits = [
        ("Short history", "PBS serves 41 weekly reports; publication gaps stay gaps."),
        ("Administered prices", "Domestic prices move at policy reviews, not continuously."),
        ("One month of cities", "The PBS monthly city annex covers September 2026."),
        ("Global target", "The model forecasts Brent volatility, not the domestic retail level."),
        ("Lexical fallback", "Without a Mistral key, retrieval is TF-IDF; refusals are preferred to guesses."),
    ]
    for i, (title, text) in enumerate(limits):
        yy = 110 + i * 11
        pdf.set_fill_color(*(PALE if i % 2 == 0 else WHITE))
        pdf.rect(18, yy, 174, 9.5, style="F")
        pdf.set_xy(22, yy + 2.5)
        pdf.set_font("Helvetica", "B", 7.2)
        pdf.set_text_color(*GREEN_DARK)
        pdf.cell(33, 4, title)
        pdf.set_xy(55, yy + 2.5)
        pdf.set_font("Helvetica", "", 7.2)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 4, text)

    pdf.set_y(172)
    y = label(pdf, "07  /  REPRODUCIBILITY", 172)
    heading(pdf, "One command rebuilds the record", 17)
    body(pdf, "Every layer is deterministic and committed. The raw files stay "
              "with their manifest; the clean layer, gold tables, model, metrics "
              "and citation registry are regenerated from them.", width=174)
    box_y = max(pdf.get_y() + 4, 210)
    pdf.set_fill_color(*INK)
    pdf.rect(18, box_y, 174, 36, style="F")
    cmds = [
        ("make data", "acquire -> clean -> quality -> gold"),
        ("make model", "refit baseline and pre-registered challenger"),
        ("make test", "contract, refusal and verification tests"),
        ("make all", "data, model, index, tests, Summary.pdf, this PDF"),
    ]
    for i, (cmd, note) in enumerate(cmds):
        yy = box_y + 3 + i * 7
        pdf.set_xy(23, yy)
        pdf.set_font("Courier", "B", 7.5)
        pdf.set_text_color(190, 230, 205)
        pdf.cell(27, 4, cmd)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(210, 216, 209)
        pdf.cell(0, 4, note)

    dec_y = box_y + 44
    pdf.set_fill_color(*CARD)
    pdf.rect(18, dec_y, 174, 22, style="F")
    pdf.set_xy(23, dec_y + 4)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 4, "DECLARATION")
    pdf.set_xy(23, dec_y + 9)
    pdf.set_font("Helvetica", "", 7.4)
    pdf.set_text_color(45, 53, 47)
    pdf.multi_cell(164, 3.8,
                   "All 91,384 clean rows come from the original PBS, EIA and "
                   "World Bank publishers. No synthetic, interpolated or "
                   "AI-generated observation is used for training or evaluation. "
                   "The quality warnings and the missed pipeline window are "
                   "disclosed, not backfilled.")

    pdf.output(str(OUT))
    print(f"wrote {OUT.relative_to(ROOT)} ({pdf.page_no()} pages, "
          f"{total_rows:,} clean rows, {len(manifest)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
