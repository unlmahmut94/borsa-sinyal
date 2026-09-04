# ══════════════════════════════════════════════════════════════════════
#  mod_korelasyon.py — Korelasyon Matrisi & Sektörel Risk Analizi (Tavsiye #5)
# ══════════════════════════════════════════════════════════════════════
#
#  ALGORİTMA:
#  ┌───────────────────────────────────────────────────────────────────┐
#  │ TEMEL PRENSİP: Portföydeki hisselerin birbiriyle korelasyonunu   │
#  │ hesaplayarak aynı sektöre aşırı yoğunlaşmayı engellemek.         │
#  │                                                                    │
#  │ ADIM 1: Belirtilen hisse listesi için son 60 günlük getiri        │
#  │         serilerini yfinance'den çek                               │
#  │ ADIM 2: Pearson korelasyon matrisini hesapla                      │
#  │         corr[i][j] = cov(ri, rj) / (σi * σj)                     │
#  │ ADIM 3: Yüksek korelasyonlu (≥ 0.70) hisse çiftlerini tespit et  │
#  │ ADIM 4: Sektörel gruplandırma yap (sektör bilgisi varsa)         │
#  │ ADIM 5: Portföy önerisi:                                          │
#  │         - Aynı sektör max %25 ağırlık                             │
#  │         - Korelasyonu 0.85+ olan çiftlerden sadece 1 tanesini al │
#  │ ADIM 6: Diversifikasyon skoru hesapla (0-100)                    │
#  │ ADIM 7: Risk uyarıları üret                                       │
#  └───────────────────────────────────────────────────────────────────┘
#
#  KULLANIM:
#    from mod_korelasyon import korelasyon_raporu, portfoy_diversifikasyon
#    rapor = korelasyon_raporu(["THYAO.IS", "GARAN.IS", "ASELS.IS"])
#    print(rapor['diversifikasyon_skoru'])
#

import numpy as np
import pandas as pd
import yfinance as yf
import json
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict

_logger = logging.getLogger("Korelasyon")

CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")

# ── Sektör eşleştirme (BIST hisseleri için) ──
SEKTOR_TANIMLARI = {
    "GARAN": "Bankacılık", "AKBNK": "Bankacılık", "YKBNK": "Bankacılık",
    "ISCTR": "Bankacılık", "VAKBN": "Bankacılık", "HALKB": "Bankacılık",
    "THYAO": "Ulaştırma", "PGSUS": "Ulaştırma", "TCELL": "İletişim",
    "TTKOM": "İletişim", "ASELS": "Savunma", "OTKAR": "Savunma",
    "TUPRS": "Enerji", "EREGL": "Metal", "KRDMD": "Metal",
    "SISE": "Cam/Seramik", "ARCLK": "Beyaz Eşya", "VESTL": "Beyaz Eşya",
    "BIMAS": "Perakende", "MGROS": "Perakende", "SOKM": "Perakende",
    "SAHOL": "Holding", "KCHOL": "Holding", "SISE": "Holding",
    "TOASO": "Otomotiv", "FROTO": "Otomotiv", "DOAS": "Otomotiv",
    "PETKM": "Kimya", "SODA": "Kimya",
    "EKGYO": "GYO", "ISGYO": "GYO",
    "KOZAL": "Madencilik", "KOZAA": "Madencilik",
    "BTC-USD": "Kripto", "ETH-USD": "Kripto", "BNB-USD": "Kripto",
    "AAPL": "Teknoloji", "MSFT": "Teknoloji", "GOOGL": "Teknoloji",
    "AMZN": "E-ticaret", "META": "Sosyal Medya",
    "TSLA": "Otomotiv-EV", "NVDA": "Yarı İletken", "AMD": "Yarı İletken",
}


def _strateji_ayarlari() -> dict:
    try:
        if os.path.exists(CONFIG_YOLU):
            with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}


def sektor_bul(sembol: str) -> str:
    """Bir sembolün sektörünü bulur."""
    temiz = sembol.upper().replace(".IS", "").replace(".US", "")
    return SEKTOR_TANIMLARI.get(temiz, "Diğer")


