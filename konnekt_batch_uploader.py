"""
Konnekt Batch Uploader - Power BI PBIX Toplu Yükleme
Doğrudan PBIX dosya upload + metadata extraction
"""

import streamlit as st
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


def render_konnekt_batch_uploader():
    """Batch Konnekt uploader UI - Doğrudan PBIX dosya upload"""
    st.markdown("### 🔗 Toplu Konnekt Upload (Batch)")
    st.info("💡 Power BI PBIX dosyalarını seç ve Konnekt API'ye toplu yükle")
    
    try:
        from konnekt_client import KonnektAPIClient
    except ImportError as e:
        st.error(f"❌ Konnekt client yüklenemiyor: {e}")
        return
    
    # Dosya upload widget
    uploaded_files = st.file_uploader(
        "PBIX dosyalarını seç (Max 10)", 
        type=["pbix"],
        accept_multiple_files=True,
        key="konnekt_file_uploader"
    )
    
    if not uploaded_files:
        st.markdown("---")
        st.markdown("**Nasıl kullanılır?**")
        st.markdown("""
        1. PBIX dosyalarını seç (upload button ile)
        2. Paralel workers ve timeout'u ayarla
        3. 'Toplu Upload Başlat' butonuna tıkla
        4. Sonuçları açılır kartlarda gör
        """)
        return
    
    if len(uploaded_files) > 10:
        st.error("❌ Maximum 10 dosya!")
        return
    
    st.markdown("#### ⚙️ Ayarlar")
    c1, c2 = st.columns(2)
    with c1:
        workers = st.number_input("Paralel Workers", value=3, min_value=1, max_value=10, key="bu_workers")
    with c2:
        timeout = st.number_input("Her dosya timeout (sec)", value=30, min_value=10, max_value=120, key="bu_timeout")
    
    if st.button("🚀 Toplu Upload Başlat", type="primary", use_container_width=True, key="bu_submit"):
        _batch_upload_files(uploaded_files, int(workers), int(timeout), KonnektAPIClient)


def _batch_upload_files(uploaded_files, workers, timeout, KonnektAPIClient):
    """Execute batch upload for uploaded PBIX files"""
    progress = st.progress(0)
    status = st.empty()
    results = {}
    completed = 0
    total = len(uploaded_files)
    lock = threading.Lock()
    
    def upload_file(idx, file_obj):
        nonlocal completed
        name = file_obj.name.replace(".pbix", "").replace(".PBIX", "")
        
        try:
            # Read file
            pbix_bytes = file_obj.read()
            
            if len(pbix_bytes) < 1000:
                res = {
                    "status": "error", 
                    "message": f"Dosya çok küçük ({len(pbix_bytes)} bytes)",
                    "size": len(pbix_bytes)
                }
            else:
                try:
                    # Upload to Konnekt
                    client = KonnektAPIClient()
                    ok, resp = client.upload_pbix(pbix_bytes, f"{name}.pbix")
                    
                    if ok:
                        meta = resp.get("data", {}) if isinstance(resp, dict) else {}
                        res = {
                            "status": "success",
                            "message": "✅ Konnekt'e yüklendi",
                            "size": len(pbix_bytes),
                            "tables": len(meta.get("tables", [])),
                            "measures": len(meta.get("measures", [])),
                            "datasources": len(meta.get("datasources", [])),
                            "relationships": len(meta.get("relationships", []))
                        }
                    else:
                        res = {
                            "status": "error", 
                            "message": f"Konnekt API hatası: {str(resp)[:100]}"
                        }
                except Exception as konnekt_err:
                    res = {
                        "status": "error",
                        "message": f"Konnekt upload hatası: {str(konnekt_err)[:80]}"
                    }
        except Exception as e:
            res = {
                "status": "error", 
                "message": f"Dosya okuma hatası: {str(e)[:80]}"
            }
        
        with lock:
            results[name] = res
            completed += 1
            pct = min(completed / total, 1.0)
            progress.progress(pct)
            status.write(f"⏳ {completed}/{total} dosya işleniyor...")
    
    # ThreadPool executor
    try:
        with ThreadPoolExecutor(max_workers=workers) as exe:
            futures = [exe.submit(upload_file, i, f) for i, f in enumerate(uploaded_files)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exec_err:
                    st.error(f"⚠️ Thread hatası: {exec_err}")
    except Exception as pool_err:
        st.error(f"❌ Thread pool hatası: {pool_err}")
        return
    
    # Results display
    st.markdown("### 📊 Sonuçlar")
    success = sum(1 for r in results.values() if r.get("status") == "success")
    error = sum(1 for r in results.values() if r.get("status") == "error")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Başarılı", success)
    col2.metric("❌ Hatalı", error)
    col3.metric("📦 Toplam", total)
    
    st.markdown("#### 📋 Detaylar")
    for name, res in sorted(results.items()):
        if res.get("status") == "success":
            icon = "✅"
            expanded = False
        elif res.get("status") == "error":
            icon = "❌"
            expanded = True
        else:
            icon = "⏳"
            expanded = False
        
        with st.expander(f"{icon} {name}", expanded=expanded):
            st.json(res)
