"""
history_manager.py
==================
Raportal Vizyoneri tasarım taleplerini yerel bir JSON dosyasında saklar.
"""

import json
import datetime
from pathlib import Path
from typing import List, Dict
from .config import VISIONARY_HISTORY_FILE

def save_visionary_request(prompt: str, result_text: str, image_path: str = None):
    """Yeni bir tasarım talebini geçmişe kaydeder."""
    history = _load_raw_history()
    
    # Çok uzun sonuçları özetle (ilk 500 karakter yeterli)
    summary = result_text[:500] + "..." if len(result_text) > 500 else result_text
    
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    display_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_image_rel_path = None
    if image_path and Path(image_path).exists():
        history_dir = Path(image_path).parent / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        new_image_name = f"mockup_{timestamp_str}.png"
        new_image_path = history_dir / new_image_name
        import shutil
        shutil.copy2(image_path, new_image_path)
        # Store relative path for portability
        saved_image_rel_path = f"assets/visionary_mockups/history/{new_image_name}"

    entry = {
        "timestamp": display_timestamp,
        "id": timestamp_str,
        "prompt": prompt,
        "summary": summary,
        "image_path": saved_image_rel_path
    }
    
    history.append(entry)
    
    if len(history) > 100: # Increase history limit slightly
        history = history[-100:]
        
    try:
        with open(VISIONARY_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_visionary_history(limit: int = 5) -> List[Dict]:
    """Son tasarım taleplerini getirir."""
    history = _load_raw_history()
    history.sort(key=lambda x: x["timestamp"], reverse=True)
    return history[:limit]

def _load_raw_history() -> List[Dict]:
    """JSON dosyasından tüm geçmişi yükler."""
    if not VISIONARY_HISTORY_FILE.exists():
        return []
    try:
        with open(VISIONARY_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