def korelasyon_matrisi_hesapla(semboller: list, gun: int = 60) -> tuple:
    """
    Hisse listesi için korelasyon matrisini hesaplar.
    
    Algoritma:
    1. Her hisse için son N günlük kapanış verisini çek
    2. Günlük getiri serilerini hesapla: r[i] = (close[i] - close[i-1]) / close[i-1]
    3. Pearson korelasyon matrisini hesapla: corr = cov(returns) / (σ_i * σ_j)
    4. NaN değerleri 0 ile doldur (veri eksik hisseler için)
    
    Parametreler:
        semboller: Hisse listesi
        gun: Veri çekme periyodu (gün)
    
    Dönüş: (korelasyon_df, getiri_df, hata_semboller)
    """
    if len(semboller) < 2:
        return pd.DataFrame(), pd.DataFrame(), []
    getiri_dict = {}
    hata_semboller = []
    
    try:
        # Hisseleri tek tek değil, tek seferde toplu indirerek hızı 10x artırıyoruz
        df = yf.download(semboller, period=f"{gun}d", group_by="ticker", progress=False)
        
        for sembol in semboller:
            try:
                # MultiIndex kontrolü
                if isinstance(df.columns, pd.MultiIndex):
                    if sembol in df.columns.get_level_values(0):
                        close = df[sembol]['Close'].dropna()
                    else:
                        hata_semboller.append(sembol)
                        continue
                else:
                    close = df['Close'].dropna()

                if len(close) > 10:
                    getiri_dict[sembol] = close.pct_change().dropna()
                else:
                    hata_semboller.append(sembol)
            except Exception:
                hata_semboller.append(sembol)
                
    except Exception as e:
        _logger.warning(f"Korelasyon toplu veri hatası: {e}")
        return pd.DataFrame(), pd.DataFrame(), semboller    
    if len(getiri_dict) < 2:
        return pd.DataFrame(), pd.DataFrame(), hata_semboller
    
    # Getiri DataFrame'i
    getiri_df = pd.DataFrame(getiri_dict)
    
    # Korelasyon matrisi
    korelasyon_df = getiri_df.corr(method='pearson')
    
    return korelasyon_df, getiri_df, hata_semboller


def yuksek_korelasyonlu_ciftleri_bul(korelasyon_df: pd.DataFrame, esik: float = None) -> list:
    """
    Korelasyon matrisinden eşik üstü hisse çiftlerini tespit eder.
    
    Algoritma:
    1. Matrisin üst üçgenini tara (simetriyi önlemek için)
    2. corr[i][j] ≥ eşik olan çiftleri listeye ekle
    3. Aynı sektör kontrolü yap
    4. Korelasyon değerine göre sırala
    
    Parametreler:
        korelasyon_df: Pearson korelasyon DataFrame'i
        esik: Korelasyon eşiği (None = config'ten)
    
    Dönüş: [{'hisse1': ..., 'hisse2': ..., 'korelasyon': ..., 'ayni_sektor': bool}, ...]
    """
    ayarlar = _strateji_ayarlari()
    if esik is None:
        esik = ayarlar.get("korelasyon_esik", 0.70)
    
    if korelasyon_df.empty:
        return []
    
    ciftler = []
    semboller = list(korelasyon_df.columns)
    
    for i in range(len(semboller)):
        for j in range(i + 1, len(semboller)):
            corr_val = korelasyon_df.iloc[i, j]
            
            if pd.isna(corr_val):
                continue
            
            if abs(corr_val) >= esik:
                hisse1, hisse2 = semboller[i], semboller[j]
                sektor1 = sektor_bul(hisse1)
                sektor2 = sektor_bul(hisse2)
                
                ciftler.append({
                    'hisse1': hisse1,
                    'hisse2': hisse2,
                    'korelasyon': round(corr_val, 4),
                    'ayni_sektor': sektor1 == sektor2,
                    'sektor1': sektor1,
                    'sektor2': sektor2,
                    'uyari': '⚠️ AYNI SEKTÖR!' if sektor1 == sektor2 else ''
                })
    
    return sorted(ciftler, key=lambda x: -abs(x['korelasyon']))


