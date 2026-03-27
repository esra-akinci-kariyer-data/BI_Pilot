from pathlib import Path
import pandas as pd
import re
import streamlit as st


CUSTOM_CSS = """
<style>
    .stApp {
        background-color: #f7f5fb;
    }

    h1, h2, h3 {
        color: #5b1fa6;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    div[data-testid="stTextInput"] input {
        border: 2px solid #c9b3f2;
        border-radius: 12px;
        padding: 0.6rem;
    }

    div[data-testid="stTextInput"] input:focus {
        border-color: #7b2cbf;
        box-shadow: 0 0 0 1px #7b2cbf;
    }

    div.stButton > button {
        background-color: #7b2cbf;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 0.6rem 1rem;
        font-weight: 600;
    }

    div.stButton > button:hover {
        background-color: #5a189a;
        color: white;
    }

    div[data-testid="metric-container"] {
        background-color: #efe7fb;
        border: 1px solid #d6c2f3;
        padding: 12px;
        border-radius: 14px;
    }

    div[data-testid="stAlert"] {
        border-radius: 14px;
    }

    .report-card {
        background: white;
        border: 1px solid #e4d7f7;
        border-left: 8px solid #7b2cbf;
        border-radius: 16px;
        padding: 18px;
        margin-bottom: 18px;
        box-shadow: 0 2px 10px rgba(91, 31, 166, 0.08);
    }

    .report-title {
        color: #5b1fa6;
        font-size: 28px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .label {
        color: #6b7280;
        font-weight: 600;
    }

    .value {
        color: #111827;
    }
</style>
"""


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

        for real_col, real_col_n in normalized_cols.items():
            if real_col_n == candidate_n:
                return real_col

        for real_col, real_col_n in normalized_cols.items():
            if candidate_n in real_col_n or real_col_n in candidate_n:
                return real_col

    return None


@st.cache_data
def load_metadata():
    base_dir = Path(__file__).resolve().parent

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

    if file_path.suffix.lower() == ".xlsx":
        df = pd.read_excel(file_path)
    else:
        try:
            df = pd.read_csv(file_path, sep=";", encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, sep=";", encoding="cp1254")

    df = clean_columns(df)
    return df, file_path.name


def prepare_columns(df: pd.DataFrame):
    col_map = {
        "name": find_best_column(df, ["Name", "Rapor Adı", "RaporAdi"]),
        "topic": find_best_column(df, ["Ana Konu"]),
        "desc": find_best_column(df, ["Bu rapor neyi gösteriyor?", "Bu rapor neyi gosteriyor"]),
        "kpi": find_best_column(df, ["Ana KPI'lar", "Ana KPI’lar", "Ana KPIlar"]),
        "similar": find_best_column(df, ["Benzer Raporlar"]),
        "path": find_best_column(df, ["Path", "RaporYolu"]),
    }

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
        (col_map["similar"], 1),
        (col_map["path"], 1),
    ]

    for col, weight in rules:
        value = normalize_text(row.get(col, ""))
        if not value:
            continue

        for token in tokens:
            if token in value:
                score += weight

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
                "similar": row.get(col_map["similar"], ""),
                "path": row.get(col_map["path"], ""),
                "score": score
            })

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results[:3]


st.set_page_config(page_title="Raportal Agent PoC", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.title("Raportal Agent PoC")
st.caption("Kullanıcı ihtiyacına göre en uygun raporu öneren pilot ekran")

try:
    df, source_name = load_metadata()
    df, col_map = prepare_columns(df)
except Exception as e:
    st.error(f"Dosya yüklenemedi: {e}")
    st.stop()

c1, c2 = st.columns([2, 1])
with c1:
    st.success(f"Metadata yüklendi: {source_name}")
with c2:
    st.info(f"Pilot rapor sayısı: {len(df)}")

st.markdown("### Hazır örnek sorular")

e1, e2, e3, e4 = st.columns(4)

if "sample_query" not in st.session_state:
    st.session_state.sample_query = ""

with e1:
    if st.button("Churn oranı"):
        st.session_state.sample_query = "churn oranini takip etmek istiyorum"

with e2:
    if st.button("Yenileme riski"):
        st.session_state.sample_query = "yenileme riski olan firmalari gormek istiyorum"

with e3:
    if st.button("Erken yenileme"):
        st.session_state.sample_query = "erken yenileme firsatlarini gormek istiyorum"

with e4:
    if st.button("Ek ürün kullanımı"):
        st.session_state.sample_query = "ek urun kullanim ve yenileme durumunu gormek istiyorum"

query = st.text_input(
    "İhtiyacını yaz",
    value=st.session_state.sample_query,
    placeholder="Örn: yenileme riski olan firmalari gormek istiyorum"
)

if st.button("Rapor Öner", type="primary"):
    if not query.strip():
        st.warning("Lütfen bir soru yaz.")
    else:
        matches = search_reports(df, query, col_map)

        if not matches:
            st.error("Uygun rapor bulunamadı.")
        else:
            st.subheader("Önerilen Raporlar")

            for i, m in enumerate(matches, start=1):
                left, right = st.columns([6, 1])

                with left:
                    st.markdown(
                        f"""
                        <div class="report-card">
                            <div class="report-title">{i}. {m['name']}</div>
                            <p><span class="label">Ana Konu:</span> <span class="value">{m['topic']}</span></p>
                            <p><span class="label">Neden:</span> <span class="value">{m['why']}</span></p>
                            <p><span class="label">KPI'lar:</span> <span class="value">{m['kpis']}</span></p>
                            <p><span class="label">Benzer Raporlar:</span> <span class="value">{m['similar']}</span></p>
                            <p><span class="label">Path:</span> <span class="value">{m['path']}</span></p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with right:
                    st.metric("Skor", m["score"])