"""
Raportal Link Checker
---------------------
raportal_links.csv'deki linklerin erisilebilir olup olmadigini kontrol eder.
Windows NTLM kimlik dogrulamasi ile KARIYER domain hesabi kullanilir.

Calistirma:
    py raportal_link_checker.py
"""

import pandas as pd
import requests
from requests_ntlm import HttpNtlmAuth
import socket
import warnings
import os
from pathlib import Path

warnings.filterwarnings("ignore")  # SSL uyarilari

BASE_DIR = Path(__file__).resolve().parent
LINKS_CSV = BASE_DIR / "raportal_links.csv"
OUTPUT_CSV = BASE_DIR / "raportal_link_check_results.csv"

BASE_HOST = "raportal.kariyer.net"
SAMPLE_SIZE = 10  # Test edilecek rapor sayisi (tum liste icin None)


def check_server_reachable():
    try:
        s = socket.create_connection((BASE_HOST, 443), timeout=5)
        s.close()
        return True
    except Exception as e:
        print(f"Sunucuya erisim YOK: {e}")
        return False


def check_link(url: str, session: requests.Session) -> tuple[int, str]:
    try:
        r = session.head(url, timeout=8, verify=False, allow_redirects=True)
        return r.status_code, "OK"
    except requests.exceptions.ConnectionError:
        return -1, "Baglanti Hatasi"
    except requests.exceptions.Timeout:
        return -2, "Zaman Asimi"
    except Exception as e:
        return -3, str(e)[:60]


def status_label(code: int) -> str:
    if code == 200:
        return "✅ Erisiliyor"
    elif code in (301, 302, 303, 307, 308):
        return "↪️ Yonlendirme"
    elif code == 401:
        return "🔐 Kimlik Dogrulama Gerekli"
    elif code == 403:
        return "🚫 Yetki Yok"
    elif code == 404:
        return "❌ Bulunamadi"
    elif code == 500:
        return "💥 Sunucu Hatasi"
    elif code < 0:
        return "⚠️ Baglanti Sorunu"
    else:
        return f"? HTTP {code}"


def main():
    print("=" * 60)
    print("  Raportal Link Checker")
    print("=" * 60)

    # Sunucu erisilebilirlik testi
    print(f"\nSunucu kontrol ediliyor: {BASE_HOST}:443 ...")
    if not check_server_reachable():
        print("Sunucu erisilebilir degil. VPN/network baglantinizi kontrol edin.")
        return

    print("Sunucuya erisim VAR ✅\n")

    # CSV yukle
    if not LINKS_CSV.exists():
        print(f"HATA: {LINKS_CSV} bulunamadi. Once raportal_link_generator.py calistirin.")
        return

    df = pd.read_csv(LINKS_CSV, sep=";", encoding="utf-8-sig")
    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
    df = df.dropna(subset=["URL"])

    # Ozet istatistik
    type_col = next((c for c in ["Type", "Tip"] if c in df.columns), None)
    name_col = "Name" if "Name" in df.columns else df.columns[1]

    print(f"Toplam rapor sayisi: {len(df)}")
    if type_col:
        type_map = {2: "SSRS Raporu", 13: "Power BI Raporu"}
        counts = df[type_col].value_counts()
        for t_val, cnt in counts.items():
            label = type_map.get(int(t_val) if str(t_val).isdigit() else t_val, str(t_val))
            print(f"  {label}: {cnt}")

    # Ornek alimi
    sample_df = df if SAMPLE_SIZE is None else df.sample(min(SAMPLE_SIZE, len(df)), random_state=42)
    print(f"\n{len(sample_df)} rapor uzerinde link testi yapiliyor...\n")

    # NTLM Session - mevcut Windows kullanici bilgileri ile
    session = requests.Session()
    domain_user = os.environ.get("USERNAME", "").strip()
    if not domain_user:
        raise RuntimeError("Windows kullanici adi bulunamadi (USERNAME env yok).")

    # Sifre bos birakildiginda NTLM bazen SSO ile calisir, aksi halde 401 doner
    session.auth = HttpNtlmAuth(f"KARIYER\\{domain_user}", "", send_cbt=False)

    results = []
    ok = 0
    auth_needed = 0
    not_found = 0
    error = 0

    for _, row in sample_df.iterrows():
        url = str(row["URL"])
        name = str(row.get(name_col, ""))[:55]
        code, detail = check_link(url, session)
        label = status_label(code)

        if code == 200:
            ok += 1
        elif code == 401:
            auth_needed += 1
        elif code == 404:
            not_found += 1
        else:
            error += 1

        results.append({
            "Rapor": name,
            "HTTP Kodu": code,
            "Durum": label,
            "URL": url,
        })
        print(f"  [{code:>4}] {label:<30} {name}")

    # Sonuclari kaydet
    result_df = pd.DataFrame(results)
    result_df.to_csv(OUTPUT_CSV, index=False, sep=";", encoding="utf-8-sig")

    print("\n" + "=" * 60)
    print("  SONUC OZETI")
    print("=" * 60)
    print(f"  Erisiliyor (200)         : {ok}")
    print(f"  Kimlik Dogrulama (401)   : {auth_needed}")
    print(f"  Bulunamadi (404)         : {not_found}")
    print(f"  Diger Hata               : {error}")
    print(f"\n  Detayli sonuclar: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
