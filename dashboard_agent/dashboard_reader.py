"""
dashboard_reader.py
===================
Dashboard içeriğini okur:
- Sayfa başlığı, görünür metin
- Filtreler, KPI değerleri, görsel başlıkları
- Çok sayfalı dashboard'larda sekme gezinme
- Her sayfa için screenshot
- Structured JSON üretme

Tüm işlemler READ-ONLY'dir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote

from .browser_agent import RaportalBrowserAgent
from .config import ANALYSIS_DIR


# ── Veri Yapıları ─────────────────────────────────────────────────────────────

@dataclass
class PageData:
    """Tek bir dashboard sayfasına (sekme) ait veriler."""
    tab_name:        str
    title:           str
    url:             str
    screenshot_path: str
    visible_text:    str
    filters:         list[str] = field(default_factory=list)
    kpi_values:      list[str] = field(default_factory=list)
    visual_titles:   list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tab_name":        self.tab_name,
            "title":           self.title,
            "url":             self.url,
            "screenshot_path": self.screenshot_path,
            # LLM'e gönderilecek metin — token sınırı için kırpılır
            "visible_text":    self.visible_text[:5000],
            "filters":         self.filters,
            "kpi_values":      self.kpi_values,
            "visual_titles":   self.visual_titles,
        }


@dataclass
class DashboardData:
    """Tüm sekmeler dahil dashboard bütünü."""
    url:         str
    report_name: str
    pages:       list[PageData]    = field(default_factory=list)
    error:       Optional[str]     = None

    def to_dict(self) -> dict:
        return {
            "url":         self.url,
            "report_name": self.report_name,
            "pages":       [p.to_dict() for p in self.pages],
            "error":       self.error,
        }


# ── DOM Çıkarma Scripti ───────────────────────────────────────────────────────

_DOM_EXTRACT_JS = """
() => {
    const uniq = arr => [...new Set(arr.filter(Boolean))];

    // ── Filtreler ──────────────────────────────────────────────────────────
    const filterSels = [
        '[class*="slicer"]',
        '[class*="filter"]',
        '[aria-label*="Filter" i]',
        '[data-testid*="filter" i]',
        '.filterCard',
    ];
    const filters = [];
    filterSels.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            const t = el.innerText?.trim();
            if (t && t.length < 250 && t.length > 1) filters.push(t);
        });
    });

    // ── KPI Kartları ──────────────────────────────────────────────────────
    const kpiSels = [
        '[class*="kpiVisual"]',
        '[class*="cardItem"]',
        '[data-viz-type="card"]',
        '[class*="card"] [class*="value"]',
        '.kpi',
    ];
    const kpis = [];
    kpiSels.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            const t = el.innerText?.trim();
            if (t && t.length < 300) kpis.push(t);
        });
    });

    // ── Görsel Başlıkları ─────────────────────────────────────────────────
    const titleSels = [
        '[class*="visualTitle"]',
        '[class*="visual-title"]',
        '[class*="titleContainer"]',
        '[aria-label*="title" i]',
        'h1, h2, h3',
        'caption',
        'th',
    ];
    const visuals = [];
    titleSels.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            const t = el.innerText?.trim();
            if (t && t.length < 150 && t.length > 1) visuals.push(t);
        });
    });

    return {
        filters: uniq(filters).slice(0, 25),
        kpis:    uniq(kpis).slice(0, 25),
        visuals: uniq(visuals).slice(0, 40),
    };
}
"""


# ── Reader ────────────────────────────────────────────────────────────────────

class DashboardReader:
    def __init__(self, agent: RaportalBrowserAgent) -> None:
        self.agent = agent

    @staticmethod
    def _report_name_from_url(url: str) -> str:
        try:
            parts = urlparse(url).path.rstrip("/").split("/")
            return unquote(parts[-1]) if parts else url
        except Exception:
            return url

    @staticmethod
    def _safe_tab_name(name: str) -> str:
        return re.sub(r"[^\w\u00C0-\u017E\- ]", "_", name).strip()[:60]

    async def _extract_structured(self) -> tuple[list[str], list[str], list[str]]:
        try:
            result = await self.agent.page.evaluate(_DOM_EXTRACT_JS)
            return (
                result.get("filters", []),
                result.get("kpis",    []),
                result.get("visuals", []),
            )
        except Exception:
            return [], [], []

    async def _read_single_page(
        self,
        tab_name: str,
        url: str,
        page_idx: int,
    ) -> PageData:
        title               = await self.agent.get_page_title()
        safe_name           = self._safe_tab_name(tab_name)
        ss_label            = f"page_{page_idx:02d}_{safe_name}"
        screenshot_path     = await self.agent.screenshot(ss_label)
        visible_text        = await self.agent.get_visible_text()
        filters, kpis, visuals = await self._extract_structured()

        return PageData(
            tab_name        = tab_name,
            title           = title,
            url             = url,
            screenshot_path = str(screenshot_path),
            visible_text    = visible_text,
            filters         = filters,
            kpi_values      = kpis,
            visual_titles   = visuals,
        )

    async def read_dashboard(self, url: str, max_pages: int = 5) -> DashboardData:
        """
        Verilen URL'deki dashboard'u tamamen oku.
        Çok sayfalıysa en fazla max_pages kadar sekmeyi gezer.
        """
        result = DashboardData(url=url, report_name=self._report_name_from_url(url))

        try:
            await self.agent.navigate(url)
        except Exception as exc:
            result.error = str(exc)
            return result

        # Sekmeleri tespit et
        tabs = await self.agent.get_tabs()

        if not tabs:
            # Tek sayfa
            page_data = await self._read_single_page("Ana Sayfa", url, 0)
            result.pages.append(page_data)
        else:
            # Çok sayfalı — her sekmeyi gez
            for i, tab in enumerate(tabs):
                if i >= max_pages:
                    break
                
                await self.agent.click_tab(tab)
                page_data = await self._read_single_page(
                    tab.get("label", f"Sayfa {i + 1}"),
                    self.agent.page.url,
                    i,
                )
                result.pages.append(page_data)

        return result
