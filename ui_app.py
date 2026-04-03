from pathlib import Path
import html
import pandas as pd
import re
import streamlit as st
import types

st.set_page_config(page_title="Raportal Recommendation Copilot", layout="wide")

try:
    import google.generativeai as genai
except ImportError:
    genai = None


APP_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #f7f9fc;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #8c28e8 !important;
        background-image: none !important;
        border-right: none !important;
    }

    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    .sidebar-brand {
        display: flex;
        align-items: center;
        padding: 1.5rem 1rem 2rem 1rem;
        font-weight: 800;
        font-size: 1.4rem;
        letter-spacing: -0.01em;
    }

    .sidebar-menu-item {
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        margin: 0.25rem 0.75rem;
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.95rem;
        cursor: pointer;
        transition: all 0.2s;
        text-decoration: none;
        color: rgba(255, 255, 255, 0.8) !important;
    }

    .sidebar-menu-item.active {
        background-color: rgba(255, 255, 255, 0.15) !important;
        color: #ffffff !important;
    }

    .sidebar-menu-item:hover {
        background-color: rgba(255, 255, 255, 0.1);
    }

    /* Main Content */
    .stHeader {
        background: transparent !important;
    }

    .main-header {
        display: flex;
        align-items: center;
        padding-bottom: 2rem;
    }

    .header-logo {
        background: #f3e8ff;
        color: #8c28e8;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 12px;
        font-size: 20px;
    }

    .header-title {
        font-weight: 700;
        font-size: 1.25rem;
        color: #1a1a1a;
    }

    .welcome-text h1 {
        font-weight: 800;
        font-size: 2.2rem;
        margin-bottom: 0.5rem;
        color: #1a1a1a;
    }

    .welcome-text p {
        color: #6b7280;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }

    /* Workflow Indicator */
    .workflow-container {
        display: flex;
        align-items: center;
        margin-bottom: 2.5rem;
        gap: 12px;
    }

    .workflow-label {
        font-weight: 700;
        font-size: 0.75rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-right: 12px;
    }

    .workflow-step {
        display: flex;
        align-items: center;
        font-size: 0.9rem;
        font-weight: 600;
        color: #a855f7;
    }

    .workflow-step span {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border: 2px solid #a855f7;
        border-radius: 50%;
        margin-right: 8px;
        font-size: 0.7rem;
    }

    .workflow-arrow {
        color: #d1d5db;
        margin: 0 4px;
    }

    /* Navigation Cards */
    .nav-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin-bottom: 2rem;
    }

    .nav-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: all 0.3s;
        cursor: pointer;
        position: relative;
    }

    .nav-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
        border-color: #8c28e8;
    }

    .card-num {
        position: absolute;
        top: 1rem;
        right: 1rem;
        color: #e5e7eb;
        font-size: 0.75rem;
        font-weight: 700;
    }

    .card-icon {
        width: 48px;
        height: 48px;
        background: #fdfbff;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        margin-bottom: 1.25rem;
        color: #8c28e8;
    }

    .card-title {
        font-weight: 700;
        font-size: 1.1rem;
        color: #1a1a1a;
        margin-bottom: 0.5rem;
    }

    .card-desc {
        font-size: 0.9rem;
        color: #6b7280;
        line-height: 1.5;
    }

    /* Result Cards */
    .result-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #e5e7eb;
        border-left: 6px solid #8c28e8;
        margin-bottom: 1.5rem;
    }

