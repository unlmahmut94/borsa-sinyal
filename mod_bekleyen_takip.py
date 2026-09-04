# ══════════════════════════════════════════════════════════════════════
#  mod_bekleyen_takip.py — Bekleyen Sinyal Akıllı Takip Motoru v1.0
#
#  AMAÇ: Uzun süredir bekleyen GÜÇLÜ AL / KRİPTO SCALP sinyallerini
#         akıllı algoritma ile yönetmek. Tarihi geçmiş, teyitlenmemiş
#         veya piyasa şartları değişmiş sinyalleri otomatik tespit edip
#         uygun aksiyonu almak.
#
#  PROBLEM:
#   - 56 sinyal BEKLIYOR durumda, bazıları 12+ gündür hareketsiz
#   - Mevcut sistem sadece hedef/stop kontrolü + 30 gün zaman aşımı yapıyor
#   - Ara değerlendirme yok → sinyaller şişiyor, portföy kilitleniyor
#
#  ALGORİTMA (5 AŞAMALI):
#  ┌─────────────────────────────────────────────────────────────────┐
#  │ AŞAMA 1 — GECİKME SINIFLANDIRMASI                               │
#  │   • 0-3 gün: TAZE (takip et, dokunma)                          │
#  │   • 4-7 gün: GECİKMİŞ (piyasa kontrolü yap)                   │
#  │   • 8-14 gün: SORUNLU (tez sinyal geçerliliğini sorgula)      │
#  │   • 15-30 gün: KRİTİK (acil karar al)                          │
#  │   • 30+ gün: ZAMAN AŞIMI (otomatik kapat)                      │
#  │                                                                  │
#  │ AŞAMA 2 — SİNYAL GEÇERLİLİK KONTROLÜ                            │
#  │   • Güncel fiyat çek                                            │
#  │   • RSI, MACD, hacim güncellemesi                               │
#  │   • Trend yönü değişmiş mi?                                     │
#  │   • Oynaklık (ATR) artmış mı?                                   │
#  │                                                                  │
#  │ AŞAMA 3 — SKOR HESAPLAMA (0-100)                                │
#  │   • Fiyat girişe göre % değişim                                 │
#  │   • RSI sinyal geçerliliği                                       │
#  │   • Trend gücü (ADX)                                            │
#  │   • Hacim trendi (OBV)                                          │
#  │   • Geçen süre ceza puanı                                       │
#  │                                                                  │
#  │ AŞAMA 4 — KARAR MOTORU                                          │
#  │   • Skor ≥ 70: DEVAM ET (sinyal hala güçlü)                    │
#  │   • Skor 40-69: YUMUŞAK ÇIKIŞ ÖNER (stop daralt, kısmi sat)    │
#  │   • Skor < 40: SERT ÇIKIŞ (pozisyonu kapat)                     │
#  │                                                                  │
#  │ AŞAMA 5 — OTOMATİK UYGULAMA                                     │
#  │   • SERT ÇIKIŞ sinyalleri otomatik kapatılır                    │
#  │   • YUMUŞAK ÇIKIŞ için Telegram'a uyarı gönderilir             │
#  │   • Rapor JSON'a yazılır, dashboard'da gösterilir              │
#  └─────────────────────────────────────────────────────────────────┘
#
#  KULLANIM:
#    from mod_bekleyen_takip import bekleyen_takip_raporu
#    rapor = bekleyen_takip_raporu(otomatik_kapat=True)
#    print(rapor['ozet'])
# ══════════════════════════════════════════════════════════════════════

import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
import yfinance as yf
import time as _time

_logger = logging.getLogger("BekleyenTakip")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | [BEKLEYEN] %(message)s",
        datefmt="%H:%M:%S"
    ))
    _logger.addHandler(h)

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")
RAPOR_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bekleyen_takip_raporu.json")
KAPATMA_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bekleyen_kapatma_log.json")

# Telegram modülünü güvenli çağır
try:
    from mod_telegram import telegram_mesaj_gonder
except ImportError:
    def telegram_mesaj_gonder(mesaj):
        pass

# Strateji config'i yükle
def _config_yukle() -> dict:
    try:
        CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")
        with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

CONFIG = _config_yukle()


# ══════════════════════════════════════════════════════════════════════
#  AŞAMA 1 — BEKLEYEN SİNYALLERİ GETİR VE SINIFLANDIR
# ══════════════════════════════════════════════════════════════════════

