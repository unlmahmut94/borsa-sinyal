# ══════════════════════════════════════════════════════════════════════
#  mod_yapay_zeka_karar.py — Strateji Analiz ve Otomatik Güncelleme
#  YZ Karnesi sekmesinin karar destek motoru.
# ══════════════════════════════════════════════════════════════════════

import sqlite3
import os
import json
import logging
from datetime import datetime
import pandas as pd
import numpy as np

_logger = logging.getLogger("YZ_Karar")
_logger.setLevel(logging.DEBUG)
if not _logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(h)

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")
STRATEJI_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")

VARSAYILAN_PARAMETRELER = {
    "atr_stop_carpani": 1.5,
    "stop_loss_min_yuzde": 2.0,
    "stop_loss_max_yuzde_bist": 5.0,
    "stop_loss_max_yuzde_diger": 6.5,
    "take_profit_yuzde": 0.08,
    "rsi_al_esigi": 30,
    "min_win_rate_hedef": 45,
    "max_risk_per_trade": 0.05,
    "kelly_fraksiyon": 0.5
}

# Geriye dönük uyumluluk: Config'te eski stop_loss_yuzde varsa ATR çarpanına dönüştür
def _stop_to_atr_carpan(stop_yuzde):
    if stop_yuzde <= 0.02: return 1.0
    if stop_yuzde <= 0.03: return 1.5
    if stop_yuzde <= 0.04: return 2.0
    return 2.5


def _parametreleri_yukle() -> dict:
    """Konfigürasyon dosyasından strateji parametrelerini yükler."""
    try:
        if os.path.exists(STRATEJI_YOLU):
            with open(STRATEJI_YOLU, "r", encoding="utf-8") as f:
                kayitli = json.load(f)
            # Geriye dönük uyumluluk: Eski stop_loss_yuzde varsa ATR çarpanına dönüştür
            if "stop_loss_yuzde" in kayitli and "atr_stop_carpani" not in kayitli:
                kayitli["atr_stop_carpani"] = _stop_to_atr_carpan(kayitli.pop("stop_loss_yuzde"))
                _logger.info(f"Eski stop_loss_yuzde → ATR çarpanı {kayitli['atr_stop_carpani']}'a dönüştürüldü")
            # Eksik anahtarları varsayılanlarla tamamla
            for k, v in VARSAYILAN_PARAMETRELER.items():
                if k not in kayitli:
                    kayitli[k] = v
            return kayitli
    except (json.JSONDecodeError, IOError) as e:
        _logger.warning(f"Konfigürasyon okunamadı: {e}")
    return dict(VARSAYILAN_PARAMETRELER)


