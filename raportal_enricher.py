import pandas as pd
import google.generativeai as genai
import os
import time
from pathlib import Path
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Configuration
# Replace with your API Key or ensure it's in environment
API_KEY = "AIzaSyDd3LmTKrkiyr6oGcaFVn6hNzJZ7jaqOhg" # User will need to provide this or I'll use their session state logic if running from app
CSV_PATH = "db_exported_catalog_v2.csv"

def enrich_metadata(api_key, file_path):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    df = pd.read_csv(file_path, sep=";", encoding="utf-8-sig")
    
    # Target columns
    DESC_COL = "Bu rapor neyi gösteriyor?"
    KPI_COL = "Ana KPI'lar"
    NAME_COL = "Name"
    PATH_COL = "Path"
    SYS_DESC_COL = "Description" # SQL Server'dan gelen açıklama

    # Identify rows to enrich (empty desc or kpi)
    if DESC_COL not in df.columns:
        df[DESC_COL] = ""
    if KPI_COL not in df.columns:
        df[KPI_COL] = ""
        
    df[DESC_COL] = df[DESC_COL].fillna("")
    df[KPI_COL] = df[KPI_COL].fillna("")
    
    mask = (df[DESC_COL] == "") | (df[KPI_COL] == "")
    rows_to_process = df[mask]
    
    print(f"Bütünsel Zenginleştirme: {len(rows_to_process)} rapor işlenecek...")

    for index, row in rows_to_process.iterrows():
        name = row.get(NAME_COL, "")
        path = row.get(PATH_COL, "")
        sys_desc = row.get(SYS_DESC_COL, "")
        if pd.isna(sys_desc):
            sys_desc = "Tanımsız"
            
        prompt = f"""
        Aşağıdaki bilgilere sahip bir kurumsal rapor için detaylı açıklama ve KPI tahmini yap.
        Rapor Adı: {name}
        Rapor Yolu: {path}
        Veritabanı Açıklaması: {sys_desc}

        Lütfen şu formatta yanıt ver:
        AÇIKLAMA: [Bu raporun ne işe yaradığını, kimlerin (satış, pazarlama vb.) kullanacağını 2 cümleyle açıkla]
        KPI: [Bu raporda takip edilebilecek 3-4 ana metriği virgülle ayırarak yaz]
        """

        try:
            response = model.generate_content(prompt)
            text = response.text
            
            # Simple parsing
            desc = ""
            kpi = ""
            if "AÇIKLAMA:" in text and "KPI:" in text:
                parts = text.split("KPI:")
                desc = parts[0].replace("AÇIKLAMA:", "").strip()
                kpi = parts[1].strip()
            
            if desc:
                df.at[index, DESC_COL] = desc
            if kpi:
                df.at[index, KPI_COL] = kpi
                
            print(f"Tamamlandı: {name}")
            # Rate limiting safety
            time.sleep(1) 
            
            # Save every 10 rows for safety
            if index % 10 == 0:
                df.to_csv(file_path, sep=";", index=False, encoding="utf-8-sig")

        except Exception as e:
            print(f"Hata ({name}): {e}")
            continue

    df.to_csv(file_path, sep=";", index=False, encoding="utf-8-sig")
    print("Zenginleştirme başarıyla tamamlandı!")

if __name__ == "__main__":
    enrich_metadata(API_KEY, CSV_PATH)
