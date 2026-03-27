from pathlib import Path
import pandas as pd
import re
import streamlit as st
import types

st.set_page_config(page_title="Raportal Agent PoC", layout="wide")

try:
    import google.generativeai as genai
except ImportError:
    genai = None


# API Key Authentication with Google Gemini
def check_authentication():
    """Check if user provided Google Gemini API key"""
    if "api_key" not in st.session_state:
        st.session_state.api_key = None
    
    with st.sidebar:
        st.markdown("<h2 style='text-align: center; color: #5b1fa6;'>Raportal Agent PoC</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666;'>Ayarlar</p>", unsafe_allow_html=True)
        
        if not st.session_state.api_key:
            api_key = st.text_input(
                "Google Gemini API Key:",
                type="password",
                placeholder="https://aistudio.google.com",
            )
            
            if st.button("Bağlan", type="primary", use_container_width=True):
                if api_key.strip():
                    try:
                        genai.configure(api_key=api_key)
                        # API key'i test et: model listesi alıp en az 1 model açık mı bak
                        available_models = list_models()
                        if not available_models:
                            st.warning("Model listesi alınamadı. Manuel giriş gerekecek.")
                            st.session_state.api_key = api_key
                            st.session_state.available_models = []
                            st.session_state.selected_model = "gemini-1"
                            st.session_state.manual_model = "gemini-1"
                        else:
                            st.session_state.api_key = api_key
                            st.session_state.available_models = available_models
                            st.session_state.selected_model = available_models[0]
                            st.success(f"API Key doğrulandı.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ API Key Hatası: {str(e)}")
                else:
                    st.error("❌ Lütfen API Key girin")
        else:
            st.success("✅ API Key Doğrulandı")
            if st.button("Çıkış Yap / Sıfırla", use_container_width=True):
                st.session_state.api_key = None
                st.session_state.available_models = []
                st.rerun()

if genai is None:
    st.error("google-generativeai paketi kurulmamış. Lütfen terminalde şu komutu çalıştırın:\n`pip install google-generativeai`")
    st.stop()


@st.cache_data
def list_models():
    if genai is None:
        raise RuntimeError("google.generativeai paketi yüklenmedi.")

    # API key'i kontrol et ve yapılandır
    api_key = st.session_state.get("api_key")
    if api_key:
        genai.configure(api_key=api_key)

    try:
        response = genai.list_models()

        # google.generativeai 0.8.6 returns generator
        if isinstance(response, types.GeneratorType):
            response = list(response)

        if isinstance(response, dict):
            model_list = response.get("models", [])
            return [m.get("name") for m in model_list if m.get("name")]
        elif isinstance(response, list):
            return [m.get("name") if isinstance(m, dict) else (m.name if hasattr(m, 'name') else str(m)) for m in response]
        else:
            return []
    except Exception as e:
        raise RuntimeError(f"Model listesi alınamadı: {e}") from e


@st.cache_data
def generate_ai_recommendation(query: str, reports: list, model_name: str) -> str:
    """Use Gemini AI to generate personalized recommendation"""
    try:
        model = genai.GenerativeModel(model_name)

        reports_text = "\n".join([
            f"- {r['name']} ({r['topic']}): {r['why']}"
            for r in reports
        ])

        prompt = f"""
        Kullanıcı sorgusu: "{query}"

        Önerilen raporlar:
        {reports_text}

        Lütfen Türkçe olarak, bu raporların kullanıcının ihtiyacını nasıl karşıladığını kısa ve öz bir şekilde açıklayınız (2-3 cümle).
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI açıklama alınamadı: {str(e)}"


check_authentication()

if st.session_state.api_key:
    genai.configure(api_key=st.session_state.api_key)
    
    # Model seçimi (Sidebar içinde)
    with st.sidebar:
        st.markdown("### Model Seçimi")
        model_options = st.session_state.get("available_models", [])
        
        if not model_options:
            model_options = ["gemini-1", "gemini-1.5", "gemini-1.5-pro", "gemini-2-lite"]
            
        with st.expander("Gelişmiş Seçenekler"):
            manual_model_input = st.text_input(
                "Manuel model adı",
                value=st.session_state.get("manual_model", ""),
                placeholder="Örn. gemini-1.5-pro"
            ).strip()
            if manual_model_input:
                st.session_state.manual_model = manual_model_input
                if manual_model_input not in model_options:
                    model_options.insert(0, manual_model_input)
                    
        if "selected_model" in st.session_state and st.session_state.selected_model in model_options:
            default_index = model_options.index(st.session_state.selected_model)
        else:
            default_index = 0
            
        selected_model = st.selectbox("Kullanılacak model", model_options, index=default_index)
        st.session_state.selected_model = selected_model


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


@st.cache_data
def generate_ai_recommendation(query: str, reports: list, model_name: str) -> str:
    """Use Gemini AI to generate personalized recommendation"""
    if model_name is None or model_name.strip() == "":
        model_name = "gemini-pro"

    try:
        model = genai.GenerativeModel(model_name)

        reports_text = "\n".join([
            f"- {r['name']} ({r['topic']}): {r['why']}"
            for r in reports
        ])

        prompt = f"""
        Kullanıcı sorgusu: "{query}"

        Önerilen raporlar:
        {reports_text}

        Lütfen Türkçe olarak, bu raporların kullanıcının ihtiyacını nasıl karşıladığını kısa ve öz bir şekilde açıklayınız (2-3 cümle).
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI açıklama alınamadı: {str(e)}"


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.title("Raportal Agent PoC")
st.caption("Kullanıcı ihtiyacına göre en uygun raporu öneren pilot ekran - AI destekli")

if not st.session_state.api_key:
    st.info("👋 Lütfen kenar çubuğundan (sol menü) API anahtarınızı girerek bağlanın.")
    st.stop()

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

selected_model = st.session_state.get("selected_model", "gemini-1")

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
            with st.spinner("AI tarafından analiz ediliyor..."):
                ai_explanation = generate_ai_recommendation(query, matches, selected_model)

            st.info(f"**AI Açıklaması:** {ai_explanation}")
            
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