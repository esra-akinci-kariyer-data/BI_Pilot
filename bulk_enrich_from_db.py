import sys
import pyodbc
import pandas as pd
import zipfile
import io
import json
import re

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def extract_kpis_from_pbix(binary_content):
    if not binary_content:
        return "No Content"
    
    try:
        with zipfile.ZipFile(io.BytesIO(binary_content)) as z:
            names = z.namelist()
            if 'Report/Layout' in names:
                # Layout is typically UTF-16 LE
                raw_bytes = z.read('Report/Layout')
                try:
                    text = raw_bytes.decode('utf-16-le')
                except:
                    text = str(raw_bytes[:5000])
                
                # We can do a rudimentary regex regex to find visual titles or just return a substring
                titles = re.findall(r'"Title":"([^"]+)"', text)
                if titles:
                    return "Görseller: " + ", ".join(list(set(titles))[:10])
                return text[:1000]
            else:
                return f"No Layout. Files: {', '.join(names[:5])}"
    except Exception as e:
        return f"ZipError: {e}"

def process_reports():
    print("Bağlanılıyor...")
    conn_str = 'Driver={ODBC Driver 18 for SQL Server};Server=biportal;Database=Raportal;Trusted_Connection=yes;TrustServerCertificate=Yes'
    conn = pyodbc.connect(conn_str)
    
    query = """
    SELECT TOP 5 ItemID, Name, Path, Type, Content 
    FROM dbo.Catalog 
    WHERE Type = 13 
      AND Content IS NOT NULL 
      AND Path NOT LIKE '%Test%' 
      AND Hidden = 0
    """
    
    df = pd.read_sql(query, conn)
    print(f"Buldum: {len(df)} rapor.")
    
    results = []
    for idx, row in df.iterrows():
        print(f"İnceleniyor: {row['Name']}")
        content_summary = extract_kpis_from_pbix(row['Content'])
        results.append({
            "Name": row["Name"],
            "Path": row["Path"],
            "Extracted": content_summary[:200]
        })
        
    print(pd.DataFrame(results))
    conn.close()

if __name__ == "__main__":
    process_reports()
