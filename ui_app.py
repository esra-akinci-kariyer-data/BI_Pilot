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
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f7f9fc; }
    section[data-testid="stSidebar"] { background-color: #8c28e8 !important; }
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea { background-color: #ffffff !important; color: #1a1a1a !important; border-radius: 10px !important; }
    section[data-testid="stSidebar"] [data-testid="stExpander"] { background-color: rgba(255, 255, 255, 0.08) !important; color: #fff !important; }
    section[data-testid="stSidebar"] * { color: #ffffff !important; }
    .sidebar-brand { font-weight: 800; font-size: 1.4rem; padding: 1.5rem 1rem; color: #ffffff; }
    .sidebar-menu-item { padding: 0.75rem 1rem; margin: 0.25rem 0.75rem; border-radius: 10px; font-weight: 600; color: rgba(255,255,255,0.8); cursor: pointer; transition: 0.2s; }
    .sidebar-menu-item.active { background: rgba(255,255,255,0.15); color: #fff; }
    .main-header { display: flex; align-items: center; padding-bottom: 2rem; }
    .header-logo { background: #f3e8ff; color: #8c28e8; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-right: 12px; font-size: 20px; }
    .header-title { font-weight: 700; font-size: 1.25rem; }
    .welcome-text h1 { font-weight: 800; font-size: 2.2rem; color: #1a1a1a; margin-bottom: 0.5rem; }
    .workflow-container { display: flex; align-items: center; margin-bottom: 2.5rem; gap: 12px; }
    .workflow-step { display: flex; align-items: center; font-size: 0.9rem; font-weight: 600; color: #a855f7; }
    .workflow-step span { width: 20px; height: 20px; border: 2px solid #a855f7; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 8px; font-size: 0.7rem; }
    .section-title { font-weight: 700; font-size: 1.2rem; color: #1a1a1a; margin: 2rem 0 1rem 0; }
    .nav-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 1.5rem; transition: 0.3s; cursor: pointer; height: 100%; }
    .nav-card:hover { transform: translateY(-4px); border-color: #8c28e8; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    .result-card { background: white; border-radius: 16px; padding: 1.5rem; border: 1px solid #e5e7eb; border-left: 6px solid #8c28e8; margin-bottom: 1.5rem; }
    .result-title { font-weight: 700; font-size: 1.2rem; margin-bottom: 0.75rem; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; margin-right: 10px; }
    .field-label { font-size: 0.75rem; font-weight: 700; color: #9ca3af; text-transform: uppercase; margin-top: 1rem; }
    .field-value { font-size: 0.95rem; color: #374151; line-height: 1.6; }
    .query-card { background: white; padding: 2rem; border-radius: 20px; border: 1px solid #e5e7eb; margin-bottom: 2rem; }
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)

# --- UTILS ---
def normalize_text(text: str) -> str:
    text = str(text).lower()
    repls = {"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"}
    for o, n in repls.items(): text = text.replace(o, n)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def clean_columns(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df

def find_best_column(df, candidates):
    for cand in candidates:
        cn = normalize_text(cand)
        for col in df.columns:
            if normalize_text(col) == cn or cn in normalize_text(col): return col
    return None

# --- AI LOGIC ---
@st.cache_data
def list_models():
    if not st.session_state.get("api_key"): return []
    try:
        genai.configure(api_key=st.session_state.api_key)
        return [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
    except: return ["gemini-1.5-flash", "gemini-1.5-pro"]

def generate_ai_recommendation(query, matches, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        txt = "\n".join([f"- {r['name']}: {r['why']}" for r in matches])
        prompt = f"Sorgu: '{query}'\nRaporlar:\n{txt}\nBu raporların neden uygun olduğunu Türkçe özetle (2 cümle)."
        return model.generate_content(prompt).text
    except Exception as e: return f"Analiz hatası: {str(e)}"

def get_ai_estimated_metadata(name, path, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        prompt = f"Rapor: '{name}'\nYol: '{path}'\nBu BI raporunun içeriğini ve KPI'larını tahmin et. Format: AÇIKLAMA: ... KPI: ..."
        res = model.generate_content(prompt).text
        desc = re.search(r"AÇIKLAMA:(.*)", res, re.I)
        kpi = re.search(r"KPI:(.*)", res, re.I)
        return (desc.group(1).strip() if desc else res[:100], kpi.group(1).strip() if kpi else "Metrik tahmini yapılamadı")
    except: return "Tahmin yapılamadı.", "-"

# --- DATA ---
@st.cache_data
def load_metadata():
    base = Path(__file__).resolve().parent
    df_p = pd.read_csv(base/"pilot_rapor_metadata_clean.csv", sep=";", encoding="utf-8-sig")
    df_m = pd.read_csv(base/"raportal_metadata_master.xlsx.csv", sep=";", encoding="utf-8-sig")
    return clean_columns(df_p), clean_columns(df_m)

def search_hybrid(df_p, df_m, query, model_name):
    qn = normalize_text(query)
    res = []
    # Pilotlar (p_map simplified here for brevity, assuming standard names)
    for _, r in df_p.iterrows():
        txt = normalize_text(str(r.get("Name")) + " " + str(r.get("Ana Konu")) + " " + str(r.get("Bu rapor neyi gösteriyor?")))
        score = sum(1.5 for t in qn.split() if t in txt)
        if score > 0:
            res.append({"name": r.get("Name"), "topic": r.get("Ana Konu"), "why": r.get("Bu rapor neyi gösteriyor?"), "kpis": r.get("Ana KPI'lar"), "path": r.get("Path"), "score": score, "verified": True})
    
    hits = [x["name"] for x in res]
    for _, r in df_m.iterrows():
        name = r.get("Name")
        if name in hits: continue
        txt = normalize_text(str(name) + " " + str(r.get("Path")))
        score = sum(1.0 for t in qn.split() if t in txt)
        if score > 0:
            res.append({"name": name, "topic": r.get("Ana Konu"), "why": r.get("Bu rapor neyi gösteriyor?"), "kpis": r.get("Ana KPI’lar"), "path": r.get("Path"), "score": score, "verified": False})
    
    return sorted(res, key=lambda x: x["score"], reverse=True)[:5]

# --- AUTH ---
if "api_key" not in st.session_state: st.session_state.api_key = None
with st.sidebar:
    st.markdown('<div class="sidebar-brand">📊 Raportal Agent</div>', unsafe_allow_html=True)
    if not st.session_state.api_key:
        ak = st.text_input("Gemini API Key", type="password")
        if st.button("Bağlan", type="primary", use_container_width=True):
            st.session_state.api_key = ak
            st.rerun()
    else:
        st.success("✅ Bağlı")
        st.session_state.selected_model = st.selectbox("Model", list_models() or ["gemini-1.5-flash"])
        if st.button("Çıkış", use_container_width=True):
            st.session_state.api_key = None
            st.rerun()

# --- MAIN ---
st.markdown('<div class="main-header"><div class="header-logo">⚡</div><div class="header-title">Raportal AI Assistant</div></div>', unsafe_allow_html=True)
st.markdown('<div class="welcome-text"><h1>Hoş Geldiniz 👋</h1><p>426 Rapor Kapasitesiyle Yayında</p></div>', unsafe_allow_html=True)

if not st.session_state.api_key:
    st.info("Devam etmek için API anahtarınızı girin.")
    st.stop()

dfp, dfm = load_metadata()
if "query" not in st.session_state: st.session_state.query = ""

if st.session_state.query:
    matches = search_hybrid(dfp, dfm, st.session_state.query, st.session_state.selected_model)
    if matches:
        st.info(generate_ai_recommendation(st.session_state.query, matches, st.session_state.selected_model))
        for i, m in enumerate(matches, 1):
            why, kpis = m["why"], m["kpis"]
            badge = '<span class="badge" style="background:#dcfce7;color:#166534;">✅ Doğrulanmış</span>' if m["verified"] else '<span class="badge" style="background:#fef9c3;color:#854d0e;">✨ AI Tahmini</span>'
            if not m["verified"] and (pd.isna(why) or why == "-"):
                with st.spinner("Tahmin ediliyor..."):
                    why, kpis = get_ai_estimated_metadata(m["name"], m["path"], st.session_state.selected_model)
            st.markdown(f"""<div class="result-card"><div class="result-title">{i}. {html.escape(str(m['name']))} {badge}</div>
            <div class="field-label">İçerik</div><div class="field-value">{html.escape(str(why))}</div>
            <div class="field-label">KPIlar</div><div class="field-value">{html.escape(str(kpis))}</div></div>""", unsafe_allow_html=True)

st.markdown('<div class="query-card">', unsafe_allow_html=True)
q_in = st.text_input("Arama terimi yazın", placeholder="Örn: churn, satış...")
if st.button("Raporları Tara", type="primary", use_container_width=True):
    st.session_state.query = q_in
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
scs = [("📉 Churn", "churn oranini takip etmek"), ("⚡ Verimlilik", "gunluk verimlilik"), ("🎯 Hedef", "aylik ve gunluk hedefler")]
for i, (t, q) in enumerate(scs):
    with [c1,c2,c3][i]:
        st.markdown(f'<div class="nav-card"><div class="card-title">{t}</div></div>', unsafe_allow_html=True)
        if st.button("Uygula", key=f"s{i}", use_container_width=True):
            st.session_state.query = q
            st.rerun()