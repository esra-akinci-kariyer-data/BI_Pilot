"""
browser_agent.py
================
Playwright tabanlı browser otomasyonu.
- Uygulamaya özel persistent context kullanır
- İlk çalıştırmada headed browser açar
- Login ekranına düşerse kullanıcıdan manuel giriş bekler
- Sonraki çalıştırmalarda aynı user data dir ile oturumu sürdürür

Tüm işlemler READ-ONLY'dir; hiçbir form submit, save, delete
ya da publish işlemi yapılmaz.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests
import urllib3

from .config import (
    RAPORTAL_BASE_URL,
    PAGE_TIMEOUT_MS,
    VISUAL_WAIT_MS,
    TAB_WAIT_MS,
    RETRY_COUNT,
    BROWSER_PROFILE_DIR,
    MANUAL_LOGIN_TIMEOUT_MS,
    NTLM_DOMAIN,
    PLAYWRIGHT_CHANNEL,
    PLAYWRIGHT_USER_DATA_DIR,
    SCREENSHOT_DIR,
    MAX_REPORT_LOAD_WAIT_MS,
    DOM_STABILITY_WAIT_MS,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from playwright.async_api import (
        Error as PlaywrightError,
        BrowserContext,
        Page,
        Response,
        async_playwright,
    )
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

try:
    from requests_ntlm import HttpNtlmAuth
    _HAS_NTLM = True
except ImportError:
    _HAS_NTLM = False


class AuthError(Exception):
    """Kimlik doğrulama hatası."""


class PageLoadError(Exception):
    """Sayfa yükleme hatası."""


class PlaywrightNotInstalledError(Exception):
    """Playwright kurulu değil."""


# ── Browser Agent ────────────────────────────────────────────────────────────

class RaportalBrowserAgent:
    """
    Playwright tabanlı read-only browser agent.
    Kullanım:
        agent = RaportalBrowserAgent(username, password)
        await agent.start()
        await agent.navigate(url)
        path = await agent.screenshot("my_report")
        await agent.close()
    """

    def __init__(
        self,
        username: str = "",
        password: str = "",
        domain: str = NTLM_DOMAIN,
        headless: bool = False,
    ) -> None:
        if not _HAS_PLAYWRIGHT:
            raise PlaywrightNotInstalledError(
                "Playwright kurulu değil. "
                "Önce: pip install playwright  →  py -m playwright install chromium"
            )
        self.username = username.strip()
        self.password = password
        self.domain   = domain.strip()
        self.headless = headless

        self._pw       = None
        self._context: Optional[BrowserContext] = None
        self.page:     Optional[Page]           = None
        self.startup_strategy: str = ""
        self.user_data_dir = str(BROWSER_PROFILE_DIR or PLAYWRIGHT_USER_DATA_DIR)

        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async def _launch_persistent_context(self) -> None:
        """Uygulamaya özel kalıcı user data dir ile browser aç."""
        common_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]

        last_error: Exception | None = None
        for label, channel in [
            ("persistent-msedge-profile", PLAYWRIGHT_CHANNEL or "msedge"),
            ("persistent-chrome-profile", "chrome"),
            ("persistent-chromium-profile", None),
        ]:
            try:
                kwargs = {
                    "user_data_dir": self.user_data_dir,
                    "headless": self.headless,
                    "ignore_https_errors": True,
                    "viewport": {"width": 1920, "height": 1080},
                    "args": common_args,
                }
                
                # Pass credentials for NTLM/SSO sites to prevent popups
                if self.username and self.password:
                    full_user = f"{self.domain}\\{self.username}" if self.domain and "\\" not in self.username else self.username
                    kwargs["http_credentials"] = {"username": full_user, "password": self.password}
                if channel:
                    kwargs["channel"] = channel
                self._context = await self._pw.chromium.launch_persistent_context(**kwargs)
                pages = self._context.pages
                self.page = pages[0] if pages else await self._context.new_page()
                self.page.set_default_timeout(PAGE_TIMEOUT_MS)
                self.startup_strategy = label
                return
            except Exception as exc:
                last_error = exc
                self._context = None
                self.page = None
                continue

        raise AuthError(f"Persistent browser başlatılamadı: {last_error}")

    async def _bootstrap_ntlm_cookies(self) -> bool:
        """Girilen domain kullanıcı/şifresiyle NTLM cookie alıp Playwright context'e enjekte et."""
        if not _HAS_NTLM:
            return False
        if not self.username or not self.password:
            return False
        if not self._context:
            return False

        full_user = self.username if "\\" in self.username else f"{self.domain}\\{self.username}"
        session = requests.Session()
        session.auth = HttpNtlmAuth(full_user, self.password, send_cbt=False)
        session.verify = False

        try:
            resp = session.get(RAPORTAL_BASE_URL + "/home", timeout=25, allow_redirects=True)
            if resp.status_code not in (200, 302):
                return False
        except Exception:
            return False

        cookies = []
        for c in session.cookies:
            item = {
                "name": c.name,
                "value": c.value,
                "domain": c.domain or ".kariyer.net",
                "path": c.path or "/",
                "secure": bool(c.secure),
                "httpOnly": False,
                "sameSite": "Lax",
            }
            if c.expires:
                item["expires"] = float(c.expires)
            cookies.append(item)

        if not cookies:
            return False

        try:
            await self._context.add_cookies(cookies)
            self.startup_strategy = self.startup_strategy + "+ntlm-cookie-bootstrap"
            return True
        except Exception:
            return False

    def _looks_like_login_state(self, current_url: str, body_text: str) -> bool:
        login_markers = ["login", "signin", "auth", "giris", "oturum"]
        page_markers = [
            "sign in",
            "log in",
            "oturum aç",
            "giriş yap",
            "kullanıcı adı",
            "şifre",
            "password",
            "email",
        ]
        return any(m in current_url for m in login_markers) or any(m in body_text for m in page_markers)

    async def _wait_for_manual_login(self, target_url: str) -> None:
        """Açılan browser penceresinde kullanıcı manuel login olana kadar bekle."""
        try:
            await self.page.goto(target_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        except Exception:
            # İlk geçiş hata verirse kullanıcı manuel login için browser penceresini kullanabilir.
            pass
        deadline = asyncio.get_running_loop().time() + (MANUAL_LOGIN_TIMEOUT_MS / 1000)

        while asyncio.get_running_loop().time() < deadline:
            try:
                current_url = self.page.url.lower()
                body_text = (await self.get_visible_text())[:2000].lower()
                if not self._looks_like_login_state(current_url, body_text):
                    await self.page.goto(target_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                    await self.page.wait_for_timeout(VISUAL_WAIT_MS)
                    current_url = self.page.url.lower()
                    body_text = (await self.get_visible_text())[:2000].lower()
                    if not self._looks_like_login_state(current_url, body_text):
                        return
                await self.page.wait_for_timeout(2000)
            except Exception:
                await self.page.wait_for_timeout(2000)

        raise AuthError(
            "Raportal oturumu yok, lütfen açılan browser'da giriş yap. "
            f"Bekleme süresi doldu ({MANUAL_LOGIN_TIMEOUT_MS // 1000} sn)."
        )

    async def _detect_login_or_access_page(self) -> None:
        """Sayfa login/error ekranına düştüyse anlaşılır hata ver."""
        current_url = self.page.url.lower()
        body_text = (await self.get_visible_text())[:2000].lower()
        patterns = [
            "oturum",
            "erişim reddedildi",
            "access denied",
            "yetkiniz yok",
            "401",
            "unauthorized",
        ]
        if self._looks_like_login_state(current_url, body_text):
            raise AuthError(
                f"Raportal oturumu yok, lütfen açılan browser'da giriş yap. Strateji: {self.startup_strategy}."
            )
        if any(p in body_text for p in patterns):
            raise AuthError(
                f"Browser erişim ekranına düştü. Strateji: {self.startup_strategy}. "
                "SSO/NTLM ile dashboard açılamadı."
            )

    async def start(self) -> None:
        """Playwright persistent context başlat."""
        self._pw = await async_playwright().start()
        await self._launch_persistent_context()
        await self._bootstrap_ntlm_cookies()

    async def navigate(self, url: str) -> int:
        """
        URL'ye git, retry mekanizması ile.
        Döndürür: HTTP status code.
        """
        last_exc: Exception = Exception("Bilinmeyen hata")

        for attempt in range(1, RETRY_COUNT + 1):
            try:
                response: Optional[Response] = await self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT_MS,
                )
                status = response.status if response else 0

                if status == 401:
                    raise AuthError(
                        "Rapor sayfası 401 döndürdü. "
                        "Raportal oturumu açık değil ya da erişim yetkiniz yok."
                    )
                if status == 404:
                    raise PageLoadError(f"Sayfa bulunamadı (404): {url}")

                # Power BI / SSRS Smart Render Wait
                await self._wait_for_report_ready()

                await self._detect_login_or_access_page()

                return status

            except PlaywrightError as exc:
                if "ERR_INVALID_AUTH_CREDENTIALS" in str(exc):
                    await self._wait_for_manual_login(url)
                    continue
                last_exc = exc
                if attempt < RETRY_COUNT:
                    await asyncio.sleep(3 * attempt)

            except AuthError:
                await self._wait_for_manual_login(url)
                continue
            except PageLoadError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < RETRY_COUNT:
                    await asyncio.sleep(3 * attempt)

        raise PageLoadError(
            f"Sayfa {RETRY_COUNT} denemede yüklenemedi. Son hata: {last_exc}"
        )

    async def _wait_for_report_ready(self) -> None:
        """
        Raporun (SSRS veya Power BI) tamamen yüklendiğinden emin olmak için evrensel akıllı bekleme yapar.
        """
        import time
        start_wait = time.time()
        timeout_sec = MAX_REPORT_LOAD_WAIT_MS / 1000
        
        async def _any_loader_visible() -> bool:
            combined_selector = (
                "text=/Loading/i, text=/Yükleniyor/i, text=/Bekleyiniz/i, text=/Loading data/i, "
                "#ReportViewerControl_AsyncWait, .ReportViewerControl_AsyncWait, "
                ".pbi-loading, .spinner, .PowerBILoading, .contentLoading"
            )
            for frame in self.page.frames:
                try:
                    locators = await frame.locator(combined_selector).all()
                    for loc in locators:
                        if await loc.is_visible():
                            box = await loc.bounding_box()
                            if box and box['width'] > 2 and box['height'] > 2:
                                return True
                except Exception:
                    continue
            return False

        async def _any_visual_proof_visible() -> bool:
            proof_selectors = [
                "svg.mainGraphicsContext", "canvas", ".visual-container", 
                ".visualContent", "table[id*='Tablix'] tr", "[id*='VisibleReportContent'] table tr",
                ".card", ".gauge"
            ]
            combined_proof = ", ".join(proof_selectors)
            for frame in self.page.frames:
                try:
                    locators = await frame.locator(combined_proof).all()
                    for loc in locators:
                        if await loc.is_visible():
                            box = await loc.bounding_box()
                            if box and box['width'] > 10 and box['height'] > 10:
                                return True
                except Exception:
                    continue
            return False

        # 1. Aşama: Konteyner Tespiti
        try:
            await self.page.wait_for_selector("#ReportViewerControl, .reportContainer, .pbi-root", timeout=10000)
        except Exception:
            pass 
            
        # 2. Aşama: Görsel Kanıt Döngüsü
        proof_start = time.time()
        visual_timeout = 15
        
        while (time.time() - start_wait) < timeout_sec:
            if not await _any_loader_visible() and await _any_visual_proof_visible():
                break
            if (time.time() - proof_start) > visual_timeout and not await _any_loader_visible():
                break
            await asyncio.sleep(0.5)

        # 3. Aşama: Stabilite
        await asyncio.sleep(0.8)

        # 4. Aşama: DOM Stability Check
        try:
            await self.page.evaluate(f"""
                async (limit) => {{
                    return new Promise((resolve) => {{
                        const getMetrics = () => {{
                            let count = document.querySelectorAll('*').length;
                            let text = document.body ? document.body.innerText.length : 0;
                            document.querySelectorAll('iframe').forEach(f => {{
                                try {{
                                    if (f.contentDocument && f.contentDocument.body) {{
                                        count += f.contentDocument.querySelectorAll('*').length;
                                        text += f.contentDocument.body.innerText.length;
                                    }}
                                }} catch(e) {{}}
                            }});
                            return {{ count, text }};
                        }};
                        let last = getMetrics();
                        let stableCycles = 0;
                        const checkInterval = 400;
                        const targetCycles = Math.ceil(limit / checkInterval);
                        const interval = setInterval(() => {{
                            const current = getMetrics();
                            if (current.count === last.count && current.text === last.text) {{
                                stableCycles++;
                            }} else {{
                                stableCycles = 0; last = current;
                            }}
                            if (stableCycles >= targetCycles) {{
                                clearInterval(interval); resolve();
                            }}
                        }}, checkInterval);
                        setTimeout(() => {{ clearInterval(interval); resolve(); }}, 20000);
                    }});
                }}
            """, DOM_STABILITY_WAIT_MS)
        except Exception:
            pass

        # 5. Aşama: Final Buffer
        await self.page.wait_for_timeout(800)

    async def screenshot(self, name: str = "screenshot") -> Path:
        """Full-page screenshot al; Streamlit cache sorunu olmaması için timestamp ekler."""
        # Eski dosyaları temizle (Pruning)
        try:
            for old_file in SCREENSHOT_DIR.glob(f"{re.sub(r'[^\w\-]', '_', name)[:70]}_*.png"):
                if time.time() - old_file.stat().st_mtime > 3600: # 1 saatten eski ise sil
                    old_file.unlink()
        except Exception:
            pass

        # Güvenli dosya adı + timestamp
        ts = int(time.time())
        safe = re.sub(r"[^\w\-]", "_", name)[:70]
        filename = f"{safe}_{ts}.png"
        path = SCREENSHOT_DIR / filename
        
        await self.page.screenshot(path=str(path), full_page=True)
        return path

    async def get_visible_text(self) -> str:
        """
        Sayfadaki görünür DOM metnini döndür.
        Gizli elementleri, script/style bloklarını filtreler.
        """
        text: str = await self.page.evaluate(
            """
            () => {
                const skip = new Set(['SCRIPT','STYLE','NOSCRIPT','HEAD','META','LINK']);
                const walker = document.createTreeWalker(
                    document.body || document.documentElement,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode(node) {
                            const p = node.parentElement;
                            if (!p) return NodeFilter.FILTER_REJECT;
                            if (skip.has(p.tagName)) return NodeFilter.FILTER_REJECT;
                            const s = window.getComputedStyle(p);
                            if (s.display==='none' || s.visibility==='hidden' || s.opacity==='0')
                                return NodeFilter.FILTER_REJECT;
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                );
                const texts = new Set();
                let node;
                while ((node = walker.nextNode())) {
                    const t = node.textContent.trim();
                    if (t.length > 1) texts.add(t);
                }
                return [...texts].join(' | ');
            }
            """
        )
        return (text or "").strip()

    async def get_page_title(self) -> str:
        return await self.page.title()

    async def get_tabs(self) -> list[dict]:
        """
        Power BI sayfa sekmelerini tespit et.
        Birden fazla selector denenir; ilk sonuç döndürülür.
        """
        # Sayfa ve sekmelerin yüklenmesi için kısa bir bekleme (Power BI render süresi)
        await self.page.wait_for_timeout(3000)
        
        tab_selectors = [
            # PBIRS / Power BI Embedded navigasyon
            ".pageNavigation button",
            "[data-testid='page-navigation-item']",
            ".reportPageNavigationItem",
            "button[aria-selected]",
            "[role='tablist'] [role='tab']",
            "[role='tab']",
            ".pbi-tab",
            ".nav-item",
            # SSRS'de sayfa geçişi yok ama sekme benzeri alanlar
            ".tabLink",
        ]
        
        # Eğer rapor iframe içindeyse iframe'leri de tara
        frames = self.page.frames
        
        for sel in tab_selectors:
            try:
                # Önce ana sayfada ara
                elements = await self.page.query_selector_all(sel)
                
                # Eğer ana sayfada yoksa iframe'lerde ara
                if len(elements) <= 1:
                    for frame in frames:
                        try:
                            elements = await frame.query_selector_all(sel)
                            if len(elements) > 1:
                                break
                        except:
                            continue

                if len(elements) > 1:
                    result = []
                    for i, el in enumerate(elements):
                        label = (await el.inner_text()).strip()
                        aria  = await el.get_attribute("aria-label") or ""
                        result.append({
                            "index":    i,
                            "label":    label or aria or f"Sayfa {i + 1}",
                            "selector": sel,
                        })
                    return result
            except Exception:
                continue
        return []

    async def click_tab(self, tab: dict) -> None:
        """Belirtilen sekmeye tıkla, Power BI render bekleme yap."""
        try:
            elements = await self.page.query_selector_all(tab["selector"])
            idx = tab.get("index", 0)
            if idx < len(elements):
                await elements[idx].click()
                await self.page.wait_for_timeout(TAB_WAIT_MS)
        except Exception:
            pass  # tıklama başarısız olursa sessizce geç

    async def close(self) -> None:
        """Tüm kaynakları temizle."""
        try:
            if self._context:
                await self._context.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
