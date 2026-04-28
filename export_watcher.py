from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


DEFAULT_CONFIG = {
    "export_dirs": [],
    "recursive": True,
    "analyze_existing_on_start": True,
    "supported_extensions": [".csv", ".xlsx", ".xls"],
    "output_dir": "./export_analysis",
    "debounce_seconds": 2,
}

KPI_HINTS = [
    "kpi",
    "oran",
    "adet",
    "tutar",
    "gelir",
    "sayi",
    "count",
    "total",
    "ciro",
    "satis",
    "hedef",
    "gercek",
    "maliyet",
    "kar",
]


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "_", text)
    return text.strip("_") or "file"


def load_config(config_path: Path | None) -> dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    if config_path and config_path.exists():
        user_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        cfg.update(user_cfg)
    return cfg


def wait_file_ready(path: Path, debounce_seconds: int) -> bool:
    # File yazımı bitmeden okumayı engeller.
    last_size = -1
    stable_count = 0
    for _ in range(20):
        if not path.exists() or not path.is_file():
            return False
        try:
            size = path.stat().st_size
        except OSError:
            return False

        if size > 0 and size == last_size:
            stable_count += 1
            if stable_count >= max(1, debounce_seconds):
                return True
        else:
            stable_count = 0
        last_size = size
        time.sleep(1)
    return False


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_table(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        try:
            df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
        except Exception:
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except Exception:
                df = pd.read_csv(path, encoding="cp1254")
        return df
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Desteklenmeyen uzanti: {ext}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def find_date_column(df: pd.DataFrame) -> str | None:
    name_candidates = [c for c in df.columns if any(k in c.lower() for k in ["date", "tarih", "gun", "ay", "donem"])]
    scan_cols = name_candidates + [c for c in df.columns if c not in name_candidates]

    for col in scan_cols:
        if df[col].dtype.kind in "mM":
            return col
        sample = df[col].dropna().astype(str).head(20)
        if sample.empty:
            continue
        parsed = pd.to_datetime(sample, errors="coerce", dayfirst=True)
        if parsed.notna().mean() >= 0.6:
            return col
    return None


def pick_kpi_columns(df: pd.DataFrame) -> list[str]:
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not num_cols:
        return []

    hinted = [c for c in num_cols if any(k in c.lower() for k in KPI_HINTS)]
    if hinted:
        return hinted[:10]
    return num_cols[:10]


def series_trend(values: pd.Series) -> str:
    values = values.dropna()
    if len(values) < 2:
        return "yetersiz veri"
    first = float(values.iloc[0])
    last = float(values.iloc[-1])
    if first == 0:
        if last == 0:
            return "sabit"
        return "artis"
    delta_pct = ((last - first) / abs(first)) * 100
    if delta_pct > 5:
        return f"artis (%{delta_pct:.1f})"
    if delta_pct < -5:
        return f"azalis (%{delta_pct:.1f})"
    return "yatay"


def summarize_kpis(df: pd.DataFrame) -> dict[str, Any]:
    df = normalize_columns(df)
    date_col = find_date_column(df)

    if date_col:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
        df = df.sort_values(date_col)

    kpi_cols = pick_kpi_columns(df)
    kpis = []
    for col in kpi_cols:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        item = {
            "name": col,
            "count": int(s.count()),
            "min": float(s.min()),
            "max": float(s.max()),
            "mean": float(s.mean()),
            "sum": float(s.sum()),
            "latest": float(s.iloc[-1]),
            "trend": series_trend(s),
        }
        kpis.append(item)

    text_lines = []
    if date_col:
        text_lines.append(f"Zaman kolonu: {date_col}")
    if not kpis:
        text_lines.append("Sayisal KPI kolonu bulunamadi.")
    else:
        for k in kpis[:5]:
            text_lines.append(
                f"{k['name']}: son={k['latest']:.2f}, ort={k['mean']:.2f}, trend={k['trend']}"
            )

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "date_column": date_col,
        "kpi_count": int(len(kpis)),
        "kpis": kpis,
        "summary_text": " | ".join(text_lines),
    }


