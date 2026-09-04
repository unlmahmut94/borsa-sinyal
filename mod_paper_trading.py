# ══════════════════════════════════════════════════════════════════════
#  mod_paper_trading.py — Kağıt Ticaret (Paper Trading) Motoru v1.0
#
#  AMAÇ: Gerçek para riske etmeden stratejiyi canlı piyasada test etmek.
#         Sanal portföy oluşturur, sinyalleri takip eder, performans ölçer.
#
#  ALGORİTMA:
#  ┌─────────────────────────────────────────────────────────────────┐
#  │ 1. Sanal portföy oluştur (paper_portfoy.json)                  │
#  │ 2. Sinyal üretildiğinde gerçek işlem yapma, sanal portföye ekle │
#  │ 3. Stop-loss / Take-profit sanal kontrol (mod_hafiza benzeri)   │
#  │ 4. Her gün portföy değerini güncelle                           │
#  │ 5. Performans metriklerini hesapla:                             │
#  │    - Toplam Getiri, Win Rate, Sharpe, Max DD                    │
#  │ 6. 1 aylık canlı performans sonrası rapor üret                  │
#  └─────────────────────────────────────────────────────────────────┘
# ══════════════════════════════════════════════════════════════════════

import json
import os
import logging
import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List

_logger = logging.getLogger("PaperTrading")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(h)

PAPER_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_portfoy.json")
PAPER_ISLEMLER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_islemler.json")
DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")


def _paper_portfoy_yukle() -> dict:
    """Sanal portföyü JSON'dan yükler, yoksa yeni oluşturur."""
    varsayilan = {
        "sermaye_baslangic": 100000,
        "sermaye_guncel": 100000,       # Nakit + açık pozisyon değeri
        "nakit": 100000,                 # Boşta bekleyen nakit
        "acik_pozisyonlar": [],          # [{hisse, adet, giris_fiyat, tarih}]
        "gecmis_bakiye": [100000],       # Günlük bakiye serisi
        "baslangic_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "toplam_islem": 0,
        "basarili_islem": 0,
        "basarisiz_islem": 0,
        "toplam_komisyon": 0.0,
    }
    try:
        if os.path.exists(PAPER_DOSYASI):
            with open(PAPER_DOSYASI, "r", encoding="utf-8") as f:
                kayitli = json.load(f)
            return {**varsayilan, **kayitli}
    except (json.JSONDecodeError, IOError):
        pass
    return varsayilan


from filelock import FileLock, Timeout

