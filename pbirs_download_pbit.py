"""
PBIRS Power BI Rapor İndirici
=============================
raportal.kariyer.net PBIRS sunucusundan tüm Power BI raporlarını
PBIT olarak indirir.

Kullanım:
    py pbirs_download_pbit.py --user esra.akinci --password SIFRENIZ

İndirilen dosyalar: pbit_downloads/ klasörüne kaydedilir.
Klasör yapısı sunucudaki path ile aynı korunur.
"""

import argparse
import os
import sys
import time
import warnings
from pathlib import Path

import requests
from requests_ntlm import HttpNtlmAuth

warnings.filterwarnings("ignore")  # SSL self-signed sertifika uyarısı

PBIRS_BASE    = "https://raportal.kariyer.net"
API_BASE      = f"{PBIRS_BASE}/powerbi/api/v2.0"
DOWNLOAD_DIR  = Path(__file__).parent / "pbit_downloads"
DOMAIN        = "KARIYER"


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def make_session(username: str, password: str) -> requests.Session:
    full_user = username if "\\" in username else f"{DOMAIN}\\{username}"
    s = requests.Session()
    s.auth   = HttpNtlmAuth(full_user, password, send_cbt=False)
    s.verify = False
    s.headers.update({"Accept": "application/json"})
    return s


def api_get(session: requests.Session, path: str) -> dict:
    url = f"{API_BASE}/{path.lstrip('/')}"
    r   = session.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Tüm CatalogItem'ları recursive olarak topla ───────────────────────────────

def collect_all_pbi_reports(session: requests.Session) -> list[dict]:
    """PowerBIReports endpoint'i tüm raporları tek sorguda döndürür."""
    print("► Tüm Power BI raporları listeleniyor…")
    data = api_get(session, "PowerBIReports?$top=2000")
    reports = data.get("value", [])
    print(f"  {len(reports)} Power BI raporu bulundu.")
    return reports


def collect_via_catalog(session: requests.Session) -> list[dict]:
    """PowerBIReports yetersiz kalırsa CatalogItems üzerinden filtrele."""
    print("► CatalogItems üzerinden taranıyor (yedek yöntem)…")
    data = api_get(session, "CatalogItems?$top=5000")
    items = data.get("value", [])
    pbi  = [i for i in items if i.get("Type") == "PowerBIReport"]
    print(f"  {len(pbi)} Power BI raporu bulundu (CatalogItems).")
    return pbi


# ── Tek rapor indir ──────────────────────────────────────────────────────────

def download_pbit(session: requests.Session, report: dict, dry_run: bool = False) -> str:
    """
    Bir raporu PBIT olarak indirir.
    Döndürür: 'ok' | 'skip' | 'error: <mesaj>'
    """
    report_id   = report.get("Id") or report.get("id") or ""
    report_name = report.get("Name") or report.get("name") or report_id
    report_path = report.get("Path") or report.get("path") or ""

    # Kayıt yolu: sunucu path yapısını koru
    relative   = report_path.lstrip("/").replace("/", os.sep)
    out_folder = DOWNLOAD_DIR / Path(relative).parent
    out_file   = out_folder / f"{_safe_name(report_name)}.pbit"

    if out_file.exists():
        return "skip"

    if dry_run:
        print(f"  [dry-run] İndirilecek: {out_file}")
        return "ok"

    out_folder.mkdir(parents=True, exist_ok=True)

    # PBIRS ExportTo (async) → PBIT
    export_url = f"{API_BASE}/PowerBIReports({report_id})/ExportTo"
    payload    = {
        "format": "PBIT",
        "powerBIReportConfiguration": {"pages": []}
    }

    try:
        resp = session.post(export_url, json=payload, timeout=30)

        # Bazı PBIRS sürümleri doğrudan 200 ve binary döner
        if resp.status_code == 200 and len(resp.content) > 100:
            out_file.write_bytes(resp.content)
            return "ok"

        # Standart async: 202 + Operation-Location header
        if resp.status_code not in (202, 200):
            # PBIT export desteklenmiyorsa PBIX'i dene
            return _download_pbix_fallback(session, report_id, report_name, out_folder)

        poll_url = (
            resp.headers.get("Operation-Location")
            or resp.headers.get("Location")
        )
        if not poll_url:
            return "error: Operation-Location header yok"

        # Tamamlanana kadar polling (max 2 dakika)
        for attempt in range(40):
            time.sleep(3)
            pr = session.get(poll_url, timeout=30)
            if pr.status_code != 200:
                continue
            status_data = pr.json()
            status = status_data.get("status", "")
            if status == "Succeeded":
                file_url = poll_url.rstrip("/") + "/files/0"
                fr = session.get(file_url, timeout=120)
                if fr.status_code == 200:
                    out_file.write_bytes(fr.content)
                    return "ok"
                return f"error: dosya indirilemedi ({fr.status_code})"
            elif status == "Failed":
                errmsg = status_data.get("message", "bilinmiyor")
                return f"error: ExportTo başarısız — {errmsg}"

        return "error: polling timeout (2 dakika)"

    except requests.RequestException as exc:
        return f"error: {exc}"


