# ══════════════════════════════════════════════════════════════════════
#  mod_grafik_yorumu.py — Grafik Görseli Yapay Zeka Yorumlama Motoru v1.0
#  Gemini Vision API ile mum grafiği analizi, kademe tahmini, stop loss
# ══════════════════════════════════════════════════════════════════════

import json
import os
import base64
import time
import urllib.request
import urllib.error
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import yfinance as yf
import pandas as pd
import numpy as np

_logger = logging.getLogger("GrafikYorumu")

# ── Gemini API Ayarları ──────────────────────────────────────────────
import os
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# ── Önbellek ─────────────────────────────────────────────────────────
_sonuc_cache = {}  # hisse_kodu -> son analiz sonucu
_canli_veri_cache = {}
_cache_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════════════
# 1. GEMINI VISION İLE GRAFİK GÖRSELİ ANALİZİ
# ══════════════════════════════════════════════════════════════════════

def _resmi_base64_yap(image_path: str) -> str:
    """Görsel dosyasını base64'e çevir."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _gemini_vision_sor(sistem_prompt: str, image_base64: str, max_retry: int = 3) -> str:
    """Gemini Vision API'ye görsel + prompt gönder, yanıt al."""
    payload = {
        "system_instruction": {"parts": [{"text": sistem_prompt}]},
        "contents": [{
            "parts": [
                {"text": "Bu mum grafiğini analiz et ve istenen çıktıyı JSON olarak ver."},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_base64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        VISION_URL, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    for deneme in range(max_retry):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                yanit = json.loads(resp.read().decode("utf-8"))
                return yanit["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                bekle = (deneme + 1) * 5
                _logger.warning(f"Rate limited, {bekle}s bekleniyor...")
                time.sleep(bekle)
                continue
            elif e.code == 400:
                hata = e.read().decode()
                _logger.error(f"Bad request: {hata}")
                return ""
            raise e
        except Exception as e:
            _logger.error(f"API hatası: {e}")
            if deneme < max_retry - 1:
                time.sleep(3)
                continue
            return ""
    return ""


def _json_ayikla(metin: str) -> Optional[dict]:
    """Gemini yanıtından JSON bloğunu ayıkla."""
    # ```json ... ``` bloklarını ara
    import re
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", metin)
    if match:
        metin = match.group(1)
    
    # JSON'a çevirmeyi dene
    metin = metin.strip()
    try:
        return json.loads(metin)
    except json.JSONDecodeError:
        pass
    
    # Süslü parantezler arasındaki en büyük JSON'u bul
    try:
        bas = metin.index("{")
        son = metin.rindex("}") + 1
        return json.loads(metin[bas:son])
    except (ValueError, json.JSONDecodeError):
        return None


# ══════════════════════════════════════════════════════════════════════
# 2. TEKNİK DESTEK ANALİZİ (Gerçek Veri ile)
# ══════════════════════════════════════════════════════════════════════

def _teknik_seviyeleri_bul(hisse_kodu: str, period: str = "6mo") -> dict:
    """Gerçek fiyat verisi üzerinden destek/direnç seviyelerini hesapla."""
    try:
        tk = yf.Ticker(hisse_kodu)
        hist = tk.history(period=period)
        if hist.empty or len(hist) < 30:
            return {}
        
        close_series = hist["Close"].squeeze()
        high_series = hist["High"].squeeze()
        low_series = hist["Low"].squeeze()
        close_arr = close_series.values
        high_arr = high_series.values
        low_arr = low_series.values
        son_fiyat = float(close_arr[-1])
        
        # Son 3 aydaki en yüksek ve en düşük
        son_3ay = max(1, len(close_arr) - 63)
        en_yuksek = float(np.max(high_arr[son_3ay:]))
        en_dusuk = float(np.min(low_arr[son_3ay:]))
        en_yuksek_index = int(np.argmax(high_arr[son_3ay:])) + son_3ay
        
        # Pivot noktaları (klasik)
        son_high = float(high_series.iloc[-1])
        son_low = float(low_series.iloc[-1])
        son_close = float(close_series.iloc[-1])
        pivot = (son_high + son_low + son_close) / 3
        r1 = 2 * pivot - son_low
        r2 = pivot + (son_high - son_low)
        r3 = son_high + 2 * (pivot - son_low)
        s1 = 2 * pivot - son_high
        s2 = pivot - (son_high - son_low)
        s3 = son_low - 2 * (son_high - pivot)
        
        # %0.382 - %0.618 - %0.786 fibonacci seviyeleri
        fark = en_yuksek - en_dusuk
        fib_382 = en_yuksek - fark * 0.382
        fib_500 = en_yuksek - fark * 0.500
        fib_618 = en_yuksek - fark * 0.618
        
        # En yüksek mumun bilgisi
        en_yuksek_mum = {
            "tarih": str(hist.index[en_yuksek_index].date()),
            "fiyat": round(en_yuksek, 2),
            "index": int(en_yuksek_index)
        }
        
        # Momentum
        son_10 = close_arr[-10:] if len(close_arr) >= 10 else close_arr
        momentum_yonu = "yukari" if son_10[-1] > son_10[0] else "asagi"
        
        return {
            "son_fiyat": round(son_fiyat, 2),
            "en_yuksek_seviye": round(en_yuksek, 2),
            "en_dusuk_seviye": round(en_dusuk, 2),
            "en_yuksek_mum": en_yuksek_mum,
            "direnc_seviyeleri": {
                "r3": round(r3, 2),
                "r2": round(r2, 2),
                "r1": round(r1, 2),
            },
            "destek_seviyeleri": {
                "s1": round(s1, 2),
                "s2": round(s2, 2),
                "s3": round(s3, 2),
            },
            "fibonacci": {
                "0_382": round(fib_382, 2),
                "0_500": round(fib_500, 2),
                "0_618": round(fib_618, 2),
            },
            "pivot": round(pivot, 2),
            "momentum": momentum_yonu,
            "volatilite_yuzde": round((en_yuksek - en_dusuk) / en_dusuk * 100, 2),
        }
    except Exception as e:
        _logger.error(f"Teknik seviye hatası ({hisse_kodu}): {e}")
        return {}


# ══════════════════════════════════════════════════════════════════════
# 3. CANLI VERİ TAKİBİ
# ══════════════════════════════════════════════════════════════════════

def canli_fiyat_ve_denge(hisse_kodu: str) -> dict:
    """Hisse için canlı fiyat, boğa/ayı dengesi, günlük değişim bilgisi."""
    try:
        tk = yf.Ticker(hisse_kodu)
        hist = tk.history(period="5d")
        if hist.empty or len(hist) < 2:
            return {"hata": "Veri bulunamadı"}
        
        son = float(hist["Close"].iloc[-1])
        onceki = float(hist["Close"].iloc[-2])
        acilis = float(hist["Open"].iloc[-1])
        yuksek = float(hist["High"].iloc[-1])
        dusuk = float(hist["Low"].iloc[-1])
        hacim = float(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0
        
        degisim_yuzde = ((son - onceki) / onceki) * 100
        
        # Boğa/Ayı dengesi (Elder Ray basitleştirilmiş)
        ema13 = float(hist["Close"].squeeze().ewm(span=13).mean().iloc[-1])
        boga_gucu = yuksek - ema13
        ayi_gucu = dusuk - ema13
        
        # Intraday gerçek aralık yüzdesi
        gercek_aralik = ((yuksek - dusuk) / onceki) * 100
        
        # Hacim ortalaması
        hacim_ort = float(hist["Volume"].squeeze().iloc[-20:].mean()) if len(hist) >= 20 else hacim
        
        return {
            "fiyat": round(son, 2),
            "acilis": round(acilis, 2),
            "yuksek": round(yuksek, 2),
            "dusuk": round(dusuk, 2),
            "degisim_yuzde": round(degisim_yuzde, 2),
            "hacim": int(hacim),
            "hacim_ort_yuzde": round((hacim / hacim_ort) * 100, 1) if hacim_ort > 0 else 100,
            "boga_gucu": round(boga_gucu, 4),
            "ayi_gucu": round(ayi_gucu, 4),
            "boga_ayi_farki": round(boga_gucu - abs(ayi_gucu), 4),
            "gercek_aralik_yuzde": round(gercek_aralik, 2),
            "guclu_mu": "Boga" if boga_gucu > abs(ayi_gucu) else "Ayi",
            "zaman": datetime.now().strftime("%H:%M:%S"),
        }
    except Exception as e:
        _logger.error(f"Canlı veri hatası ({hisse_kodu}): {e}")
        return {"hata": str(e)}


# ══════════════════════════════════════════════════════════════════════
# 4. ANA ANALİZ FONKSİYONU (Görsel + Teknik)
# ══════════════════════════════════════════════════════════════════════

ANALIZ_PROMPT = """Sen bir profesyonel borsa teknik analistisin. 
Sana verilen mum grafiği görselini analiz et ve aşağıdaki formatta JSON çıktısı ver.

Grafikte gördüğün:
1. En yüksek mumun tepe noktası (fiyat seviyesi olarak tahminin)
2. En belirgin direnç seviyeleri (grafikte gördüğün yatay çizgiler/zirveler)
3. En belirgin destek seviyeleri (grafikte gördüğün dipler)
4. Mevcut trend durumu (yükseliş/düşüş/yatay)
5. Eğer fiyat en yüksek direnci kırarsa hedef seviyeler (kademe kademe)
6. Eğer fiyat en önemli desteği kırarsa hedef seviyeler
7. Stop loss için en mantıklı seviye
8. Risk/Ödül oranı tahmini

YANIT FORMATI (sadece JSON, başka metin yok):
{
  "grafik_yorumu": {
    "en_yuksek_tepe": float (tahmini fiyat),
    "trend": "yukari" | "asagi" | "yatay",
    "trend_gucu": "guclu" | "orta" | "zayif"
  },
  "direnc_seviyeleri": [float, float, float],
  "destek_seviyeleri": [float, float, float],
  "kademe_hedefleri": {
    "yukari_kirilim": {
      "ana_direnc": float (kırılması gereken seviye),
      "hedef_1": float (ilk hedef),
      "hedef_2": float (ikinci hedef),
      "hedef_3": float (üçüncü hedef),
      "beklenen_yon": "yukari"
    },
    "asagi_kirilim": {
      "ana_destek": float (kırılması gereken seviye),
      "hedef_1": float,
      "hedef_2": float,
      "beklenen_yon": "asagi"
    }
  },
  "stop_loss": {
    "uzun_pozisyon_icin": float,
    "kisa_pozisyon_icin": float
  },
  "risk_odul_orani": float,
  "ozet": "Kısa bir yorum metni"
}
"""


def grafik_gorsel_analiz(gorsel_yolu: str, hisse_kodu: str) -> dict:
    """
    Ana analiz fonksiyonu.
    - Gemini Vision ile görseli analiz eder
    - Gerçek teknik verilerle seviyeleri hesaplar
    - İkisini birleştirip kapsamlı rapor üretir
    
    Parametreler:
        gorsel_yolu: Mum grafiği ekran görüntüsü dosya yolu
        hisse_kodu: Hisse kodu (örn: THYAO.IS, AAPL)
    
    Dönüş:
        dict: Kapsamlı analiz sonucu
    """
    sonuc = {
        "basarili": False,
        "hisse_kodu": hisse_kodu,
        "analiz_zamani": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "gemini_yorumu": None,
        "teknik_veri": None,
        "kademe_tahminleri": None,
        "canli_veri": None,
        "mesaj": ""
    }
    
    # 1. Gemini Vision ile görsel analizi
    try:
        if not os.path.exists(gorsel_yolu):
            sonuc["mesaj"] = f"Görsel dosyası bulunamadı: {gorsel_yolu}"
            return sonuc
        
        image_b64 = _resmi_base64_yap(gorsel_yolu)
        gemini_yanit = _gemini_vision_sor(ANALIZ_PROMPT, image_b64)
        
        if gemini_yanit:
            gorsel_veri = _json_ayikla(gemini_yanit)
            if gorsel_veri:
                sonuc["gemini_yorumu"] = gorsel_veri
            else:
                sonuc["gemini_yorumu"] = {"ham_yanit": gemini_yanit[:300]}
        else:
            sonuc["gemini_yorumu"] = {"hata": "API yanıt vermedi"}
    except Exception as e:
        _logger.error(f"Görsel analiz hatası: {e}")
        sonuc["gemini_yorumu"] = {"hata": str(e)}
    
    # 2. Teknik seviyeleri hesapla
    try:
        teknik = _teknik_seviyeleri_bul(hisse_kodu)
        if teknik:
            sonuc["teknik_veri"] = teknik
    except Exception as e:
        _logger.error(f"Teknik veri hatası: {e}")
    
    # 3. Kademe tahminlerini oluştur
    try:
        sonuc["kademe_tahminleri"] = _kademe_tahminleri_olustur(
            sonuc["gemini_yorumu"], sonuc["teknik_veri"]
        )
    except Exception as e:
        _logger.error(f"Kademe tahmini hatası: {e}")
    
    # 4. Canlı veri
    sonuc["canli_veri"] = canli_fiyat_ve_denge(hisse_kodu)
    
    # 5. Özet
    sonuc["basarili"] = True
    sonuc["mesaj"] = "Analiz başarıyla tamamlandı"
    
    # Cache'e kaydet
    with _cache_lock:
        _sonuc_cache[hisse_kodu] = sonuc
    
    return sonuc


def _kademe_tahminleri_olustur(gemini_yorum: Optional[dict], teknik_veri: Optional[dict]) -> dict:
    """Gemini yorumu + teknik veriyi birleştirerek kademe tahminleri üret."""
    kademeler = {
        "yukari_senaryo": {},
        "asagi_senaryo": {},
        "stop_loss": {},
        "risk_odul": 0,
        "detay": ""
    }
    
    # Gemini'den gelen veriler
    yukari_hedefler = {}
    asagi_hedefler = {}
    stop_loss_veri = {}
    risk_odul = 0
    
    if gemini_yorum and "kademe_hedefleri" in gemini_yorum:
        kh = gemini_yorum["kademe_hedefleri"]
        if "yukari_kirilim" in kh:
            yukari_hedefler = kh["yukari_kirilim"]
        if "asagi_kirilim" in kh:
            asagi_hedefler = kh["asagi_kirilim"]
        if "stop_loss" in kh:
            stop_loss_veri = kh["stop_loss"]
        risk_odul = kh.get("risk_odul_orani", 0)
    
    # Teknik veriden daha kesin seviyeler
    son_fiyat = teknik_veri.get("son_fiyat", 0) if teknik_veri else 0
    en_yuksek = teknik_veri.get("en_yuksek_seviye", 0) if teknik_veri else 0
    en_dusuk = teknik_veri.get("en_dusuk_seviye", 0) if teknik_veri else 0
    direnc = teknik_veri.get("direnc_seviyeleri", {}) if teknik_veri else {}
    destek = teknik_veri.get("destek_seviyeleri", {}) if teknik_veri else {}
    
    # Yukarı kırılım hedefleri
    yukari_ana_direnc = yukari_hedefler.get("ana_direnc", direnc.get("r1", son_fiyat * 1.02))
    hedef1_yukari = yukari_hedefler.get("hedef_1", direnc.get("r2", son_fiyat * 1.05))
    hedef2_yukari = yukari_hedefler.get("hedef_2", direnc.get("r3", son_fiyat * 1.08))
    hedef3_yukari = yukari_hedefler.get("hedef_3", son_fiyat * 1.12)
    
    kademeler["yukari_senaryo"] = {
        "kirilmasi_gereken": round(yukari_ana_direnc, 2),
        "hedef_1": round(hedef1_yukari, 2),
        "hedef_1_getiri": round((hedef1_yukari / son_fiyat - 1) * 100, 2) if son_fiyat > 0 else 0,
        "hedef_2": round(hedef2_yukari, 2),
        "hedef_2_getiri": round((hedef2_yukari / son_fiyat - 1) * 100, 2) if son_fiyat > 0 else 0,
        "hedef_3": round(hedef3_yukari, 2),
        "hedef_3_getiri": round((hedef3_yukari / son_fiyat - 1) * 100, 2) if son_fiyat > 0 else 0,
    }
    
    # Aşağı kırılım hedefleri
    asagi_ana_destek = asagi_hedefler.get("ana_destek", destek.get("s1", son_fiyat * 0.98))
    hedef1_asagi = asagi_hedefler.get("hedef_1", destek.get("s2", son_fiyat * 0.95))
    hedef2_asagi = asagi_hedefler.get("hedef_2", destek.get("s3", son_fiyat * 0.92))
    
    kademeler["asagi_senaryo"] = {
        "kirilmasi_gereken": round(asagi_ana_destek, 2),
        "hedef_1": round(hedef1_asagi, 2),
        "hedef_1_getiri": round((hedef1_asagi / son_fiyat - 1) * 100, 2) if son_fiyat > 0 else 0,
        "hedef_2": round(hedef2_asagi, 2),
        "hedef_2_getiri": round((hedef2_asagi / son_fiyat - 1) * 100, 2) if son_fiyat > 0 else 0,
    }
    
    # Stop loss
    uzun_sl = stop_loss_veri.get("uzun_pozisyon_icin", destek.get("s1", son_fiyat * 0.97))
    kisa_sl = stop_loss_veri.get("kisa_pozisyon_icin", direnc.get("r1", son_fiyat * 1.03))
    
    kademeler["stop_loss"] = {
        "uzun_icin": round(uzun_sl, 2),
        "uzun_kayip_yuzde": round((uzun_sl / son_fiyat - 1) * 100, 2) if son_fiyat > 0 else 0,
        "kisa_icin": round(kisa_sl, 2),
        "kisa_kayip_yuzde": round((kisa_sl / son_fiyat - 1) * 100, 2) if son_fiyat > 0 else 0,
    }
    
    # Risk/Ödül oranı
    if risk_odul == 0 and son_fiyat > 0:
        hedef = hedef1_yukari - son_fiyat
        risk = son_fiyat - uzun_sl
        if risk > 0:
            risk_odul = round(hedef / risk, 2)
    
    kademeler["risk_odul"] = risk_odul if risk_odul > 0 else 1.0
    
    # Trend yönü özeti
    trend = "yukari"
    if gemini_yorum and "grafik_yorumu" in gemini_yorum:
        trend = gemini_yorum["grafik_yorumu"].get("trend", "yatay")
    
    kademeler["detay"] = f"Trend: {trend.upper()} | R/R: 1:{risk_odul}" if risk_odul > 0 else f"Trend: {trend.upper()}"
    
    return kademeler


def son_analizi_getir(hisse_kodu: str) -> Optional[dict]:
    """Cache'lenmiş son analiz sonucunu döndür."""
    with _cache_lock:
        return _sonuc_cache.get(hisse_kodu)


def canli_veriyi_guncelle(hisse_kodu: str) -> dict:
    """Canlı veriyi güncelle ve cache'e kaydet."""
    veri = canli_fiyat_ve_denge(hisse_kodu)
    with _cache_lock:
        _canli_veri_cache[hisse_kodu] = veri
    
    # Ana sonuca da ekle
    with _cache_lock:
        if hisse_kodu in _sonuc_cache:
            _sonuc_cache[hisse_kodu]["canli_veri"] = veri
            _sonuc_cache[hisse_kodu]["analiz_zamani"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    return veri
