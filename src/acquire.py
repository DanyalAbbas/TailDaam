"""Acquire raw data from original publishers.

Sources
-------
EIA-PETRO : US Energy Information Administration daily petroleum spot prices.
            Original publisher, US Government work -> public domain.
PBS-SPI   : Pakistan Bureau of Statistics weekly Sensitive Price Indicator
            reports (petrol super + high-speed diesel, PKR/litre).
            Government of Pakistan open publication.
WB-PINK   : World Bank Commodity Markets "Pink Sheet" monthly prices.
            CC BY 4.0.

All raw files are hashed and recorded in data/manifest.csv.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

from common import RAW, record_file

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
TIMEOUT = 25

EIA_SERIES = {
    "RBRTEd": ("brent_europe_spot", "USD/bbl"),
    "RWTCd": ("wti_cushing_spot", "USD/bbl"),
    "EER_EPMRU_PF4_RGC_DPGd": ("gasoline_gulf_regular", "USD/gal"),
    "EER_EPMRU_PF4_Y35NY_DPGd": ("gasoline_ny_regular", "USD/gal"),
    "EER_EPD2DXL0_PF4_RGC_DPGd": ("diesel_gulf_ulsd", "USD/gal"),
    "EER_EPD2DXL0_PF4_Y35NY_DPGd": ("diesel_ny_ulsd", "USD/gal"),
    "EER_EPJK_PF4_RGC_DPGd": ("jet_gulf", "USD/gal"),
    "EER_EPD2F_PF4_Y35NY_DPGd": ("heating_oil_ny", "USD/gal"),
    "EER_EPLLPA_PF4_Y44MB_DPGd": ("propane_mont_belvieu", "USD/gal"),
    "EER_EPD2DC_PF4_Y05LA_DPGd": ("diesel_la_carb", "USD/gal"),
    "EER_EPMRR_PF4_Y05LA_DPGd": ("gasoline_la_rbob", "USD/gal"),
}

PBS_WEEKLY_DATES = [
    # Thursdays for which PBS still serves the report (discovered 2026-10-21).
    "15.05.2025", "17.07.2025", "24.07.2025", "09.10.2025", "30.10.2025",
    "06.11.2025", "13.11.2025", "20.11.2025", "27.11.2025", "11.12.2025",
    "01.01.2026", "15.01.2026", "22.01.2026", "29.01.2026", "12.02.2026",
    "19.02.2026", "26.02.2026", "05.03.2026", "26.03.2026", "02.04.2026",
    "09.04.2026", "16.04.2026", "23.04.2026", "30.04.2026", "07.05.2026",
    "14.05.2026", "21.05.2026", "04.06.2026", "11.06.2026", "18.06.2026",
    "02.07.2026", "23.07.2026", "30.07.2026", "06.08.2026", "13.08.2026",
    "27.08.2026", "03.09.2026", "24.09.2026", "01.10.2026", "08.10.2026",
    "15.10.2026",
]

PBS_WEEKLY_URL = (
    "https://www.pbs.gov.pk/wp-content/uploads/2020/07/3.-SPI-Report-{date}.xlsx"
)
PBS_MONTHLY_URL = (
    "https://www.pbs.gov.pk/wp-content/uploads/2020/07/"
    "SPI-Monthly-Prices-Annex-9.xlsx"
)
WB_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "5d903e848db1d1b83e0ec8f744e55570-0350012021/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)


def download(url: str, dest: Path, retries: int = 3) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
            if r.status_code == 200 and r.content:
                dest.write_bytes(r.content)
                return True
            print(f"  HTTP {r.status_code} for {url}", file=sys.stderr)
        except Exception as e:  # network flake
            print(f"  attempt {attempt} failed for {url}: {e}", file=sys.stderr)
        time.sleep(1.5 * attempt)
    return False


def fetch_eia() -> int:
    got = 0
    for series_id, (name, _unit) in EIA_SERIES.items():
        url = f"https://www.eia.gov/dnav/pet/hist_xls/{series_id}.xls"
        dest = RAW / "eia" / f"{series_id}.xls"
        if dest.exists() and dest.stat().st_size > 1000:
            got += 1
            continue
        if download(url, dest):
            record_file(dest, "EIA-PETRO", "U.S. Energy Information Administration",
                        url, "public-domain (US Government work)",
                        query=f"daily spot price series {series_id} ({name})")
            got += 1
    return got


def _fetch_one_pbs(d: str) -> bool:
    url = PBS_WEEKLY_URL.format(date=d)
    dest = RAW / "pbs_spi" / f"spi_{d}.xlsx"
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    if download(url, dest, retries=2):
        record_file(dest, "PBS-SPI", "Pakistan Bureau of Statistics",
                    url, "Government of Pakistan open publication",
                    query=f"weekly SPI report week ended {d}")
        return True
    return False


def fetch_pbs_weekly() -> int:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_fetch_one_pbs, PBS_WEEKLY_DATES))
    return sum(results)


def fetch_pbs_monthly() -> bool:
    dest = RAW / "pbs_spi" / "SPI-Monthly-Prices-Annex-9.xlsx"
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    if download(PBS_MONTHLY_URL, dest):
        record_file(dest, "PBS-SPI", "Pakistan Bureau of Statistics",
                    PBS_MONTHLY_URL,
                    "Government of Pakistan open publication",
                    query="monthly average prices of essential items by city")
        return True
    return False


def fetch_worldbank() -> bool:
    dest = RAW / "worldbank" / "CMO-Historical-Data-Monthly.xlsx"
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    if download(WB_URL, dest):
        record_file(dest, "WB-PINK", "World Bank",
                    WB_URL, "CC BY 4.0",
                    query="Commodity Markets Pink Sheet historical monthly prices")
        return True
    return False


def main() -> int:
    print("Fetching EIA daily petroleum series...")
    n_eia = fetch_eia()
    print(f"  {n_eia}/{len(EIA_SERIES)} EIA series present")
    print("Fetching PBS weekly SPI reports...")
    n_pbs = fetch_pbs_weekly()
    print(f"  {n_pbs}/{len(PBS_WEEKLY_DATES)} PBS weekly reports present")
    print("Fetching PBS monthly annex...")
    print("  ok" if fetch_pbs_monthly() else "  FAILED")
    print("Fetching World Bank Pink Sheet...")
    print("  ok" if fetch_worldbank() else "  FAILED")
    if n_eia == 0 and n_pbs == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