def _download_pbix_fallback(session: requests.Session, report_id: str, report_name: str, out_folder: Path) -> str:
    """PBIT export başarısız olursa PBIX olarak indir."""
    out_file = out_folder / f"{_safe_name(report_name)}.pbix"
    if out_file.exists():
        return "skip"
    try:
        r = session.get(f"{API_BASE}/PowerBIReports({report_id})/Content", timeout=120)
        if r.status_code == 200 and len(r.content) > 100:
            out_file.write_bytes(r.content)
            return "ok (pbix)"
        return f"error: PBIX indirme de başarısız ({r.status_code})"
    except Exception as exc:
        return f"error: {exc}"


def _safe_name(name: str) -> str:
    """Dosya sisteminde geçersiz karakterleri temizler."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


# ── Ana akış ─────────────────────────────────────────────────────────────────

def main():
    import re  # noqa: F401 – _safe_name için

    parser = argparse.ArgumentParser(description="PBIRS Power BI raporlarını PBIT olarak indir")
    parser.add_argument("--user",     required=True,  help="KARIYER domain kullanıcı adı (örn. esra.akinci)")
    parser.add_argument("--password", required=True,  help="Domain şifresi")
    parser.add_argument("--dry-run",  action="store_true", help="Dosya indirmeden listeyi göster")
    parser.add_argument("--limit",    type=int, default=0,  help="Kaç rapor indirilecek (0 = tümü)")
    args = parser.parse_args()

    session = make_session(args.user, args.password)

    # Bağlantı testi
    print("► Sunucuya bağlanılıyor…")
    try:
        test = session.get(f"{API_BASE}/PowerBIReports?$top=1", timeout=15)
        if test.status_code == 401:
            print("✗ Kimlik doğrulama başarısız (401). Kullanıcı adı/şifre kontrol edin.")
            sys.exit(1)
        elif test.status_code != 200:
            print(f"✗ Beklenmeyen durum: {test.status_code}")
            sys.exit(1)
        print(f"✓ Bağlantı başarılı (KARIYER\\{args.user})")
    except Exception as exc:
        print(f"✗ Bağlantı hatası: {exc}")
        sys.exit(1)

    # Rapor listesi
    try:
        reports = collect_all_pbi_reports(session)
    except Exception:
        reports = collect_via_catalog(session)

    if not reports:
        print("Hiç Power BI raporu bulunamadı.")
        sys.exit(0)

    if args.limit:
        reports = reports[: args.limit]
        print(f"  (--limit {args.limit} uygulandı)")

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # İndirme döngüsü
    ok_count   = 0
    skip_count = 0
    err_count  = 0

    for i, report in enumerate(reports, 1):
        name = report.get("Name") or report.get("name") or "?"
        path = report.get("Path") or report.get("path") or ""
        print(f"[{i:3d}/{len(reports)}] {path or name} … ", end="", flush=True)

        result = download_pbit(session, report, dry_run=args.dry_run)

        if result == "ok":
            ok_count += 1
            print("✓ indirildi")
        elif result == "ok (pbix)":
            ok_count += 1
            print("✓ indirildi (pbix)")
        elif result == "skip":
            skip_count += 1
            print("– zaten var")
        else:
            err_count += 1
            print(f"✗ {result}")

    print()
    print(f"═══ Tamamlandı ═══")
    print(f"  ✓ İndirildi : {ok_count}")
    print(f"  – Atlandı   : {skip_count}")
    print(f"  ✗ Hata      : {err_count}")
    print(f"  Klasör       : {DOWNLOAD_DIR.resolve()}")


if __name__ == "__main__":
    import re
    main()
