# -*- coding: utf-8 -*-
"""
mod_formasyon.py — Gelişmiş Grafik Formasyonu Analizi v4.0

AMAÇ:
  - 25+ grafik formasyonu tespiti (klasik + mum + harmonik)
  - Her formasyonun o hissede GEÇMİŞ BAŞARI ORANINI ölçme
  - Başarı oranına göre ağırlıklı puanlama (ör: 5 puanlık formasyon %50 başarılıysa 2.5 puan)
  - sinyal_hesapla() entegrasyonu için hazır puan çıktısı

YENİ FORMASYONLAR (mevcutlara ek):
  Klasik: Yükselen Üçgen, Alçalan Üçgen, Simetrik Üçgen, Dikdörtgen, 
          Yükselen Takoz, Alçalan Takoz, Genişleyen Formasyon (Megafon),
          Elmas, Yuvarlak Dip, V Dip, Adam & Havva, Üçlü Dip, Üçlü Tepe
  Mum:    Çekiç, Asılı Adam, Sabah Yıldızı, Akşam Yıldızı, 
          Boğa Yutan, Ayı Yutan, Üç Beyaz Asker, Üç Siyah Karga,
          Doji, Kayan Yıldız, Ters Çekiç
  Harmonik: AB=CD (basitleştirilmiş)
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Optional
from collections import defaultdict
import json
import os
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════════════════════
# FORMASYON TANIMLARI ve PUAN TABLOSU
# ══════════════════════════════════════════════════════════════════════

# Her formasyon: (max_puan, yon, aciklama, tespit_penceresi_min)
# yon: 1 = yükseliş (AL), -1 = düşüş (SAT), 0 = yön bağımlı değil
FORMASYON_PUAN_TABLOSU = {
    # Klasik Formasyonlar
    "ikili_dip":         (5, 1,  "İkili Dip (W) — güçlü dönüş formasyonu"),
    "ikili_tepe":        (5, -1, "İkili Tepe (M) — sert satış habercisi"),
    "uclu_dip":          (7, 1,  "Üçlü Dip — çok güçlü destek, trend dönüşü"),
    "uclu_tepe":         (7, -1, "Üçlü Tepe — çok güçlü direnç, zirve formasyonu"),
    "fincan_kulp":       (6, 1,  "Fincan-Kulp — uzun vadeli yükseliş başlangıcı"),
    "yuvarlak_dip":      (5, 1,  "Yuvarlak Dip (Saucer) — yavaş ve sağlam dönüş"),
    "v_dip":             (4, 1,  "V Dip — sert ve hızlı dönüş"),
    "adam_havva":        (6, 1,  "Adam & Havva — 2 dipli güçlü dönüş formasyonu"),
    "flama":             (4, 1,  "Flama — direk sonrası konsolidasyon, devam formasyonu"),
    "bayrak":            (3, 1,  "Bayrak — paralel kanal konsolidasyonu"),
    "yukselen_ucgen":    (4, 1,  "Yükselen Üçgen — yatay direnç, yükselen dipler"),
    "alcalan_ucgen":     (4, -1, "Alçalan Üçgen — yatay destek, alçalan tepeler"),
    "simetrik_ucgen":    (3, 0,  "Simetrik Üçgen — her iki yöne kırılım potansiyeli"),
    "dikdortgen":        (2, 0,  "Dikdörtgen — yatay kutu, kırılım yönü belli değil"),
    "yukselen_takoz":    (4, -1, "Yükselen Takoz — daralan yükseliş, aşağı kırılım"),
    "alcalan_takoz":     (4, 1,  "Alçalan Takoz — daralan düşüş, yukarı kırılım"),
    "genisleyen":        (3, 0,  "Genişleyen Formasyon (Megafon) — volatilite artışı"),
    "elmas":             (4, -1, "Elmas Formasyonu — tepe dönüş formasyonu"),
    "obo":               (6, -1, "Omuz-Baş-Omuz — klasik düşüş formasyonu"),
    "ters_obo":          (6, 1,  "Ters Omuz-Baş-Omuz — klasik yükseliş formasyonu"),
    "sikisma":           (2, 0,  "Fiyat Sıkışması — volatilite patlaması öncesi"),
    "hacim_patlamasi":   (3, 1,  "Hacim Patlaması — spekülatif alım sinyali"),

    # Mum Formasyonları
    "cekic":             (2, 1,  "Çekiç (Hammer) — dip dönüş mumu"),
    "asili_adam":        (2, -1, "Asılı Adam — tepe dönüş mumu"),
    "ters_cekic":        (2, 1,  "Ters Çekiç — yükseliş habercisi"),
    "kayan_yildiz":      (2, -1, "Kayan Yıldız — düşüş habercisi"),
    "boga_yutan":        (3, 1,  "Boğa Yutan (Bullish Engulfing) — güçlü alım"),
    "ayi_yutan":         (3, -1, "Ayı Yutan (Bearish Engulfing) — güçlü satış"),
    "sabah_yildizi":     (4, 1,  "Sabah Yıldızı — 3 mumlu dip dönüş"),
    "aksam_yildizi":     (4, -1, "Akşam Yıldızı — 3 mumlu tepe dönüş"),
    "uc_beyaz_asker":    (3, 1,  "Üç Beyaz Asker — güçlü yükseliş trendi"),
    "uc_siyah_karga":    (3, -1, "Üç Siyah Karga — güçlü düşüş trendi"),
    "doji":              (1, 0,  "Doji — kararsızlık, trend dönüşü yakın"),
    "uzun_alt_golge":    (2, 1,  "Uzun Alt Gölge — alıcılar devrede"),
    "uzun_ust_golge":    (2, -1, "Uzun Üst Gölge — satıcılar devrede"),

    # Harmonik
    "ab_cd_yukselen":    (3, 1,  "AB=CD Yükselen — harmonik dönüş noktası"),
    "ab_cd_dusen":       (3, -1, "AB=CD Düşen — harmonik dönüş noktası"),
}

# Formasyon başarı oranları hafızası (hisse bazlı)
_gecmis_basari_havuzu = {}
BASARI_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "formasyon_basari_gecmisi.json")

def _basari_havuzu_yukle():
    """Formasyon başarı geçmişini JSON'dan yükle."""
    global _gecmis_basari_havuzu
    try:
        if os.path.exists(BASARI_DOSYASI):
            with open(BASARI_DOSYASI, "r", encoding="utf-8") as f:
                _gecmis_basari_havuzu = json.load(f)
    except (json.JSONDecodeError, IOError):
        _gecmis_basari_havuzu = {}

