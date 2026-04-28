from pathlib import Path
import html
import pandas as pd
import re
import streamlit as st
import types

st.set_page_config(page_title="Raportal AI Assistant", layout="wide")

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
    section[data-testid="stSidebar"] * { color: #ffffff !important; }
    .sidebar-brand { font-weight: 800; font-size: 1.4rem; padding: 1.5rem 1rem; color: #ffffff; }
    
    .main-header { display: flex; align-items: center; padding-bottom: 2rem; }
    .header-logo { background: #f3e8ff; color: #8c28e8; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-right: 12px; font-size: 20px; }
    .header-title { font-weight: 700; font-size: 1.25rem; }
    
    .section-title { font-weight: 700; font-size: 1.2rem; color: #1a1a1a; margin: 2rem 0 1rem 0; }
    
    /* Category/Drilldown Pills */
    .category-pill {
        display: inline-block;
        padding: 8px 16px;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 20px;
        margin-right: 8px;
        margin-bottom: 8px;
        cursor: pointer;
        font-size: 0.85rem;
        font-weight: 600;
        transition: 0.2s;
    }
    .category-pill:hover { border-color: #8c28e8; color: #8c28e8; }
    
    /* Top Recommendations Card */
    .recommend-card {
        background: linear-gradient(135deg, #ffffff 0%, #f9f7ff 100%);
        border: 1px solid #e0d4ff;
        border-radius: 16px;
        padding: 1.25rem;
        transition: 0.3s;
        cursor: pointer;
        position: relative;
        overflow: hidden;
        margin-bottom: 1rem;
        height: 100%;
    }
    .recommend-card:hover { transform: translateY(-5px); border-color: #8c28e8; box-shadow: 0 10px 20px rgba(140,40,232,0.1); }
    .trend-label { position: absolute; top: 0; right: 0; background: #8c28e8; color: #fff; font-size: 0.6rem; padding: 2px 8px; border-bottom-left-radius: 8px; font-weight: 700; }
    
    .result-card { background: white; border-radius: 16px; padding: 1.5rem; border: 1px solid #e5e7eb; border-left: 6px solid #8c28e8; margin-bottom: 1.5rem; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; }
    .field-label { font-size: 0.7rem; font-weight: 700; color: #9ca3af; text-transform: uppercase; margin-top: 0.8rem; }
    .field-value { font-size: 0.9rem; color: #374151; line-height: 1.5; }
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)

# --- TREND DATA ---
TREND_REPORTS = [
    {"name": "Gunluk Hedef Dashboard", "path": "Genel/Hedefler"},
    {"name": "Verimlilik Raporu", "path": "IK/Verimlilik"},
    {"name": "K-Board", "path": "IK/K-Board"},
    {"name": "Canl─▒ ─░K├çO Dashboard", "path": "Operasyon/Cagri"},
    {"name": "Ayl─▒k Churn", "path": "Musteri/Analiz"}
]

# --- UTILS ---
def normalize_text(text: str) -> str:
    text = str(text).lower()
    repls = {"─▒": "i", "┼ƒ": "s", "─ƒ": "g", "├╝": "u", "├╢": "o", "├º": "c"}
    for o, n in repls.items(): text = text.replace(o, n)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

@st.cache_data
def load_metadata():
    base = Path(__file__).resolve().parent
    df_p = pd.read_csv(base/"pilot_rapor_metadata_clean.csv", sep=";", encoding="utf-8-sig")
    df_m = pd.read_csv(base/"raportal_metadata_master.xlsx.csv", sep=";", encoding="utf-8-sig")
    return df_p, df_m

@st.cache_data
def get_drilldown_tree(df_m):
    tree = {}
    for _, r in df_m.iterrows():
        path = str(r.get("Path", "Genel"))
        parts = [p.strip() for p in path.split("/") if p.strip()]
        curr = tree
        for part in parts:
            if part not in curr: curr[part] = {}
            curr = curr[part]
        curr["__report__"] = r.get("Name")
    return tree

def get_ai_prediction(name, path, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        prompt = f"Rapor: '{name}' (Yol: {path}). ─░├ºeri─ƒi ve KPI'lar─▒ tahmin et. Format: A├çIKLAMA: ... KPI: ..."
        res = model.generate_content(prompt).text
        d = re.search(r"A├çIKLAMA:(.*)", res, re.I)
        k = re.search(r"KPI:(.*)", res, re.I)
        return (d.group(1).strip() if d else res[:100], k.group(1).strip() if k else "-")
    except: return "Tahmin yap─▒lamad─▒.", "-"

def search_reports(df_p, df_m, query):
    qn = normalize_text(query)
    found = []
    for _, r in df_p.iterrows():
        txt = normalize_text(str(r.get("Name")) + " " + str(r.get("Ana Konu")) + " " + str(r.get("Bu rapor neyi g├╢steriyor?")))
        if any(t in txt for t in qn.split()):
            found.append({"name": r.get("Name"), "topic": r.get("Ana Konu"), "why": r.get("Bu rapor neyi g├╢steriyor?"), "kpis": r.get("Ana KPI'lar"), "path": r.get("Path"), "verified": True})
    
    hits = [x["name"] for x in found]
    for _, r in df_m.iterrows():
        if r.get("Name") in hits: continue
        txt = normalize_text(str(r.get("Name")) + " " + str(r.get("Path")))
        if any(t in txt for t in qn.split()):
            found.append({"name": r.get("Name"), "topic": "-", "why": "-", "kpis": "-", "path": r.get("Path"), "verified": False})
    return found[:5]

# --- UI COMPONENTS ---
def render_trend_card(report, key):
    st.markdown(f"""
    <div class="recommend-card">
        <div class="trend-label">G├╢zde</div>
        <div style="font-weight:700; font-size:1rem; color:#1a1a1a;">{report['name']}</div>
        <div style="font-size:0.75rem; color:#8c28e8; margin-top:5px;">{report['path']}</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Analiz Et", key=f"btn_{key}", use_container_width=True):
        st.session_state.query = report['name']
        st.rerun()

def render_drilldown(tree, current_level=0):
    cols = st.columns(len(tree.keys()) if tree else 1)
    for i, (key, sub) in enumerate(tree.items()):
        if key == "__report__": continue
        if st.button(f"≡ƒôü {key}", key=f"drill_{current_level}_{i}"):
            st.session_state.drill_filter = key
            st.rerun()

# --- APP START ---
if "api_key" not in st.session_state: st.session_state.api_key = None
if "query" not in st.session_state: st.session_state.query = ""

with st.sidebar:
    st.markdown('<div class="sidebar-brand">≡ƒôè Raportal Agent</div>', unsafe_allow_html=True)
    if not st.session_state.api_key:
        ak = st.text_input("API Key", type="password")
        if st.button("Aktif Et", type="primary", use_container_width=True):
            st.session_state.api_key = ak
            st.rerun()
    else:
        st.success("Ba─ƒlant─▒ Ba┼ƒar─▒l─▒")
        st.session_state.model = st.selectbox("Model", ["gemini-1.5-flash", "gemini-1.5-pro"])
        if st.button("S─▒f─▒rla", use_container_width=True):
            st.session_state.api_key = None
            st.rerun()

st.markdown('<div class="main-header"><div class="header-logo">ΓÜí</div><div class="header-title">Raportal AI Assistant</div></div>', unsafe_allow_html=True)

if not st.session_state.api_key:
    st.info("Devam etmek i├ºin API anahtar─▒n─▒z─▒ girin.")
    st.stop()

genai.configure(api_key=st.session_state.api_key)
dfp, dfm = load_metadata()
tree = get_drilldown_tree(dfm)

# --- TOP RECOMMENDATIONS ---
st.markdown('<div class="section-title">≡ƒöÑ Sizin ─░├ºin ├ûnerilenler</div>', unsafe_allow_html=True)
t_cols = st.columns(5)
for i, rep in enumerate(TREND_REPORTS):
    with t_cols[i]: render_trend_card(rep, i)

# --- DRILLDOWN ---
st.markdown('<div class="section-title">≡ƒôé Rapor K├╝t├╝phanesinde Gezin</div>', unsafe_allow_html=True)
render_drilldown(tree)

# --- SEARCH ---
st.markdown('<div class="section-title">≡ƒöì Detayl─▒ Rapor Sorgula</div>', unsafe_allow_html=True)
q_in = st.text_input("─░htiyac─▒n─▒z─▒ yaz─▒n (├ûrn: miktar, churn, hedef...)", value=st.session_state.query)
if st.button("Taramay─▒ Ba┼ƒlat", type="primary", use_container_width=True):
    st.session_state.query = q_in
    st.rerun()

# --- RESULTS ---
if st.session_state.query:
    matches = search_reports(dfp, dfm, st.session_state.query)
    if matches:
        st.markdown('<div class="section-title">Bulunan Sonu├ºlar</div>', unsafe_allow_html=True)
        for m in matches:
            why, kpis = m["why"], m["kpis"]
            badge = '<span class="badge" style="background:#dcfce7;color:#166534;">Γ£à Do─ƒrulanm─▒┼ƒ</span>' if m["verified"] else '<span class="badge" style="background:#fef9c3;color:#854d0e;">Γ£¿ AI Tahmini</span>'
            if not m["verified"] and (pd.isna(why) or why == "-"):
                with st.spinner("AI analiz ediliyor..."):
                    why, kpis = get_ai_prediction(m["name"], m["path"], st.session_state.model)
            st.markdown(f"""
            <div class="result-card">
                <div class="result-title">{m['name']} {badge}</div>
                <div class="field-label">─░├ºerik Analizi</div><div class="field-value">{why}</div>
                <div class="field-label">Temel Metrikler</div><div class="field-value">{kpis}</div>
                <div class="field-label">Klas├╢r Yolu</div><div class="field-value" style="font-size:0.75rem; color:#9ca3af;">{m['path']}</div>
            </div>
            """, unsafe_allow_html=True)