def bekleyen_sinyalleri_getir() -> list:
    """
    Veritabanından tüm BEKLIYOR durumundaki sinyalleri çeker,
    her birine gecikme bilgisi ekler.

    Dönüş: Her sinyal için dict listesi
    """
    try:
        conn = sqlite3.connect(DB_YOLU)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'")
        if not c.fetchone():
            conn.close()
            return []

        c.execute("""
            SELECT id, tarih, hisse, sinyal_tipi, giris_fiyati, 
                   hedef_fiyat, stop_fiyat, durum, kapanis_fiyati
            FROM ai_sinyaller 
            WHERE durum LIKE 'BEK%IYOR'
            ORDER BY tarih ASC
        """)
        rows = c.fetchall()
        conn.close()

        simdi = datetime.now()
        sonuc = []

        for row in rows:
            row_dict = dict(row)
            tarih_str = row_dict.get('tarih', '')

            # Tarihi parse et
            try:
                sinyal_dt = datetime.strptime(tarih_str, "%Y-%m-%d %H:%M:%S")
            except:
                try:
                    sinyal_dt = datetime.strptime(tarih_str, "%Y-%m-%d")
                except:
                    sinyal_dt = simdi

            gecikme_saat = round((simdi - sinyal_dt).total_seconds() / 3600, 1)
            gecikme_gun = gecikme_saat / 24

            # Gecikme sınıflandırması
            if gecikme_gun <= 3:
                gecikme_sinif = "TAZE"
                gecikme_seviye = 0
            elif gecikme_gun <= 7:
                gecikme_sinif = "GECIKMIS"
                gecikme_seviye = 1
            elif gecikme_gun <= 14:
                gecikme_sinif = "SORUNLU"
                gecikme_seviye = 2
            elif gecikme_gun <= 30:
                gecikme_sinif = "KRITIK"
                gecikme_seviye = 3
            else:
                gecikme_sinif = "ZAMAN_ASIMI"
                gecikme_seviye = 4

            # Hisse tipini belirle (KRIPTO vs HISSE)
            sinyal_tipi = str(row_dict.get('sinyal_tipi', '')).upper()
            hisse_kodu = str(row_dict.get('hisse', '')).upper()
            is_kripto = 'USDT' in hisse_kodu or 'KRIPTO' in sinyal_tipi or 'SCALP' in sinyal_tipi

            row_dict['gecikme_saat'] = gecikme_saat
            row_dict['gecikme_gun'] = round(gecikme_gun, 1)
            row_dict['gecikme_sinif'] = gecikme_sinif
            row_dict['gecikme_seviye'] = gecikme_seviye
            row_dict['is_kripto'] = is_kripto
            row_dict['sinyal_dt'] = sinyal_dt
            row_dict['guncel_fiyat'] = None
            row_dict['guncel_rsi'] = None
            row_dict['guncel_trend'] = None
            row_dict['skor'] = 0
            row_dict['karar'] = 'BEKLEMEDE'
            row_dict['karar_detay'] = ''
            row_dict['yuzde_degisim'] = 0.0

            sonuc.append(row_dict)

        return sonuc

    except Exception as e:
        _logger.error(f"Bekleyen sinyaller okunamadı: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════
#  AŞAMA 2 — PİYASA VERİSİ ÇEK VE İNDİKATÖRLERİ GÜNCELLE
# ══════════════════════════════════════════════════════════════════════

def _teknik_guncelle(hisse_kodu: str) -> dict:
    """
    Bir hisse için güncel fiyat ve teknik indikatörleri çeker.

    Dönüş: {
        'fiyat': float,
        'rsi': float,
        'macd_sinyal': str ('AL'/'SAT'/'NOTR'),
        'trend': str ('YUKSELIS'/'DUSUS'/'YATAY'),
        'adx': float,
        'hacim_artiyor': bool,
        'ma50': float,
        'atr': float,
        'hata': str veya None
    }
    """
    sonuc = {
        'fiyat': None, 'rsi': None, 'macd_sinyal': 'NOTR',
        'trend': 'YATAY', 'adx': 0, 'hacim_artiyor': False,
        'ma50': None, 'atr': 0, 'hata': None
    }

    # Kripto sembol dönüşümü: XXXUSDT → XXX-USD (yfinance formatı)
    sorgu_kodu = hisse_kodu
    if 'USDT' in hisse_kodu.upper():
        sorgu_kodu = hisse_kodu.upper().replace('USDT', '-USD')
    
    try:
        tk = yf.Ticker(sorgu_kodu)
        df = tk.history(period="1mo")
        
        # Eğer USDT formatında veri gelmezse orijinal kodu dene
        if df.empty and sorgu_kodu != hisse_kodu:
            tk = yf.Ticker(hisse_kodu)
            df = tk.history(period="1mo")

        if df.empty or len(df) < 20:
            sonuc['hata'] = f"Veri yok (sadece {len(df)} gun)"
            return sonuc

        close = df['Close'].squeeze()
        high = df['High'].squeeze()
        low = df['Low'].squeeze()
        volume = df['Volume'].squeeze()

        sonuc['fiyat'] = round(float(close.iloc[-1]), 6)
        sonuc['ma50'] = round(float(close.rolling(50).mean().iloc[-1]), 6) if len(close) >= 50 else sonuc['fiyat']

        # RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_vals = 100 - (100 / (1 + rs))
        sonuc['rsi'] = round(float(rsi_vals.iloc[-1]), 1) if not pd.isna(rsi_vals.iloc[-1]) else 50.0

        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        if len(macd_line) >= 2 and len(signal_line) >= 2:
            if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
                sonuc['macd_sinyal'] = 'AL'
            elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
                sonuc['macd_sinyal'] = 'SAT'
            elif macd_line.iloc[-1] > signal_line.iloc[-1]:
                sonuc['macd_sinyal'] = 'AL'
            else:
                sonuc['macd_sinyal'] = 'SAT'

        # Trend (MA20 vs MA50)
        ma20 = close.rolling(20).mean()
        if len(ma20) >= 2 and len(close) >= 50:
            ma50 = close.rolling(50).mean()
            if ma20.iloc[-1] > ma50.iloc[-1] and close.iloc[-1] > ma20.iloc[-1]:
                sonuc['trend'] = 'YUKSELIS'
            elif ma20.iloc[-1] < ma50.iloc[-1] and close.iloc[-1] < ma20.iloc[-1]:
                sonuc['trend'] = 'DUSUS'
            else:
                sonuc['trend'] = 'YATAY'
        elif close.iloc[-1] > ma20.iloc[-1]:
            sonuc['trend'] = 'YUKSELIS'
        elif close.iloc[-1] < ma20.iloc[-1]:
            sonuc['trend'] = 'DUSUS'

        # ADX (14)
        if len(high) >= 28:
            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            plus_dm = high.diff().where(high.diff() > low.diff(-1).abs(), 0).rolling(14).mean()
            minus_dm = (-low.diff()).where((-low.diff()) > high.diff().abs(), 0).rolling(14).mean()
            plus_di = 100 * (plus_dm / atr.replace(0, np.nan))
            minus_di = 100 * (minus_dm / atr.replace(0, np.nan))
            dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
            adx = dx.rolling(14).mean()
            sonuc['adx'] = round(float(adx.iloc[-1]), 1) if not pd.isna(adx.iloc[-1]) else 20
            sonuc['atr'] = round(float(atr.iloc[-1]), 6)
        else:
            sonuc['adx'] = 20

        # Hacim trendi
        if len(volume) >= 10:
            vol_ort = volume.iloc[-10:].mean()
            sonuc['hacim_artiyor'] = bool(volume.iloc[-1] > vol_ort * 1.2)

    except Exception as e:
        sonuc['hata'] = str(e)[:100]

    return sonuc


# ══════════════════════════════════════════════════════════════════════
#  AŞAMA 3 — SKOR HESAPLAMA
# ══════════════════════════════════════════════════════════════════════

def _skor_hesapla(sinyal: dict, teknik: dict) -> tuple:
    """
    Bekleyen bir sinyal için 0-100 arası geçerlilik skoru hesaplar.

    Puanlama Kriterleri:
    ┌────────────────────────────────────────────────────┬────────┐
    │ Kriter                                              │ Max Pn │
    ├────────────────────────────────────────────────────┼────────┤
    │ Fiyat girişe göre % değişim (pozitif = iyi)        │   25   │
    │ RSI hala AL bölgesinde mi? (< 50)                  │   20   │
    │ Trend yönü (YUKSELIS = iyi)                        │   20   │
    │ MACD sinyali (AL = iyi)                            │   15   │
    │ Hacim artıyor mu?                                   │   10   │
    │ ADX gücü (> 25 = iyi)                              │    5   │
    │ ATR oynaklık (çok yüksek = kötü)                   │    5   │
    │ Gecikme ceza puanı (her 5 gün -5)                  │  -25   │
    └────────────────────────────────────────────────────┴────────┘

    Dönüş: (skor, detay_dict)
    """
    skor = 50  # Başlangıç nötr
    detay = {}

    giris_fiyat = float(sinyal.get('giris_fiyati', 0))
    guncel_fiyat = teknik.get('fiyat')
    gecikme_gun = float(sinyal.get('gecikme_gun', 0))
    is_kripto = sinyal.get('is_kripto', False)

    # --- Fiyat Değişimi (25 puan) ---
    if guncel_fiyat and giris_fiyat > 0:
        yuzde_degisim = (guncel_fiyat - giris_fiyat) / giris_fiyat * 100
        sinyal['yuzde_degisim'] = round(yuzde_degisim, 2)

        if yuzde_degisim >= 5:
            skor += 25
            detay['fiyat'] = f"+%{yuzde_degisim:.1f} → +25p"
        elif yuzde_degisim >= 2:
            skor += 18
            detay['fiyat'] = f"+%{yuzde_degisim:.1f} → +18p"
        elif yuzde_degisim >= 0:
            skor += 12
            detay['fiyat'] = f"+%{yuzde_degisim:.1f} → +12p"
        elif yuzde_degisim >= -2:
            skor += 5
            detay['fiyat'] = f"%{yuzde_degisim:.1f} → +5p"
        elif yuzde_degisim >= -5:
            skor -= 5
            detay['fiyat'] = f"%{yuzde_degisim:.1f} → -5p"
        else:
            skor -= 15
            detay['fiyat'] = f"%{yuzde_degisim:.1f} → -15p"
    else:
        detay['fiyat'] = "fiyat yok → 0p"

    # --- RSI (20 puan) ---
    rsi = teknik.get('rsi')
    if rsi is not None:
        if 25 <= rsi <= 45:
            skor += 20
            detay['rsi'] = f"RSI={rsi:.0f} aşırı satım bölgesi → +20p"
        elif 45 < rsi <= 55:
            skor += 12
            detay['rsi'] = f"RSI={rsi:.0f} nötr → +12p"
        elif 55 < rsi <= 70:
            skor += 5
            detay['rsi'] = f"RSI={rsi:.0f} yükselişte → +5p"
        elif rsi < 25:
            skor += 15
            detay['rsi'] = f"RSI={rsi:.0f} derin aşırı satım → +15p"
        else:
            skor -= 10
            detay['rsi'] = f"RSI={rsi:.0f} aşırı alım → -10p"
    else:
        detay['rsi'] = "RSI yok → 0p"

    # --- Trend Yönü (20 puan) ---
    trend = teknik.get('trend', 'YATAY')
    if trend == 'YUKSELIS':
        skor += 20
        detay['trend'] = "YÜKSELİŞ → +20p"
    elif trend == 'YATAY':
        skor += 8
        detay['trend'] = "YATAY → +8p"
    else:
        skor -= 10
        detay['trend'] = "DÜŞÜŞ → -10p"

    # --- MACD (15 puan) ---
    macd = teknik.get('macd_sinyal', 'NOTR')
    if macd == 'AL':
        skor += 15
        detay['macd'] = "AL sinyali → +15p"
    elif macd == 'SAT':
        skor -= 8
        detay['macd'] = "SAT sinyali → -8p"
    else:
        detay['macd'] = "NÖTR → 0p"

    # --- Hacim (10 puan) ---
    if teknik.get('hacim_artiyor'):
        skor += 10
        detay['hacim'] = "hacim artıyor → +10p"
    else:
        detay['hacim'] = "hacim normal → 0p"

    # --- ADX (5 puan) ---
    adx = teknik.get('adx', 0)
    if adx >= 25:
        skor += 5
        detay['adx'] = f"ADX={adx:.0f} güçlü trend → +5p"
    elif adx >= 20:
        skor += 2
        detay['adx'] = f"ADX={adx:.0f} orta → +2p"
    else:
        detay['adx'] = f"ADX={adx:.0f} zayıf → 0p"

    # --- ATR Oynaklık (5 puan) ---
    atr = teknik.get('atr', 0)
    if atr > 0 and guncel_fiyat and guncel_fiyat > 0:
        atr_yuzde = atr / guncel_fiyat * 100
        if 1 <= atr_yuzde <= 3:
            skor += 5
            detay['atr'] = f"ATR %{atr_yuzde:.1f} ideal → +5p"
        elif atr_yuzde > 5:
            skor -= 3
            detay['atr'] = f"ATR %{atr_yuzde:.1f} çok oynak → -3p"
        else:
            detay['atr'] = f"ATR %{atr_yuzde:.1f} → 0p"
    else:
        detay['atr'] = "ATR yok → 0p"

    # --- Gecikme Cezası (maks -25) ---
    ceza = min(25, int(gecikme_gun / 5) * 5)
    skor -= ceza
    detay['gecikme'] = f"{gecikme_gun:.0f} gun gecikme → -{ceza}p"
    if gecikme_gun > 14:
        detay['gecikme_uyari'] = "⚠️ 14+ gün beklemede!"

    # --- Kripto Bonus/Malus ---
    if is_kripto:
        # Kriptolar daha volatil → gecikme cezası 1.5x
        ek_ceza = min(10, int(gecikme_gun / 7) * 3)
        skor -= ek_ceza
        if ek_ceza > 0:
            detay['kripto_ceza'] = f"kripto volatilite → -{ek_ceza}p"

    # 0-100 arasına sıkıştır
    skor = max(0, min(100, skor))

    return skor, detay


# ══════════════════════════════════════════════════════════════════════
#  AŞAMA 4 — KARAR MOTORU
# ══════════════════════════════════════════════════════════════════════

def _karar_ver(skor: int, gecikme_gun: float, yuzde_degisim: float, is_kripto: bool) -> tuple:
    """
    Skora göre karar verir.

    Karar Seviyeleri:
    - DEVAM: Skor ≥ 70, sinyal hala güçlü
    - YUMUSAK_CIKIS: Skor 40-69, stop daralt veya kısmi sat
    - SERT_CIKIS: Skor < 40 veya gecikme > 25 gün, pozisyonu kapat
    - ZAMAN_ASIMI: gecikme > 30 gün

    Dönüş: (karar, detay_mesaj)
    """
    # Zaman aşımı kontrolü
    if gecikme_gun > 30:
        return "ZAMAN_ASIMI", f"30 gün aşıldı (gecikme: {gecikme_gun:.0f} gün) — otomatik kapatılacak"

    # Zarar kes seviyesi kontrolü
    if yuzde_degisim <= -7:
        return "SERT_CIKIS", f"Girişten %{yuzde_degisim:.1f} düşüş — zarar kes"

    # Kripto için daha agresif eşikler
    if is_kripto:
        if skor >= 65:
            return "DEVAM", f"Skor {skor}/100 — kripto sinyali hala geçerli, beklemede kal"
        elif skor >= 35:
            return "YUMUSAK_CIKIS", f"Skor {skor}/100 — kripto piyasası zayıflıyor, stop daraltılmalı"
        else:
            return "SERT_CIKIS", f"Skor {skor}/100 — kripto sinyali geçersiz, pozisyon kapatılmalı"
    else:
        # Hisse senedi için standart eşikler
        if skor >= 70:
            return "DEVAM", f"Skor {skor}/100 — sinyal hala güçlü, beklemede kal"
        elif skor >= 40:
            return "YUMUSAK_CIKIS", f"Skor {skor}/100 — sinyal zayıflıyor, stop seviyesi daraltılmalı veya kısmi satış"
        else:
            # 20+ gün bekleyen düşük skorlu → sert çıkış
            if gecikme_gun >= 20 and skor < 50:
                return "SERT_CIKIS", f"Skor {skor}/100 + {gecikme_gun:.0f} gün bekleme — pozisyon kapatılmalı"
            else:
                return "SERT_CIKIS", f"Skor {skor}/100 — sinyal geçersiz, pozisyon kapatılmalı"


# ══════════════════════════════════════════════════════════════════════
#  AŞAMA 5 — ANA TAKİP FONKSİYONU
# ══════════════════════════════════════════════════════════════════════

def bekleyen_takip_raporu(otomatik_kapat: bool = False, max_kontrol: int = 0,
                          sadece_sinif: str = None) -> dict:
    """
    Tüm bekleyen sinyalleri tarar, değerlendirir ve rapor üretir.

    Parametreler:
        otomatik_kapat: True ise SERT_CIKIS ve ZAMAN_ASIMI kararları otomatik uygulanır
        max_kontrol: 0 = hepsini kontrol et, > 0 = en fazla N sinyali kontrol et
        sadece_sinif: None = hepsi, 'KRITIK' = sadece kritik olanlar, 'SORUNLU' vs.

    Dönüş:
        {
            'rapor_tarihi': str,
            'toplam_bekleyen': int,
            'kontrol_edilen': int,
            'sinif_dagilimi': dict,
            'karar_dagilimi': dict,
            'sinyaller': [dict, ...],
            'otomatik_kapatilan': int,
            'otomatik_kapatma_log': [dict, ...],
            'ozet': str
        }
    """
    _logger.info("=" * 60)
    _logger.info("  BEKLEYEN SİNYAL TAKİP RAPORU BAŞLATILDI")
    _logger.info("=" * 60)

    # Aşama 1: Bekleyen sinyalleri getir
    tum_sinyaller = bekleyen_sinyalleri_getir()

    if not tum_sinyaller:
        return {
            'rapor_tarihi': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'toplam_bekleyen': 0, 'kontrol_edilen': 0,
            'sinif_dagilimi': {}, 'karar_dagilimi': {},
            'sinyaller': [], 'otomatik_kapatilan': 0,
            'otomatik_kapatma_log': [], 'ozet': "📊 Bekleyen sinyal yok."
        }

    # Sınıf dağılımını hesapla
    sinif_dagilimi = defaultdict(int)
    for s in tum_sinyaller:
        sinif_dagilimi[s['gecikme_sinif']] += 1

    _logger.info(f"Toplam bekleyen: {len(tum_sinyaller)} | "
                 f"TAZE:{sinif_dagilimi.get('TAZE',0)} "
                 f"GECIKMIS:{sinif_dagilimi.get('GECIKMIS',0)} "
                 f"SORUNLU:{sinif_dagilimi.get('SORUNLU',0)} "
                 f"KRITIK:{sinif_dagilimi.get('KRITIK',0)} "
                 f"ZAMAN_ASIMI:{sinif_dagilimi.get('ZAMAN_ASIMI',0)}")

    # Filtrele (sadece_sinif)
    kontrol_listesi = tum_sinyaller
    if sadece_sinif:
        kontrol_listesi = [s for s in tum_sinyaller if s['gecikme_sinif'] == sadece_sinif]
        _logger.info(f"Filtre: sadece {sadece_sinif} → {len(kontrol_listesi)} sinyal")

    # Max kontrol limiti
    if max_kontrol > 0 and len(kontrol_listesi) > max_kontrol:
        # Önce en kritik olanları al (gecikme_seviye yüksek)
        kontrol_listesi.sort(key=lambda x: (-x['gecikme_seviye'], x['gecikme_gun']))
        kontrol_listesi = kontrol_listesi[:max_kontrol]
        _logger.info(f"Max kontrol limiti: {max_kontrol} sinyal")

    kontrol_edilen = 0
    karar_dagilimi = defaultdict(int)
    otomatik_kapatma_log = []
    otomatik_kapatilan = 0

    # Aşama 2-4: Her sinyali değerlendir
    for i, sinyal in enumerate(kontrol_listesi):
        hisse = sinyal['hisse']
        gecikme_gun = sinyal['gecikme_gun']
        gecikme_sinif = sinyal['gecikme_sinif']

        _logger.info(f"[{i+1}/{len(kontrol_listesi)}] {hisse} "
                    f"({gecikme_gun:.0f}g, {gecikme_sinif})")

        # TAZE sinyalleri atla (3 günden az)
        if gecikme_sinif == 'TAZE' and not sadece_sinif:
            sinyal['karar'] = 'DEVAM'
            sinyal['karar_detay'] = 'TAZE sinyal — henüz değerlendirme yapılmadı'
            sinyal['skor'] = 75
            karar_dagilimi['DEVAM'] += 1
            kontrol_edilen += 1
            continue

        # Piyasa verisini çek
        teknik = _teknik_guncelle(hisse)

        if teknik.get('hata'):
            _logger.warning(f"  ⚠️ {hisse}: Veri hatası — {teknik['hata']}")
            sinyal['karar'] = 'DEVAM'
            sinyal['karar_detay'] = f"Veri çekilemedi: {teknik['hata']} — atlandı"
            sinyal['skor'] = 60
            sinyal['guncel_fiyat'] = None
            karar_dagilimi['DEVAM'] += 1
            kontrol_edilen += 1
            continue

        # Teknik verileri sinyale ekle
        sinyal['guncel_fiyat'] = teknik['fiyat']
        sinyal['guncel_rsi'] = teknik['rsi']
        sinyal['guncel_trend'] = teknik['trend']

        # Aşama 3: Skor hesapla
        skor, detay = _skor_hesapla(sinyal, teknik)
        sinyal['skor'] = skor
        sinyal['skor_detay'] = detay

        # Aşama 4: Karar ver
        karar, karar_detay = _karar_ver(
            skor, gecikme_gun, sinyal.get('yuzde_degisim', 0), sinyal.get('is_kripto', False)
        )
        sinyal['karar'] = karar
        sinyal['karar_detay'] = karar_detay
        karar_dagilimi[karar] += 1
        kontrol_edilen += 1

        _logger.info(f"  → Skor: {skor}/100 | Karar: {karar} | {karar_detay}")

        # Aşama 5: Otomatik kapatma
        if otomatik_kapat and karar in ('SERT_CIKIS', 'ZAMAN_ASIMI'):
            kapatma_sonuc = _pozisyon_kapat(sinyal)
            if kapatma_sonuc['basarili']:
                otomatik_kapatilan += 1
                otomatik_kapatma_log.append(kapatma_sonuc)
                _logger.info(f"  ✅ OTOMATİK KAPATILDI: {hisse} @ {teknik['fiyat']}")

        # Rate limit koruması
        _time.sleep(0.3)

    # Özet metni oluştur
    ozet = _ozet_olustur(tum_sinyaller, kontrol_listesi, sinif_dagilimi,
                         karar_dagilimi, otomatik_kapatilan, otomatik_kapatma_log)

    # Raporu kaydet
    rapor = {
        'rapor_tarihi': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'toplam_bekleyen': len(tum_sinyaller),
        'kontrol_edilen': kontrol_edilen,
        'sinif_dagilimi': dict(sinif_dagilimi),
        'karar_dagilimi': dict(karar_dagilimi),
        'sinyaller': kontrol_listesi,
        'otomatik_kapatilan': otomatik_kapatilan,
        'otomatik_kapatma_log': otomatik_kapatma_log,
        'ozet': ozet
    }

    _raporu_kaydet(rapor)

    _logger.info("=" * 60)
    _logger.info(f"  RAPOR TAMAMLANDI | Kapatılan: {otomatik_kapatilan} | "
                 f"DEVAM:{karar_dagilimi.get('DEVAM',0)} "
                 f"YUMUSAK:{karar_dagilimi.get('YUMUSAK_CIKIS',0)} "
                 f"SERT:{karar_dagilimi.get('SERT_CIKIS',0)}")
    _logger.info("=" * 60)

    return rapor


# ══════════════════════════════════════════════════════════════════════
#  POZİSYON KAPATMA
# ══════════════════════════════════════════════════════════════════════

def _pozisyon_kapat(sinyal: dict) -> dict:
    """
    Bir sinyali veritabanında kapatır.

    Dönüş: {'basarili': bool, 'islem_id': int, 'hisse': str, 'kapanis_fiyat': float, 'durum': str}
    """
    try:
        conn = sqlite3.connect(DB_YOLU)
        c = conn.cursor()

        islem_id = sinyal['id']
        hisse = sinyal['hisse']
        guncel_fiyat = sinyal.get('guncel_fiyat') or float(sinyal.get('giris_fiyati', 0))
        karar = sinyal['karar']

        yeni_durum = '⛔ BAŞARISIZ' if karar == 'SERT_CIKIS' else '⏰ ZAMAN AŞIMI'

        c.execute('''UPDATE ai_sinyaller
                     SET durum = ?, kapanis_fiyati = ?
                     WHERE id = ?''',
                  (yeni_durum, guncel_fiyat, islem_id))

        conn.commit()
        conn.close()

        # Telegram bildirimi
        try:
            mesaj = (f"<b>🔴 BEKLEYEN POZİSYON KAPATILDI</b>\n\n"
                    f"Sembol: <b>{hisse}</b>\n"
                    f"Sebep: <b>{yeni_durum}</b>\n"
                    f"Giriş: {sinyal.get('giris_fiyati', '?')}\n"
                    f"Kapanış: {guncel_fiyat}\n"
                    f"Skor: {sinyal.get('skor', '?')}/100\n"
                    f"Gecikme: {sinyal.get('gecikme_gun', 0):.0f} gün")
            telegram_mesaj_gonder(mesaj)
        except:
            pass

        return {
            'basarili': True,
            'islem_id': islem_id,
            'hisse': hisse,
            'kapanis_fiyat': guncel_fiyat,
            'durum': yeni_durum,
            'skor': sinyal.get('skor', 0),
            'gecikme_gun': sinyal.get('gecikme_gun', 0)
        }

    except Exception as e:
        _logger.error(f"Kapatma hatası ({sinyal.get('hisse', '?')}): {e}")
        return {'basarili': False, 'islem_id': sinyal.get('id', 0),
                'hisse': sinyal.get('hisse', '?'), 'kapanis_fiyat': 0,
                'durum': 'HATA', 'hata': str(e)[:200]}


# ══════════════════════════════════════════════════════════════════════
#  ÖZET VE RAPORLAMA
# ══════════════════════════════════════════════════════════════════════

def _ozet_olustur(tum_sinyaller: list, kontrol_listesi: list,
                  sinif_dagilimi: dict, karar_dagilimi: dict,
                  otomatik_kapatilan: int, kapatma_log: list) -> str:
    """İnsan tarafından okunabilir özet metni."""
    simdi = datetime.now().strftime("%d.%m.%Y %H:%M")

    satirlar = []
    satirlar.append("╔══════════════════════════════════════════════════╗")
    satirlar.append("║     BEKLEYEN SİNYAL TAKİP RAPORU                ║")
    satirlar.append(f"║     {simdi}                          ║")
    satirlar.append("╠══════════════════════════════════════════════════╣")
    satirlar.append(f"║ Toplam Bekleyen : {len(tum_sinyaller):>4d}                          ║")
    satirlar.append(f"║ Kontrol Edilen  : {len(kontrol_listesi):>4d}                          ║")
    satirlar.append("╠══════════════════════════════════════════════════╣")
    satirlar.append("║ GECİKME DAĞILIMI:                               ║")
    for sinif in ['TAZE', 'GECIKMIS', 'SORUNLU', 'KRITIK', 'ZAMAN_ASIMI']:
        adet = sinif_dagilimi.get(sinif, 0)
        if adet > 0:
            emoji = {'TAZE': '🟢', 'GECIKMIS': '🟡', 'SORUNLU': '🟠', 'KRITIK': '🔴', 'ZAMAN_ASIMI': '💀'}
            satirlar.append(f"║   {emoji.get(sinif,'⚪')} {sinif:<15s}: {adet:>4d}                       ║")
    satirlar.append("╠══════════════════════════════════════════════════╣")
    satirlar.append("║ KARAR DAĞILIMI:                                 ║")
    for karar in ['DEVAM', 'YUMUSAK_CIKIS', 'SERT_CIKIS', 'ZAMAN_ASIMI']:
        adet = karar_dagilimi.get(karar, 0)
        if adet > 0:
            emoji = {'DEVAM': '✅', 'YUMUSAK_CIKIS': '⚠️', 'SERT_CIKIS': '🔴', 'ZAMAN_ASIMI': '💀'}
            satirlar.append(f"║   {emoji.get(karar,'⚪')} {karar:<15s}: {adet:>4d}                       ║")
    satirlar.append("╠══════════════════════════════════════════════════╣")

    if otomatik_kapatilan > 0:
        satirlar.append(f"║ ⚡ OTOMATİK KAPATILAN: {otomatik_kapatilan:>4d}                     ║")
        for log in kapatma_log[:5]:
            satirlar.append(f"║   • {log['hisse']:<12s} @ {log['kapanis_fiyat']:<10.4f} {log['durum']}  ║")
        if len(kapatma_log) > 5:
            satirlar.append(f"║   ... ve {len(kapatma_log)-5} tane daha            ║")

    satirlar.append("╚══════════════════════════════════════════════════╝")

    # Kritik sinyalleri listele
    kritik_sinyaller = [s for s in kontrol_listesi
                       if s.get('karar') in ('SERT_CIKIS', 'ZAMAN_ASIMI', 'YUMUSAK_CIKIS')]

    if kritik_sinyaller:
        satirlar.append("")
        satirlar.append("📋 AKSİYON GEREKTİREN SİNYALLER:")
        satirlar.append("-" * 60)
        for s in sorted(kritik_sinyaller, key=lambda x: x.get('skor', 0)):
            satirlar.append(
                f"  {s['karar']:<15s} | {s['hisse']:<14s} | "
                f"Skor:{s.get('skor',0):>3d} | "
                f"Gecikme:{s.get('gecikme_gun',0):>5.0f}g | "
                f"Değ:%{s.get('yuzde_degisim',0):>+.1f} | "
                f"{s.get('karar_detay','')[:60]}"
            )

    # DEVAM edenleri özetle
    devam_edenler = [s for s in kontrol_listesi if s.get('karar') == 'DEVAM']
    if devam_edenler:
        satirlar.append("")
        satirlar.append(f"✅ DEVAM EDEN {len(devam_edenler)} SİNYAL (hala geçerli):")
        for s in sorted(devam_edenler, key=lambda x: -x.get('skor', 0))[:10]:
            satirlar.append(
                f"  {s['hisse']:<14s} | Skor:{s.get('skor',0):>3d}/100 | "
                f"{s.get('gecikme_gun',0):.0f}g | "
                f"Güncel:{s.get('guncel_fiyat','?')} | "
                f"{s.get('guncel_trend','?')}"
            )
        if len(devam_edenler) > 10:
            satirlar.append(f"  ... ve {len(devam_edenler)-10} tane daha")

    return "\n".join(satirlar)


def _raporu_kaydet(rapor: dict):
    """Takip raporunu JSON'a kaydeder."""
    try:
        # Dairesel referansları temizle (datetime objeleri)
        temiz_rapor = json.loads(json.dumps(rapor, default=str, ensure_ascii=False))
        with open(RAPOR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(temiz_rapor, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _logger.error(f"Rapor kaydedilemedi: {e}")


# ══════════════════════════════════════════════════════════════════════
#  KOLAY KULLANIM FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════

def hizli_durum_ozeti() -> str:
    """
    Sadece özet metni döndürür, piyasa verisi çekmez.
    Dashboard'da hızlı widget için.
    """
    tum_sinyaller = bekleyen_sinyalleri_getir()
    if not tum_sinyaller:
        return "📊 Bekleyen sinyal yok."

    sinif_dagilimi = defaultdict(int)
    for s in tum_sinyaller:
        sinif_dagilimi[s['gecikme_sinif']] += 1

    kritik = sinif_dagilimi.get('KRITIK', 0)
    sorunlu = sinif_dagilimi.get('SORUNLU', 0)
    taze = sinif_dagilimi.get('TAZE', 0)
    toplam = len(tum_sinyaller)

    if kritik > 0:
        return f"🔴 {toplam} bekleyen — {kritik} KRİTİK, {sorunlu} sorunlu! Acil inceleme gerekli."
    elif sorunlu > 3:
        return f"🟠 {toplam} bekleyen — {sorunlu} sorunlu sinyal var. Takip raporu çalıştırın."
    else:
        return f"🟢 {toplam} bekleyen — {taze} taze, sistem normal."


def sadece_kritikleri_tara(otomatik_kapat: bool = False) -> dict:
    """Sadece KRITIK ve ZAMAN_ASIMI sinyallerini tarar."""
    return bekleyen_takip_raporu(
        otomatik_kapat=otomatik_kapat,
        sadece_sinif='KRITIK'
    )


def tam_tarama(otomatik_kapat: bool = False) -> dict:
    """Tüm bekleyen sinyalleri tarar."""
    return bekleyen_takip_raporu(otomatik_kapat=otomatik_kapat)


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  BEKLEYEN SİNYAL TAKİP MOTORU — TEST")
    print("=" * 60)

    # Hızlı durum özeti
    print("\n📊 HIZLI DURUM:")
    print(hizli_durum_ozeti())

    # Sadece kritik olanları tara (otomatik kapatma KAPALI)
    print("\n\n🔍 KRITIK SİNYALLER TARANIYOR...")
    print("   (otomatik kapatma: KAPALI)")
    rapor = sadece_kritikleri_tara(otomatik_kapat=False)
    print("\n" + rapor['ozet'])

    if rapor['karar_dagilimi'].get('SERT_CIKIS', 0) > 0:
        print(f"\n⚠️ {rapor['karar_dagilimi']['SERT_CIKIS']} sinyal SERT ÇIKIŞ öneriliyor.")
        print("   Otomatik kapatmak için: bekleyen_takip_raporu(otomatik_kapat=True)")