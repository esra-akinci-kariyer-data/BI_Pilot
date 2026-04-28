"""
data_context.py
===============
BIDB/DWH sunucusundan gerçek dünya varlıklarını (İKÇO isimleri, Bölümler vb.)
çekerek taslakların 'real-world' görünmesini sağlar.
"""

import pyodbc
from typing import Optional, Dict, List
from .config import BIDB_SQL_SERVER, BIDB_SQL_DATABASE

# Basit bir session-level cache
_ENTITY_CACHE: Dict[str, List[str]] = {}

def get_real_world_entities() -> Dict[str, List[str]]:
    """
    DWH.logintanim tablosundan gerçek bölümleri ve İKÇO isimlerini çeker.
    Sonuçları cache'ler.
    """
    global _ENTITY_CACHE
    if _ENTITY_CACHE:
        return _ENTITY_CACHE

    drivers = ['{ODBC Driver 18 for SQL Server}', '{ODBC Driver 17 for SQL Server}', '{SQL Server}']
    entities = {"bolumler": [], "ikcolar": []}

    for driver in drivers:
        try:
            conn = pyodbc.connect(
                f"Driver={driver};Server={BIDB_SQL_SERVER};Database={BIDB_SQL_DATABASE};"
                f"Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;",
                timeout=5
            )
            cursor = conn.cursor()
            
            # Gerçek Bölümler
            cursor.execute("SELECT DISTINCT TOP 15 bolum FROM logintanim WHERE bolum IS NOT NULL AND bolum != ''")
            entities["bolumler"] = [r[0] for r in cursor.fetchall()]
            
            # Gerçek İKÇO İsimleri
            cursor.execute("""
                SELECT DISTINCT TOP 15 ad 
                FROM logintanim 
                WHERE ad IS NOT NULL AND ad NOT IN ('aa', 'TBD', '.', 'Aday', 'Kariyer.net')
            """)
            entities["ikcolar"] = [r[0] for r in cursor.fetchall()]

            # Gerçek Yenileme Tipleri
            try:
                cursor.execute("SELECT DISTINCT TOP 10 yenilemetipi FROM [18_Satislar] WHERE yenilemetipi IS NOT NULL")
                entities["yenileme_tipleri"] = [r[0] for r in cursor.fetchall()]
            except:
                entities["yenileme_tipleri"] = ["Erken", "Ek Ürün", "Aynı Yıl", "İlk Satış", "Pasiften"]

            # Gerçek Müşteri İsimleri ve Kodları (Musteri tablosundan)
            try:
                cursor.execute("SELECT TOP 15 musteri_kod, unvan FROM Musteri WHERE unvan IS NOT NULL AND unvan != ''")
                rows = cursor.fetchall()
                entities["musteriler"] = [{"kod": r[0], "unvan": r[1]} for r in rows]
            except:
                entities["musteriler"] = []
            
            conn.close()
            _ENTITY_CACHE = entities
            return entities
        except Exception:
            continue

    return entities
