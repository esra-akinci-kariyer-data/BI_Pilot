"""
Dashboard Agent — Konfigürasyon
=================================
Tüm ayarlar burada merkezi olarak tutulur.
Hassas bilgi (şifre, token) kesinlikle bu dosyaya yazılmaz;
ortam değişkeninden ya da çalışma zamanında kullanıcıdan alınır.
"""

import os
from pathlib import Path

# ── Raportal ─────────────────────────────────────────────────────────────────
RAPORTAL_BASE_URL: str = "https://raportal.kariyer.net"
PBIRS_API_BASE:    str = f"{RAPORTAL_BASE_URL}/powerbi/api/v2.0"

# ── ReportServer SQL (metadata) ───────────────────────────────────────────────
REPORTSERVER_SQL_SERVER:   str = os.getenv("REPORTSERVER_SQL_SERVER",   "biportal")
REPORTSERVER_SQL_DATABASE: str = os.getenv("REPORTSERVER_SQL_DATABASE", "ReportServer")

# ── BIDB / DWH (real-world entities) ─────────────────────────────────────────
BIDB_SQL_SERVER:   str = os.getenv("BIDB_SQL_SERVER",   "bidb")
BIDB_SQL_DATABASE: str = os.getenv("BIDB_SQL_DATABASE", "DWH")

# ── Browser ───────────────────────────────────────────────────────────────────
# Playwright için kalıcı, uygulamaya özel user data dir.
# Kurumsal Chrome/Edge profilini kopyalamak yerine bu dizin kullanılır.
BROWSER_PROFILE_DIR: str | None = os.getenv("BROWSER_PROFILE_DIR") or None

# ── Çıktı klasörleri ─────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent

SCREENSHOT_DIR: Path = _BASE / "dashboard_screenshots"
ANALYSIS_DIR:   Path = _BASE / "dashboard_analyses"
PLAYWRIGHT_USER_DATA_DIR: Path = _BASE / ".pw-raportal-profile"

SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
PLAYWRIGHT_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── History ──────────────────────────────────────────────────────────────────
VISIONARY_HISTORY_FILE: Path = _BASE / "visionary_history.json"

# ── Zamanlama (ms) ────────────────────────────────────────────────────────────
PAGE_TIMEOUT_MS:    int = 60_000   # sayfa yüklenme
MAX_REPORT_LOAD_WAIT_MS: int = 180_000 # Raporun tamamen açılması için max bekleme (3 dk)
VISUAL_WAIT_MS:     int = 8_000    # Güvenli render bekleme
TAB_WAIT_MS:        int = 3_000    # sekme geçişi sonrası bekleme
DOM_STABILITY_WAIT_MS:   int = 2_000  # İçeriğin sabitlendiğinden emin olma süresi
RETRY_COUNT:        int = 3
MANUAL_LOGIN_TIMEOUT_MS: int = 180_000

# ── NTLM / Domain ────────────────────────────────────────────────────────────
NTLM_DOMAIN: str = os.getenv("NTLM_DOMAIN", "KARIYER")

# ── LLM ──────────────────────────────────────────────────────────────────────
GEMINI_MODEL: str = "gemini-1.5-flash"
PLAYWRIGHT_CHANNEL: str = os.getenv("PLAYWRIGHT_CHANNEL", "msedge")
