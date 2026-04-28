import os
import time
import base64
import logging
import webbrowser
import google.generativeai as genai
from PIL import Image, ImageGrab
import io

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RaportalVision")

class RaportalVisionAgent:
    def __init__(self, api_key, username, password):
        # Trim whitespace to avoid common API_KEY_INVALID errors
        self.api_key = api_key.strip() if api_key else None
        self.username = username
        self.password = password
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                logger.info("Gemini Vision AI configured successfully.")
            except Exception as e:
                logger.error(f"Failed to configure Gemini: {e}")

    def _focus_target_window(self, search_terms=["Raportal", "Power BI", "Edge", "Chrome"]):
        """Attempts to find and focus a window matching the report search terms."""
        try:
            import pywinauto
            from pywinauto import Desktop
            
            logger.info(f"Attempting to focus report window containing: {search_terms}")
            windows = Desktop(backend="uia").windows()
            for win in windows:
                title = win.window_text()
                if any(term.lower() in title.lower() for term in search_terms):
                    logger.info(f"Focusing window: {title}")
                    win.set_focus()
                    time.sleep(1) # Give it a moment to settle
                    return True
            
            # Fallback: If not found, minimize the Streamlit window to reveal what's behind
            logger.warning("No specific report window found. Attempting to minimize current app to reveal background.")
            # This is a bit aggressive but helps in automation scenarios
            return False
        except Exception as e:
            logger.error(f"Focus window failed: {e}")
            return False

    def capture_sheets_simple(self, url, wait_seconds=20):
        """Opens default browser, focuses it, and takes a FULL SCREEN shot."""
        screenshots = []
        try:
            logger.info(f"Opening report: {url}")
            webbrowser.open(url)
            
            # Wait for browser to open and content to start loading
            logger.info(f"Waiting {wait_seconds}s for load and focus...")
            time.sleep(5) # Early wait
            
            # Try to bring the browser to front
            self._focus_target_window()
            
            # Remaining wait for report body to render
            time.sleep(wait_seconds - 5)
            
            # One more focus attempt just before capture
            self._focus_target_window()
            
            logger.info("Capturing DATA SCREEN...")
            img = ImageGrab.grab() 
            
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            
            screenshots.append({"name": "Canlı Görünüm", "image": img_byte_arr.getvalue()})
            return screenshots
            
        except Exception as e:
            logger.error(f"Professional capture failed: {e}")
            return []

    def analyze_with_ai(self, screenshots, prompt_addon="", model_name='gemini-1.5-flash'):
        """Sends screenshots to Gemini Vision with focus on REAL NUMBERS and KPIs."""
        if not self.api_key: return "API Key eksik."
        if not screenshots: return "Hata: Ekran görüntüsü alınamadı."
            
        try:
            # Auto-discover models
            available_models = []
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        available_models.append(m.name)
            except:
                pass
            
            model = None
            target = f"models/{model_name.replace('models/', '')}"
            if target in available_models:
                model = genai.GenerativeModel(target)
            
            if not model:
                for alt in ['flash', 'pro', '1.5']:
                    found = [m for m in available_models if alt in m.lower()]
                    if found:
                        model = genai.GenerativeModel(found[0])
                        break
            
            if not model:
                model = genai.GenerativeModel('gemini-1.5-flash')

            vision_parts = [
                "SEN BİR PROFESYONEL VERİ ANALİSTİSİN. GÖRÜNTÜDEKİ GERÇEK RAKAMLARI BUL.",
                "1. Görüntüdeki tüm sayısal KPI'ları (örn: Churn Oranı, Toplam Satış, Hedef yüzdesi) tablo halinde çıkar.",
                "2. Grafiklerin yanındaki lejant (legend) değerlerini ve eksenlerdeki gerçek rakamları oku.",
                "3. Nisan 2024 (veya güncel ay) için görünen net sayısal durumu belirt.",
                "4. Arayüz elemanlarını (butonlar, menüler) görmezden gel, sadece veriye odaklan.",
                f"\nKullanıcı Notu: {prompt_addon}",
                "\nLütfen 'GERÇEK VERİ ÖZETİ' başlığıyla çok kısa ve rakam odaklı bir rapor sun."
            ]
            
            for ss in screenshots:
                img = Image.open(io.BytesIO(ss["image"]))
                vision_parts.append(img)
                
            # --- PROFESSIONAL RETRY LOGIC FOR 429 ---
            max_retries = 3
            last_err = None
            for attempt in range(max_retries):
                try:
                    response = model.generate_content(vision_parts)
                    return response.text
                except Exception as e:
                    last_err = e
                    if "429" in str(e):
                        wait_time = 5 * (attempt + 1)
                        logger.warning(f"Quota exceeded (429). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    raise e
            
            return f"AI Analiz Hatası (Kota Aşımı): 3 deneme başarısız oldu. Lütfen 30 saniye bekleyip tekrar deneyin. Detay: {last_err}"
        except Exception as e:
            return f"AI Analiz Hatası: {e}"