def write_analysis_outputs(out_dir: Path, src_path: Path, result: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_ts()
    slug = safe_slug(src_path.stem)

    payload = {
        "source_file": str(src_path),
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        **result,
    }

    json_path = out_dir / f"{stamp}_{slug}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Rapor Analizi - {src_path.name}",
        "",
        f"- Analiz Zamanı: {payload['analyzed_at']}",
        f"- Satır Sayısı: {payload['row_count']}",
        f"- Kolon Sayısı: {payload['column_count']}",
        f"- KPI Sayısı: {payload['kpi_count']}",
        "",
        "## Özet",
        payload["summary_text"],
        "",
    ]
    if payload["kpis"]:
        md_lines.extend([
            "## KPI Detayları",
            "| KPI | Son Değer | Ortalama | Min | Max | Trend |",
            "|---|---:|---:|---:|---:|---|",
        ])
        for k in payload["kpis"]:
            md_lines.append(
                f"| {k['name']} | {k['latest']:.2f} | {k['mean']:.2f} | {k['min']:.2f} | {k['max']:.2f} | {k['trend']} |"
            )

    md_path = out_dir / f"{stamp}_{slug}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    index_path = out_dir / "analysis_index.csv"
    idx_row = pd.DataFrame([
        {
            "analyzed_at": payload["analyzed_at"],
            "source_file": str(src_path),
            "row_count": payload["row_count"],
            "kpi_count": payload["kpi_count"],
            "summary": payload["summary_text"],
            "json_output": str(json_path),
            "md_output": str(md_path),
        }
    ])
    if index_path.exists():
        old = pd.read_csv(index_path, encoding="utf-8-sig")
        all_rows = pd.concat([old, idx_row], ignore_index=True)
    else:
        all_rows = idx_row
    all_rows.to_csv(index_path, index=False, encoding="utf-8-sig")


@dataclass
class WatchContext:
    cfg: dict[str, Any]
    seen_hashes: dict[str, str]


def process_file(path: Path, ctx: WatchContext) -> None:
    if path.suffix.lower() not in set(ctx.cfg["supported_extensions"]):
        return
    if not wait_file_ready(path, int(ctx.cfg["debounce_seconds"])):
        return

    try:
        current_hash = file_hash(path)
    except Exception:
        return

    key = str(path.resolve())
    if ctx.seen_hashes.get(key) == current_hash:
        return

    try:
        df = load_table(path)
        result = summarize_kpis(df)
        out_dir = Path(ctx.cfg["output_dir"]).resolve()
        write_analysis_outputs(out_dir, path, result)
        ctx.seen_hashes[key] = current_hash
        print(f"[OK] Analiz tamamlandi: {path.name}")
    except Exception as exc:
        print(f"[HATA] {path.name}: {exc}")


class ExportEventHandler(FileSystemEventHandler):
    def __init__(self, ctx: WatchContext):
        super().__init__()
        self.ctx = ctx

    def on_created(self, event):
        if not event.is_directory:
            process_file(Path(event.src_path), self.ctx)

    def on_modified(self, event):
        if not event.is_directory:
            process_file(Path(event.src_path), self.ctx)


def scan_existing(ctx: WatchContext) -> None:
    dirs = [Path(p).resolve() for p in ctx.cfg["export_dirs"]]
    recursive = bool(ctx.cfg["recursive"])
    exts = set(ctx.cfg["supported_extensions"])
    for d in dirs:
        if not d.exists():
            continue
        files = d.rglob("*") if recursive else d.glob("*")
        for f in files:
            if f.is_file() and f.suffix.lower() in exts:
                process_file(f, ctx)


def validate_config(cfg: dict[str, Any]) -> None:
    if not cfg.get("export_dirs"):
        raise ValueError("Config icinde export_dirs bos olamaz.")


def run_once(cfg: dict[str, Any]) -> None:
    ctx = WatchContext(cfg=cfg, seen_hashes={})
    scan_existing(ctx)
    print("Tek seferlik analiz tamamlandi.")


def run_watch(cfg: dict[str, Any]) -> None:
    ctx = WatchContext(cfg=cfg, seen_hashes={})
    observer = Observer()
    handler = ExportEventHandler(ctx)

    dirs = [Path(p).resolve() for p in cfg["export_dirs"]]
    recursive = bool(cfg["recursive"])

    for d in dirs:
        if not d.exists():
            print(f"[UYARI] Klasor bulunamadi, atlandi: {d}")
            continue
        observer.schedule(handler, str(d), recursive=recursive)
        print(f"[IZLEME] {d}")

    if cfg.get("analyze_existing_on_start", True):
        scan_existing(ctx)

    observer.start()
    print("Izleme basladi. Durdurmak icin Ctrl+C.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Izleme durduruluyor...")
    finally:
        observer.stop()
        observer.join()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raportal export klasor izleyici ve KPI analiz araci")
    parser.add_argument("--config", type=str, default="export_watch_config.json", help="Config dosya yolu")
    parser.add_argument("--once", action="store_true", help="Mevcut dosyalari tek sefer analiz et ve cik")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg_path = Path(args.config)

    if not cfg_path.exists() and cfg_path.name == "export_watch_config.json":
        example = Path("export_watch_config.example.json")
        if example.exists():
            cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Config olusturuldu: {cfg_path.resolve()}")

    cfg = load_config(cfg_path if cfg_path.exists() else None)
    validate_config(cfg)

    if args.once:
        run_once(cfg)
        return
    run_watch(cfg)


if __name__ == "__main__":
    main()