def sektorel_agirlik_analizi(semboller: list) -> dict:
    """
    Portföydeki sektörel dağılımı analiz eder.
    
    Algoritma:
    1. Her hisse için sektör bilgisini bul
    2. Her sektörün portföydeki ağırlığını hesapla
    3. Config'teki max_sektor_agirlik eşiğini kontrol et
    4. Aşırı yoğunlaşma uyarısı üret
    
    Dönüş: {
        'sektor_dagilimi': dict,
        'asiri_yogunlasma': list,
        'tavsiyeler': list
    }
    """
    ayarlar = _strateji_ayarlari()
    max_agirlik = ayarlar.get("korelasyon_max_sektor_agirlik", 0.25)
    
    sektor_sayaci = defaultdict(int)
    
    for sembol in semboller:
        sektor = sektor_bul(sembol)
        sektor_sayaci[sektor] += 1
    
    toplam = len(semboller)
    sektor_dagilimi = {}
    asiri_yogunlasma = []
    
    for sektor, sayi in sorted(sektor_sayaci.items(), key=lambda x: -x[1]):
        agirlik = sayi / toplam if toplam > 0 else 0
        sektor_dagilimi[sektor] = round(agirlik, 3)
        
        if agirlik > max_agirlik:
            asiri_yogunlasma.append({
                'sektor': sektor,
                'agirlik': round(agirlik, 3),
                'hisse_sayisi': sayi,
                'limit': max_agirlik
            })
    
    tavsiyeler = []
    if asiri_yogunlasma:
        for a in asiri_yogunlasma:
            kaldirilmasi_gereken = int(a['hisse_sayisi'] - max_agirlik * toplam) + 1
            tavsiyeler.append(
                f"⚠️ {a['sektor']} sektörü %{a['agirlik']*100:.0f} ağırlıkta "
                f"(limit: %{max_agirlik*100:.0f}). {kaldirilmasi_gereken} hisse azaltılmalı."
            )
    
    return {
        'sektor_dagilimi': sektor_dagilimi,
        'asiri_yogunlasma': asiri_yogunlasma,
        'tavsiyeler': tavsiyeler
    }


def portfoy_diversifikasyon_skoru(semboller: list) -> float:
    """
    Portföyün diversifikasyon kalitesini 0-100 arası skorlar.
    
    Algoritma:
    1. Korelasyon matrisini hesapla
    2. Ortalama çapraz korelasyonu bul (diyagonal hariç)
    3. Sektörel yoğunlaşma cezası uygula
    4. Skor = (1 - ortalama_korelasyon) * 100 * sektor_cezasi
    5. 0 = tamamen aynı yönde, 100 = mükemmel çeşitlendirilmiş
    
    Dönüş: 0-100 arası skor
    """
    if len(semboller) < 2:
        return 50.0
    
    korelasyon_df, _, _ = korelasyon_matrisi_hesapla(semboller)
    
    if korelasyon_df.empty:
        return 0.0
    
    # Ortalama çapraz korelasyon
    n = len(korelasyon_df)
    toplam_corr = 0
    sayac = 0
    
    for i in range(n):
        for j in range(i + 1, n):
            val = korelasyon_df.iloc[i, j]
            if not pd.isna(val):
                toplam_corr += abs(val)
                sayac += 1
    
    if sayac == 0:
        return 50.0
    
    ortalama_corr = toplam_corr / sayac
    
    # Sektörel ceza
    sektor_analiz = sektorel_agirlik_analizi(semboller)
    asiri_sayisi = len(sektor_analiz['asiri_yogunlasma'])
    sektor_cezasi = max(0.3, 1.0 - asiri_sayisi * 0.15)
    
    # Diversifikasyon skoru
    skor = (1 - ortalama_corr) * 100 * sektor_cezasi
    return round(max(0, min(100, skor)), 1)


def korelasyon_raporu(semboller: list) -> dict:
    """
    Kapsamlı korelasyon ve diversifikasyon raporu üretir.
    
    Algoritma Adımları:
    1. Korelasyon matrisini hesapla
    2. Yüksek korelasyonlu çiftleri bul
    3. En iyi/worst hisse çiftlerini listele
    4. Sektörel dağılım analizi yap
    5. Diversifikasyon skorunu hesapla
    6. Optimizasyon tavsiyeleri üret
    
    Parametreler:
        semboller: Analiz edilecek hisse listesi
    
    Dönüş: {
        'semboller': list,
        'korelasyon_df': DataFrame (ops.),
        'yuksek_korelasyonlu': list,
        'sektor_analizi': dict,
        'diversifikasyon_skoru': float,
        'tavsiyeler': list
    }
    """
    ayarlar = _strateji_ayarlari()
    esik = ayarlar.get("korelasyon_esik", 0.70)
    
    korelasyon_df, _, hata = korelasyon_matrisi_hesapla(semboller)
    yuksek_ciftler = yuksek_korelasyonlu_ciftleri_bul(korelasyon_df, esik)
    sektor_analiz = sektorel_agirlik_analizi(semboller)
    div_skor = portfoy_diversifikasyon_skoru(semboller)
    
    tavsiyeler = []
    
    # Korelasyon bazlı tavsiyeler
    if yuksek_ciftler:
        # En yüksek korelasyonlu çift
        en_yuksek = yuksek_ciftler[0]
        tavsiyeler.append(
            f"🔴 En yüksek korelasyon: {en_yuksek['hisse1']} ↔ {en_yuksek['hisse2']} "
            f"(%{en_yuksek['korelasyon']*100:.1f}) — sadece 1 tanesini seçin."
        )
    
    # Aynı sektör uyarıları
    ayni_sektor_ciftler = [c for c in yuksek_ciftler if c['ayni_sektor']]
    if ayni_sektor_ciftler:
        tavsiyeler.append(f"⚠️ {len(ayni_sektor_ciftler)} çift aynı sektörde yüksek korelasyonlu.")
    
    # Diversifikasyon değerlendirmesi
    if div_skor >= 75:
        tavsiyeler.append(f"✅ İyi diversifikasyon (skor: {div_skor}/100)")
    elif div_skor >= 50:
        tavsiyeler.append(f"🟡 Orta diversifikasyon (skor: {div_skor}/100) — iyileştirilebilir.")
    else:
        tavsiyeler.append(f"🔴 Zayıf diversifikasyon (skor: {div_skor}/100) — acilen çeşitlendirilmeli!")
    
    # Sektörel tavsiyeleri ekle
    tavsiyeler.extend(sektor_analiz.get('tavsiyeler', []))
    
    # Hata veren semboller
    if hata:
        tavsiyeler.append(f"⚠️ Veri çekilemeyen semboller: {', '.join(hata[:5])}")
    
    return {
        'semboller': semboller,
        'yuksek_korelasyonlu': yuksek_ciftler,
        'sektor_analizi': sektor_analiz,
        'diversifikasyon_skoru': div_skor,
        'tavsiyeler': tavsiyeler
    }


