"""
Raportal Link Generator
-----------------------
Mevcut metadata CSV'sinden tüm raporların raportal.kariyer.net linklerini üretir
ve raportal_links.csv dosyasına kaydeder.

Çalıştırma:
    py raportal_link_generator.py
"""

import pandas as pd
from urllib.parse import quote
from pathlib import Path

BASE_URL = "https://raportal.kariyer.net"

PREFERRED_FILES = [
    "db_exported_catalog_v2.csv",
    "db_exported_catalog.csv",
    "raportal_metadata_master.xlsx.csv",
    "pilot_rapor_metadata_clean.csv",
]


def build_url(path: str, tip: str) -> str:
    clean_path = str(path).strip("/")
    base_type = "powerbi" if "dashboard" in str(tip).lower() else "report"
    encoded_path = quote(clean_path, safe="/")
    return f"{BASE_URL}/home/{base_type}/{encoded_path}"


def load_csv(base_dir: Path) -> pd.DataFrame:
    for name in PREFERRED_FILES:
        p = base_dir / name
        if p.exists():
            try:
                df = pd.read_csv(p, sep=";", encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(p, sep=";", encoding="cp1254")
            print(f"Kaynak dosya: {name}  ({len(df)} satır)")
            return df
    raise FileNotFoundError("Metadata CSV bulunamadı.")


def generate_links(base_dir: Path = None) -> pd.DataFrame:
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent

    df = load_csv(base_dir)

    # Sütun adlarını temizle
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]

    # Silinen ve test klasörlerini çıkar
    if "Klasör1" in df.columns:
        df = df[~df["Klasör1"].str.contains("Silinen Raporlar", na=False)]
        df = df[~df["Klasör1"].str.contains("test", case=False, na=False)]

    # URL üret
    path_col = "Path" if "Path" in df.columns else df.columns[2]
    tip_col = "Tip" if "Tip" in df.columns else "Report"

    df["URL"] = df.apply(
        lambda row: build_url(row.get(path_col, ""), row.get(tip_col, "Report")),
        axis=1,
    )

    # Çıktı için kolonları seç
    keep_cols = []
    for col in ["ItemID", "Name", "Klasör1", "Path", "Tip", "Hidden", "Kullanim", "URL"]:
        if col in df.columns:
            keep_cols.append(col)

    result = df[keep_cols].copy()
    result = result.sort_values(["Klasör1", "Name"] if "Klasör1" in result.columns else ["Name"])

    output_path = base_dir / "raportal_links.csv"
    result.to_csv(output_path, index=False, sep=";", encoding="utf-8-sig")

    print(f"\n✅ {len(result)} rapor linki oluşturuldu → {output_path}")
    return result


if __name__ == "__main__":
    df = generate_links()
    print("\n--- İlk 20 rapor ---")
    show_cols = [c for c in ["Name", "Tip", "URL"] if c in df.columns]
    print(df[show_cols].head(20).to_string(index=False))
