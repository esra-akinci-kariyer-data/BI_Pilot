"""
main.py — Dashboard Agent CLI
==============================
Kullanım:
    py main.py --url "https://raportal.kariyer.net/home/report/Model/FinalCheck"
               --user esra.akinci
               --apikey <GEMINI_KEY>   # ya da GEMINI_API_KEY ortam değişkeni

Çıktı:
    dashboard_analyses/<rapor_adı>.md
    dashboard_screenshots/  klasörüne screenshot'lar
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path

# package import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard_agent.browser_agent import (
    RaportalBrowserAgent,
    AuthError,
    PageLoadError,
    PlaywrightNotInstalledError,
)
from dashboard_agent.dashboard_reader import DashboardReader
from dashboard_agent.analyzer import analyze_dashboard
from dashboard_agent.config import NTLM_DOMAIN, ANALYSIS_DIR, SCREENSHOT_DIR


async def _run(url: str, username: str, password: str, domain: str, api_key: str) -> str:
    agent = RaportalBrowserAgent(username, password, domain)
    try:
        print("► Browser başlatılıyor…")
        await agent.start()

        reader = DashboardReader(agent)
        print("► Dashboard okunuyor…")
        data = await reader.read_dashboard(url)

        if data.error:
            print(f"✗ {data.error}")
            return data.error

        print(f"  {len(data.pages)} sayfa/sekme bulundu.")

        # Ham veriyi kaydet
        json_out = ANALYSIS_DIR / f"{_safe(data.report_name)}.json"
        json_out.write_text(
            json.dumps(data.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  JSON: {json_out}")

        # AI analiz
        print("► AI analiz üretiliyor…")
        analysis = analyze_dashboard(data, api_key)

        md_out = ANALYSIS_DIR / f"{_safe(data.report_name)}.md"
        md_out.write_text(analysis, encoding="utf-8")
        print(f"  Markdown: {md_out}")
        print(f"  Screenshots: {SCREENSHOT_DIR}")

        return analysis

    except PlaywrightNotInstalledError as e:
        msg = f"✗ {e}"
        print(msg)
        return msg
    except AuthError as e:
        msg = f"✗ Raportal oturumu açık değil veya kimlik hatası:\n{e}"
        print(msg)
        return msg
    except PageLoadError as e:
        msg = f"✗ Sayfa yüklenemedi:\n{e}"
        print(msg)
        return msg
    except Exception as e:
        msg = f"✗ Beklenmedik hata: {e}"
        print(msg)
        return msg
    finally:
        await agent.close()


def _safe(name: str) -> str:
    import re
    return re.sub(r"[^\w\u00C0-\u017E\-]", "_", name).strip()[:80]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raportal dashboard URL'sini analiz et"
    )
    parser.add_argument("--url",    required=True,  help="Dashboard URL'si")
    parser.add_argument("--user",   required=True,  help="Domain kullanıcı adı (örn. esra.akinci)")
    parser.add_argument("--domain", default=NTLM_DOMAIN, help="NTLM domain (varsayılan: KARIYER)")
    parser.add_argument("--apikey", default=os.getenv("GEMINI_API_KEY", ""),
                        help="Gemini API key (ya da GEMINI_API_KEY env var)")
    args = parser.parse_args()

    password = getpass.getpass(f"Şifre ({args.domain}\\{args.user}): ")

    result = asyncio.run(
        _run(args.url, args.user, password, args.domain, args.apikey)
    )
    print("\n" + "═" * 60)
    print(result)


if __name__ == "__main__":
    main()