def _paper_portfoy_kaydet(portfoy: dict):
    """Sanal portföyü JSON'a kilitli (güvenli) kaydeder."""
    lock = FileLock(f"{PAPER_DOSYASI}.lock", timeout=5)
    try:
        with lock:
            with open(PAPER_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(portfoy, f, indent=2, ensure_ascii=False, default=str)
    except (IOError, Timeout) as e:
        _logger.error(f"Paper portföy kaydedilemedi: {e}")

def _paper_islem_kaydet(islem: dict):
    """Paper işlemi JSON log'una kilitli ekler."""
    lock = FileLock(f"{PAPER_ISLEMLER}.lock", timeout=5)
    try:
        with lock:
            if os.path.exists(PAPER_ISLEMLER):
                with open(PAPER_ISLEMLER, "r", encoding="utf-8") as f:
                    islemler = json.load(f)
            else:
                islemler = []
            
            islemler.append(islem)
            
            with open(PAPER_ISLEMLER, "w", encoding="utf-8") as f:
                json.dump(islemler, f, indent=2, ensure_ascii=False, default=str)
    except (IOError, Timeout):
        pass

def paper_sinyal_ac(hisse_kodu: str, sinyal_tipi: str, giris_fiyat: float,
                    hedef_fiyat: float = None, stop_fiyat: float = None,
                    risk_yuzdesi: float = 0.05) -> dict:
    """
    SANAL POZİSYON AÇ
    Gerçek para kullanmadan sanal bir pozisyon açar.
    
    Algoritma:
    1. Portföyü yükle
    2. Pozisyon büyüklüğünü hesapla (sermayenin %5-15'i)
    3. Komisyon hesapla
    4. Nakit'ten düş, pozisyona ekle
    5. Kaydet
    """
    portfoy = _paper_portfoy_yukle()
    nakit = portfoy['nakit']
    
    # Aynı hissede zaten açık pozisyon var mı?
    for p in portfoy['acik_pozisyonlar']:
        if p['hisse'] == hisse_kodu:
            return {
                'durum': 'hata',
                'mesaj': f"⚠️ {hisse_kodu} için zaten açık pozisyon var."
            }
    
    # ── GERÇEKÇİ PİYASA MEKANİKLERİ (Tavsiye #10) ──
    config = _paper_config_yukle()
    slippage_yuzde = config.get("paper_slippage_yuzde", 0.002)
    kismi_dolum_orani = config.get("paper_kismi_dolum_orani", 0.85)
    
    # Slippage: Alışta fiyat biraz yukarı kayar
    slippage = giris_fiyat * slippage_yuzde
    efektif_giris = giris_fiyat + slippage  # ALIŞTA slippage yukarı
    
    # Kısmi dolum: Emrin sadece %85-100'ü gerçekleşir
    dolum_orani = np.random.uniform(kismi_dolum_orani, 1.0)
    
    pozisyon_tutari = nakit * risk_yuzdesi * dolum_orani
    komisyon = pozisyon_tutari * config.get("komisyon_orani", 0.002)  # %0.2
    adet = pozisyon_tutari / efektif_giris
    
    if pozisyon_tutari + komisyon > nakit:
        return {'durum': 'hata', 'mesaj': '⚠️ Yetersiz bakiye.'}
    
    # Likidite kontrolü: Min işlem hacmi
    try:
        tk = yf.Ticker(hisse_kodu)
        info = tk.history(period="5d")
        if not info.empty:
            ortalama_hacim = float(info['Volume'].mean())
            min_islem_hacmi = config.get("min_islem_hacmi", 100000)
            if ortalama_hacim < min_islem_hacmi:
                return {
                    'durum': 'hata',
                    'mesaj': f'⚠️ {hisse_kodu} düşük likidite (hacim: {ortalama_hacim:,.0f})'
                }
    except:
        pass
    
    # Stop ve hedef belirle (verilmediyse ATR bazlı)
    if stop_fiyat is None:
        try:
            from mod_pozisyon_yonetimi import stop_loss_hesapla, _atr_hesapla
            df = tk.history(period="2mo")
            atr = _atr_hesapla(df, period=14) if not df.empty else efektif_giris * 0.03
            stop_fiyat = stop_loss_hesapla(efektif_giris, atr) if atr > 0 else round(efektif_giris * 0.97, 2)
        except:
            stop_fiyat = round(efektif_giris * 0.97, 2)
    
    if hedef_fiyat is None:
        try:
            from mod_pozisyon_yonetimi import hedef_fiyat_hesapla
            hedef_fiyat = hedef_fiyat_hesapla(efektif_giris, atr if 'atr' in dir() else efektif_giris * 0.02)
        except:
            hedef_fiyat = round(efektif_giris * 1.08, 2)
    
    # Portföyü güncelle
    nakit -= (pozisyon_tutari + komisyon)
    portfoy['nakit'] = nakit
    portfoy['toplam_komisyon'] = portfoy.get('toplam_komisyon', 0) + komisyon
    
    yeni_pozisyon = {
        "hisse": hisse_kodu,
        "adet": round(adet, 2),
        "giris_fiyat": round(efektif_giris, 4),
        "hedef_fiyat": hedef_fiyat,
        "stop_fiyat": stop_fiyat,
        "acilis_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sinyal_tipi": sinyal_tipi,
        "dolum_orani": round(dolum_orani, 2),
        "slippage": round(slippage, 4),
    }
    portfoy['acik_pozisyonlar'].append(yeni_pozisyon)
    
    _paper_portfoy_kaydet(portfoy)
    
    _paper_islem_kaydet({
        "tip": "AL",
        "hisse": hisse_kodu,
        "fiyat": round(efektif_giris, 4),
        "ham_fiyat": giris_fiyat,
        "slippage": round(slippage, 4),
        "adet": round(adet, 2),
        "tutar": round(pozisyon_tutari, 2),
        "komisyon": round(komisyon, 2),
        "dolum_orani": round(dolum_orani, 2),
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sinyal": sinyal_tipi
    })
    
    _logger.info(f"📄 PAPER AL: {hisse_kodu} × {adet:.1f} @ {efektif_giris:.4f} (slippage:%{slippage_yuzde*100:.2f}, dolum:%{dolum_orani*100:.0f})")
    
    return {
        'durum': 'basarili',
        'hisse': hisse_kodu,
        'adet': round(adet, 2),
        'giris_fiyat': round(efektif_giris, 4),
        'hedef': hedef_fiyat,
        'stop': stop_fiyat,
        'pozisyon_tutari': round(pozisyon_tutari, 2),
        'kalan_nakit': round(nakit, 2),
        'slippage': round(slippage, 4),
        'dolum_orani': round(dolum_orani, 2),
        'gercekci_mekanik': True,
    }


def _paper_config_yukle() -> dict:
    """Paper trading config parametrelerini yükler."""
    CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")
    varsayilan = {
        "paper_slippage_yuzde": 0.002,
        "paper_kismi_dolum_orani": 0.85,
        "komisyon_orani": 0.002,
        "min_islem_hacmi": 100000,
    }
    try:
        if os.path.exists(CONFIG_YOLU):
            with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
                kayitli = json.load(f)
            return {**varsayilan, **kayitli}
    except:
        pass
    return varsayilan


def paper_pozisyonlari_kontrol_et() -> dict:
    """
    SANAL POZİSYONLARI KONTROL ET
    Açık paper pozisyonların hedef/stop durumunu gerçekçi piyasa
    mekanikleriyle kontrol eder.
    
    Algoritma (İYİLEŞTİRİLMİŞ):
    1. Tüm açık pozisyonları al
    2. Her biri için güncel fiyat çek
    3. Stop-loss veya take-profit tetiklendiyse:
       a. Satışta slippage uygula (fiyat biraz aşağı kayar)
       b. Kısmi dolum kontrolü
       c. Komisyon hesapla
    4. Başarı/başarısız istatistiklerini güncelle
    5. Piyasa rejimine göre ek risk uyarısı
    6. Portföyü kaydet
    
    Dönüş: Kapanan pozisyonların özeti
    """
    config = _paper_config_yukle()
    slippage_yuzde = config.get("paper_slippage_yuzde", 0.002)
    kismi_dolum_orani = config.get("paper_kismi_dolum_orani", 0.85)
    
    portfoy = _paper_portfoy_yukle()
    acik_pozisyonlar = portfoy.get('acik_pozisyonlar', [])
    
    if not acik_pozisyonlar:
        return {'kapanan': 0, 'mesaj': 'Açık pozisyon yok.'}
    
    kapanan = 0
    kalan_pozisyonlar = []
    kapanan_detay = []
    
    for poz in acik_pozisyonlar:
        hisse = poz['hisse']
        giris = poz['giris_fiyat']
        hedef = poz['hedef_fiyat']
        stop = poz['stop_fiyat']
        adet = poz['adet']
        
        try:
            # Güncel fiyatı çek
            tk = yf.Ticker(hisse)
            df = tk.history(period="5d")
            if df.empty:
                kalan_pozisyonlar.append(poz)
                continue
            
            guncel_fiyat = float(df['Close'].iloc[-1])
            max_fiyat = float(df['High'].max())
            min_fiyat = float(df['Low'].min())
            
            kapanis_nedeni = None
            kapanis_fiyat = guncel_fiyat
            
            # Hedef kontrolü
            if max_fiyat >= hedef:
                kapanis_nedeni = "🎯 HEDEF"
                kapanis_fiyat = hedef
            
            # Stop kontrolü
            elif min_fiyat <= stop:
                kapanis_nedeni = "🛑 STOP"
                kapanis_fiyat = stop
            
            # 30 günlük zaman aşımı
            acilis_tarihi = datetime.strptime(poz['acilis_tarihi'], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - acilis_tarihi).days > 30:
                kapanis_nedeni = "⏰ ZAMAN AŞIMI"
                kapanis_fiyat = guncel_fiyat
            
            if kapanis_nedeni:
                # ── GERÇEKÇİ SATIŞ MEKANİKLERİ ──
                # Satışta slippage: fiyat biraz aşağı kayar
                satis_slippage = kapanis_fiyat * slippage_yuzde
                efektif_kapanis = kapanis_fiyat - satis_slippage  # SATIŞTA slippage aşağı
                
                # Kısmi dolum: pozisyonun %85-100'ü kapanır
                dolum_orani = np.random.uniform(kismi_dolum_orani, 1.0)
                efektif_adet = adet * dolum_orani
                
                satis_tutari = efektif_adet * efektif_kapanis
                komisyon = satis_tutari * config.get("komisyon_orani", 0.002)
                net_gelir = satis_tutari - komisyon
                
                # Kapanmayan kısım için kalan pozisyon
                kalan_adet = adet - efektif_adet
                
                kar_zarar = (efektif_kapanis - giris) / giris * 100
                
                portfoy['nakit'] += net_gelir
                portfoy['toplam_komisyon'] = portfoy.get('toplam_komisyon', 0) + komisyon
                portfoy['toplam_islem'] = portfoy.get('toplam_islem', 0) + 1
                
                if kapanis_nedeni == "🎯 HEDEF":
                    portfoy['basarili_islem'] = portfoy.get('basarili_islem', 0) + 1
                else:
                    portfoy['basarisiz_islem'] = portfoy.get('basarisiz_islem', 0) + 1
                
                kapanan += 1
                kapanan_detay.append({
                    "hisse": hisse,
                    "neden": kapanis_nedeni,
                    "giris": giris,
                    "kapanis": round(efektif_kapanis, 4),
                    "kar_zarar_pct": round(kar_zarar, 2),
                    "sure_gun": (datetime.now() - acilis_tarihi).days,
                    "slippage_satis": round(satis_slippage, 4),
                    "dolum_orani": round(dolum_orani, 2),
                })
                
                # Kalan miktar varsa pozisyonu güncelle
                if kalan_adet > 0.01:
                    poz_kopya = dict(poz)
                    poz_kopya['adet'] = round(kalan_adet, 2)
                    kalan_pozisyonlar.append(poz_kopya)
                
                _paper_islem_kaydet({
                    "tip": kapanis_nedeni,
                    "hisse": hisse,
                    "fiyat": round(efektif_kapanis, 4),
                    "ham_fiyat": kapanis_fiyat,
                    "slippage": round(satis_slippage, 4),
                    "adet": round(efektif_adet, 2),
                    "tutar": round(satis_tutari, 2),
                    "kar_zarar_pct": round(kar_zarar, 2),
                    "dolum_orani": round(dolum_orani, 2),
                    "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                
                _logger.info(f"📄 PAPER KAPANIŞ: {hisse} → {kapanis_nedeni} @ {efektif_kapanis:.4f} (%{kar_zarar:.1f}) [slip:%{slippage_yuzde*100:.2f}, dolum:%{dolum_orani*100:.0f}]")
            else:
                kalan_pozisyonlar.append(poz)
                
        except Exception as e:
            _logger.warning(f"Paper kontrol hatası ({hisse}): {e}")
            kalan_pozisyonlar.append(poz)
    
    # Portföyü güncelle
    portfoy['acik_pozisyonlar'] = kalan_pozisyonlar
    
    # Güncel toplam değeri hesapla
    toplam_deger = portfoy['nakit']
    for p in kalan_pozisyonlar:
        try:
            tk = yf.Ticker(p['hisse'])
            df = tk.history(period="2d")
            if not df.empty:
                toplam_deger += p['adet'] * float(df['Close'].iloc[-1])
        except:
            toplam_deger += p['adet'] * p['giris_fiyat']
    
    portfoy['sermaye_guncel'] = round(toplam_deger, 2)
    portfoy['gecmis_bakiye'].append(round(toplam_deger, 2))
    
    _paper_portfoy_kaydet(portfoy)
    
    return {
        'kapanan': kapanan,
        'kapanan_detay': kapanan_detay,
        'acik_kalan': len(kalan_pozisyonlar),
        'toplam_deger': round(toplam_deger, 2),
        'nakit': round(portfoy['nakit'], 2),
        'toplam_getiri_pct': round((toplam_deger / portfoy['sermaye_baslangic'] - 1) * 100, 2),
    }


def paper_rapor_olustur() -> str:
    """
    SANAL PORTFÖY PERFORMANS RAPORU
    
    Algoritma:
    1. Portföyü yükle
    2. Güncel değeri hesapla
    3. Getiri, Win Rate, Sharpe, Max DD hesapla
    4. Önceki işlemleri analiz et
    5. Tavsiye üret
    """
    portfoy = _paper_portfoy_yukle()
    
    # Önce pozisyonları kontrol et
    kontrol = paper_pozisyonlari_kontrol_et()
    portfoy = _paper_portfoy_yukle()  # Güncel halini al
    
    baslangic = portfoy['sermaye_baslangic']
    guncel = portfoy['sermaye_guncel']
    nakit = portfoy['nakit']
    acik_poz = len(portfoy['acik_pozisyonlar'])
    toplam_islem = portfoy.get('toplam_islem', 0)
    basarili = portfoy.get('basarili_islem', 0)
    basarisiz = portfoy.get('basarisiz_islem', 0)
    toplam_komisyon = portfoy.get('toplam_komisyon', 0)
    
    net_getiri = round((guncel - baslangic) / baslangic * 100, 2)
    win_rate = round(basarili / max(toplam_islem, 1) * 100, 1)
    
    # Basit Sharpe
    bakiye_serisi = portfoy.get('gecmis_bakiye', [baslangic])
    if len(bakiye_serisi) > 5:
        gunluk_getiriler = [(bakiye_serisi[i] - bakiye_serisi[i-1]) / bakiye_serisi[i-1] 
                           for i in range(1, len(bakiye_serisi))]
        ortalama = np.mean(gunluk_getiriler) if gunluk_getiriler else 0
        std = np.std(gunluk_getiriler, ddof=1) if len(gunluk_getiriler) > 1 else 1
        sharpe = round((ortalama / std) * np.sqrt(252), 2) if std > 0 else 0
    else:
        sharpe = 0
    
    # Max Drawdown
    seri = pd.Series(bakiye_serisi)
    cummax = seri.cummax()
    drawdown = (seri - cummax) / cummax * 100
    max_dd = round(abs(float(drawdown.min())), 2) if not drawdown.empty else 0
    
    gun_sayisi = (datetime.now() - datetime.strptime(portfoy['baslangic_tarihi'], "%Y-%m-%d %H:%M:%S")).days
    
    satirlar = []
    satirlar.append("╔══════════════════════════════════════════════════╗")
    satirlar.append("║        📄 PAPER TRADING PERFORMANS RAPORU        ║")
    satirlar.append("╚══════════════════════════════════════════════════╝")
    satirlar.append(f"  Başlangıç Sermaye : ₺{baslangic:,.0f}")
    satirlar.append(f"  Güncel Değer      : ₺{guncel:,.0f}")
    satirlar.append(f"  Net Getiri        : %{net_getiri} ({gun_sayisi} gün)")
    satirlar.append(f"  Nakit              : ₺{nakit:,.0f}")
    satirlar.append(f"  Açık Pozisyon      : {acik_poz} adet")
    satirlar.append("  ───────────────────────────────────────────────")
    satirlar.append(f"  Toplam İşlem       : {toplam_islem}")
    satirlar.append(f"  ✅ Başarılı        : {basarili}")
    satirlar.append(f"  ❌ Başarısız       : {basarisiz}")
    satirlar.append(f"  Win Rate           : %{win_rate}")
    satirlar.append(f"  Toplam Komisyon    : ₺{toplam_komisyon:,.2f}")
    satirlar.append("  ───────────────────────────────────────────────")
    satirlar.append(f"  Sharpe Oranı       : {sharpe}")
    satirlar.append(f"  Max Drawdown       : %{max_dd}")
    satirlar.append("  ───────────────────────────────────────────────")
    
    if toplam_islem >= 10:
        if win_rate >= 55 and net_getiri > 0:
            satirlar.append("  🟢 TAVSİYE: Strateji GERÇEK paraya hazır!")
            satirlar.append(f"     Paper'da %{net_getiri} getiri, %{win_rate} win rate.")
        elif win_rate >= 45:
            satirlar.append("  🟡 TAVSİYE: Küçük miktarla gerçek işleme başlanabilir.")
        else:
            satirlar.append("  🔴 TAVSİYE: Strateji henüz hazır değil. İyileştirme yapın.")
    else:
        satirlar.append(f"  ⚪ TAVSİYE: Henüz {toplam_islem}/10 işlem. En az 10 işlem sonrası değerlendirme yapılır.")
    
    return "\n".join(satirlar)


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(paper_rapor_olustur())