</style>
"""

st.markdown(APP_CSS, unsafe_allow_html=True)


if genai is None:
    st.error("google-generativeai paketi kurulmamış. Lütfen terminalde şu komutu çalıştırın:\n`pip install google-generativeai`")
    st.stop()


@st.cache_data
def list_models():
    if genai is None:
        raise RuntimeError("google.generativeai paketi yüklenmedi.")

    api_key = st.session_state.get("api_key")
    if api_key:
        genai.configure(api_key=api_key)

    try:
        response = genai.list_models()

        if isinstance(response, types.GeneratorType):
            response = list(response)

        if isinstance(response, dict):
            model_list = response.get("models", [])
            return [m.get("name") for m in model_list if m.get("name")]
        if isinstance(response, list):
            return [
                m.get("name") if isinstance(m, dict)
                else (m.name if hasattr(m, "name") else str(m))
                for m in response
            ]
        return []
    except Exception as e:
        raise RuntimeError(f"Model listesi alınamadı: {e}") from e


@st.cache_data
def generate_ai_recommendation(query: str, reports: list, model_name: str) -> str:
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


# API Key Authentication with Google Gemini
def check_authentication():
    if "api_key" not in st.session_state:
        st.session_state.api_key = None

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <span style="font-size: 1.6rem; margin-right: 10px;">📊</span> Raportal Agent
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### Gemini Bağlantısı")

        if not st.session_state.api_key:
            api_key = st.text_input(
                "Google Gemini API Key",
                type="password",
                placeholder="https://aistudio.google.com",
            )

            if st.button("Bağlan", type="primary", use_container_width=True):
                if api_key.strip():
                    try:
                        genai.configure(api_key=api_key)
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
                            st.success("API Key doğrulandı.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ API Key Hatası: {str(e)}")
                else:
                    st.error("❌ Lütfen API Key girin")
        else:
            st.success("✅ Bağlantı Aktif")
            if st.button("Çıkış Yap / Sıfırla", use_container_width=True):
                st.session_state.api_key = None
                st.session_state.available_models = []
                st.rerun()

            st.markdown("<br><hr style='border-color: rgba(255,255,255,0.2)'><br>", unsafe_allow_html=True)
            st.markdown(
                """
                <div class="sidebar-menu-item active">🏠 Dashboard</div>
                <div class="sidebar-menu-item">🔍 Rapor Öner</div>
                <div class="sidebar-menu-item">📂 Metadata Listesi</div>
                <div class="sidebar-menu-item">📊 Rapor Kullanım Analizi</div>
                <div class="sidebar-menu-item">💡 Dashboard Önerisi</div>
                <div class="sidebar-menu-item">⚖️ KPI Kıyaslama</div>
                <div class="sidebar-menu-item">ℹ️ Hakkında</div>
                """,
                unsafe_allow_html=True,
            )


check_authentication()

if st.session_state.api_key:
    genai.configure(api_key=st.session_state.api_key)

    with st.sidebar:
        st.markdown("### Model Seçimi")
        model_options = st.session_state.get("available_models", [])

        if not model_options:
            model_options = ["gemini-1", "gemini-1.5", "gemini-1.5-pro", "gemini-2-lite"]

        with st.expander("Gelişmiş Seçenekler"):
            manual_model_input = st.text_input(
                "Manuel model adı",
                value=st.session_state.get("manual_model", ""),
                placeholder="Örn. gemini-1.5-pro",
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
                "score": score,
            })

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results[:3]


def safe_text(value) -> str:
    return html.escape(str(value)) if value not in (None, "") else "-"


# Main Content Area Header
st.markdown(
    """
    <div class="main-header">
        <div class="header-logo">⚡</div>
        <div class="header-title">Raportal AI Assistant</div>
    </div>
    <div class="welcome-text">
        <h1>Hoş Geldiniz 👋</h1>
        <p>Raportal Agent — Metadata destekli ve AI tabanlı akıllı rapor öneri asistanı</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Workflow Steps for Raportal
st.markdown(
    """
    <div class="workflow-container">
        <div class="workflow-label">ANALİZ AKIŞI</div>
        <div class="workflow-step"><span>1</span> İhtiyaç Tanımı</div>
        <div class="workflow-arrow">→</div>
        <div class="workflow-step"><span>2</span> Metadata Eşleşme</div>
        <div class="workflow-arrow">→</div>
        <div class="workflow-step"><span>3</span> AI Skorlama</div>
        <div class="workflow-arrow">→</div>
        <div class="workflow-step"><span>4</span> Rapor Önerisi</div>
        <div class="workflow-arrow">→</div>
        <div class="workflow-step"><span>5</span> Detaylı Analiz</div>
    </div>
    """,
    unsafe_allow_html=True,
)


if not st.session_state.api_key:
    st.info("👋 Sol menüden API anahtarını girerek devam edebilirsin.")
    st.stop()

# Load Data
try:
    df, source_name = load_metadata()
    df, col_map = prepare_columns(df)
except Exception as e:
    st.error(f"Dosya yüklenemedi: {e}")
    st.stop()

selected_model = st.session_state.get("selected_model", "gemini-1")


# 6-Card Grid Layout
col1, col2, col3 = st.columns(3)

if "sample_query" not in st.session_state:
    st.session_state.sample_query = ""

