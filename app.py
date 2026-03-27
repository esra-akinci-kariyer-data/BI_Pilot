from pathlib import Path
import pandas as pd
import re


def normalize_text(text: str) -> str:
    text = str(text)
    text = text.replace("\ufeff", "")
    text = text.lower()

    replacements = {
        "ı": "i", "İ": "i",
        "ş": "s", "Ş": "s",
        "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u",
        "ö": "o", "Ö": "o",
        "ç": "c", "Ç": "c",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def find_best_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized_cols = {col: normalize_text(col) for col in df.columns}

    for candidate in candidates:
        candidate_n = normalize_text(candidate)

        # birebir eşleşme
        for real_col, real_col_n in normalized_cols.items():
            if real_col_n == candidate_n:
                return real_col

        # içerme eşleşmesi
        for real_col, real_col_n in normalized_cols.items():
            if candidate_n in real_col_n or real_col_n in candidate_n:
                return real_col

    return None


def load_metadata(base_dir: Path) -> pd.DataFrame:
    print("Klasör:", base_dir)
    print("Klasördeki dosyalar:")
    for f in base_dir.iterdir():
        print("-", f.name)

    preferred_names = [
        "pilot_rapor_metadata_clean.csv",
        "pilot_rapor_metadata.csv",
        "pilot_rapor_metadata.xlsx",
        "pilot_rapor_metadata.csv.xlsx",
    ]

    file_path = None

    for name in preferred_names:
        p = base_dir / name
        if p.exists():
            file_path = p
            break

    if file_path is None:
        csv_files = list(base_dir.glob("*.csv"))
        xlsx_files = list(base_dir.glob("*.xlsx"))

        if csv_files:
            file_path = csv_files[0]
        elif xlsx_files:
            file_path = xlsx_files[0]
        else:
            raise FileNotFoundError("Klasörde okunacak .csv veya .xlsx dosyası bulunamadı.")

    print("\nOkunan dosya:", file_path.name)

    if file_path.suffix.lower() == ".xlsx":
        df = pd.read_excel(file_path)
    else:
        # önce UTF-8 dene, olmazsa cp1254
        try:
            df = pd.read_csv(file_path, sep=";", encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, sep=";", encoding="cp1254")

    df = clean_columns(df)
    return df


def prepare_columns(df: pd.DataFrame):
    col_map = {
        "name": find_best_column(df, ["Name", "Rapor Adı", "RaporAdi"]),
        "topic": find_best_column(df, ["Ana Konu"]),
        "desc": find_best_column(df, ["Bu rapor neyi gösteriyor?", "Bu rapor neyi gosteriyor"]),
        "kpi": find_best_column(df, ["Ana KPI'lar", "Ana KPI’lar", "Ana KPIlar"]),
        "time": find_best_column(df, ["Zaman Seviyesi"]),
        "filters": find_best_column(df, ["Kullanılan Filtreler", "Kullanilan Filtreler"]),
        "target": find_best_column(df, ["Hedef Kullanıcı", "Hedef Kullanici"]),
        "auth": find_best_column(df, ["Yetkili Gruplar / Kullanıcılar", "Yetkili Gruplar / Kullanicilar"]),
        "similar": find_best_column(df, ["Benzer Raporlar"]),
        "note": find_best_column(df, ["Not"]),
    }

    print("\nBulunan kolon eşleşmeleri:")
    for k, v in col_map.items():
        print(f"- {k}: {v}")

    # Eksik kolon varsa boş kolon üret
    for key, col_name in col_map.items():
        if col_name is None:
            fallback_name = f"__{key}__"
            df[fallback_name] = ""
            col_map[key] = fallback_name

    return df, col_map


def score_report(row, query: str, col_map: dict) -> int:
    query_n = normalize_text(query)
    tokens = query_n.split()

    score = 0
    rules = [
        (col_map["name"], 5),
        (col_map["topic"], 4),
        (col_map["kpi"], 3),
        (col_map["desc"], 2),
        (col_map["filters"], 1),
        (col_map["similar"], 1),
        (col_map["note"], 1),
    ]

    for col, weight in rules:
        value = normalize_text(row.get(col, ""))
        if not value:
            continue

        for token in tokens:
            if token in value:
                score += weight

    # ek kurallar
    name_text = normalize_text(row.get(col_map["name"], ""))
    topic_text = normalize_text(row.get(col_map["topic"], ""))
    desc_text = normalize_text(row.get(col_map["desc"], ""))
    all_text = " ".join([name_text, topic_text, desc_text])

    if "churn" in query_n and "churn" in all_text:
        score += 5

    if "risk" in query_n and ("risk" in all_text or "alarm" in all_text):
        score += 5

    if "yenileme" in query_n and "erken" in query_n and "erken" in all_text:
        score += 5

    if "ek" in query_n and "urun" in query_n and ("ek urun" in all_text or "hak" in all_text):
        score += 5

    return score


def search_reports(df: pd.DataFrame, query: str, col_map: dict):
    results = []

    for _, row in df.iterrows():
        score = score_report(row, query, col_map)

        if score > 0:
            results.append({
                "name": row.get(col_map["name"], ""),
                "topic": row.get(col_map["topic"], ""),
                "why": row.get(col_map["desc"], ""),
                "kpis": row.get(col_map["kpi"], ""),
                "time": row.get(col_map["time"], ""),
                "filters": row.get(col_map["filters"], ""),
                "target": row.get(col_map["target"], ""),
                "similar": row.get(col_map["similar"], ""),
                "note": row.get(col_map["note"], ""),
                "score": score
            })

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results[:3]


def main():
    base_dir = Path(__file__).resolve().parent
    df = load_metadata(base_dir)
    df, col_map = prepare_columns(df)

    print("\nİlk satırlar:")
    print(df.head())
    print("\nKolonlar:")
    print(df.columns.tolist())

    query = input("\nSorunu yaz: ").strip()
    matches = search_reports(df, query, col_map)

    if not matches:
        print("\nUygun rapor bulunamadi.")
        return

    print("\nOnerilen raporlar:\n")
    for i, m in enumerate(matches, start=1):
        print(f"{i}. {m['name']}")
        print(f"   Ana konu: {m['topic']}")
        print(f"   Neden: {m['why']}")
        print(f"   KPI'lar: {m['kpis']}")
        print(f"   Zaman seviyesi: {m['time']}")
        print(f"   Kullanilan filtreler: {m['filters']}")
        print(f"   Hedef kullanici: {m['target']}")
        print(f"   Benzer raporlar: {m['similar']}")
        print(f"   Not: {m['note']}")
        print(f"   Skor: {m['score']}\n")


if __name__ == "__main__":
    main()