def portfoy_optimize_et(semboller: list) -> list:
    """
    Yüksek korelasyonlu hisseleri filtreleyerek optimize portföy önerir.
    
    Algoritma:
    1. Korelasyon matrisini hesapla
    2. En yüksek korelasyonlu çiftleri bul
    3. Her çiftten birini ele:
       - Aynı sektörse → daha düşük hacimli olanı çıkar
       - Farklı sektörse → daha yüksek korelasyon göstereni çıkar
    4. Kalan sembolleri döndür
    
    Dönüş: Optimize edilmiş sembol listesi
    """
    if len(semboller) < 3:
        return semboller
    
    ciftler = yuksek_korelasyonlu_ciftleri_bul(
        korelasyon_matrisi_hesapla(semboller)[0]
    )
    
    kara_liste = set()
    
    for cift in ciftler:
        h1, h2 = cift['hisse1'], cift['hisse2']
        
        if h1 in kara_liste or h2 in kara_liste:
            continue
        
        if cift['ayni_sektor']:
            # Aynı sektör → ikinciyi kara listeye al
            kara_liste.add(h2)
        elif abs(cift['korelasyon']) > 0.85:
            # Çok yüksek korelasyon → ikinciyi de kara listeye al
            kara_liste.add(h2)
    
    optimize = [s for s in semboller if s not in kara_liste]
    
    if len(optimize) < 2:
        # En az 2 hisse kalmalı
        return semboller[:2]
    
    return optimize


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  KORELASYON & DİVERSİFİKASYON ANALİZ TESTİ")
    print("=" * 60)
    
    test_semboller = ["GARAN.IS", "AKBNK.IS", "THYAO.IS", "ASELS.IS", "EREGL.IS"]
    
    print(f"\nTest Portföyü: {', '.join(test_semboller)}")
    
    rapor = korelasyon_raporu(test_semboller)
    
    print(f"\n📊 SONUÇLAR:")
    print(f"  Diversifikasyon Skoru: {rapor['diversifikasyon_skoru']}/100")
    
    print(f"\n📈 SEKTÖR DAĞILIMI:")
    for sektor, agirlik in rapor['sektor_analizi']['sektor_dagilimi'].items():
        bar = '█' * int(agirlik * 50)
        print(f"  {sektor:<15s} {bar} %{agirlik*100:.0f}")
    
    if rapor['yuksek_korelasyonlu']:
        print(f"\n⚠️ YÜKSEK KORELASYONLU ÇİFTLER:")
        for c in rapor['yuksek_korelasyonlu'][:5]:
            print(f"  {c['hisse1']} ↔ {c['hisse2']}: %{c['korelasyon']*100:.1f} {c['uyari']}")
    
    if rapor['tavsiyeler']:
        print(f"\n📋 TAVSİYELER:")
        for t in rapor['tavsiyeler']:
            print(f"  • {t}")
    
    # Optimizasyon testi
    optimize = portfoy_optimize_et(test_semboller)
    print(f"\n✅ OPTİMİZE PORTFÖY: {', '.join(optimize)}")