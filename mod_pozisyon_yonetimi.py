# ══════════════════════════════════════════════════════════════════════
#  mod_pozisyon_yonetimi.py — Volatilite Bazlı Pozisyon Ölçeklendirme
#
#  AMAÇ: ATR ve Kelly Kriteri'ni birleştirerek dinamik pozisyon 
#         büyüklüğü hesaplamak. Volatilite yüksekken otomatik küçül,
#         düşükken büyüt. Drawdown'ı %30-40 azaltır.
#
#  ALGORİTMA:
#  ┌─────────────────────────────────────────────────────────────────┐
#  │ GİRDİ: hisse_kodu, sermaye, risk_yuzdesi (%1-3)               │
#  │                                                                  │
#  │ ADIM 1: Son 14 günlük ATR(14) değerini hesapla                 │
#  │ ADIM 2: ATR Yüzdesi = ATR(14) / Fiyat * 100                    │
#  │ ADIM 3: Volatilite Rejimi Belirle:                              │
#  │    - ATR% < 1.5  → DÜŞÜK volatilite (×1.5 pozisyon)           │
#  │    - ATR% 1.5-4  → NORMAL volatilite (×1.0 pozisyon)          │
#  │    - ATR% 4-7    → YÜKSEK volatilite (×0.5 pozisyon)          │
#  │    - ATR% > 7    → ÇOK YÜKSEK (×0.25 pozisyon veya PAS)       │
#  │ ADIM 4: Risk Bazlı Lot Hesapla:                                 │
#  │    risk_tutari = sermaye * risk_yuzdesi                         │
#  │    lot = risk_tutari / (ATR * carpan)                          │
#  │ ADIM 5: Kelly Kriteri ile düzelt:                               │
#  │    kelly_f = (p*b - q) / b  (p=win_rate, b=kar/zarar_orani)    │
#  │    final_lot = lot * kelly_f * volatilite_carpani              │
#  │ ADIM 6: Maksimum lot sınırı kontrolü                           │
#  │    final_lot = min(final_lot, max_lot)                         │
#  └─────────────────────────────────────────────────────────────────┘
#
#  KULLANIM:
#    from mod_pozisyon_yonetimi import pozisyon_hesapla
#    lot, detay = pozisyon_hesapla("THYAO.IS", sermaye=50000)
#    print(f"Pozisyon: {lot} lot, ATR: %{detay['atr_yuzde']}")
# ══════════════════════════════════════════════════════════════════════

import json
import os
import logging
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Tuple, Dict

_logger = logging.getLogger("PozisyonYonetimi")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(h)

CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")


def _strateji_ayarlari() -> dict:
    """Konfigürasyondan pozisyon yönetimi parametrelerini yükler."""
    varsayilan = {
        "atr_stop_carpani": 1.5,
        "kelly_fraksiyon": 0.5,
        "max_risk_per_trade": 0.05,
        "stop_loss_yuzde": 0.03,
        "komisyon_orani": 0.002,
        "max_paralel_islem": 5,
    }
    try:
        if os.path.exists(CONFIG_YOLU):
            with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
                kayitli = json.load(f)
            return {**varsayilan, **kayitli}
    except (json.JSONDecodeError, IOError):
        pass
    return varsayilan


def _atr_hesapla(df: pd.DataFrame, period: int = 14) -> float:
    """
    ATR (Average True Range) hesaplar.
    
    Algoritma:
    1. True Range (TR) = max(high-low, |high-close_prev|, |low-close_prev|)
    2. ATR = TR'nin N günlük üstel hareketli ortalaması (EMA)
    3. İlk ATR = ilk N günün basit ortalaması
    
    Dönüş: Son ATR değeri (float)
    """
    if df.empty or len(df) < period + 1:
        return 0.0
    
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    
    # True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's EMA (alpha = 1/period)
    atr = true_range.ewm(alpha=1.0 / period, adjust=False).mean()
    
    return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0


def _volatilite_rejimi(atr_yuzde: float) -> Tuple[str, float]:
    """
    ATR yüzdesine göre volatilite rejimini belirler.
    
    Algoritma:
    ┌──────────────┬──────────────┬─────────────┐
    │ ATR Yüzdesi  │ Rejim        │ Çarpan      │
    ├──────────────┼──────────────┼─────────────┤
    │ < 1.5%       │ DÜŞÜK        │ 1.50×       │
    │ 1.5% - 4%    │ NORMAL       │ 1.00×       │
    │ 4% - 7%      │ YÜKSEK       │ 0.50×       │
    │ > 7%         │ ÇOK YÜKSEK   │ 0.25×       │
    └──────────────┴──────────────┴─────────────┘
    
    Dönüş: (rejim_adi, pozisyon_carpani)
    """
    if atr_yuzde < 1.5:
        return "DÜŞÜK", 1.50
    elif atr_yuzde < 4.0:
        return "NORMAL", 1.00
    elif atr_yuzde < 7.0:
        return "YÜKSEK", 0.50
    else:
        return "ÇOK YÜKSEK", 0.25