def _parametreleri_kaydet(params: dict) -> bool:
    """Strateji parametrelerini dosyaya yazar."""
    try:
        with open(STRATEJI_YOLU, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        _logger.error(f"Konfigürasyon yazılamadı: {e}")
        return False


def _sinyal_istatistikleri_hesapla() -> dict:
    """
    Veritabanındaki geçmiş sinyallerden performans istatistiklerini çıkarır.

    Dönüş: {
        'toplam_islem': int,
        'basarili': int,
        'basarisiz': int,
        'bekleyen': int,
        'zaman_asimi': int,
        'win_rate': float,
        'stop_rate': float,
        'ortalama_hedef_yuzde': float,
        'ortalama_stop_yuzde': float,
        'ortalama_kar': float,
        'ortalama_zarar': float,
        'bekleyen_hisseler': list
    }
    """
    try:
        conn = sqlite3.connect(DB_YOLU)
        df = pd.read_sql_query("SELECT * FROM ai_sinyaller", conn)
        conn.close()
    except Exception as e:
        _logger.warning(f"Veritabanı okunamadı: {e}")
        return {'toplam_islem': 0, 'win_rate': 0.0}

    if df.empty:
        return {'toplam_islem': 0, 'win_rate': 0.0}

    basarili = int(len(df[df['durum'].str.contains('BAŞARILI', na=False)]))
    basarisiz = int(len(df[df['durum'].str.contains('BAŞARISIZ', na=False)]))
    bekleyen = int(len(df[df['durum'] == 'BEKLIYOR'])) if 'BEKLIYOR' in df['durum'].values else 0
    zaman_asimi = int(len(df[df['durum'].str.contains('ZAMAN AŞIMI', na=False)]))
    kapanan = basarili + basarisiz + zaman_asimi

    win_rate = round((basarili / kapanan * 100), 1) if kapanan > 0 else 0.0
    stop_rate = round((basarisiz / kapanan * 100), 1) if kapanan > 0 else 0.0

    # Ortalama hedef/stop yüzdelerini hesapla
    df_hesapli = df[df['giris_fiyati'].notna() & (df['giris_fiyati'] > 0)].copy()
    if not df_hesapli.empty:
        df_hesapli['hedef_yuzde'] = ((df_hesapli['hedef_fiyat'] - df_hesapli['giris_fiyati']) 
                                       / df_hesapli['giris_fiyati']) * 100
        df_hesapli['stop_yuzde'] = ((df_hesapli['giris_fiyati'] - df_hesapli['stop_fiyat'])
                                     / df_hesapli['giris_fiyati']) * 100
        ortalama_hedef = round(float(df_hesapli['hedef_yuzde'].mean()), 2)
        ortalama_stop = round(float(df_hesapli['stop_yuzde'].mean()), 2)
    else:
        ortalama_hedef = 8.0
        ortalama_stop = 3.0

    # Bekleyen hisse listesi
    bekleyen_hisseler = df[df['durum'] == 'BEKLIYOR']['hisse'].tolist() if 'BEKLIYOR' in df['durum'].values else []

    return {
        'toplam_islem': int(len(df)),
        'basarili': basarili,
        'basarisiz': basarisiz,
        'bekleyen': bekleyen,
        'zaman_asimi': zaman_asimi,
        'kapanan': kapanan,
        'win_rate': win_rate,
        'stop_rate': stop_rate,
        'ortalama_hedef_yuzde': ortalama_hedef,
        'ortalama_stop_yuzde': ortalama_stop,
        'bekleyen_hisseler': bekleyen_hisseler
    }


def strateji_analiz_et() -> str:
    """
    Geçmiş işlem verilerine dayanarak strateji parametreleri için öneri üretir.
    YZ Karnesi sekmesi tarafından çağrılır.

    Dönüş: Analiz metni (içinde "UYARI" geçiyorsa parametre değişikliği önerilir)
    """
    stats = _sinyal_istatistikleri_hesapla()
    params = _parametreleri_yukle()

    if stats.get('toplam_islem', 0) == 0:
        return "Henüz yeterli işlem verisi yok. En az 5 kapanmış işlem sonrası analiz yapılabilir."

    kapanan = stats.get('kapanan', 0)

    if kapanan < 5:
        return (f"⚡ Yeterli veri birikiyor... ({kapanan}/5 kapanmış işlem). "
                "Şu anki parametreler korunuyor.")

    win_rate = stats.get('win_rate', 0)
    stop_rate = stats.get('stop_rate', 0)
    mevcut_atr = params.get('atr_stop_carpani', 1.5)
    mevcut_tp = params.get('take_profit_yuzde', 0.08)
    mevcut_rsi = params.get('rsi_al_esigi', 30)

    # ── Analiz mantığı ──
    oneriler = []

    # 1. Win rate analizi
    if win_rate < 35:
        oneriler.append(f"Win Rate %{win_rate:.1f} → **KRİTİK DÜŞÜK**. ATR çarpanı daraltılmalı, RSI eşiği düşürülmeli.")
    elif win_rate < 45:
        oneriler.append(f"Win Rate %{win_rate:.1f} → **DÜŞÜK**. Parametre optimizasyonu önerilir.")
    elif win_rate < 55:
        oneriler.append(f"Win Rate %{win_rate:.1f} → **ORTA**. Küçük iyileştirmeler yapılabilir.")
    else:
        oneriler.append(f"Win Rate %{win_rate:.1f} → **İYİ**. Mevcut strateji sağlıklı.")

    # 2. ATR Stop-Loss analizi
    if stop_rate > 55 and win_rate < 45:
        yeni_atr = round(max(1.0, mevcut_atr - 0.2), 1)
        oneriler.append(f"Stop oranı %{stop_rate:.1f} → ATR Çarpanı {mevcut_atr}'ten {yeni_atr}'e düşürülmeli (daha dar stop).")
    elif stop_rate < 30 and win_rate > 55:
        yeni_atr = round(min(2.5, mevcut_atr + 0.2), 1)
        oneriler.append(f"Düşük stop oranı %{stop_rate:.1f} → ATR Çarpanı {mevcut_atr}'ten {yeni_atr}'e yükseltilebilir (daha çok fırsat).")

    # 3. Take-profit analizi
    if win_rate > 55 and mevcut_tp < 0.12:
        yeni_tp = round(min(0.15, mevcut_tp + 0.02), 3)
        oneriler.append(f"Yüksek başarı → Take-profit %{mevcut_tp*100:.1f}'ten %{yeni_tp*100:.1f}'e yükseltilebilir.")
    elif win_rate < 40 and mevcut_tp > 0.05:
        yeni_tp = round(max(0.03, mevcut_tp - 0.02), 3)
        oneriler.append(f"Düşük başarı → Take-profit %{mevcut_tp*100:.1f}'ten %{yeni_tp*100:.1f}'e düşürülmeli.")

    # 4. RSI eşiği analizi
    if win_rate < 40 and mevcut_rsi > 25:
        yeni_rsi = max(20, mevcut_rsi - 5)
        oneriler.append(f"RSI al eşiği {mevcut_rsi}'ten {yeni_rsi}'e düşürülmeli (daha derin dipleri yakalamak için).")
    elif win_rate > 60 and mevcut_rsi < 40:
        yeni_rsi = min(45, mevcut_rsi + 5)
        oneriler.append(f"RSI al eşiği {mevcut_rsi}'ten {yeni_rsi}'e yükseltilebilir (kaliteli sinyaller için).")

    # Özet metin oluştur
    ozet = (f"📊 **{stats['toplam_islem']}** toplam işlem | "
            f"✅ **{stats['basarili']}** başarılı | "
            f"❌ **{stats['basarisiz']}** stop | "
            f"⏳ **{stats['bekleyen']}** bekleyen\n\n")

    if oneriler:
        ozet += "\n\n".join(oneriler)
        if any(kw in " ".join(oneriler) for kw in ["KRİTİK", "DÜŞÜK", "düşürülmeli", "UYARI"]):
            ozet = "⚠️ UYARI: " + ozet
    else:
        ozet += "✅ Mevcut strateji parametreleri optimum seviyede. Değişiklik önerilmiyor."

    return ozet


def strateji_guncelle(risk_ayari: float = 0.05) -> str:
    """
    Geçmiş performansa göre strateji parametrelerini otomatik günceller.
    YZ Karnesi'ndeki "Parametreleri Güncelle" butonu tarafından çağrılır.

    Parametreler:
        risk_ayari: Risk tolerans seviyesi (0.01 = çok düşük risk, 0.10 = yüksek risk)

    Dönüş: Güncelleme sonuç mesajı
    """
    stats = _sinyal_istatistikleri_hesapla()
    params = _parametreleri_yukle()

    if stats.get('kapanan', 0) < 5:
        return "⏳ Henüz yeterli veri yok (en az 5 kapanmış işlem gerekli). Parametreler korundu."

    win_rate = stats.get('win_rate', 0)
    stop_rate = stats.get('stop_rate', 0)

    degisiklikler = []
    yeni_params = dict(params)

    # ── Otomatik optimizasyon ──
    risk_ayari = max(0.01, min(0.10, risk_ayari))

    # 🔥 ATR tabanlı Stop-Loss ayarı (dinamik, hisse bazlı)
    mevcut_atr = params.get('atr_stop_carpani', 1.5)
    if win_rate < 40:
        yeni_atr = round(max(1.0, mevcut_atr - 0.2 * (risk_ayari * 10)), 1)
        if yeni_atr != mevcut_atr:
            yeni_params['atr_stop_carpani'] = yeni_atr
            degisiklikler.append(f"ATR Stop Çarpanı: {mevcut_atr} → {yeni_atr}")
    elif win_rate > 60:
        yeni_atr = round(min(2.5, mevcut_atr + 0.1 * (risk_ayari * 10)), 1)
        if yeni_atr != mevcut_atr:
            yeni_params['atr_stop_carpani'] = yeni_atr
            degisiklikler.append(f"ATR Stop Çarpanı: {mevcut_atr} → {yeni_atr}")

    # Take-profit ayarı
    if win_rate > 50 and stop_rate < 45:
        yeni_tp = round(min(0.15, params['take_profit_yuzde'] + 0.015 * (risk_ayari * 10)), 3)
        if yeni_tp != params['take_profit_yuzde']:
            yeni_params['take_profit_yuzde'] = yeni_tp
            degisiklikler.append(f"Take-Profit: %{params['take_profit_yuzde']*100:.1f} → %{yeni_tp*100:.1f}")
    elif win_rate < 40:
        yeni_tp = round(max(0.04, params['take_profit_yuzde'] - 0.015), 3)
        if yeni_tp != params['take_profit_yuzde']:
            yeni_params['take_profit_yuzde'] = yeni_tp
            degisiklikler.append(f"Take-Profit: %{params['take_profit_yuzde']*100:.1f} → %{yeni_tp*100:.1f}")

    # RSI eşiği ayarı
    if win_rate < 40 and params['rsi_al_esigi'] > 22:
        yeni_rsi = max(20, params['rsi_al_esigi'] - 5)
        if yeni_rsi != params['rsi_al_esigi']:
            yeni_params['rsi_al_esigi'] = yeni_rsi
            degisiklikler.append(f"RSI Eşiği: {params['rsi_al_esigi']} → {yeni_rsi}")
    elif win_rate > 60 and params['rsi_al_esigi'] < 40:
        yeni_rsi = min(45, params['rsi_al_esigi'] + 5)
        if yeni_rsi != params['rsi_al_esigi']:
            yeni_params['rsi_al_esigi'] = yeni_rsi
            degisiklikler.append(f"RSI Eşiği: {params['rsi_al_esigi']} → {yeni_rsi}")

    # Risk yönetimi iyileştirmeleri
    yeni_params['min_win_rate_hedef'] = max(35, min(55, int(win_rate - 5)))
    yeni_params['max_risk_per_trade'] = round(0.02 + risk_ayari * 0.8, 3)
    yeni_params['kelly_fraksiyon'] = round(0.3 + risk_ayari * 5, 2)

    if degisiklikler:
        basarili = _parametreleri_kaydet(yeni_params)
        if basarili:
            degisim_ozeti = "\n".join(f"  • {d}" for d in degisiklikler)
            return (f"✅ **Strateji parametreleri güncellendi!**\n\n"
                    f"📊 Mevcut Win Rate: %{win_rate:.1f}\n\n"
                    f"**Değişiklikler:**\n{degisim_ozeti}\n\n"
                    f"Bir sonraki taramada yeni parametreler kullanılacak.")
        else:
            return "❌ Parametreler kaydedilemedi. Dosya izinlerini kontrol edin."
    else:
        return (f"✅ **Parametreler zaten optimum seviyede.**\n\n"
                f"📊 Win Rate: %{win_rate:.1f} | Stop Rate: %{stop_rate:.1f}\n"
                f"Herhangi bir değişiklik gerekmiyor.")


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  YZ STRATEJİ KARAR MOTORU TEST")
    print("=" * 60)

    print("\n📊 Strateji Analizi:")
    print("-" * 40)
    analiz = strateji_analiz_et()
    print(analiz)

    print("\n" + "=" * 60)
    print("  Parametre Güncelleme Testi (risk=0.05):")
    print("-" * 40)
    sonuc = strateji_guncelle(0.05)
    print(sonuc)

    print("\n📁 Güncel Parametreler:")
    print("-" * 40)
    params = _parametreleri_yukle()
    for k, v in params.items():
        print(f"  {k}: {v}")