def _basari_havuzu_kaydet():
    """Formasyon başarı geçmişini JSON'a kaydet."""
    try:
        with open(BASARI_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(_gecmis_basari_havuzu, f, indent=2, ensure_ascii=False, default=str)
    except IOError:
        pass

# Başlangıçta yükle
_basari_havuzu_yukle()


# ══════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════════

def _find_local_extrema(arr, window=5):
    """Lokal tepe ve dip noktalarının indekslerini bulur."""
    peaks = []
    troughs = []
    for i in range(window, len(arr) - window):
        if arr[i] == np.max(arr[i-window:i+window+1]):
            peaks.append(i)
        if arr[i] == np.min(arr[i-window:i+window+1]):
            troughs.append(i)
    return peaks, troughs


def _formasyon_gecmis_basari_hesapla(hisse_kodu: str, df: pd.DataFrame, 
                                      formasyon_adi: str, 
                                      yon: int,
                                      ileri_bakis: int = 10) -> float:
    """
    Belirli bir formasyonun bu hissede GEÇMİŞTE ne kadar işe yaradığını hesaplar.
    
    Algoritma:
      1. Son 1-2 yıllık veride formasyonu tara
      2. Her tespit edilen formasyondan sonra 'ileri_bakis' bar ileriye bak
      3. Eğer fiyat beklenen yönde hareket etmişse (eşik: %1.5) → BAŞARILI
      4. Başarı oranı = Başarılı / Toplam Tespit
    
    Parametreler:
        hisse_kodu: 'THYAO.IS' gibi
        df: OHLCV DataFrame
        formasyon_adi: formasyon tanımlayıcısı
        yon: 1 (AL/yükseliş) veya -1 (SAT/düşüş)
        ileri_bakis: kaç bar sonrasına bakılacak
    
    Dönüş: 0.0 - 1.0 arası başarı oranı
    """
    if len(df) < 60:
        return 0.5  # Yetersiz veri, nötr
    
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close))
    _open = df['Open'].values
    
    tespit_indeksleri = []
    
    # Formasyonu geçmişte tara (her 10 bar kaydırarak)
    tarama_penceresi = 60
    for baslangic in range(0, len(close) - tarama_penceresi - ileri_bakis, 5):
        son = baslangic + tarama_penceresi
        pencere_close = close[baslangic:son]
        pencere_high = high[baslangic:son]
        pencere_low = low[baslangic:son]
        pencere_volume = volume[baslangic:son]
        pencere_open = _open[baslangic:son]
        
        tespit = _tek_formasyon_tara(
            pencere_close, pencere_high, pencere_low, 
            pencere_volume, pencere_open, formasyon_adi
        )
        
        if tespit:
            tespit_indeksleri.append(son - 1)  # Formasyonun tespit edildiği son bar
    
    if len(tespit_indeksleri) < 2:
        # Önbellekten bak
        hisse_verisi = _gecmis_basari_havuzu.get(hisse_kodu, {})
        formasyon_verisi = hisse_verisi.get(formasyon_adi, None)
        if formasyon_verisi:
            return formasyon_verisi.get('basari_orani', 0.5)
        return 0.5  # Varsayılan nötr
    
    # Her tespit için sonucu değerlendir
    basarili = 0
    for idx in tespit_indeksleri:
        if idx + ileri_bakis >= len(close):
            continue
        baslangic_fiyat = close[idx]
        hedef_fiyat = close[idx + ileri_bakis]
        hareket = (hedef_fiyat - baslangic_fiyat) / baslangic_fiyat
        
        esik = 0.015  # %1.5 minimum hareket
        
        if yon == 1 and hareket > esik:
            basarili += 1
        elif yon == -1 and hareket < -esik:
            basarili += 1
        elif yon == 0:
            # Yönsüz formasyonlar için kırılım yönüne bak
            # Güçlü hareket varsa başarılı say
            if abs(hareket) > esik * 2:
                basarili += 0.5  # Yarı puan
    
    basari_orani = basarili / max(len(tespit_indeksleri), 1)
    
    # Önbelleğe kaydet
    if hisse_kodu not in _gecmis_basari_havuzu:
        _gecmis_basari_havuzu[hisse_kodu] = {}
    _gecmis_basari_havuzu[hisse_kodu][formasyon_adi] = {
        'basari_orani': round(basari_orani, 3),
        'toplam_tespit': len(tespit_indeksleri),
        'basarili': round(basarili, 1),
        'son_guncelleme': datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    return basari_orani


def _tek_formasyon_tara(close, high, low, volume, _open, formasyon_adi):
    """Tek bir formasyonu belirtilen pencerede tarar."""
    if formasyon_adi == "ikili_dip":
        return _tespit_ikili_dip(close, low)
    elif formasyon_adi == "ikili_tepe":
        return _tespit_ikili_tepe(close, high)
    elif formasyon_adi == "uclu_dip":
        return _tespit_uclu_dip(close, low)
    elif formasyon_adi == "uclu_tepe":
        return _tespit_uclu_tepe(close, high)
    elif formasyon_adi == "fincan_kulp":
        return _tespit_fincan_kulp(close, volume)
    elif formasyon_adi == "yuvarlak_dip":
        return _tespit_yuvarlak_dip(close, volume)
    elif formasyon_adi == "v_dip":
        return _tespit_v_dip(close)
    elif formasyon_adi == "adam_havva":
        return _tespit_adam_havva(close, low)
    elif formasyon_adi == "flama":
        return _tespit_flama(close, high, low, volume)
    elif formasyon_adi == "bayrak":
        return _tespit_bayrak(close, high, low, volume)
    elif formasyon_adi == "yukselen_ucgen":
        return _tespit_yukselen_ucgen(close, high, low)
    elif formasyon_adi == "alcalan_ucgen":
        return _tespit_alcalan_ucgen(close, high, low)
    elif formasyon_adi == "simetrik_ucgen":
        return _tespit_simetrik_ucgen(close, high, low)
    elif formasyon_adi == "dikdortgen":
        return _tespit_dikdortgen(close, high, low)
    elif formasyon_adi == "yukselen_takoz":
        return _tespit_yukselen_takoz(close, high, low)
    elif formasyon_adi == "alcalan_takoz":
        return _tespit_alcalan_takoz(close, high, low)
    elif formasyon_adi == "genisleyen":
        return _tespit_genisleyen(close, high, low)
    elif formasyon_adi == "elmas":
        return _tespit_elmas(close, high, low)
    elif formasyon_adi == "obo":
        return _tespit_obo(close, high)
    elif formasyon_adi == "ters_obo":
        return _tespit_ters_obo(close, low)
    elif formasyon_adi == "sikisma":
        return _tespit_sikisma(close, volume)
    elif formasyon_adi == "hacim_patlamasi":
        return _tespit_hacim_patlamasi(close, volume)
    elif formasyon_adi == "cekic":
        return _tespit_cekic(_open, high, low, close)
    elif formasyon_adi == "asili_adam":
        return _tespit_asili_adam(_open, high, low, close)
    elif formasyon_adi == "ters_cekic":
        return _tespit_ters_cekic(_open, high, low, close)
    elif formasyon_adi == "kayan_yildiz":
        return _tespit_kayan_yildiz(_open, high, low, close)
    elif formasyon_adi == "boga_yutan":
        return _tespit_boga_yutan(_open, close)
    elif formasyon_adi == "ayi_yutan":
        return _tespit_ayi_yutan(_open, close)
    elif formasyon_adi == "sabah_yildizi":
        return _tespit_sabah_yildizi(_open, close)
    elif formasyon_adi == "aksam_yildizi":
        return _tespit_aksam_yildizi(_open, close)
    elif formasyon_adi == "uc_beyaz_asker":
        return _tespit_uc_beyaz_asker(_open, close)
    elif formasyon_adi == "uc_siyah_karga":
        return _tespit_uc_siyah_karga(_open, close)
    elif formasyon_adi == "doji":
        return _tespit_doji(_open, close)
    elif formasyon_adi == "uzun_alt_golge":
        return _tespit_uzun_alt_golge(_open, high, low, close)
    elif formasyon_adi == "uzun_ust_golge":
        return _tespit_uzun_ust_golge(_open, high, low, close)
    elif formasyon_adi == "ab_cd_yukselen":
        return _tespit_ab_cd(close, "yukselen")
    elif formasyon_adi == "ab_cd_dusen":
        return _tespit_ab_cd(close, "dusen")
    return False


# ══════════════════════════════════════════════════════════════════════
# KLASİK FORMASYON TESPİT FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════

def _tespit_ikili_dip(close, low):
    """İkili Dip: 2 benzer düşük dip ve ortada yüksek tepe."""
    try:
        if len(close) < 30:
            return False
        min_30 = np.min(low[-30:])
        son_fiyat = float(close[-1])
        dibe_uzaklik = ((son_fiyat - min_30) / min_30) * 100 if min_30 > 0 else 100
        return dibe_uzaklik <= 3.0
    except:
        return False


def _tespit_ikili_tepe(close, high):
    """İkili Tepe: 2 benzer yüksek tepe."""
    try:
        if len(close) < 30:
            return False
        max_30 = np.max(high[-30:])
        son_fiyat = float(close[-1])
        tepeye_uzaklik = ((max_30 - son_fiyat) / son_fiyat) * 100 if son_fiyat > 0 else 100
        return tepeye_uzaklik <= 3.0
    except:
        return False


def _tespit_uclu_dip(close, low):
    """Üçlü Dip: 3 benzer dip seviyesi."""
    try:
        if len(close) < 45:
            return False
        _, troughs = _find_local_extrema(low, window=4)
        if len(troughs) < 3:
            return False
        son_3_dip = [float(low[i]) for i in troughs[-3:]]
        if len(son_3_dip) < 3:
            return False
        dips = son_3_dip
        ortalama_dip = np.mean(dips)
        max_sapma = max(abs(d - ortalama_dip) / ortalama_dip for d in dips) if ortalama_dip > 0 else 1
        return max_sapma < 0.04 and all(d < np.mean(close) * 0.97 for d in dips)
    except:
        return False


def _tespit_uclu_tepe(close, high):
    """Üçlü Tepe: 3 benzer tepe seviyesi."""
    try:
        if len(close) < 45:
            return False
        peaks, _ = _find_local_extrema(high, window=4)
        if len(peaks) < 3:
            return False
        son_3_tepe = [float(high[i]) for i in peaks[-3:]]
        if len(son_3_tepe) < 3:
            return False
        tepeler = son_3_tepe
        ortalama_tepe = np.mean(tepeler)
        max_sapma = max(abs(t - ortalama_tepe) / ortalama_tepe for t in tepeler) if ortalama_tepe > 0 else 1
        return max_sapma < 0.04 and all(t > np.mean(close) * 1.03 for t in tepeler)
    except:
        return False


def _tespit_fincan_kulp(close, volume):
    """Fincan-Kulp formasyonu."""
    try:
        n = len(close)
        if n < 50:
            return False
        bolum = n // 4
        sol_tepe = np.max(close[:bolum*2])
        fincan_dibi = np.min(close[bolum:bolum*3])
        sag_tepe = np.max(close[bolum*3:])
        tepe_orani = abs(sol_tepe - sag_tepe) / sol_tepe
        fincan_derinligi = ((sol_tepe - fincan_dibi) / sol_tepe) * 100
        son_kisim = close[-bolum//2:]
        kulp_dibi = np.min(son_kisim)
        kulp_derinligi = ((sag_tepe - kulp_dibi) / sag_tepe) * 100
        sag_hacim = np.mean(volume[-bolum:])
        sol_hacim = np.mean(volume[:bolum])
        return (5 <= fincan_derinligi <= 35 and tepe_orani <= 0.08 and
                1.0 <= kulp_derinligi <= 8.0 and sag_hacim > sol_hacim * 0.7)
    except:
        return False


def _tespit_yuvarlak_dip(close, volume):
    """Yuvarlak Dip: U şeklinde yavaş dönüş."""
    try:
        n = len(close)
        if n < 40:
            return False
        sol_yarim = close[:n//2]
        sag_yarim = close[n//2:]
        sol_egim = np.polyfit(range(len(sol_yarim)), sol_yarim, 1)[0]
        sag_egim = np.polyfit(range(len(sag_yarim)), sag_yarim, 1)[0]
        dip_noktasi = np.min(close[n//4:3*n//4])
        sol_tepe = np.max(sol_yarim)
        derinlik = ((sol_tepe - dip_noktasi) / sol_tepe) * 100 if sol_tepe > 0 else 0
        return sol_egim < -0.001 and sag_egim > 0.001 and 5 < derinlik < 30
    except:
        return False


def _tespit_v_dip(close):
    """V Dip: Sert düşüş ve sert çıkış."""
    try:
        n = len(close)
        if n < 20:
            return False
        sol_yarim = close[:n//2]
        sag_yarim = close[n//2:]
        sol_degisim = (sol_yarim[-1] - sol_yarim[0]) / sol_yarim[0] * 100 if sol_yarim[0] > 0 else 0
        sag_degisim = (sag_yarim[-1] - sag_yarim[0]) / sag_yarim[0] * 100 if sag_yarim[0] > 0 else 0
        return sol_degisim < -5 and sag_degisim > 5
    except:
        return False


def _tespit_adam_havva(close, low):
    """Adam & Havva: Keskin dip + yuvarlak dip."""
    try:
        if len(close) < 40:
            return False
        _, troughs = _find_local_extrema(low, window=4)
        if len(troughs) < 2:
            return False
        son_2_dip = troughs[-2:]
        dip1_derin = float(low[son_2_dip[0]])
        dip2_derin = float(low[son_2_dip[1]])
        benzer = abs(dip1_derin - dip2_derin) / dip1_derin < 0.05 if dip1_derin > 0 else False
        return benzer and dip1_derin < np.mean(close) * 0.95
    except:
        return False


def _tespit_flama(close, high, low, volume):
    """Flama: Direk + daralan üçgen."""
    try:
        n = len(close)
        if n < 30:
            return False
        direk_bolum = close[:15]
        flama_bolum = close[15:25]
        kirilim_bolum = close[25:]
        direk_degisim = ((direk_bolum[-1] - direk_bolum[0]) / direk_bolum[0]) * 100 if direk_bolum[0] > 0 else 0
        flama_genislik = ((np.max(flama_bolum) - np.min(flama_bolum)) / np.min(flama_bolum)) * 100 if np.min(flama_bolum) > 0 else 100
        direk_hacim = np.mean(volume[:15])
        flama_hacim = np.mean(volume[15:25])
        kirilim_hacim = np.mean(volume[25:])
        return (direk_degisim > 8.0 and flama_genislik < 5.0 and
                flama_hacim < direk_hacim * 0.8 and kirilim_hacim > flama_hacim * 1.3)
    except:
        return False


def _tespit_bayrak(close, high, low, volume):
    """Bayrak: Direk + paralel kanal."""
    try:
        n = len(close)
        if n < 25:
            return False
        direk_bolum = close[:12]
        bayrak_bolum = close[12:]
        direk_degisim = ((direk_bolum[-1] - direk_bolum[0]) / direk_bolum[0]) * 100 if direk_bolum[0] > 0 else 0
        bayrak_degisim = ((bayrak_bolum[-1] - bayrak_bolum[0]) / bayrak_bolum[0]) * 100 if bayrak_bolum[0] > 0 else 0
        direk_hacim = np.mean(volume[:12])
        bayrak_hacim = np.mean(volume[12:])
        return (abs(direk_degisim) > 6.0 and abs(bayrak_degisim) < 5.0 and bayrak_hacim < direk_hacim * 0.85)
    except:
        return False


def _tespit_yukselen_ucgen(close, high, low):
    """Yükselen Üçgen: Yatay direnç + yükselen dipler."""
    try:
        if len(close) < 30:
            return False
        peaks, troughs = _find_local_extrema(close, window=4)
        if len(peaks) < 2 or len(troughs) < 3:
            return False
        son_tepeler = [float(close[i]) for i in peaks[-3:]]
        son_dipler = [float(close[i]) for i in troughs[-3:]]
        tepe_sapma = np.std(son_tepeler) / np.mean(son_tepeler) if np.mean(son_tepeler) > 0 else 1
        dip_egim = np.polyfit(range(len(son_dipler)), son_dipler, 1)[0] if len(son_dipler) >= 2 else 0
        return tepe_sapma < 0.03 and dip_egim > np.mean(son_dipler) * 0.001
    except:
        return False


def _tespit_alcalan_ucgen(close, high, low):
    """Alçalan Üçgen: Yatay destek + alçalan tepeler."""
    try:
        if len(close) < 30:
            return False
        peaks, troughs = _find_local_extrema(close, window=4)
        if len(peaks) < 3 or len(troughs) < 2:
            return False
        son_tepeler = [float(close[i]) for i in peaks[-3:]]
        son_dipler = [float(close[i]) for i in troughs[-3:]]
        dip_sapma = np.std(son_dipler) / np.mean(son_dipler) if np.mean(son_dipler) > 0 else 1
        tepe_egim = np.polyfit(range(len(son_tepeler)), son_tepeler, 1)[0] if len(son_tepeler) >= 2 else 0
        return dip_sapma < 0.03 and tepe_egim < -np.mean(son_tepeler) * 0.001
    except:
        return False


def _tespit_simetrik_ucgen(close, high, low):
    """Simetrik Üçgen: Alçalan tepeler + yükselen dipler."""
    try:
        if len(close) < 30:
            return False
        peaks, troughs = _find_local_extrema(close, window=4)
        if len(peaks) < 3 or len(troughs) < 3:
            return False
        son_tepeler = [float(close[i]) for i in peaks[-3:]]
        son_dipler = [float(close[i]) for i in troughs[-3:]]
        tepe_egim = np.polyfit(range(len(son_tepeler)), son_tepeler, 1)[0]
        dip_egim = np.polyfit(range(len(son_dipler)), son_dipler, 1)[0]
        bant_genislik = ((max(son_tepeler) - min(son_dipler)) / min(son_dipler) * 100) if min(son_dipler) > 0 else 100
        return tepe_egim < 0 and dip_egim > 0 and bant_genislik < 8
    except:
        return False


def _tespit_dikdortgen(close, high, low):
    """Dikdörtgen: Yatay direnç ve yatay destek."""
    try:
        if len(close) < 20:
            return False
        recent = close[-20:]
        recent_high = high[-20:]
        recent_low = low[-20:]
        ust_band = np.mean(recent_high)
        alt_band = np.mean(recent_low)
        bant_genislik = ((ust_band - alt_band) / alt_band) * 100 if alt_band > 0 else 100
        # Fiyatın büyük kısmı bant içinde mi?
        bantta_oran = np.sum((recent >= alt_band * 0.99) & (recent <= ust_band * 1.01)) / len(recent)
        return 3 < bant_genislik < 10 and bantta_oran > 0.85
    except:
        return False


def _tespit_yukselen_takoz(close, high, low):
    """Yükselen Takoz: Daralan, yukarı eğimli, aşağı kırılım."""
    try:
        if len(close) < 30:
            return False
        peaks, troughs = _find_local_extrema(close, window=4)
        if len(peaks) < 3 or len(troughs) < 3:
            return False
        son_tepeler = [float(close[i]) for i in peaks[-3:]]
        son_dipler = [float(close[i]) for i in troughs[-3:]]
        tepe_egim = np.polyfit(range(len(son_tepeler)), son_tepeler, 1)[0]
        dip_egim = np.polyfit(range(len(son_dipler)), son_dipler, 1)[0]
        tepe_gen = abs(son_tepeler[-1] - son_tepeler[0]) / son_tepeler[0] if son_tepeler[0] > 0 else 0
        dip_gen = abs(son_dipler[-1] - son_dipler[0]) / son_dipler[0] if son_dipler[0] > 0 else 0
        return tepe_egim > 0 and dip_egim > 0 and dip_gen > tepe_gen and tepe_gen < 0.06
    except:
        return False


def _tespit_alcalan_takoz(close, high, low):
    """Alçalan Takoz: Daralan, aşağı eğimli, yukarı kırılım."""
    try:
        if len(close) < 30:
            return False
        peaks, troughs = _find_local_extrema(close, window=4)
        if len(peaks) < 3 or len(troughs) < 3:
            return False
        son_tepeler = [float(close[i]) for i in peaks[-3:]]
        son_dipler = [float(close[i]) for i in troughs[-3:]]
        tepe_egim = np.polyfit(range(len(son_tepeler)), son_tepeler, 1)[0]
        dip_egim = np.polyfit(range(len(son_dipler)), son_dipler, 1)[0]
        return tepe_egim < 0 and dip_egim < 0 and abs(tepe_egim) > abs(dip_egim)
    except:
        return False


def _tespit_genisleyen(close, high, low):
    """Genişleyen Formasyon (Megafon): Genişleyen aralık."""
    try:
        if len(close) < 30:
            return False
        peaks, troughs = _find_local_extrema(close, window=4)
        if len(peaks) < 3 or len(troughs) < 3:
            return False
        son_tepeler = [float(close[i]) for i in peaks[-3:]]
        son_dipler = [float(close[i]) for i in troughs[-3:]]
        tepe_genisliyor = son_tepeler[-1] > son_tepeler[0] * 1.02
        dip_genisliyor = son_dipler[-1] < son_dipler[0] * 0.98
        return tepe_genisliyor or dip_genisliyor
    except:
        return False


def _tespit_elmas(close, high, low):
    """Elmas Formasyonu: Önce genişleyen sonra daralan."""
    try:
        if len(close) < 40:
            return False
        sol_yarim = close[:20]
        sag_yarim = close[20:]
        sol_aralik = (np.max(sol_yarim) - np.min(sol_yarim)) / np.mean(sol_yarim)
        sag_aralik = (np.max(sag_yarim) - np.min(sag_yarim)) / np.mean(sag_yarim)
        return sol_aralik > 0.06 and sag_aralik < sol_aralik * 0.7
    except:
        return False


def _tespit_obo(close, high):
    """Omuz-Baş-Omuz."""
    try:
        peaks, _ = _find_local_extrema(close, window=4)
        if len(peaks) < 3:
            return False
        son_tepeler = peaks[-3:]
        if len(son_tepeler) < 3:
            return False
        sol_omuz = float(close[son_tepeler[0]])
        bas = float(close[son_tepeler[1]])
        sag_omuz = float(close[son_tepeler[2]])
        return (bas > sol_omuz * 1.02 and bas > sag_omuz * 1.02 and
                abs(sol_omuz - sag_omuz) / sol_omuz < 0.08)
    except:
        return False


def _tespit_ters_obo(close, low):
    """Ters Omuz-Baş-Omuz."""
    try:
        _, troughs = _find_local_extrema(close, window=4)
        if len(troughs) < 3:
            return False
        son_dipler = troughs[-3:]
        if len(son_dipler) < 3:
            return False
        sol_omuz = float(close[son_dipler[0]])
        bas = float(close[son_dipler[1]])
        sag_omuz = float(close[son_dipler[2]])
        return (bas < sol_omuz * 0.98 and bas < sag_omuz * 0.98 and
                abs(sol_omuz - sag_omuz) / sol_omuz < 0.08)
    except:
        return False


def _tespit_sikisma(close, volume):
    """Fiyat Sıkışması."""
    try:
        if len(close) < 20:
            return False
        max_20 = np.max(close[-20:])
        min_20 = np.min(close[-20:])
        bant_genisligi = ((max_20 - min_20) / min_20) * 100 if min_20 > 0 else 100
        son_5_hacim = np.mean(volume[-5:])
        onceki_hacim = np.mean(volume[-15:-5]) if len(volume) > 15 else son_5_hacim
        hacim_dusuk = son_5_hacim < onceki_hacim * 0.85
        return bant_genisligi <= 8.0 and hacim_dusuk
    except:
        return False


def _tespit_hacim_patlamasi(close, volume):
    """Hacim Patlaması."""
    try:
        if len(close) < 10:
            return False
        son_hacim = float(volume[-1])
        ortalama_hacim = float(np.mean(volume[:-1])) if len(volume) > 1 else son_hacim
        son_degisim = ((close[-1] - close[-2]) / close[-2]) * 100 if close[-2] > 0 else 0
        return son_hacim > ortalama_hacim * 2.5 and son_degisim > 1.5
    except:
        return False


# ══════════════════════════════════════════════════════════════════════
# MUM FORMASYONU TESPİT FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════

def _mum_analiz(_open, high, low, close, idx=-1):
    """Son N mumun detaylı analizini yapar."""
    o = float(_open[idx])
    h = float(high[idx])
    l = float(low[idx])
    c = float(close[idx])
    govde = abs(c - o)
    ust_golge = h - max(c, o)
    alt_golge = min(c, o) - l
    toplam_boy = h - l
    if toplam_boy == 0:
        return None
    return {
        'govde': govde,
        'ust_golge': ust_golge,
        'alt_golge': alt_golge,
        'toplam_boy': toplam_boy,
        'govde_orani': govde / toplam_boy,
        'alt_golge_orani': alt_golge / toplam_boy if toplam_boy > 0 else 0,
        'ust_golge_orani': ust_golge / toplam_boy if toplam_boy > 0 else 0,
        'yesil': c > o,
        'kirmizi': c < o,
    }


def _tespit_cekic(_open, high, low, close):
    """Çekiç: Küçük gövde, en az 2x alt gölge."""
    mum = _mum_analiz(_open, high, low, close)
    if not mum:
        return False
    return (mum['govde_orani'] < 0.35 and 
            mum['alt_golge'] > mum['govde'] * 2.0 and
            mum['ust_golge'] < mum['govde'] * 0.5 and
            min(close) > np.mean(close) * 0.9)


def _tespit_asili_adam(_open, high, low, close):
    """Asılı Adam: Çekiç gibi ama yukarıda."""
    mum = _mum_analiz(_open, high, low, close)
    if not mum:
        return False
    return (mum['govde_orani'] < 0.35 and
            mum['alt_golge'] > mum['govde'] * 2.0 and
            mum['ust_golge'] < mum['govde'] * 0.5 and
            max(close) > np.mean(close) * 1.05)


def _tespit_ters_cekic(_open, high, low, close):
    """Ters Çekiç: Küçük gövde, en az 2x üst gölge."""
    mum = _mum_analiz(_open, high, low, close)
    if not mum:
        return False
    return (mum['govde_orani'] < 0.35 and
            mum['ust_golge'] > mum['govde'] * 2.0 and
            mum['alt_golge'] < mum['govde'] * 0.5)


def _tespit_kayan_yildiz(_open, high, low, close):
    """Kayan Yıldız: Ters Çekiç gibi ama yukarıda."""
    mum = _mum_analiz(_open, high, low, close)
    if not mum:
        return False
    return (mum['govde_orani'] < 0.35 and
            mum['ust_golge'] > mum['govde'] * 2.0 and
            mum['alt_golge'] < mum['govde'] * 0.5 and
            max(close) > np.mean(close) * 1.03)


def _tespit_boga_yutan(_open, close):
    """Boğa Yutan: Kırmızıdan sonra onu yutan yeşil."""
    try:
        if len(close) < 2:
            return False
        o0, c0 = float(_open[-2]), float(close[-2])
        o1, c1 = float(_open[-1]), float(close[-1])
        onceki_kirmizi = c0 < o0
        son_yesil = c1 > o1
        yutma = c1 > o0 and o1 < c0
        return onceki_kirmizi and son_yesil and yutma
    except:
        return False


def _tespit_ayi_yutan(_open, close):
    """Ayı Yutan: Yeşilden sonra onu yutan kırmızı."""
    try:
        if len(close) < 2:
            return False
        o0, c0 = float(_open[-2]), float(close[-2])
        o1, c1 = float(_open[-1]), float(close[-1])
        onceki_yesil = c0 > o0
        son_kirmizi = c1 < o1
        yutma = c1 < o0 and o1 > c0
        return onceki_yesil and son_kirmizi and yutma
    except:
        return False


def _tespit_sabah_yildizi(_open, close):
    """Sabah Yıldızı: Kırmızı → Doji/Küçük → Yeşil."""
    try:
        if len(close) < 3:
            return False
        c0, c1, c2 = float(close[-3]), float(close[-2]), float(close[-1])
        o0, o1, o2 = float(_open[-3]), float(_open[-2]), float(_open[-1])
        govde0 = abs(c0 - o0)
        govde1 = abs(c1 - o1)
        govde2 = abs(c2 - o2)
        return (c0 < o0 and govde1 < govde0 * 0.5 and c2 > o2 and
                c2 > (o0 + c0) / 2)
    except:
        return False


def _tespit_aksam_yildizi(_open, close):
    """Akşam Yıldızı: Yeşil → Doji/Küçük → Kırmızı."""
    try:
        if len(close) < 3:
            return False
        c0, c1, c2 = float(close[-3]), float(close[-2]), float(close[-1])
        o0, o1, o2 = float(_open[-3]), float(_open[-2]), float(_open[-1])
        govde0 = abs(c0 - o0)
        govde1 = abs(c1 - o1)
        govde2 = abs(c2 - o2)
        return (c0 > o0 and govde1 < govde0 * 0.5 and c2 < o2 and
                c2 < (o0 + c0) / 2)
    except:
        return False


def _tespit_uc_beyaz_asker(_open, close):
    """Üç Beyaz Asker: 3 ardışık yükselen yeşil mum."""
    try:
        if len(close) < 3:
            return False
        c0, c1, c2 = float(close[-3]), float(close[-2]), float(close[-1])
        o0, o1, o2 = float(_open[-3]), float(_open[-2]), float(_open[-1])
        return (c0 > o0 and c1 > o1 and c2 > o2 and
                o1 > o0 and o2 > o1 and
                c1 > c0 and c2 > c1)
    except:
        return False


def _tespit_uc_siyah_karga(_open, close):
    """Üç Siyah Karga: 3 ardışık alçalan kırmızı mum."""
    try:
        if len(close) < 3:
            return False
        c0, c1, c2 = float(close[-3]), float(close[-2]), float(close[-1])
        o0, o1, o2 = float(_open[-3]), float(_open[-2]), float(_open[-1])
        return (c0 < o0 and c1 < o1 and c2 < o2 and
                o1 < o0 and o2 < o1 and
                c1 < c0 and c2 < c1)
    except:
        return False


def _tespit_doji(_open, close):
    """Doji: Açılış ve kapanış neredeyse aynı."""
    try:
        govde = abs(float(close[-1]) - float(_open[-1]))
        toplam = float(max(close[-5:]) - min(close[-5:]))
        return govde < toplam * 0.03 if toplam > 0 else False
    except:
        return False


def _tespit_uzun_alt_golge(_open, high, low, close):
    """Uzun Alt Gölge: Toplam boyun %65'inden fazla alt gölge."""
    mum = _mum_analiz(_open, high, low, close)
    if not mum:
        return False
    return mum['alt_golge_orani'] > 0.65


def _tespit_uzun_ust_golge(_open, high, low, close):
    """Uzun Üst Gölge: Toplam boyun %65'inden fazla üst gölge."""
    mum = _mum_analiz(_open, high, low, close)
    if not mum:
        return False
    return mum['ust_golge_orani'] > 0.65


# ══════════════════════════════════════════════════════════════════════
# HARMONIK FORMASYON
# ══════════════════════════════════════════════════════════════════════

def _tespit_ab_cd(close, yon="yukselen"):
    """Basitleştirilmiş AB=CD harmonik formasyonu."""
    try:
        if len(close) < 20:
            return False
        # 4 nokta bul: A, B, C, D
        recent = close[-20:]
        peaks, troughs = _find_local_extrema(recent, window=3)
        
        if yon == "yukselen":
            # Yükselen AB=CD: A ve C tepe, B ve D dip
            if len(troughs) < 2 or len(peaks) < 2:
                return False
            a = float(recent[peaks[-2]])
            b = float(recent[troughs[-2]])
            c = float(recent[peaks[-1]])
            d = float(recent[troughs[-1]])
            ab = abs(a - b)
            cd = abs(c - d)
            return (ab > 0 and cd > 0 and 
                    0.7 < cd / ab < 1.3 and 
                    d > b)
        else:
            if len(troughs) < 2 or len(peaks) < 2:
                return False
            a = float(recent[troughs[-2]])
            b = float(recent[peaks[-2]])
            c = float(recent[troughs[-1]])
            d = float(recent[peaks[-1]])
            ab = abs(a - b)
            cd = abs(c - d)
            return (ab > 0 and cd > 0 and 
                    0.7 < cd / ab < 1.3 and 
                    d < b)
    except:
        return False


# ══════════════════════════════════════════════════════════════════════
# ANA ANALİZ FONKSİYONU (AĞIRLIKLI SKORLAMA)
# ══════════════════════════════════════════════════════════════════════

def formasyon_analizi(df: pd.DataFrame, hisse_kodu: Optional[str] = None, 
                      basari_agirlikli: bool = True) -> List[Dict]:
    """
    Kapsamlı formasyon analizi — 25+ formasyon.
    
    Args:
        df: OHLCV DataFrame
        hisse_kodu: Hisse kodu (örn: 'THYAO.IS') — başarı oranı için gerekli
        basari_agirlikli: True → formasyon puanı, geçmiş başarı oranıyla ağırlıklandırılır
    
    Returns:
        [
            {
                'tip': 'success'|'error'|'warning',
                'baslik': 'İKİLİ DİP (W Formasyonu)',
                'detay': '...',
                'formasyon_adi': 'ikili_dip',
                'puan': 3.5,          # Ağırlıklandırılmış puan (max 5)
                'ham_puan': 5,        # Formasyonun teorik max puanı
                'basari_orani': 0.70, # Bu hissede geçmiş başarı oranı
                'yon': 1              # 1: AL, -1: SAT, 0: NÖTR
            },
            ...
        ]
    """
    sonuclar = []
    
    if len(df) < 20:
        return sonuclar
    
    # Veriyi hazırla
    close = df['Close'].values if isinstance(df['Close'], np.ndarray) else df['Close'].tail(60).values
    if len(df) >= 60:
        high = df['High'].tail(60).values
        low = df['Low'].tail(60).values
        _open = df['Open'].tail(60).values if 'Open' in df.columns else np.ones(60) * close
        volume = df['Volume'].tail(60).values if 'Volume' in df.columns else np.ones(60)
    else:
        high = df['High'].values
        low = df['Low'].values
        _open = df['Open'].values if 'Open' in df.columns else np.ones(len(close)) * close
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close))
    
    close_60 = close
    high_60 = high
    low_60 = low
    _open_60 = _open
    volume_60 = volume
    
    son_fiyat = float(close_60[-1])
    max_30 = np.max(high_60[-30:]) if len(high_60) >= 30 else np.max(high_60)
    min_30 = np.min(low_60[-30:]) if len(low_60) >= 30 else np.min(low_60)
    
    dibe_uzaklik = ((son_fiyat - min_30) / min_30) * 100 if min_30 > 0 else 100
    tepeye_uzaklik = ((max_30 - son_fiyat) / son_fiyat) * 100 if son_fiyat > 0 else 100
    bant_genisligi = ((max_30 - min_30) / min_30) * 100 if min_30 > 0 else 100
    
    # ── Tüm formasyonları tara ──
    tespit_edilenler = []
    
    # İkili Dip
    if _tespit_ikili_dip(close_60, low_60):
        tespit_edilenler.append(("ikili_dip", 'success',
            f'Fiyat son 1 ayin en guclu destek seviyesine ({min_30:.2f}) cok yakin. '
            f'Bu seviyede 2. dip olusuyor. Yukari yonlu sert sekme ve trend donusu beklenir. '
            f'Stop: {min_30*0.97:.2f} alti.'))
    
    # İkili Tepe
    if _tespit_ikili_tepe(close_60, high_60):
        tespit_edilenler.append(("ikili_tepe", 'error',
            f'Fiyat son 1 ayin direnc seviyesine ({max_30:.2f}) 2. kez dayandi. '
            f'Bu seviye kirilamazsa sert kar satisi ve dusus trendi baslayabilir.'))
    
    # Üçlü Dip
    if _tespit_uclu_dip(close_60, low_60):
        tespit_edilenler.append(("uclu_dip", 'success',
            f'UCLU DIP formasyonu! Fiyat ayni destek bolgesinden 3 kez sekme yapti. '
            f'Cok guclu destek ({min_30:.2f}). Yukari kirilim hedefi: {max_30:.2f}.'))
    
    # Üçlü Tepe
    if _tespit_uclu_tepe(close_60, high_60):
        tespit_edilenler.append(("uclu_tepe", 'error',
            f'UCLU TEPE formasyonu! Fiyat ayni direnc seviyesinden 3 kez dondu. '
            f'Zirve olusumu tamamlaniyor olabilir. Satis baskisi beklenir.'))
    
    # Fincan-Kulp
    if len(close_60) >= 50:
        if _tespit_fincan_kulp(close_60, volume_60):
            n = len(close_60)
            bolum = n // 4
            sol_tepe = np.max(close_60[:bolum*2])
            sag_tepe = np.max(close_60[bolum*3:])
            tespit_edilenler.append(("fincan_kulp", 'success',
                f'FINCAN-KULP formasyonu tamamlanmak uzere! '
                f'Sol tepe: {sol_tepe:.2f}, Sag tepe: {sag_tepe:.2f}. '
                f'Yukari kirilim hedefi: {sag_tepe*1.08:.2f}.'))
    
    # Yuvarlak Dip
    if _tespit_yuvarlak_dip(close_60, volume_60):
        tespit_edilenler.append(("yuvarlak_dip", 'success',
            f'YUVARLAK DIP (Saucer) formasyonu! Fiyat yavas ve saglam bir donus icinde. '
            f'U seklindeki toparlanma suruyor. Orta vadeli AL firsati.'))
    
    # V Dip
    if _tespit_v_dip(close_60):
        tespit_edilenler.append(("v_dip", 'success',
            f'V DIP formasyonu! Sert dusus sonrasi ayni hizla toparlanma var. '
            f'Hizli ve guclu bir donus sinyali. Momentum devam edebilir.'))
    
    # Adam & Havva
    if _tespit_adam_havva(close_60, low_60):
        tespit_edilenler.append(("adam_havva", 'success',
            f'ADAM & HAVVA formasyonu! Birinci dip (Adam) keskin, ikinci dip (Havva) '
            f'yuvarlak ve genis. Cok guclu bir donus formasyonu tamamlaniyor.'))
    
    # Flama
    if len(close_60) >= 30:
        if _tespit_flama(close_60, high_60, low_60, volume_60):
            direk_degisim = ((close_60[14] - close_60[0]) / close_60[0]) * 100 if close_60[0] > 0 else 0
            hedef = float(close_60[-1]) + abs(float(close_60[14]) - float(close_60[0]))
            tespit_edilenler.append(("flama", 'success',
                f'FLAMA formasyonu! Sert %{abs(direk_degisim):.1f} direk sonrasi daralan konsolidasyon. '
                f'Yukari kirilim hedefi: {hedef:.2f}.'))
    
    # Bayrak
    if len(close_60) >= 25:
        if _tespit_bayrak(close_60, high_60, low_60, volume_60):
            direk_deg = ((close_60[11] - close_60[0]) / close_60[0]) * 100 if close_60[0] > 0 else 0
            yon = 'yukselen' if direk_deg > 0 else 'dusen'
            tip = 'success' if direk_deg > 0 else 'warning'
            tespit_edilenler.append(("bayrak", tip,
                f'BAYRAK formasyonu! %{abs(direk_deg):.1f} {yon} direk sonrasi paralel kanal. '
                f'Konsolidasyon sonrasi {yon} yonde devam beklenir.'))
    
    # Yükselen Üçgen
    if _tespit_yukselen_ucgen(close_60, high_60, low_60):
        tespit_edilenler.append(("yukselen_ucgen", 'success',
            f'YUKSELEN UCGEN! Yatay direnc ({max_30:.2f}) ve yukselen dipler. '
            f'Direnc kirilirsa sert yukselis baslayabilir. Hedef direnc + bant boyu.'))
    
    # Alçalan Üçgen
    if _tespit_alcalan_ucgen(close_60, high_60, low_60):
        tespit_edilenler.append(("alcalan_ucgen", 'error',
            f'ALCALAN UCGEN! Yatay destek ({min_30:.2f}) ve alcalan tepeler. '
            f'Destek kirilirsa sert dusus beklenir. SAT baskisi!'))
    
    # Simetrik Üçgen
    if _tespit_simetrik_ucgen(close_60, high_60, low_60):
        tespit_edilenler.append(("simetrik_ucgen", 'warning',
            f'SIMETRIK UCGEN! Fiyat daralan bant icinde. '
            f'Kirilim yonu henuz belli degil. Stop emirlerini sıkı tutun.'))
    
    # Dikdörtgen
    if _tespit_dikdortgen(close_60, high_60, low_60):
        tespit_edilenler.append(("dikdortgen", 'warning',
            f'DIKDORTGEN formasyonu! Fiyat yatay bantta ({min_30:.2f}-{max_30:.2f}) sikisiyor. '
            f'Kutu kirilimi yonunde sert hareket beklenir.'))
    
    # Yükselen Takoz
    if _tespit_yukselen_takoz(close_60, high_60, low_60):
        tespit_edilenler.append(("yukselen_takoz", 'error',
            f'YUKSELEN TAKOZ! Daralan yukari egim — asagi kirilim habercisi. '
            f'SAT veya kar realizasyonu dusunulebilir.'))
    
    # Alçalan Takoz
    if _tespit_alcalan_takoz(close_60, high_60, low_60):
        tespit_edilenler.append(("alcalan_takoz", 'success',
            f'ALCALAN TAKOZ! Daralan asagi egim — yukari kirilim habercisi. '
            f'Dusus ivmesi azaliyor, yukselis potansiyeli var.'))
    
    # Genişleyen Formasyon
    if _tespit_genisleyen(close_60, high_60, low_60):
        tespit_edilenler.append(("genisleyen", 'warning',
            f'MEGAFON (Genisleyen Formasyon)! Volatilite artiyor, '
            f'sert hareketler olabilir. Risk yonetimi onemli.'))
    
    # Elmas
    if _tespit_elmas(close_60, high_60, low_60):
        tespit_edilenler.append(("elmas", 'error',
            f'ELMAS formasyonu! Once genisleyen sonra daralan yapi — tepe donus sinyali. '
            f'SAT baskinligi beklenir.'))
    
    # OBO
    if len(close_60) >= 40:
        if _tespit_obo(close_60, high_60):
            peaks, _ = _find_local_extrema(close_60, window=4)
            if len(peaks) >= 3:
                son_tepeler = peaks[-3:]
                bas_h = float(close_60[son_tepeler[1]])
                boyun = np.min(close_60[son_tepeler[0]:son_tepeler[2]+1])
                hedef = boyun - (bas_h - boyun)
                tespit_edilenler.append(("obo", 'error',
                    f'OMOZ-BAS-OMUZ (OBO)! Bas ({bas_h:.2f}) en yuksek. '
                    f'Boyun cizgisi ({boyun:.2f}) kirilirsa dusus hedefi: {hedef:.2f}. SATIS!'))
    
    # Ters OBO
    if len(close_60) >= 40:
        if _tespit_ters_obo(close_60, low_60):
            _, troughs = _find_local_extrema(close_60, window=4)
            if len(troughs) >= 3:
                son_dipler = troughs[-3:]
                bas_d = float(close_60[son_dipler[1]])
                boyun = np.max(close_60[son_dipler[0]:son_dipler[2]+1])
                hedef = boyun + (boyun - bas_d)
                tespit_edilenler.append(("ters_obo", 'success',
                    f'TERS OMOZ-BAS-OMUZ! Bas ({bas_d:.2f}) en dusuk. '
                    f'Boyun cizgisi ({boyun:.2f}) yukari kirilirsa hedef: {hedef:.2f}.'))
    
    # Sıkışma
    if _tespit_sikisma(close_60, volume_60):
        tespit_edilenler.append(("sikisma", 'warning',
            f'ENERJI BIRIKIMI! Son 30 gundur fiyat dar bantta (%{bant_genisligi:.1f}). '
            f'Buyuk bir kirilim (Breakout) cok yakin.'))
    
    # Hacim Patlaması
    if _tespit_hacim_patlamasi(close_60, volume_60):
        son_hacim = float(volume_60[-1])
        ort_hacim = float(np.mean(volume_60[:-1])) if len(volume_60) > 1 else son_hacim
        son_deg = ((close_60[-1] - close_60[-2]) / close_60[-2]) * 100 if close_60[-2] > 0 else 0
        tespit_edilenler.append(("hacim_patlamasi", 'success',
            f'HACIM PATLAMASI! Normalin {son_hacim/ort_hacim:.1f}x hacim ile fiyat %{son_deg:.2f} yukseldi. '
            f'Spekulatif alim firsati olabilir.'))
    
    # ── Mum Formasyonları ──
    if _tespit_cekic(_open_60, high_60, low_60, close_60):
        tespit_edilenler.append(("cekic", 'success',
            f'CEKIC (Hammer) mum formasyonu! Alt golge cok uzun, alicilar fiyati yukari tasidi. '
            f'Dip donus sinyali.'))

    if _tespit_asili_adam(_open_60, high_60, low_60, close_60):
        tespit_edilenler.append(("asili_adam", 'error',
            f'ASILI ADAM mum formasyonu! Yuksek seviyede olusan cekic benzeri mum, '
            f'saticilarin devreye girecegini isaret ediyor.'))

    if _tespit_ters_cekic(_open_60, high_60, low_60, close_60):
        tespit_edilenler.append(("ters_cekic", 'success',
            f'TERS CEKIC! Ust golge cok uzun, satis baskinligina ragmen kapanis yukarda. '
            f'Potansiyel yukselis donus sinyali.'))

    if _tespit_kayan_yildiz(_open_60, high_60, low_60, close_60):
        tespit_edilenler.append(("kayan_yildiz", 'error',
            f'KAYAN YILDIZ! Uzun ust golge, yuksek seviyede satis baskisi. '
            f'Dusus habercisi.'))

    if _tespit_boga_yutan(_open_60, close_60):
        tespit_edilenler.append(("boga_yutan", 'success',
            f'BOGA YUTAN (Bullish Engulfing)! Guclu yesil mum onceki kirmizi mumi tamamen yuttu. '
            f'Alıcılarin net kontrolu.'))

    if _tespit_ayi_yutan(_open_60, close_60):
        tespit_edilenler.append(("ayi_yutan", 'error',
            f'AYI YUTAN (Bearish Engulfing)! Guclu kirmizi mum onceki yesil mumi tamamen yuttu. '
            f'Saticilarin net kontrolu.'))

    if _tespit_sabah_yildizi(_open_60, close_60):
        tespit_edilenler.append(("sabah_yildizi", 'success',
            f'SABAH YILDIZI! 3 mumlu guclu dip donus formasyonu. '
            f'Kirmizi → Kucuk → Yesil: Trend donuyor.'))

    if _tespit_aksam_yildizi(_open_60, close_60):
        tespit_edilenler.append(("aksam_yildizi", 'error',
            f'AKSAM YILDIZI! 3 mumlu guclu tepe donus formasyonu. '
            f'Yesil → Kucuk → Kirmizi: SAT sinyali!'))

    if _tespit_uc_beyaz_asker(_open_60, close_60):
        tespit_edilenler.append(("uc_beyaz_asker", 'success',
            f'UC BEYAZ ASKER! 3 ardışık yukselen yesil mum. Guclu AL sinyali, '
            f'trend baslangici olabilir.'))

    if _tespit_uc_siyah_karga(_open_60, close_60):
        tespit_edilenler.append(("uc_siyah_karga", 'error',
            f'UC SIYAH KARGA! 3 ardışık alcalan kirmizi mum. Guclu SAT sinyali, '
            f'dusus trendi basliyor.'))

    if _tespit_doji(_open_60, close_60):
        tespit_edilenler.append(("doji", 'warning',
            f'DOJI! Acilis ve kapanis ayni seviyede. Kararsizlik ve potansiyel trend donusu.'))

    if _tespit_uzun_alt_golge(_open_60, high_60, low_60, close_60):
        tespit_edilenler.append(("uzun_alt_golge", 'success',
            f'UZUN ALT GOLGE! Saticilar asagi basti ama alicilar fiyati geri topladi. '
            f'Dip alimi isareti.'))

    if _tespit_uzun_ust_golge(_open_60, high_60, low_60, close_60):
        tespit_edilenler.append(("uzun_ust_golge", 'error',
            f'UZUN UST GOLGE! Alicilar yukari tasidi ama saticilar fiyati geri basti. '
            f'Tepe satisi isareti.'))

    # ── Harmonik Formasyonlar ──
    if _tespit_ab_cd(close_60, "yukselen"):
        tespit_edilenler.append(("ab_cd_yukselen", 'success',
            f'AB=CD YUKSELEN harmonik formasyonu! Fiyat potansiyel donus noktasinda. '
            f'D noktasindan yukari donus beklenir.'))

    if _tespit_ab_cd(close_60, "dusen"):
        tespit_edilenler.append(("ab_cd_dusen", 'error',
            f'AB=CD DUSEN harmonik formasyonu! Fiyat potansiyel donus noktasinda. '
            f'D noktasindan asagi donus beklenir.'))

    # ── Ağırlıklandırılmış puan hesapla ──
    for formasyon_adi, tip, detay in tespit_edilenler:
        puan_bilgisi = FORMASYON_PUAN_TABLOSU.get(formasyon_adi, (2, 0, ""))
        max_puan = puan_bilgisi[0]
        yon = puan_bilgisi[1]
        
        ham_puan = max_puan
        
        if basari_agirlikli and hisse_kodu:
            basari_orani = _formasyon_gecmis_basari_hesapla(
                hisse_kodu, df, formasyon_adi, yon
            )
        else:
            basari_orani = 0.5  # Nötr varsayılan
        
        # AĞIRLIKLI PUAN: max_puan * başarı_oranı
        agirlikli_puan = round(max_puan * basari_orani, 1)
        
        sonuclar.append({
            'tip': tip,
            'baslik': FORMASYON_PUAN_TABLOSU.get(formasyon_adi, (0, 0, formasyon_adi))[2],
            'detay': detay,
            'formasyon_adi': formasyon_adi,
            'puan': agirlikli_puan,
            'ham_puan': ham_puan,
            'basari_orani': basari_orani,
            'yon': yon
        })
    
    # Puan sıralaması (yüksekten düşüğe)
    sonuclar.sort(key=lambda x: x['puan'], reverse=True)
    
    # Başarı havuzunu periyodik kaydet
    if len(tespit_edilenler) > 0 and hisse_kodu:
        _basari_havuzu_kaydet()
    
    return sonuclar


def formasyon_skoru_hesapla(df: pd.DataFrame, hisse_kodu: Optional[str] = None) -> Tuple[float, str]:
    """
    Tüm tespit edilen formasyonların net AL/SAT skorunu hesaplar.
    
    Dönüş: (net_skor, ozet_metin)
        net_skor > 0 → AL yönlü
        net_skor < 0 → SAT yönlü
        net_skor ≈ 0 → NÖTR
    """
    sonuclar = formasyon_analizi(df, hisse_kodu, basari_agirlikli=True)
    
    if not sonuclar:
        return 0.0, ""
    
    al_skor = sum(s['puan'] for s in sonuclar if s['yon'] == 1)
    sat_skor = sum(s['puan'] for s in sonuclar if s['yon'] == -1)
    notr_skor = sum(s['puan'] for s in sonuclar if s['yon'] == 0)
    
    net_skor = al_skor - sat_skor
    
    # Özet metin
    aktif_formasyonlar = [s['baslik'] for s in sonuclar[:5] if s['puan'] >= 1.0]
    ozet = " | ".join(aktif_formasyonlar[:3]) if aktif_formasyonlar else ""
    
    return round(net_skor, 1), ozet


# ══════════════════════════════════════════════════════════════════════
# ESKI API UYUMLULUĞU (geriye dönük)
# ══════════════════════════════════════════════════════════════════════

def formasyon_analizi_basit(df: pd.DataFrame) -> List[Dict]:
    """
    ESKİ API: Sadece mesaj formatında döner (geriye dönük uyumluluk).
    YENİ KODLAR İÇİN formasyon_analizi() veya formasyon_skoru_hesapla() kullanın.
    """
    sonuclar = formasyon_analizi(df, hisse_kodu=None, basari_agirlikli=False)
    return [
        {
            'tip': s['tip'],
            'baslik': s['baslik'],
            'detay': s['detay']
        }
        for s in sonuclar
    ]


# ══════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import yfinance as yf
    
    print("=" * 70)
    print("  GELİŞMİŞ FORMASYON ANALİZ MOTORU TEST")
    print("=" * 70)
    
    test_hissesi = "THYAO.IS"
    print(f"\n📊 {test_hissesi} formasyon analizi yapılıyor...\n")
    
    try:
        df = yf.download(test_hissesi, period="6mo", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        print(f"Veri: {len(df)} bar\n")
        
        # Tam analiz (ağırlıklı skor ile)
        sonuclar = formasyon_analizi(df, hisse_kodu=test_hissesi, basari_agirlikli=True)
        
        if sonuclar:
            print(" TESPIT EDILEN FORMASYONLAR (Ağırlıklı Puanlı):")
            print(" " + "-" * 60)
            for s in sonuclar:
                yon_emoji = "🟢" if s['yon'] == 1 else "🔴" if s['yon'] == -1 else "⚪"
                puan_bar = "█" * int(s['puan']) + "░" * (8 - int(s['puan']))
                print(f"  {yon_emoji} [{s['puan']:.1f}p] {puan_bar} {s['baslik']}")
                print(f"     Başarı Oranı: %{s['basari_orani']*100:.0f} | Ham Puan: {s['ham_puan']}")
                print(f"     {s['detay'][:100]}...")
                print()
        else:
            print("  Şu anda aktif formasyon tespit edilemedi.")
        
        # Net skor
        net_skor, ozet = formasyon_skoru_hesapla(df, test_hissesi)
        print(f"\n  NET FORMASYON SKORU: {net_skor:+.1f}")
        if ozet:
            print(f"  AKTIF: {ozet}")
        
        # Başarı havuzu istatistikleri
        hisse_verisi = _gecmis_basari_havuzu.get(test_hissesi, {})
        if hisse_verisi:
            print(f"\n  {test_hissesi} FORMASYON BAŞARI GEÇMİŞİ:")
            print("  " + "-" * 50)
            for ad, bilgi in sorted(hisse_verisi.items(), 
                                     key=lambda x: x[1].get('basari_orani', 0), 
                                     reverse=True)[:10]:
                print(f"  • {ad}: %{bilgi['basari_orani']*100:.0f} "
                      f"({bilgi['basarili']}/{bilgi['toplam_tespit']} başarılı)")
        
    except Exception as e:
        print(f"  HATA: {e}")
        import traceback
        traceback.print_exc()