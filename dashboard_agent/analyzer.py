"""
analyzer.py
===========
Dashboard verisini (screenshot + DOM metin) Gemini'ye gönderir,
Türkçe iş yorumu üretir.

Güvenlik: API key sadece çalışma zamanında geçirilir; dosyaya yazılmaz.
"""

from __future__ import annotations

import base64
import time
import logging
import io
from pathlib import Path
from typing import Optional
from PIL import Image

from .config import GEMINI_MODEL
from .dashboard_reader import DashboardData

try:
    import google.generativeai as genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False


# ── Prompt şablону ─────────────────────────────────────────────────────────

_SYSTEM = (
    "Sen Kariyer.net için kıdemli bir İş Analisti (BI Business Analyst) ve veri hikayeleştirme uzmanısın. "
    "Görevin, dashboard görsellerindeki verileri derinlemesine analiz ederek profesyonel bir yönetici özeti (Executive Summary) sunmaktır. "
    "Sadece raporun ne olduğunu söyleme; tablolar ve grafiklerdeki sayıları, yüzdeleri ve dönem karşılaştırmalarını (yıllar, aylar vb.) kullanarak 'verilerle konuş'."
)

_OUTPUT_TEMPLATE = """
---

### 📝 Rapor Tanıtımı: **{report_name}**

{intro_text}

---
"""


def _encode_image(path: str, max_size: int = 1024) -> Optional[dict]:
    """Screenshot'ı optimize eder (resize + compressed JPEG) ve Gemini formatına çevirir."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        # Görseli aç ve optimize et
        with Image.open(p) as img:
            if img.width > max_size:
                ratio = max_size / float(img.width)
                new_height = int(float(img.height) * ratio)
                img = img.resize((max_size, new_height), Image.Resampling.LANCZOS)
            
            # RGB'ye çevir (JPEG için şart) ve sıkıştır (75 kalite)
            img = img.convert("RGB")
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=75, optimize=True)
            data = buffer.getvalue()
            
        return {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode()}
    except Exception as e:
        logging.error(f"Görsel optimizasyon hatası ({path}): {e}")
        return None


def _build_parts(report_name: str, pages: list[dict], max_img_size: int = 1024) -> list:
    """Gemini'ye gönderilecek içerik listesini oluştur."""
    parts: list = [
        _SYSTEM,
        f"\n\n## İncelenen Dashboard: **{report_name}**\n",
    ]

    for p in pages:
        tab    = p.get("tab_name",      "–")
        title  = p.get("title",         "–")
        text   = p.get("visible_text",  "")[:1000]
        flt    = ", ".join(p.get("filters",       [])) or "tespit edilemedi"
        kpis   = ", ".join(p.get("kpi_values",    [])) or "tespit edilemedi"
        visuals= ", ".join(p.get("visual_titles", [])) or "tespit edilemedi"

        parts.append(
            f"\n\n---\n"
            f"### Sekme: {tab}\n"
            f"**Sayfa başlığı:** {title}\n"
            f"**Görünen metin:** {text}\n"
            f"**Filtreler:** {flt}\n"
            f"**KPI değerleri:** {kpis}\n"
            f"**Görsel başlıkları:** {visuals}\n"
        )

        # Screenshot ekle
        img = _encode_image(p.get("screenshot_path", ""), max_size=max_img_size)
        if img:
            parts.append(img)

    # Çıktı format talebi
    parts.append(
        "\n\nYukarıdaki dashboard verilerine dayanarak profesyonel bir analiz yaz. "
        "Talimatlar:\n"
        "1. **Verilerle Konuş:** Tablolarda gördüğün en yüksek/en düşük hacimli değerleri, kritik yüzdeleri ve önemli farkları doğrudan belirt.\n"
        "2. **Karşılaştırma Yap:** Varsa yıllar (2025, 2026...), aylar veya kategoriler arası değişimleri ve trendleri mutlaka yorumla.\n"
        "3. **Stratejik Bakış:** Bu verilerin iş başarısı (Satış dönüşümü, ekip performansı, risk yönetimi vb.) açısından ne anlama geldiğini net bir şekilde çıkar.\n"
        "4. **Format:** '### 📝 Profesyonel Rapor Analizi' başlığıyla başla ve Kariyer.net standartlarına uygun, kurumsal bir dil kullan.\n\n"
        f"### 📝 Profesyonel Rapor Analizi: **{report_name}**\n\n"
        "[Buraya veriye dayalı, derinlikli yönetici özetini yaz]\n\n"
        "---"
    )

    return parts


