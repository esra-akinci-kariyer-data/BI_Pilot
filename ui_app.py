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

    section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea {
        background-color: #ffffff !important;
        color: #1a1a1a !important;
        border-radius: 10px !important;
    }

    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 12px !important;
    }

    section[data-testid="stSidebar"] [data-testid="stExpander"] * {
        color: #ffffff !important;
    }

    /* Menu Separation */
    .sidebar-menu-section {
        margin-top: 2rem;
    }

    .sidebar-brand {
        display: flex;
        align-items: center;
        padding: 1.5rem 1rem 2rem 1rem;
        font-weight: 800;
        font-size: 1.4rem;
        letter-spacing: -0.01em;
        color: #ffffff !important;
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

    /* Section Titles */
    .section-title {
        font-weight: 700;
        font-size: 1.1rem;
        color: #1a1a1a;
        margin: 2.5rem 0 1.25rem 0;
        display: flex;
        align-items: center;
    }

    /* Navigation Cards */
    .nav-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: all 0.3s;
        cursor: pointer;
        position: relative;
        height: 100%;
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

    .result-title {
        font-weight: 700;
        font-size: 1.2rem;
        color: #1a1a1a;
        margin-bottom: 0.75rem;
    }

    .badge {
        display: inline-block;
        padding: 2px 10px;
        background: #f3e8ff;
        color: #8c28e8;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 8px;
    }

    .field-label {
        font-size: 0.75rem;
        font-weight: 700;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 1rem;
    }

    .field-value {
        font-size: 0.95rem;
        color: #374151;
        line-height: 1.6;
    }

    /* Query Card */
    .query-card {
        background: white;
        padding: 2rem;
        border-radius: 20px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 2rem;
    }
</style>
"""

st.markdown(APP_CSS, unsafe_allow_html=True)


if genai is None:
    st.error("google-generativeai paketi kurulmamış. Lütfen terminalde şu komutu çalıştırın:\n`pip install google-generativeai`")
    st.stop()


@st.cache_data
def list_models():
    api_key = st.session_state.get("api_key")
    if api_key:
        genai.configure(api_key=api_key)
    try:
        response = genai.list_models()
        if isinstance(response, types.GeneratorType):
            response = list(response)
        return [m.name for m in response if hasattr(m, "name")]
    except:
        return []


@st.cache_data
def generate_ai_recommendation(query: str, reports: list, model_name: str) -> str:
    if not model_name:
        model_name = "gemini-1.5-flash"
    try:
        model = genai.GenerativeModel(model_name)
        reports_text = "\n".join([f"- {r['name']} ({r['topic']}): {r['why']}" for r in reports])
        prompt = f"""Kullanıcı sorgusu: "{query}"\n\nÖnerilen raporlar:\n{reports_text}\n\nLütfen Türkçe olarak, bu raporların kullanıcının ihtiyacını nasıl karşıladığını kısa ve öz bir şekilde açıklayınız (2-3 cümle)."""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI açıklama alınamadı: {str(e)}"


def check_authentication():
    if "api_key" not in st.session_state:
        st.session_state.api_key = None

    with st.sidebar:
        st.markdown('<div class="sidebar-brand">📊 Raportal Agent</div>', unsafe_allow_html=True)
        
        if not st.session_state.api_key:
            st.markdown("#### Gemini Bağlantısı")
            api_key = st.text_input("Google Gemini API Key", type="password", placeholder="https://aistudio.google.com")
            if st.button("Bağlan", type="primary", use_container_width=True):
                if api_key.strip():
                    try:
                        genai.configure(api_key=api_key)
                        models = list_models()
                        st.session_state.api_key = api_key
                        st.session_state.available_models = models if models else ["gemini-1.5-flash", "gemini-1.5-pro"]
                        st.session_state.selected_model = st.session_state.available_models[0]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Hata: {str(e)}")
        else:
            st.success("✅ Bağlantı Aktif")
            st.markdown("### Model Seçimi")
            model_options = st.session_state.get("available_models", ["gemini-1.5-flash", "gemini-1.5-pro"])
            selected_model = st.selectbox("Kullanılacak model", model_options, key="sidebar_model_select")
            st.session_state.selected_model = selected_model

            st.markdown('<div class="sidebar-menu-section">', unsafe_allow_html=True)
            st.markdown("""
                <div class="sidebar-menu-item active">🏠 Dashboard</div>
                <div class="sidebar-menu-item">🔍 Rapor Öner</div>
                <div class="sidebar-menu-item">📂 Metadata Listesi</div>
                <div class="sidebar-menu-item">📊 Rapor Kullanım Analizi</div>
                <div class="sidebar-menu-item">💡 Dashboard Önerisi</div>
                <div class="sidebar-menu-item">⚖️ KPI Kıyaslama</div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("Çıkış Yap / Sıfırla", use_container_width=True):
                st.session_state.api_key = None
                st.rerun()

def normalize_text(text: str) -> str:
    text = str(text).lower()
    replacements = {"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    return df

def find_best_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for cand in candidates:
        cand_n = normalize_text(cand)
        for col in df.columns:
            if normalize_text(col) == cand_n or cand_n in normalize_text(col):
                return col
    return None

@st.cache_data
def load_metadata():
    base_dir = Path(__file__).resolve().parent
    file_path = base_dir / "pilot_rapor_metadata_clean.csv"
    if not file_path.exists():
        file_path = next(base_dir.glob("*.csv"), None)
    
    if not file_path:
        raise FileNotFoundError("Metadata dosyası bulunamadı.")
    
    try:
        df = pd.read_csv(file_path, sep=";", encoding="utf-8-sig")
    except:
        df = pd.read_csv(file_path, sep=";", encoding="cp1254")
    return clean_columns(df), file_path.name

def prepare_columns(df: pd.DataFrame):
    col_map = {
        "name": find_best_column(df, ["Name", "Rapor Adı"]),
        "topic": find_best_column(df, ["Ana Konu"]),
        "desc": find_best_column(df, ["Bu rapor neyi gösteriyor?"]),
        "kpi": find_best_column(df, ["Ana KPI'lar"]),
        "similar": find_best_column(df, ["Benzer Raporlar"]),
        "path": find_best_column(df, ["Path", "RaporYolu"]),
    }
    for k, v in col_map.items():
        if v is None:
            df[f"__{k}__"] = "-"
            col_map[k] = f"__{k}__"
    return df, col_map

def search_reports(df, query, col_map):
    query_n = normalize_text(query)
    results = []
    for _, row in df.iterrows():
        score = 0
        all_text = normalize_text(str(row.get(col_map["name"])) + " " + str(row.get(col_map["topic"])) + " " + str(row.get(col_map["desc"])))
        for token in query_n.split():
            if token in all_text: score += 1
        if score > 0:
            results.append({
                "name": row.get(col_map["name"]), "topic": row.get(col_map["topic"]),
                "why": row.get(col_map["desc"]), "kpis": row.get(col_map["kpi"]),
                "similar": row.get(col_map["similar"]), "path": row.get(col_map["path"]),
                "score": score
            })
    return sorted(results, key=lambda x: x["score"], reverse=True)[:3]

def safe_text(val):
    return html.escape(str(val)) if val and str(val).strip() != "nan" else "-"

# --- APP START ---
check_authentication()

st.markdown("""
<div class="main-header"><div class="header-logo">⚡</div><div class="header-title">Raportal AI Assistant</div></div>
<div class="welcome-text"><h1>Hoş Geldiniz 👋</h1><p>Raportal Agent — Akıllı rapor öneri asistanı</p></div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="workflow-container">
    <div class="workflow-label">ANALİZ AKIŞI</div>
    <div class="workflow-step"><span>1</span> İhtiyaç</div><div class="workflow-arrow">→</div>
    <div class="workflow-step"><span>2</span> Eşleşme</div><div class="workflow-arrow">→</div>
    <div class="workflow-step"><span>3</span> AI Skor</div><div class="workflow-arrow">→</div>
    <div class="workflow-step"><span>4</span> Öneri</div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.api_key:
    st.info("👋 Devam etmek için sidebar'dan API anahtarınızı girin.")
    st.stop()

# Data Load
df, s_name = load_metadata()
df, col_map = prepare_columns(df)

if "last_query" not in st.session_state: st.session_state.last_query = ""
if "sample_query" not in st.session_state: st.session_state.sample_query = ""

# --- RESULTS (TOP PRIORITY) ---
if st.session_state.last_query:
    matches = search_reports(df, st.session_state.last_query, col_map)
    if matches:
        with st.spinner("AI Analiz Ediyor..."):
            explanation = generate_ai_recommendation(st.session_state.last_query, matches, st.session_state.selected_model)
        
        st.markdown('<div class="section-title">AI Değerlendirmesi</div>', unsafe_allow_html=True)
        st.info(explanation)
        
        st.markdown('<div class="section-title">Önerilen Raporlar</div>', unsafe_allow_html=True)
        for i, m in enumerate(matches, 1):
            st.markdown(f"""
<div class="result-card">
    <div class="result-title">{i}. {safe_text(m['name'])}</div>
    <div class="badge">{safe_text(m['topic'])}</div>
    <div class="field-label">Ana Konu</div><div class="field-value">{safe_text(m['topic'])}</div>
    <div class="field-label">Neden Önerildi?</div><div class="field-value">{safe_text(m['why'])}</div>
    <div class="field-label">KPI'lar</div><div class="field-value">{safe_text(m['kpis'])}</div>
    <div class="field-label">Yol</div><div class="field-value">{safe_text(m['path'])}</div>
</div>
""", unsafe_allow_html=True)
        st.markdown("---")

# --- SEARCH & SCENARIOS ---
st.markdown('<div class="section-title">İhtiyacı Tanımla</div>', unsafe_allow_html=True)
st.markdown('<div class="query-card">', unsafe_allow_html=True)
q_in = st.text_input("İhtiyacınızı yazın", value=st.session_state.sample_query, placeholder="Örn: Churn raporu...")
if st.button("Rapor Öner", type="primary"):
    if q_in.strip():
        st.session_state.last_query = q_in
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Örnek Senaryolar</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
scenarios = [
    ("📉 Churn", "churn oranini takip etmek istiyorum", "card1", c1),
    ("⚠️ Risk", "yenileme riski olan firmalari gormek istiyorum", "card2", c2),
    ("🚀 Fırsat", "erken yenileme firsatlarini gormek istiyorum", "card3", c3)
]
for title, q, key, col in scenarios:
    with col:
        st.markdown(f'<div class="nav-card"><div class="card-title">{title}</div></div>', unsafe_allow_html=True)
        if st.button("Seç", key=key, use_container_width=True):
            st.session_state.sample_query = q
            st.rerun()