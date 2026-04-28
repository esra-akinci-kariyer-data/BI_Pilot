import sys
import pyodbc
import pandas as pd
import json

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def fetch_report_catalog():
    print("Veritabanına bağlanılyor (biportal)...")
    conn_str = 'Driver={ODBC Driver 18 for SQL Server};Server=biportal;Database=Raportal;Trusted_Connection=yes;TrustServerCertificate=Yes'
    conn = pyodbc.connect(conn_str, timeout=10)
    
    # 2=SSRS Report, 13=Power BI Report
    query = """
    SELECT 
        ItemID,
        Name,
        Path,
        Type,
        CreationDate,
        ModifiedDate,
        Hidden
    FROM dbo.Catalog
    WHERE Type IN (2, 13) 
      AND Path NOT LIKE '%Silinen Raporlar%'
      AND Path NOT LIKE '%Test%'
      AND Hidden = 0
    ORDER BY Path
    """
    
    print("Sorgu calistiriliyor...")
    df = pd.read_sql(query, conn)
    
    # Sadece ilk 5 raporu konsola basalım kontrol amaçlı
    print(df.head(5))
    print(f"\nToplam Bulunan Gecerli Rapor Sayisi: {len(df)}")
    
    # Gecici olarak metadata excel/csv yapisina cevirilebilir
    df.to_csv("db_exported_catalog.csv", index=False, sep=";", encoding="utf-8-sig")
    print("db_exported_catalog.csv dosyasi kaydedildi.")
    
    conn.close()

if __name__ == "__main__":
    fetch_report_catalog()