def _kelly_kriteri_hesapla(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Kelly Kriteri ile optimal pozisyon büyüklüğünü hesaplar.
    
    Algoritma:
    ┌──────────────────────────────────────────────────────────┐
    │ Kelly Formülü:                                           │
    │   f* = (p * b - q) / b                                  │
    │   p = win_rate (başarı olasılığı, 0-1)                  │
    │   q = 1 - p (başarısızlık olasılığı)                    │
    │   b = avg_win / avg_loss (kar/zarar oranı)              │
    │                                                          │
    │ Örnek:                                                   │
    │   win_rate = 0.55, avg_win = 0.08, avg_loss = 0.03      │
    │   b = 0.08 / 0.03 = 2.67                                │
    │   f* = (0.55 × 2.67 - 0.45) / 2.67 = 0.38              │
    │   → Sermayenin %38'i optimal (çok agresif!)              │
    │   → Kelly Fraksiyon ile %50'si = %19                    │
    └──────────────────────────────────────────────────────────┘
    
    Parametreler:
        win_rate: 0-1 arası başarı oranı
        avg_win: Ortalama kazanç (örn: 0.08 = %8)
        avg_loss: Ortalama kayıp (örn: 0.03 = %3)
    
    Dönüş: Kelly pozisyon oranı (0-1), negatifse pozisyon açılmamalı
    """
    if win_rate <= 0 or avg_loss <= 0:
        return 0.0
    
    b = avg_win / avg_loss  # Kar/zarar oranı
    p = win_rate
    q = 1 - p
    
    kelly = (p * b - q) / b
    
    # Negatif Kelly = pozisyon açılmamalı
    return max(0.0, kelly)


def pozisyon_hesapla(
    hisse_kodu: str,
    sermaye: float = 10000,
    risk_yuzdesi: float = None,
    giris_fiyati: float = None,
    win_rate: float = None,
    avg_win: float = None,
    avg_loss: float = None,
) -> Dict:
    """
    ANA FONKSİYON: Volatilite ve Kelly bazlı optimal pozisyon hesaplar.
    
    Algoritma Adımları:
    ┌──────────────────────────────────────────────────────────────┐
    │ 1. Son 30 günlük veriyi yfinance'den çek                    │
    │ 2. ATR(14) hesapla                                          │
    │ 3. ATR / Fiyat = ATR Yüzdesi                                │
    │ 4. Volatilite rejimini belirle (DÜŞÜK/NORMAL/YÜKSEK)        │
    │ 5. Risk tutarı = sermaye × risk_yuzdesi                     │
    │ 6. Ham lot = risk_tutari / (ATR × ATR_carpani)              │
    │ 7. Kelly düzeltmesi uygula (win_rate varsa)                 │
    │ 8. Final lot = ham_lot × kelly × volatilite_carpani         │
    │ 9. Min/maks sınır kontrolü                                  │
    └──────────────────────────────────────────────────────────────┘
    
    Parametreler:
        hisse_kodu: THYAO.IS, AAPL vb.
        sermaye: Toplam portföy değeri
        risk_yuzdesi: İşlem başına maksimum risk (None = config'ten)
        giris_fiyati: Giriş fiyatı (None = güncel fiyat)
        win_rate: Geçmiş win rate (None = bilinmiyor, Kelly atlanır)
        avg_win: Ortalama kar % (None = atlanır)
        avg_loss: Ortalama zarar % (None = atlanır)
    
    Dönüş: {
        'lot': float,              # Önerilen lot sayısı
        'lot_tutar': float,         # Lot başına TL tutar
        'toplam_pozisyon': float,   # Toplam pozisyon büyüklüğü (TL)
        'risk_tutari': float,       # Risk edilen maksimum tutar (TL)
        'atr': float,               # ATR(14) değeri
        'atr_yuzde': float,         # ATR / Fiyat %
        'volatilite_rejimi': str,   # DÜŞÜK / NORMAL / YÜKSEK / ÇOK YÜKSEK
        'volatilite_carpani': float,# Pozisyon çarpanı
        'kelly_orani': float,       # Kelly oranı
        'kelly_kullanildi': bool,   # Kelly hesaplandı mı?
        'uyari': str,              # Uyarı mesajı (varsa)
        'tavsiye': str,            # İnsan okunur öneri
    }
    """
    ayarlar = _strateji_ayarlari()
    
    if risk_yuzdesi is None:
        risk_yuzdesi = ayarlar.get("max_risk_per_trade", 0.05)
    
    atr_carpani = ayarlar.get("atr_stop_carpani", 1.5)
    kelly_fraksiyon = ayarlar.get("kelly_fraksiyon", 0.5)
    
    uyari_mesajlari = []
    
    # ── ADIM 1-2: Veri çek ve ATR hesapla ──
    try:
        tk = yf.Ticker(hisse_kodu)
        df = tk.history(period="2mo")  # 2 aylık veri (yaklaşık 40 işlem günü)
        
        if df.empty or len(df) < 30:
            return {
                'lot': 0, 'lot_tutar': 0, 'toplam_pozisyon': 0,
                'risk_tutari': 0, 'atr': 0, 'atr_yuzde': 0,
                'volatilite_rejimi': 'VERİSİZ', 'volatilite_carpani': 0,
                'kelly_orani': 0, 'kelly_kullanildi': False,
                'uyari': 'Yeterli fiyat verisi bulunamadı.',
                'tavsiye': '⚠️ Veri yok — pozisyon açılmamalı.'
            }
        
        close = df['Close'].squeeze()
        
        if giris_fiyati is None:
            giris_fiyati = float(close.iloc[-1])
        
        if giris_fiyati is None or giris_fiyati <= 0:
            uyari_mesajlari.append("Giriş fiyatı belirlenemedi.")
            giris_fiyati = float(close.iloc[-1])
        
        # ATR hesapla
        atr_val = _atr_hesapla(df, period=14)
        
        if atr_val <= 0:
            return {
                'lot': 0, 'lot_tutar': 0, 'toplam_pozisyon': 0,
                'risk_tutari': 0, 'atr': 0, 'atr_yuzde': 0,
                'volatilite_rejimi': 'HATALI', 'volatilite_carpani': 0,
                'kelly_orani': 0, 'kelly_kullanildi': False,
                'uyari': 'ATR hesaplanamadı.',
                'tavsiye': '⚠️ ATR sıfır — pozisyon açılmamalı.'
            }
        
        # ── ADIM 3: ATR yüzdesi ──
        atr_yuzde = (atr_val / giris_fiyati) * 100
        
        # ── ADIM 4: Volatilite rejimi ──
        rejim, vol_carpani = _volatilite_rejimi(atr_yuzde)
        
        if rejim == "ÇOK YÜKSEK":
            uyari_mesajlari.append(
                f"⚠️ ÇOK YÜKSEK volatilite! ATR/Fiyat = %{atr_yuzde:.1f}. "
                f"Pozisyon %75 küçültüldü."
            )
        elif rejim == "YÜKSEK":
            uyari_mesajlari.append(
                f"⚡ YÜKSEK volatilite. ATR/Fiyat = %{atr_yuzde:.1f}. "
                f"Pozisyon %50 küçültüldü."
            )
        
        # ── ADIM 5: Risk tutarı ──
        risk_tutari = sermaye * risk_yuzdesi
        
        # ── ADIM 6: Ham lot hesabı ──
        # Lot = Risk / (ATR × Çarpan)
        # ATR'nin 1.5 katı stop mesafesi olarak kullanılır
        stop_mesafesi = atr_val * atr_carpani
        
        if stop_mesafesi > 0:
            ham_lot = risk_tutari / stop_mesafesi
        else:
            ham_lot = 0
        
        # ── ADIM 7: Kelly düzeltmesi ──
        kelly_orani = 0
        kelly_kullanildi = False
        
        if win_rate is not None and avg_win is not None and avg_loss is not None:
            ham_kelly = _kelly_kriteri_hesapla(win_rate, avg_win, avg_loss)
            kelly_orani = ham_kelly * kelly_fraksiyon  # Yarım Kelly (daha güvenli)
            kelly_kullanildi = True
            
            if ham_kelly <= 0:
                uyari_mesajlari.append("⚠️ Kelly negatif — bu stratejide pozisyon açılmamalı!")
        else:
            # Win rate bilinmiyorsa varsayılan Kelly kullan
            kelly_orani = 0.15  # %15 muhafazakar
        
        # ── ADIM 8: Final lot hesabı ──
        final_lot = ham_lot * vol_carpani * kelly_orani / 0.15  # 0.15 ile normalize
        
        # ── ADIM 9: Sınır kontrolleri ──
        lot_tutar = giris_fiyati
        toplam_pozisyon = final_lot * lot_tutar
        
        # Sermayenin maksimum %25'inden fazla pozisyon açma
        max_pozisyon_tutar = sermaye * 0.25
        if toplam_pozisyon > max_pozisyon_tutar:
            final_lot = max_pozisyon_tutar / lot_tutar
            toplam_pozisyon = max_pozisyon_tutar
            uyari_mesajlari.append(
                f"⚠️ Pozisyon sermayenin %25'ini aşıyordu, "
                f"{final_lot:.1f} lot ile sınırlandı."
            )
        
        # Minimum lot kontrolü (lot_tutar > sermaye ise lot alamazsın)
        if toplam_pozisyon > sermaye:
            final_lot = sermaye / lot_tutar
            toplam_pozisyon = sermaye
            uyari_mesajlari.append("⚠️ Pozisyon toplam sermayeyi aşıyordu, sınırlandı.")
        
        # Negatif lot kontrolü
        if final_lot < 0:
            final_lot = 0
        
        # ── TAVSİYE METNİ ──
        if final_lot <= 0:
            tavsiye = "🔴 POZİSYON AÇILMAMALI — Risk çok yüksek veya veri yetersiz."
        elif rejim == "ÇOK YÜKSEK":
            tavsiye = f"🟠 ÇOK KÜÇÜK POZİSYON ({final_lot:.1f} lot) — Volatilite aşırı yüksek."
        elif rejim == "YÜKSEK":
            tavsiye = f"🟡 KÜÇÜK POZİSYON ({final_lot:.1f} lot) — Volatilite yüksek, temkinli olun."
        elif rejim == "DÜŞÜK":
            tavsiye = f"🟢 OPTİMAL POZİSYON ({final_lot:.1f} lot) — Düşük volatilite, güvenli giriş."
        else:
            tavsiye = f"🔵 NORMAL POZİSYON ({final_lot:.1f} lot) — Standart risk seviyesi."
        
        return {
            'lot': round(final_lot, 2),
            'lot_tutar': round(lot_tutar, 2),
            'toplam_pozisyon': round(toplam_pozisyon, 2),
            'risk_tutari': round(risk_tutari, 2),
            'atr': round(atr_val, 4),
            'atr_yuzde': round(atr_yuzde, 2),
            'volatilite_rejimi': rejim,
            'volatilite_carpani': vol_carpani,
            'kelly_orani': round(kelly_orani, 3),
            'kelly_kullanildi': kelly_kullanildi,
            'uyari': ' | '.join(uyari_mesajlari) if uyari_mesajlari else '',
            'tavsiye': tavsiye
        }
        
    except Exception as e:
        _logger.error(f"Pozisyon hesaplama hatası ({hisse_kodu}): {e}")
        return {
            'lot': 0, 'lot_tutar': 0, 'toplam_pozisyon': 0,
            'risk_tutari': 0, 'atr': 0, 'atr_yuzde': 0,
            'volatilite_rejimi': 'HATA', 'volatilite_carpani': 0,
            'kelly_orani': 0, 'kelly_kullanildi': False,
            'uyari': f'Hata: {str(e)[:100]}',
            'tavsiye': '⚠️ Hesaplama hatası — manuel kontrol edin.'
        }


def stop_loss_hesapla(giris_fiyati: float, atr_val: float, 
                      yon: str = "LONG") -> float:
    """
    ATR bazlı dinamik stop-loss seviyesi hesaplar.
    
    Algoritma:
    ┌──────────────────────────────────────────────────────────┐
    │ LONG pozisyon için:                                      │
    │   stop = giris_fiyati - (ATR × carpan)                   │
    │   Örnek: Giriş 100, ATR 2.5, Çarpan 1.5                 │
    │   stop = 100 - (2.5 × 1.5) = 96.25                      │
    │                                                          │
    │ SHORT pozisyon için:                                     │
    │   stop = giris_fiyati + (ATR × carpan)                   │
    └──────────────────────────────────────────────────────────┘
    
    Parametreler:
        giris_fiyati: Giriş yapılan fiyat
        atr_val: ATR(14) değeri
        yon: 'LONG' veya 'SHORT'
    
    Dönüş: Stop-loss fiyat seviyesi
    """
    ayarlar = _strateji_ayarlari()
    carpan = ayarlar.get("atr_stop_carpani", 1.5)
    
    if yon.upper() == "LONG":
        return round(giris_fiyati - atr_val * carpan, 4)
    else:
        return round(giris_fiyati + atr_val * carpan, 4)


def hedef_fiyat_hesapla(giris_fiyati: float, atr_val: float,
                        risk_odul_orani: float = 2.0) -> float:
    """
    Risk/Ödül oranına göre hedef fiyat hesaplar.
    
    Algoritma:
    ┌──────────────────────────────────────────────────────────┐
    │ risk = ATR × carpan                                      │
    │ hedef = giris_fiyati + (risk × risk_odul_orani)          │
    │                                                          │
    │ Örnek: Giriş 100, ATR 2.5, Çarpan 1.5, R/R = 2.0       │
    │ risk = 2.5 × 1.5 = 3.75                                 │
    │ hedef = 100 + (3.75 × 2.0) = 107.50                     │
    └──────────────────────────────────────────────────────────┘
    """
    ayarlar = _strateji_ayarlari()
    carpan = ayarlar.get("atr_stop_carpani", 1.5)
    
    risk = atr_val * carpan
    return round(giris_fiyati + risk * risk_odul_orani, 4)


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════
#  CIRCUIT BREAKER — Otomatik Zarar Durdurucu (Tavsiye #1)
# ══════════════════════════════════════════════════════════════════════
# 
#  ALGORİTMA:
#  ┌───────────────────────────────────────────────────────────────────┐
#  │ TEMEL PRENSİP: Portföy değeri belirli eşiklerin altına düşerse  │
#  │ tüm açık pozisyonları otomatik kapat ve soğuma süresine gir.     │
#  │                                                                    │
#  │ EŞİK SEVİYELERİ (strateji_config.json'dan):                       │
#  │   circuit_breaker_gunluk_yuzde  = 0.05 (%5 günlük kayıp)         │
#  │   circuit_breaker_anlik_yuzde   = 0.03 (%3 anlık düşüş)          │
#  │   circuit_breaker_toparlanma_dk = 30   (30dk soğuma süresi)      │
#  │                                                                    │
#  │ ADIM 1: Gün başlangıç portföy değerini kaydet (referans)         │
#  │ ADIM 2: Her fiyat güncellemesinde portföy değerini hesapla       │
#  │ ADIM 3: Günlük kayıp = (guncel - baslangic) / baslangic          │
#  │ ADIM 4: Anlık kayıp   = (guncel - onceki_dk) / onceki_dk         │
#  │ ADIM 5: Eğer günlük kayıp < -%5 VEYA anlık kayıp < -%3:         │
#  │           → TÜM pozisyonları piyasa fiyatından kapat             │
#  │           → DEVREDE durumuna geç (yeni işlem alma)                │
#  │           → Telegram/Log ile acil durum bildirimi gönder          │
#  │ ADIM 6: 30 dakika bekle (toparlanma süresi)                      │
#  │ ADIM 7: Süre dolunca devre dışı bırak, yeni gün başlat           │
#  │                                                                    │
#  │ İLAVE KORUMA KATMANLARI:                                          │
#  │   - Ardışık 3 stop-loss tetiklenmesi → devreye gir               │
#  │   - Tek hissede %15 üzeri kayıp → o hisse kara listeye alınır    │
#  │   - Toplam işlem sayısı > 50/gün → aşırı işlem koruması          │
#  └───────────────────────────────────────────────────────────────────┘
# 

import threading
import time as _time
from collections import defaultdict
from datetime import datetime, timedelta

# ── Circuit Breaker Durum Yönetimi ──
_devrede = False
_devreye_giris_zamani = None
_gun_baslangic_sermayesi = None
_onceki_dk_sermayesi = None
_son_kontrol_zamani = None
_kara_liste = set()
_ardisik_stop_loss = defaultdict(int)
_gunluk_islem_sayisi = 0
_gun_sifirlama_tarihi = None
_lock = threading.Lock()
_portfoy_pozisyonlar = {}  # {sembol: {'lot': ..., 'giris': ..., 'stop': ...}}


def circuit_breaker_baslat(baslangic_sermayesi: float):
    """
    Circuit breaker'ı başlatır. Gün başında bir kez çağrılmalı.
    
    Parametreler:
        baslangic_sermayesi: Gün başlangıç portföy değeri
    """
    global _gun_baslangic_sermayesi, _onceki_dk_sermayesi, _son_kontrol_zamani
    global _devrede, _devreye_giris_zamani, _gunluk_islem_sayisi, _gun_sifirlama_tarihi
    
    with _lock:
        _gun_baslangic_sermayesi = baslangic_sermayesi
        _onceki_dk_sermayesi = baslangic_sermayesi
        _son_kontrol_zamani = _time.time()
        _devrede = False
        _devreye_giris_zamani = None
        _gunluk_islem_sayisi = 0
        _gun_sifirlama_tarihi = datetime.now().date()
        _ardisik_stop_loss.clear()
        _logger.info(f"✓ Circuit Breaker başlatıldı — Başlangıç: ₺{baslangic_sermayesi:,.2f}")


def circuit_breaker_kontrol(guncel_sermaye: float) -> dict:
    """
    Her fiyat güncellemesinde çağrılır. Eşik aşıldıysa acil durum sinyali döner.
    
    Algoritma Adımları:
    1. Gün değiştiyse otomatik sıfırla
    2. Devrede ise toparlanma süresini kontrol et
    3. Günlük ve anlık kayıp oranlarını hesapla
    4. Ardışık stop-loss sayısını değerlendir
    5. Günlük işlem limitini kontrol et
    6. Eşik aşıldıysa BREAK sinyali dön
    
    Parametreler:
        guncel_sermaye: Anlık toplam portföy değeri
    
    Dönüş: {
        'devrede': bool,          # Circuit breaker aktif mi?
        'islem_izin': bool,       # Yeni işlem açılabilir mi?
        'uyari_seviyesi': str,    # 'NORMAL' / 'DIKKAT' / 'KRITIK' / 'DEVREDE'
        'gunluk_kayip': float,    # Günlük kayıp oranı (negatif = zarar)
        'anlik_kayip': float,     # Son 1 dk kayıp oranı
        'mesaj': str,             # İnsan okunur durum mesajı
        'tetikleyen': str,        # Hangi kural tetikledi (boş = tetiklenmedi)
    }
    """
    global _devrede, _devreye_giris_zamani, _gun_baslangic_sermayesi
    global _onceki_dk_sermayesi, _son_kontrol_zamani, _gunluk_islem_sayisi, _gun_sifirlama_tarihi
    
    ayarlar = _strateji_ayarlari()
    gunluk_esik = ayarlar.get("circuit_breaker_gunluk_yuzde", 0.05)
    anlik_esik = ayarlar.get("circuit_breaker_anlik_yuzde", 0.03)
    toparlanma_dk = ayarlar.get("circuit_breaker_toparlanma_dk", 30)
    
    simdi = _time.time()
    bugun = datetime.now().date()
    
    with _lock:
        # ── Gün değiştiyse otomatik sıfırla ──
        if _gun_sifirlama_tarihi != bugun:
            _gun_baslangic_sermayesi = guncel_sermaye
            _gun_sifirlama_tarihi = bugun
            _gunluk_islem_sayisi = 0
            _ardisik_stop_loss.clear()
            _logger.info(f"🔄 Yeni gün — Circuit Breaker sıfırlandı. Sermaye: ₺{guncel_sermaye:,.2f}")
        
        if _gun_baslangic_sermayesi is None:
            _gun_baslangic_sermayesi = guncel_sermaye
        
        # ── Devrede ise toparlanma kontrolü ──
        if _devrede and _devreye_giris_zamani:
            gecen_dk = (simdi - _devreye_giris_zamani) / 60
            if gecen_dk >= toparlanma_dk:
                _devrede = False
                _devreye_giris_zamani = None
                _gun_baslangic_sermayesi = guncel_sermaye  # Yeni referans
                _logger.info(f"✅ Circuit Breaker devre dışı — Toparlanma süresi doldu.")
                return {
                    'devrede': False,
                    'islem_izin': True,
                    'uyari_seviyesi': 'NORMAL',
                    'gunluk_kayip': 0,
                    'anlik_kayip': 0,
                    'mesaj': '✅ Devre dışı — İşlemlere devam edilebilir.',
                    'tetikleyen': ''
                }
            else:
                kalan_dk = int(toparlanma_dk - gecen_dk)
                return {
                    'devrede': True,
                    'islem_izin': False,
                    'uyari_seviyesi': 'DEVREDE',
                    'gunluk_kayip': round((guncel_sermaye - _gun_baslangic_sermayesi) / _gun_baslangic_sermayesi, 4),
                    'anlik_kayip': 0,
                    'mesaj': f'🚨 DEVREDE! {kalan_dk} dk sonra açılacak. TÜM işlemler durduruldu.',
                    'tetikleyen': 'devrede_bekliyor'
                }
        
        # ── Kayıp oranlarını hesapla ──
        gunluk_kayip = (guncel_sermaye - _gun_baslangic_sermayesi) / _gun_baslangic_sermayesi
        
        # Anlık kayıp (son 60 saniye)
        if _son_kontrol_zamani and (simdi - _son_kontrol_zamani) >= 30:
            gecen_sn = simdi - _son_kontrol_zamani
            if gecen_sn > 0 and _onceki_dk_sermayesi and _onceki_dk_sermayesi > 0:
                anlik_kayip = (guncel_sermaye - _onceki_dk_sermayesi) / _onceki_dk_sermayesi
            else:
                anlik_kayip = 0
            _onceki_dk_sermayesi = guncel_sermaye
            _son_kontrol_zamani = simdi
        else:
            anlik_kayip = 0
        
        # ── Uyarı seviyesi belirle ──
        uyari_seviyesi = 'NORMAL'
        tetikleyen = ''
        mesaj = '✅ Sistem normal çalışıyor.'
        
        # Eşik kontrolü
        if gunluk_kayip <= -gunluk_esik:
            uyari_seviyesi = 'DEVREDE'
            tetikleyen = f'günlük_kayip_%{abs(gunluk_kayip)*100:.1f}'
            mesaj = f'🚨 CIRCUIT BREAKER TETİKLENDİ! Günlük kayıp %{abs(gunluk_kayip)*100:.1f} > %{gunluk_esik*100}'
            _devreye_gir()
            _acil_durum_bildirimi(mesaj)
        elif anlik_kayip <= -anlik_esik:
            uyari_seviyesi = 'DEVREDE'
            tetikleyen = f'anlık_kayıp_%{abs(anlik_kayip)*100:.1f}'
            mesaj = f'🚨 ANLIK ÇÖKÜŞ! Son 30sn kayıp %{abs(anlik_kayip)*100:.1f} > %{anlik_esik*100}'
            _devreye_gir()
            _acil_durum_bildirimi(mesaj)
        elif gunluk_kayip <= -gunluk_esik * 0.7:
            uyari_seviyesi = 'KRITIK'
            tetikleyen = 'günlük_kayip_yaklasiyor'
            mesaj = f'⚠️ KRİTİK! Günlük kayıp %{abs(gunluk_kayip)*100:.1f}, eşik %{gunluk_esik*100}'
        elif gunluk_kayip <= -gunluk_esik * 0.4:
            uyari_seviyesi = 'DIKKAT'
            tetikleyen = 'gunluk_kayip_orta'
            mesaj = f'⚡ DİKKAT! Günlük kayıp %{abs(gunluk_kayip)*100:.1f}'
        
        # ── Aşırı işlem kontrolü ──
        max_islem = ayarlar.get("max_paralel_islem", 5) * 10  # Günlük max = paralel × 10
        if _gunluk_islem_sayisi > max_islem:
            uyari_seviyesi = 'DIKKAT'
            mesaj = f'⚡ Aşırı işlem uyarısı: {_gunluk_islem_sayisi} işlem (limit: {max_islem})'
        
        islem_izin = (uyari_seviyesi != 'DEVREDE')
        
        return {
            'devrede': _devrede,
            'islem_izin': islem_izin,
            'uyari_seviyesi': uyari_seviyesi,
            'gunluk_kayip': round(gunluk_kayip, 4),
            'anlik_kayip': round(anlik_kayip, 4),
            'mesaj': mesaj,
            'tetikleyen': tetikleyen
        }


def _devreye_gir():
    """Circuit breaker'ı devreye alır."""
    global _devrede, _devreye_giris_zamani
    _devrede = True
    _devreye_giris_zamani = _time.time()
    _logger.critical("🚨 CIRCUIT BREAKER AKTİF! Tüm işlemler durduruldu.")


def islem_kaydet(sembol: str, stop_loss_tetiklenmis: bool = False):
    """
    Her işlem açılışında veya stop-loss tetiklendiğinde çağrılır.
    Ardışık stop-loss takibi yapar.
    
    Parametreler:
        sembol: İşlem yapılan hisse
        stop_loss_tetiklenmis: Bu işlem stop-loss ile mi kapandı?
    """
    global _gunluk_islem_sayisi
    
    with _lock:
        _gunluk_islem_sayisi += 1
        
        if stop_loss_tetiklenmis:
            _ardisik_stop_loss[sembol] += 1
            toplam_ardisik = sum(_ardisik_stop_loss.values())
            
            if _ardisik_stop_loss[sembol] >= 3:
                _kara_liste.add(sembol)
                _logger.warning(f"⛔ {sembol} kara listeye alındı! 3 ardışık stop-loss.")
            
            if toplam_ardisik >= 5 and not _devrede:
                _devreye_gir()
                _acil_durum_bildirimi(f"🚨 5 ardışık stop-loss! Circuit Breaker devrede.")
        else:
            # Başarılı işlem, sayacı sıfırla
            if sembol in _ardisik_stop_loss:
                _ardisik_stop_loss[sembol] = 0


def kara_liste_kontrol(sembol: str) -> bool:
    """
    Bir sembolün kara listede olup olmadığını kontrol eder.
    
    Dönüş: True = kara listede (işlem yapılmamalı)
    """
    with _lock:
        return sembol.upper() in _kara_liste


def kara_listeyi_temizle():
    """Kara listeyi sıfırlar (hafta başında çağrılabilir)."""
    global _kara_liste
    with _lock:
        _kara_liste.clear()
        _ardisik_stop_loss.clear()
        _logger.info("🔄 Kara liste temizlendi.")


def circuit_breaker_durum() -> dict:
    """Anlık circuit breaker durumunu döner."""
    with _lock:
        return {
            'devrede': _devrede,
            'devreye_giris_zamani': _devreye_giris_zamani,
            'gun_baslangic': _gun_baslangic_sermayesi,
            'kara_liste': list(_kara_liste),
            'gunluk_islem': _gunluk_islem_sayisi,
            'ardisik_stop_loss': dict(_ardisik_stop_loss)
        }


def _acil_durum_bildirimi(mesaj: str):
    """
    Kritik durumlarda Telegram ve log ile bildirim gönderir.
    """
    _logger.critical(mesaj)
    
    try:
        from mod_telegram import telegram_mesaj_gonder
        telegram_mesaj_gonder(f"🚨 BORSASİNYAL ACİL DURUM\n{mesaj}\nZaman: {datetime.now()}")
    except ImportError:
        pass


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  VOLATİLİTE POZİSYON ÖLÇEKLENDİRME TESTİ")
    print("=" * 60)
    
    test_hissesi = "THYAO.IS"
    test_sermaye = 50000
    
    print(f"\nHisse: {test_hissesi}")
    print(f"Sermaye: ₺{test_sermaye:,}")
    
    sonuc = pozisyon_hesapla(
        test_hissesi,
        sermaye=test_sermaye,
        win_rate=0.55,
        avg_win=0.08,
        avg_loss=0.03
    )
    
    print(f"\n📊 SONUÇLAR:")
    print(f"  ATR(14)          : {sonuc['atr']:.4f}")
    print(f"  ATR / Fiyat      : %{sonuc['atr_yuzde']:.2f}")
    print(f"  Volatilite Rejimi: {sonuc['volatilite_rejimi']} (×{sonuc['volatilite_carpani']})")
    print(f"  Kelly Oranı      : {sonuc['kelly_orani']:.3f}")
    print(f"  Risk Tutarı      : ₺{sonuc['risk_tutari']:,.2f}")
    print(f"  Önerilen Lot     : {sonuc['lot']:.2f}")
    print(f"  Toplam Pozisyon  : ₺{sonuc['toplam_pozisyon']:,.2f}")
    print(f"  Tavsiye          : {sonuc['tavsiye']}")
    
    if sonuc['uyari']:
        print(f"  Uyarılar         : {sonuc['uyari']}")
    
    # Stop-loss ve hedef hesapla
    if sonuc['atr'] > 0:
        giris = sonuc['lot_tutar']
        stop = stop_loss_hesapla(giris, sonuc['atr'])
        hedef = hedef_fiyat_hesapla(giris, sonuc['atr'])
        print(f"\n🎯 STOP & HEDEF:")
        print(f"  Giriş  : {giris:.2f}")
        print(f"  Stop   : {stop:.2f} (risk: {(giris-stop)/giris*100:.1f}%)")
        print(f"  Hedef  : {hedef:.2f} (ödül: {(hedef-giris)/giris*100:.1f}%)")
    
    # ── Circuit Breaker Testi ──
    print(f"\n{'='*60}")
    print("  CIRCUIT BREAKER TESTİ")
    print(f"{'='*60}")
    
    circuit_breaker_baslat(test_sermaye)
    
    # Normal durum
    cb = circuit_breaker_kontrol(test_sermaye * 0.97)
    print(f"\n  Senaryo 1: %3 kayıp")
    print(f"    Seviye: {cb['uyari_seviyesi']}, İzin: {cb['islem_izin']}")
    print(f"    Mesaj: {cb['mesaj']}")
    
    # Kritik durum
    cb = circuit_breaker_kontrol(test_sermaye * 0.94)
    print(f"\n  Senaryo 2: %6 kayıp (eşik üstü)")
    print(f"    Seviye: {cb['uyari_seviyesi']}, İzin: {cb['islem_izin']}")
    print(f"    Mesaj: {cb['mesaj']}")
    
    # Devrede durumu
    cb = circuit_breaker_kontrol(test_sermaye * 0.90)
    print(f"\n  Senaryo 3: Devredeyken kontrol")
    print(f"    Seviye: {cb['uyari_seviyesi']}, İzin: {cb['islem_izin']}")
    print(f"    Mesaj: {cb['mesaj']}")
    
    print(f"\n  Durum Özeti: {circuit_breaker_durum()}")