# ── Dışarıya açık fonksiyon ───────────────────────────────────────────────────

def analyze_dashboard(
    dashboard: DashboardData,
    api_key:   str,
    model_name: str = GEMINI_MODEL,
) -> str:
    """
    DashboardData → Türkçe Markdown analiz.
    Döndürür: analiz metni (str).
    """
    if not _HAS_GENAI:
        return (
            "**Hata:** `google-generativeai` paketi yüklü değil.\n"
            "Çözüm: `pip install google-generativeai`"
        )

    if not api_key:
        return "**Hata:** Gemini API key girilmedi. Soldan bağlanın."

    if dashboard.error:
        return f"**Dashboard okunamadı:**\n\n{dashboard.error}"

    if not dashboard.pages:
        return "**Dashboard'da hiç sayfa verisi bulunamadı.**"

    genai.configure(api_key=api_key)
    model    = genai.GenerativeModel(model_name)
    
    max_retries = 10 # Artırıldı
    for attempt in range(max_retries):
        try:
            # Her başarısız 429 denemesinde görsel boyutunu küçült (Progessive Compression)
            # 1. deneme: 1024px, 2. deneme: 800px, 3. deneme: 600px, 4+. deneme: 400px
            current_img_size = 1024
            if attempt == 1: current_img_size = 800
            elif attempt == 2: current_img_size = 600
            elif attempt >= 3: current_img_size = 400
            
            # Parts'ı her denemede (boyut değiştiyse) yeniden oluştur
            current_parts = _build_parts(
                dashboard.report_name,
                [p.to_dict() for p in dashboard.pages],
                max_img_size=current_img_size
            )

            response = model.generate_content(current_parts)
            return getattr(response, "text", str(response))
        except Exception as exc:
            msg = str(exc)
            
            # Kota aşımı (429) durumu
            if ("429" in msg or "quota" in msg.lower()) and attempt < max_retries - 1:
                # Fallback Piramidi: Pro -> Flash-1.5 -> Flash-8B
                next_model = None
                if "flash" not in model_name.lower():
                    next_model = "gemini-1.5-flash"
                elif "8b" not in model_name.lower() and attempt > 3:
                    next_model = "gemini-1.5-flash-8b"
                
                if next_model:
                    logging.warning(f"Gemini 429: {model_name} kotası doldu, '{next_model}' deneniyor...")
                    model_name = next_model
                    model = genai.GenerativeModel(model_name)
                
                # Exponential backoff + Jitter
                import random
                # 3. denemeden sonra 65 saniye bekle (Free tier reset period)
                base_wait = (attempt + 1) * 15
                if attempt >= 2: base_wait = 65 
                
                wait_time = base_wait + random.randint(1, 10)
                logging.warning(f"Gemini 429 tespit edildi. {wait_time}s içinde tekrar denenecek... (Deneme {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue

            # Model 404 hatası: Kullanıcının anahtarında bu isim yoksa alternatifleri dene
            if ("404" in msg or "not found" in msg.lower()) and attempt < max_retries - 1:
                fallbacks = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-pro-vision"]
                next_model = next((m for m in fallbacks if m != model_name and m not in str(exc)), None)
                if next_model:
                    logging.warning(f"Gemini 404: {model_name} bulunamadı, '{next_model}' deneniyor...")
                    model_name = next_model
                    model = genai.GenerativeModel(model_name)
                    continue
            
            if "429" in msg or "quota" in msg.lower():
                return (
                    "**Gemini kota aşıldı (429).**\n\n"
                    "Bu hata çok fazla istek gönderildiğinde (veya ücretsiz kota dolduğunda) oluşur.\n"
                    "Sistem {} kez otomatik deneme (kademeli bekleme ile) yaptı ancak başarısız oldu.\n\n"
                    "**Çözümler:**\n"
                    "1. **En önemli:** Soldaki model listesinden içerisinde **'flash'** ibaresi geçen bir model seçin (Flash modellerin kotası Pro modellerine göre çok daha yüksektir).\n"
                    "2. Birkaç dakika bekleyip tekrar deneyin.\n"
                    "3. Üstteki sliderdan sayfa sayısını azaltın (Örn: 1 veya 2 sayfa).\n"
                    "4. Farklı bir Gemini API key kullanın."
                    .format(max_retries)
                )
            if "400" in msg and "Interactions API" in msg:
                return (
                    "**Model Uyumsuzluğu (400 - Interactions API Only).**\n\n"
                    "Seçtiğiniz model (`{}`) görüntülü rapor analizi için uygun değil. "
                    "Bu model sadece canlı sohbet veya web araştırması için tasarlanmıştır.\n\n"
                    "**Çözüm:** Lütfen soldaki panelden 'gemini-1.5-flash' veya 'gemini-2.0-flash' gibi **standart** bir model seçin."
                    .format(model_name)
                )

            if "403" in msg or "permission" in msg.lower() or "ip address" in msg.lower():
                return (
                    "**Gemini Erişim Reddi (403).**\n\n"
                    "Bu hata genellikle iki nedenden kaynaklanır:\n"
                    "1. **IP Kısıtlaması:** Kurumsal API anahtarınız sadece belirli IP adreslerine (şirket sunucuları gibi) izin veriyor olabilir.\n"
                    "2. **Yetki Eksikliği:** Kullandığınız model bu anahtara açık olmayabilir.\n\n"
                    "**Çözüm:** Soldaki panelden 'Erişilebilir Modelleri Tara' butonuna basarak anahtarınızın hangi modellere izni olduğunu kontrol edin."
                )
            if "404" in msg or "not found" in msg.lower():
                return f"**Model Bulunamadı (404):** '{model_name}' bu anahtar için geçerli değil. Lütfen soldan 'Erişilebilir Modelleri Tara' butonuna basın."
            
            return f"**AI analiz hatası:**\n\n{exc}"


def suggest_report_template(
    user_prompt: str,
    api_key: str,
    model_name: str = "gemini-1.5-flash",
    inspiration_context: str = "",
    inspiration_data: list[dict] = None,
    real_entities: dict = None,
    report_type: str = "Otomatik (AI Karar Versin)",
    excel_schema: str = ""
) -> str:
    """
    Kullanıcının iş ihtiyacına göre bir rapor taslağı önerir.
    'report_type' parametresine göre Power BI, SSRS (Paginated) veya Excel kurgular.
    'excel_schema' verilmişse, tasarımı o tablo yapısına göre oluşturur.
    """
    if not _HAS_GENAI:
        return "Hata: `google-generativeai` paketi yüklü değil."
    if not api_key:
        return "Hata: Gemini API key eksik."

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    # Context Parts
    prompt_parts = []

    # --- DYNAMIC TECHNOLOGY / DATA CONTEXT ---
    if excel_schema:
        prompt_parts.append(f"### 📁 YÜKLENEN EXCEL VERİSİ (GROUND TRUTH)\nKullanıcı bir Excel/CSV dosyası yükledi. Tasarımında SADECE bu kolonları kullan:\n{excel_schema}\n")
    
    if report_type and report_type != "Otomatik (AI Karar Versin)":
        prompt_parts.append(f"### HEDEF TEKNOLOJİ: {report_type}\nTaslağını bu teknolojiye (Power BI/SSRS/Excel) uygun kurgula.\n")
    
    # --- REAL WORLD ENTITIES (Data-Driven Design) ---
    entity_block = ""
    if real_entities:
        bolumler = ", ".join(real_entities.get("bolumler", []))
        ikcolar = ", ".join(real_entities.get("ikcolar", []))
        yenileme_tipleri = ", ".join(real_entities.get("yenileme_tipleri", []))
        musteri_listesi = ", ".join([f"{m['unvan']} ({m['kod']})" for m in real_entities.get("musteriler", [])])
        entity_block = f"""
    ### GERÇEK DÜNYA VERİLERİ VE KAYNAKLAR (KRİTİK!)
    Aşağıdaki isimler Kariyer.net'in gerçek organizasyon yapısından ve BIDB veritabanından alınmıştır.
    Tasarımında örnek veri yerine MUTLAKA bu gerçek bilgileri kullan:
    
    1. **BIDB Ground Truth:** Satış, ürün tanımı, paket bilgileri ve yenileme tipleri için **[18_satislar]** tablosundaki mantığı temel al.
    2. **Kurumsal Yerleşim:** Kariyer.net kurumsal kimliği gereği, her dashboard sayfasının **SOL ÜST** köşesinde mutlaka Kariyer.net logosu bulunmalıdır.
    3. **Organizasyon:**
       - Gerçek Bölümler: {bolumler}
       - Gerçek İKÇO İsimleri: {ikcolar}
       - Gerçek Yenileme Tipleri: {yenileme_tipleri}
       - Gerçek Müşteri Listesi: {musteri_listesi}
    --------------------------------------------------
    """
    # --- SYSTEM INSTRUCTIONS ---
    prompt_parts.append(f"""
    SENARYO: AGENT SYSTEM PROMPT
 
    Sen bir Kariyer.net BI Solutions Architect ve Tasarım Ajanısın (Raportal Vizyoneri).
    Görevin, kullanıcının talebini analiz ederek Kariyer.net standartlarında (Kariyer Moru #8c28e8 ağırlıklı) profesyonel bir dashboard tasarımı üretmektir.
 
    {entity_block}
    Eğer talep Satış/Portföy üzerineyse, İşe Alım terminolojisini (Aday, İlan, Başvuru vb.) KESİNLİKLE kullanma! Talebin özündeki iş sorusuna sadık kal.

    Amacın, kullanıcının talebinden iş ihtiyacını doğru anlamak, uygun analiz yaklaşımını seçmek, mümkünse veri/metadata ile eşleştirmek ve sonuçta Power BI standartlarına uygun, sade, aksiyon alınabilir ve mantıklı bir dashboard tasarımı önermektir.

    ### GÖRSEL İLHAM TALİMATI
    Eğer aşağıda mevcut raporların ekran görüntüleri paylaşılmışsa, bu görüntüleri Kariyer.net'in yerleşim düzenini, grafik tiplerini ve görsel hiyerarşisini anlamak için 'Görsel Referans' olarak kullan. Yeni tasarımı bu standartlara yakın kurgula.
    """)

    # --- INSPIRATION DATA (Metadata & Screenshots) ---
    if inspiration_context or inspiration_data:
        prompt_parts.append("\n### 💡 MEVCUT RAPORLARDAN İLHAM (REFERANS BİLGİLER)\n")
        
        if inspiration_context:
            prompt_parts.append(f"Aşağıdaki raporlar metadata bazlı benzer bulundu:\n{inspiration_context}\n")
            
        if inspiration_data:
            for i, item in enumerate(inspiration_data):
                prompt_parts.append(f"**Referans Rapor {i+1} Analizi:** {item.get('text', '')[:500]}\n")
                img_part = _encode_image(item.get("image_path", ""))
                if img_part:
                    prompt_parts.append(img_part)

    # --- CORE TASK & FORMAT ---
    prompt_parts.append(f"""
    --------------------------------------------------
    ### KULLANICI İHTİYACI
    "{user_prompt}"

    ### TEMEL GÖREVİN
    Kullanıcının yazdığı ihtiyacı yukarıdaki referansları da dikkate alarak analiz et:
    1. İş ihtiyacını çıkar
    2. KPI, boyut ve filtreleri belirle
    3. En uygun dashboard şablonunu seç
    4. TASARIM ÖNERİSİNİ ÜRET (Mandatory Format)

    ### ZORUNLU ÇIKTI FORMATI (Markdown)
    1. **İhtiyaç Özeti** (Amaç, Hedef Kullanıcı, Analiz Tipi)
    2. **Önerilen Dashboard Şablonu** (Şablon Adı, Seçilme Nedeni)
    3. **Dashboard Tasarımı** (Sayfa Sayısı, Görsellerin yerleşimi vb.)
    4. **KPI ve Boyutlar**
    5. **Tasarım Gerekçesi** (Neden bu tasarım Kariyer.net standartlarına uygundur?)
    6. **Alternatif Tasarım Önerileri**
    7. **Eksik Veri / Riskler**

    Lütfen profesyonel bir BI Solutions Architect gibi tasarımı oluştur.
    """)

    try:
        # Model ismi temizleme (bazen SDK prefix ekleyebiliyor)
        clean_model_name = model_name.split("/")[-1]
        model = genai.GenerativeModel(clean_model_name)
        response = model.generate_content(prompt_parts)
        return response.text
    except Exception as e:
        error_str = str(e)
        
        # Kullanıcı dostu IP kısıtlaması uyarısı
        if "IP_ADDRESS_BLOCKED" in error_str or "IP address restriction" in error_str:
            return (
                "⚠️ **Gemini API Anahtarınızda IP Kısıtlaması Bulunuyor!**\n\n"
                "Bu hata, Google'ın güvenlik ayarları gereği mevcut internet bağlantınızdan (IP adresinizden) gelen isteği reddettiği anlamına gelir.\n\n"
                "**Kesin Çözüm İşlemleri:**\n"
                "1. [Google AI Studio](https://aistudio.google.com/app/apikey) adresine gidin.\n"
                "2. Kullandığınız API anahtarının yanındaki **'Edit'** veya ayarlar simgesine tıklayın.\n"
                "3. **'IP Restrictions'** (IP Kısıtlamaları) bölümünü bulun.\n"
                "4. Bu kısmı **'None'** (Yok) olarak değiştirin veya mevcut IP adresinizi listeye ekleyin.\n\n"
                "*Not: Şirket ağı veya VPN kullanıyorsanız IP adresiniz değiştiği için bu hatayı alıyor olabilirsiniz.*"
            )

        # 404 durumunda alternatif model ismini dene (flash-latest)
        if "404" in error_str or "not found" in error_str.lower():
            try:
                fallback_name = "gemini-1.5-flash-latest" if "latest" not in clean_model_name else "gemini-1.5-flash"
                model = genai.GenerativeModel(fallback_name)
                response = model.generate_content(prompt_parts)
                return response.text
            except Exception as e2:
                return f"Tasarım oluşturulurken model hatası oluştu (404): {error_str}. Alternatif denemesi de başarısız: {str(e2)}"
        
        # 400 durumunda Interactions API hatası kontrolü
        if "400" in error_str and "Interactions API" in error_str:
            return (
                "⚠️ **Model Uyumsuzluğu (Interactions API Only).**\n\n"
                "Seçtiğiniz model (`{}`) bu tasarım işlemi için uygun değil. "
                "Bu tip modeller (Örn: deep-research) sadece özel sohbet arayüzleri için tasarlanmıştır.\n\n"
                "**Çözüm:** Lütfen soldaki panelden **'gemini-1.5-flash'** veya **'gemini-2.0-flash'** gibi standart bir model seçerek tekrar deneyin."
                .format(clean_model_name)
            )

        return f"Tasarım oluşturulurken bir hata oluştu: {error_str}"
        
        return f"Tasarım oluşturulurken bir hata oluştu: {error_str}"
