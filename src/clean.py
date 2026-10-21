"""Clean raw files into typed long-format tables with stable row ids."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from common import CLEAN, RAW
from acquire import EIA_SERIES


def _num(x):
    try:
        s = str(x).replace(",", "").strip()
        if s in ("", "…", "...", "nan", "NA", "N/A", "-"):
            return None
        return float(s)
    except Exception:
        return None


def clean_eia() -> pd.DataFrame:
    rows = []
    for series_id, (name, unit) in EIA_SERIES.items():
        path = RAW / "eia" / f"{series_id}.xls"
        if not path.exists():
            continue
        xl = pd.ExcelFile(path)
        sheet = xl.sheet_names[-1]
        df = xl.parse(sheet, header=None)
        for _, r in df.iloc[3:].iterrows():
            d, v = r.iloc[0], _num(r.iloc[1])
            if v is None or pd.isna(d):
                continue
            try:
                date = pd.to_datetime(d).date().isoformat()
            except Exception:
                continue
            rows.append({
                "row_id": f"eia:{series_id}:{date}",
                "date": date,
                "series_id": series_id,
                "series_name": name,
                "value": v,
                "unit": unit,
                "source_file": f"data/raw/eia/{series_id}.xls",
            })
    out = pd.DataFrame(rows)
    out = out.drop_duplicates("row_id").sort_values(["series_id", "date"])
    return out


_PRODUCT_MAP = {
    "petrol super": "petrol_super",
    "hi-speed diesel": "hsd",
}


def clean_pbs_weekly() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW / "pbs_spi").glob("spi_*.xlsx")):
        m = re.search(r"spi_(\d{2})\.(\d{2})\.(\d{4})", path.name)
        if not m:
            continue
        dd, mm, yyyy = m.groups()
        week_end = f"{yyyy}-{mm}-{dd}"
        try:
            xl = pd.ExcelFile(path)
        except Exception:
            continue
        for s in xl.sheet_names:
            frame = xl.parse(s, header=None)
            if frame.shape[1] < 5:
                continue
            for _, r in frame.iterrows():
                vals = [str(x).strip().lower() for x in r.tolist()]
                product = None
                name_idx = None
                for j, v in enumerate(vals):
                    if v in _PRODUCT_MAP:
                        product = _PRODUCT_MAP[v]
                        name_idx = j
                        break
                if product is None:
                    continue
                # layout: [.., item_no, name, unit, current, previous, year_ago, ...]
                price_idx = name_idx + 2
                current = _num(r.iloc[price_idx]) if price_idx < len(r) else None
                if current is None:
                    continue
                rows.append({
                    "row_id": f"pbs:{week_end}:{product}",
                    "week_end": week_end,
                    "product": product,
                    "price_pkr_l": current,
                    "prev_week_pkr_l": _num(r.iloc[price_idx + 1]),
                    "year_ago_pkr_l": _num(r.iloc[price_idx + 2]),
                    "source_file": str(path.relative_to(RAW.parent)),
                })
    out = pd.DataFrame(rows).drop_duplicates("row_id")
    return out.sort_values(["product", "week_end"])


def clean_pbs_monthly() -> pd.DataFrame:
    path = RAW / "pbs_spi" / "SPI-Monthly-Prices-Annex-9.xlsx"
    if not path.exists():
        return pd.DataFrame()
    xl = pd.ExcelFile(path)
    rows = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet, header=None)
        if df.empty:
            continue
        # month from title row (e.g. "... for the month of September 2026")
        title = " ".join(str(x) for x in df.iloc[0].dropna().tolist())
        m = re.search(r"month of\s+([A-Za-z]+)\s+(\d{4})", title)
        if not m:
            continue
        month = pd.to_datetime(f"{m.group(1)} {m.group(2)}").strftime("%Y-%m")
        header_idx = None
        for i in range(min(6, len(df))):
            if any("Description" in str(x) for x in df.iloc[i].tolist()):
                header_idx = i
                break
        if header_idx is None:
            continue
        header = [str(x).strip() for x in df.iloc[header_idx].tolist()]
        city_cols = []
        avg_col = None
        for j, h in enumerate(header):
            hl = h.lower()
            if j <= 2:
                continue
            if hl.startswith("average prices"):
                avg_col = j
                break
            if h and hl not in ("nan",) and "%" not in hl:
                city_cols.append((j, h))
        if avg_col is not None:
            city_cols.append((avg_col, "National average"))
        for _, r in df.iloc[header_idx + 1:].iterrows():
            name = str(r.iloc[1]).strip().lower()
            product = _PRODUCT_MAP.get(name)
            if not product:
                continue
            for j, city in city_cols:
                v = _num(r.iloc[j]) if j < len(r) else None
                if v is None:
                    continue
                rows.append({
                    "row_id": f"pbsm:{month}:{product}:{city}",
                    "month": month,
                    "city": city,
                    "product": product,
                    "price_pkr_l": v,
                    "source_file": str(path.relative_to(RAW.parent)),
                })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.drop_duplicates("row_id").sort_values(["month", "product", "city"])


_ENERGY_KEYS = ("crude oil", "natural gas", "coal", "liquefied natural gas")


def clean_worldbank() -> pd.DataFrame:
    path = RAW / "worldbank" / "CMO-Historical-Data-Monthly.xlsx"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_excel(path, sheet_name="Monthly Prices", header=None)
    names = [str(x).strip() for x in df.iloc[4].tolist()]
    units = [str(x).strip() for x in df.iloc[5].tolist()]
    rows = []
    for j in range(1, len(names)):
        name = names[j]
        if name in ("nan", "") or not any(k in name.lower() for k in _ENERGY_KEYS):
            continue
        for i in range(6, len(df)):
            period = str(df.iloc[i, 0]).strip()
            if not re.match(r"^\d{4}M\d{2}$", period):
                continue
            v = _num(df.iloc[i, j])
            if v is None:
                continue
            rows.append({
                "row_id": f"wb:{period}:{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}",
                "month": f"{period[:4]}-{period[5:]}",
                "commodity": name,
                "value": v,
                "unit": units[j] if j < len(units) else "",
                "source_file": "data/raw/worldbank/CMO-Historical-Data-Monthly.xlsx",
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.drop_duplicates("row_id").sort_values(["commodity", "month"])


def main() -> int:
    CLEAN.mkdir(parents=True, exist_ok=True)
    tables = {
        "eia_daily": clean_eia(),
        "pbs_weekly_pk": clean_pbs_weekly(),
        "pbs_monthly_city": clean_pbs_monthly(),
        "wb_monthly_energy": clean_worldbank(),
    }
    for name, df in tables.items():
        if df.empty:
            print(f"WARN: {name} is empty", file=sys.stderr)
            continue
        df.to_parquet(CLEAN / f"{name}.parquet", index=False)
        print(f"{name}: {len(df):,} rows -> data/clean/{name}.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