# Row 1
with col1:
    st.markdown(
        """
        <div class="nav-card">
            <div class="card-num">1</div>
            <div class="card-icon">📉</div>
            <div class="card-title">Churn Analizi</div>
            <div class="card-desc">Müşteri kayıp oranı ve risk segmentlerini detaylı inceleyin.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Senaryoyu Seç", key="card1", use_container_width=True):
        st.session_state.sample_query = "churn oranini takip etmek istiyorum"

with col2:
    st.markdown(
        """
        <div class="nav-card">
            <div class="card-num">2</div>
            <div class="card-icon">⚠️</div>
            <div class="card-title">Risk Takibi</div>
            <div class="card-desc">Yenileme ihtimali düşük firmaları ve alarm sinyallerini görün.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Senaryoyu Seç", key="card2", use_container_width=True):
        st.session_state.sample_query = "yenileme riski olan firmalari gormek istiyorum"

with col3:
    st.markdown(
        """
        <div class="nav-card">
            <div class="card-num">3</div>
            <div class="card-icon">🚀</div>
            <div class="card-title">Erken Yenileme</div>
            <div class="card-desc">Fırsat olan müşterileri ve davranış sinyallerini analiz edin.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Senaryoyu Seç", key="card3", use_container_width=True):
        st.session_state.sample_query = "erken yenileme firsatlarini gormek istiyorum"

# Row 2
col4, col5, col6 = st.columns(3)
with col4:
    st.markdown(
        """
        <div class="nav-card">
            <div class="card-num">4</div>
            <div class="card-icon">➕</div>
            <div class="card-title">Ek Ürün Fırsatı</div>
            <div class="card-desc">Çapraz satış ve ek ürün yenileme ilişkisini keşfedin.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Senaryoyu Seç", key="card4", use_container_width=True):
        st.session_state.sample_query = "ek urun kullanim ve yenileme durumunu gormek istiyorum"

with col5:
    st.markdown(
        """
        <div class="nav-card">
            <div class="card-num">5</div>
            <div class="card-icon">📊</div>
            <div class="card-title">Genel Performans</div>
            <div class="card-desc">Satış ve operasyonel verimlilik raporlarını karşılaştırın.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Senaryoyu Seç", key="card5", use_container_width=True):
        st.session_state.sample_query = "genel satis ve performans durumunu gormek istiyorum"

with col6:
    st.markdown(
        """
        <div class="nav-card">
            <div class="card-num">6</div>
            <div class="card-icon">📋</div>
            <div class="card-title">Metadata Yönetimi</div>
            <div class="card-desc">Rapor listesini ve detaylı metadata bilgilerini yönetin.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Senaryoyu Seç", key="card6", use_container_width=True):
        st.session_state.sample_query = "ilgili raporlardaki metadata listesini gorebilir miyim"

st.markdown('<div class="section-title">İhtiyacı tanımla</div>', unsafe_allow_html=True)
st.markdown('<div class="query-card">', unsafe_allow_html=True)

query = st.text_input(
    "İş ihtiyacını yaz",
    value=st.session_state.sample_query,
    placeholder="Örn: yenileme riski olan firmalari görmek istiyorum",
    label_visibility="visible",
)

search_clicked = st.button("Rapor Öner", type="primary")

st.markdown('</div>', unsafe_allow_html=True)

if search_clicked:
    if not query.strip():
        st.warning("Lütfen bir ihtiyaç veya soru gir.")
    else:
        matches = search_reports(df, query, col_map)

        if not matches:
            st.error("Bu ihtiyaca uygun rapor bulunamadı.")
        else:
            with st.spinner("AI öneri açıklaması hazırlanıyor..."):
                ai_explanation = generate_ai_recommendation(query, matches, selected_model)

            st.markdown('<div class="section-title">AI değerlendirmesi</div>', unsafe_allow_html=True)
            st.info(ai_explanation)

            st.markdown('<div class="section-title">Önerilen raporlar</div>', unsafe_allow_html=True)

            for i, m in enumerate(matches, start=1):
                badge_list = []
                if m.get("topic"):
                    badge_list.append(f'<span class="badge">{safe_text(m["topic"])}</span>')
                if m.get("score") is not None:
                    badge_list.append(f'<span class="badge">Skor: {safe_text(m["score"])}</span>')

                badges_html = "".join(badge_list)

                st.markdown(
                    f"""
                    <div class="result-card">
                        <div class="result-title">{i}. {safe_text(m['name'])}</div>
                        <div style="margin-bottom:10px;">{badges_html}</div>

                        <div class="field-label">Ana Konu</div>
                        <div class="field-value">{safe_text(m['topic'])}</div>

                        <div class="field-label">Neden Önerildi?</div>
                        <div class="field-value">{safe_text(m['why'])}</div>

                        <div class="field-label">Ana KPI'lar</div>
                        <div class="field-value">{safe_text(m['kpis'])}</div>

                        <div class="field-label">Benzer Raporlar</div>
                        <div class="field-value">{safe_text(m['similar'])}</div>

                        <div class="field-label">Rapor Yolu</div>
                        <div class="field-value">{safe_text(m['path'])}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )