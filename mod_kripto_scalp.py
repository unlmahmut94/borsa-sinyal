import pandas as pd
import ssl
import logging
from binance.client import Client
from mod_hafiza import sinyal_kaydet

logger = logging.getLogger(__name__)

def _binance_client_olustur():
    """Binance Client'i farkli yapilandirmalarla olusturmayi dener."""
    tld_listesi = ['com', 'us', 'co']
    
    for tld in tld_listesi:
        try:
            client = Client(tld=tld)
            client.ping()
            logger.info(f"Binance Client basariyla baglandi (tld={tld})")
            return client
        except Exception as e:
            logger.warning(f"Binance tld={tld} ile baglanamadi: {e}")
            continue
    
    # Son care: SSL dogrulamasi olmadan dene
    try:
        client = Client(tld='com')
        client.session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        client.ping()
        logger.warning("Binance Client SSL dogrulamasi olmadan baglandi!")
        return client
    except Exception as e:
        logger.error(f"Binance Client olusturulamadi: {e}")
        raise ConnectionError(f"Binance API'ye baglanilamiyor. Lutfen VPN kullanin veya ag ayarlarinizi kontrol edin.\nHata: {e}")

# Modul yuklendiginde client'i olusturmayi dene, basarisiz olursa None birak
try:
    client = _binance_client_olustur()
except Exception as e:
    print(f"UYARI: {e}")
    client = None

def kripto_canli_tara(semboller, ui_progress=None, ui_text=None):
    if client is None:
        print("HATA: Binance Client olusturulamadi. Islem yapilamiyor.")
        return []
    
    firsatlar = []
    toplam = len(semboller)
    
    for i, sembol in enumerate(semboller):
        try:
            if ui_progress and ui_text:
                ilerleme = int(((i + 1) / toplam) * 100)
                ui_progress.progress(ilerleme)
                ui_text.text(f"Kripto Taranıyor: {sembol} ... (%{ilerleme})")

            klines = client.get_klines(symbol=sembol, interval=Client.KLINE_INTERVAL_5MINUTE, limit=2)
            import time
            time.sleep(0.2)
            df = pd.DataFrame(klines, columns=['Zaman', 'Acilis', 'Yuksek', 'Dusuk', 'Kapanis', 'Hacim', 'x', 'y', 'z', 'a', 'b', 'c'])
            
            for col in ['Acilis', 'Kapanis', 'Hacim']:
                df[col] = df[col].astype(float)
            
            son_mum = df.iloc[-1]
            onceki_mum = df.iloc[-2]
            degisim = ((son_mum['Kapanis'] - son_mum['Acilis']) / son_mum['Acilis']) * 100
            
            # Daha yuksek esik: %0.5 yerine %1.0 ve hacim %20 yerine %30
            if degisim > 1.0 and son_mum['Hacim'] > (onceki_mum['Hacim'] * 1.3):
                hedef = son_mum['Kapanis'] * 1.10  # %10 hedef
                stop = son_mum['Kapanis'] * 0.95   # %5 stop - daha genis stop daha basarili olur
                
                firsatlar.append({'Sembol': sembol, 'Fiyat': son_mum['Kapanis'], 'Artis %': degisim, 'Hedef': hedef, 'Stop': stop, 'Hacim_Artis': round((son_mum['Hacim'] / onceki_mum['Hacim'] - 1) * 100, 1)})
                
                sinyal_kaydet(sembol, "KRIPTO SCALP", son_mum['Kapanis'], hedef, stop)
                
                try:
                    from mod_telegram import telegram_mesaj_gonder
                    hacim_oran = round((son_mum['Hacim'] / onceki_mum['Hacim'] - 1) * 100, 1)
                    telegram_mesaji = (
                        f"<b>KRIPTO SCALP FIRSATI!</b>\n\n"
                        f"Sembol: <b>{sembol}</b>\n"
                        f"Fiyat: ${son_mum['Kapanis']:.6f}\n"
                        f"5 Dk Artis: %{degisim:.2f}\n"
                        f"Hacim Artisi: %{hacim_oran}\n"
                        f"Hedef: ${hedef:.6f} (+%10)\n"
                        f"Stop: ${stop:.6f} (-%5)\n\n"
                        f"Risk/Getiri orani yuksek islem!"
                    )
                    telegram_mesaj_gonder(telegram_mesaji)
                except Exception as e:
                    pass
        except:
            continue

    return sorted(firsatlar, key=lambda x: x['Artis %'], reverse=True)


# ══════════════════════════════════════════════════════════════════════
#  MULTI-TIMEFRAME TEYİT SİSTEMİ (Tavsiye #3)
# ══════════════════════════════════════════════════════════════════════
#
#  ALGORİTMA:
#  ┌───────────────────────────────────────────────────────────────────┐
#  │ TEMEL PRENSİP: Bir sinyalin güvenilir olması için birden fazla  │
#  │ zaman diliminde aynı yönde olması gerekir.                        │
#  │                                                                    │
#  │ ADIM 1: Config'ten teyit edilecek zaman dilimlerini al           │
#  │         (varsayılan: ["5dk", "1sa", "1gun"])                      │
#  │ ADIM 2: Her zaman dilimi için ayrı ayrı OHLCV verisi çek         │
#  │ ADIM 3: Her TF'de sinyal yönünü hesapla:                          │
#  │         - 5dk: Son 2 mum değişimi > %1.0 + hacim artışı          │
#  │         - 1sa: Son 2 saatlik mum RSI + MACD kontrolü              │
#  │         - 1gun: Günlük EMA(20) > EMA(50) ve RSI > 50             │
#  │ ADIM 4: Teyit skoru hesapla:                                      │
#  │         teyit_skoru = uyumlu_TF_sayisi / toplam_TF                │
#  │ ADIM 5: Sinyal kalitesini sınıflandır:                            │
#  │         - 3/3 uyumlu → "GÜÇLÜ TEYİT" (×1.0 ağırlık)             │
#  │         - 2/3 uyumlu → "ORTA TEYİT"  (×0.7 ağırlık)             │
#  │         - 1/3 uyumlu → "ZAYIF TEYİT" (×0.3 ağırlık, sadece uyar)│
#  │         - 0/3 uyumlu → "TEYİTSİZ"    (sinyal üretme)             │
#  │ ADIM 6: Teyit sonucunu sinyale ekle                               │
#  └───────────────────────────────────────────────────────────────────┘
#

import json
import os

def _teyit_config_yukle() -> list:
    """Config'ten teyit zaman dilimlerini yükler."""
    try:
        CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")
        with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("teyit_zaman_dilimleri", ["5dk", "1sa", "1gun"])
    except:
        return ["5dk", "1sa", "1gun"]


def coklu_zaman_dilimi_teyit(sembol: str, ana_sinyal_yonu: str = "AL") -> dict:
    """
    Birden fazla zaman diliminde sinyal teyidi yapar.
    
    Parametreler:
        sembol: Kripto sembolü (örn: BTCUSDT)
        ana_sinyal_yonu: "AL" veya "SAT"
    
    Dönüş: {
        'teyit_skoru': float,        # 0.0 - 1.0
        'teyit_seviyesi': str,       # GÜÇLÜ / ORTA / ZAYIF / TEYİTSİZ
        'teyit_detay': dict,         # Her TF için ayrı sonuç
        'tavsiye': str               # İnsan okunur tavsiye
    }
    """
    if client is None:
        return {
            'teyit_skoru': 0.5,
            'teyit_seviyesi': 'BELİRSİZ',
            'teyit_detay': {},
            'tavsiye': '⚠️ Binance bağlantısı yok, teyit yapılamadı.'
        }
    
    zaman_dilimleri = _teyit_config_yukle()
    teyit_sonuclari = {}
    uyumlu_tf = 0
    
    # TF → Binance interval eşleştirmesi
    TF_INTERVAL_MAP = {
        "5dk": Client.KLINE_INTERVAL_5MINUTE,
        "15dk": Client.KLINE_INTERVAL_15MINUTE,
        "1sa": Client.KLINE_INTERVAL_1HOUR,
        "4sa": Client.KLINE_INTERVAL_4HOUR,
        "1gun": Client.KLINE_INTERVAL_1DAY,
    }
    
    for tf in zaman_dilimleri:
        interval = TF_INTERVAL_MAP.get(tf)
        if interval is None:
            continue
        
        try:
            # ADIM 2: Her TF için veri çek
            limit = 30 if tf == "1gun" else 20 if tf == "1sa" else 10
            klines = client.get_klines(symbol=sembol, interval=interval, limit=limit)
            
            if not klines or len(klines) < 3:
                continue
            
            # DataFrame'e çevir
            closes = [float(k[4]) for k in klines]  # k[4] = close
            volumes = [float(k[5]) for k in klines]  # k[5] = volume
            
            # ADIM 3: TF'ye özel sinyal hesabı
            tf_yonu = _tf_sinyal_yonu_hesapla(closes, volumes, tf)
            
            teyit_sonuclari[tf] = {
                'yon': tf_yonu,
                'son_fiyat': closes[-1],
                'uyumlu': tf_yonu == ana_sinyal_yonu
            }
            
            if tf_yonu == ana_sinyal_yonu:
                uyumlu_tf += 1
                
        except Exception as e:
            logger.warning(f"TF teyit hatası ({sembol}, {tf}): {e}")
            teyit_sonuclari[tf] = {'yon': 'HATA', 'son_fiyat': 0, 'uyumlu': False}
    
    # ADIM 4: Teyit skoru
    toplam_tf = len(zaman_dilimleri)
    teyit_skoru = uyumlu_tf / toplam_tf if toplam_tf > 0 else 0
    
    # ADIM 5: Sınıflandırma
    if teyit_skoru >= 1.0:
        teyit_seviyesi = "GÜÇLÜ TEYİT"
        agirlik = 1.0
        tavsiye = f"✅ {toplam_tf}/{toplam_tf} zaman dilimi uyumlu — Güvenle işlem açılabilir."
    elif teyit_skoru >= 0.67:
        teyit_seviyesi = "ORTA TEYİT"
        agirlik = 0.7
        tavsiye = f"🟡 {uyumlu_tf}/{toplam_tf} zaman dilimi uyumlu — Dikkatli işlem açılabilir."
    elif teyit_skoru >= 0.33:
        teyit_seviyesi = "ZAYIF TEYİT"
        agirlik = 0.3
        tavsiye = f"🟠 {uyumlu_tf}/{toplam_tf} zaman dilimi uyumlu — Sadece ufak pozisyon, riskli."
    else:
        teyit_seviyesi = "TEYİTSİZ"
        agirlik = 0.0
        tavsiye = f"🔴 {uyumlu_tf}/{toplam_tf} zaman dilimi uyumlu — İŞLEM AÇILMAMALI!"
    
    return {
        'teyit_skoru': round(teyit_skoru, 2),
        'teyit_seviyesi': teyit_seviyesi,
        'teyit_agirlik': agirlik,
        'teyit_detay': teyit_sonuclari,
        'tavsiye': tavsiye
    }


def _tf_sinyal_yonu_hesapla(closes: list, volumes: list, tf: str) -> str:
    """
    Bir zaman dilimi için sinyal yönünü hesaplar.
    
    Algoritma (TF'ye özel):
    ┌──────────┬───────────────────────────────────────────────────┐
    │ TF       │ Kural                                             │
    ├──────────┼───────────────────────────────────────────────────┤
    │ 5dk      │ Son 2 mumun kapanış ortalaması > açılış ort.      │
    │          │ VE son hacim > önceki 5 mum hacim ortalaması      │
    │ 1sa      │ Son kapanış > EMA(9) VE RSI(14) > 40             │
    │          │ VE hacim trendi yükselişte                        │
    │ 1gun     │ EMA(5) > EMA(20) VE son kapanış > EMA(50)        │
    │          │ VE son 3 gün hacim artış trendinde                │
    └──────────┴───────────────────────────────────────────────────┘
    
    Dönüş: "AL", "SAT", veya "NOTR"
    """
    if len(closes) < 5 or len(volumes) < 5:
        return "NOTR"
    
    try:
        import numpy as np
        closes_arr = np.array(closes)
        volumes_arr = np.array(volumes)
        
        if tf == "5dk":
            # Son 2 mum pozitif ve hacim artıyor
            son_2_kapanis_ort = closes_arr[-2:].mean()
            son_2_acilis_ort = closes_arr[-4:-2].mean() if len(closes) >= 4 else closes_arr[:-2].mean()
            
            hacim_artiyor = volumes_arr[-1] > volumes_arr[-5:].mean()
            fiyat_yukseliyor = closes_arr[-1] > closes_arr[-2]
            
            if fiyat_yukseliyor and hacim_artiyor:
                return "AL"
            elif not fiyat_yukseliyor and hacim_artiyor:
                return "SAT"
            else:
                return "NOTR"
        
        elif tf == "1sa":
            # EMA(9) ve RSI
            ema9 = pd.Series(closes_arr).ewm(span=9, adjust=False).mean().iloc[-1]
            rsi = _basit_rsi(closes_arr, 14)
            
            hacim_trend = volumes_arr[-1] > volumes_arr[-3:].mean()
            
            if closes_arr[-1] > ema9 and rsi > 40 and hacim_trend:
                return "AL"
            elif closes_arr[-1] < ema9 and rsi < 60 and hacim_trend:
                return "SAT"
            else:
                return "NOTR"
        
        elif tf == "1gun" or tf == "4sa":
            # EMA çaprazlaması
            ema5 = pd.Series(closes_arr).ewm(span=5, adjust=False).mean().iloc[-1]
            ema20 = pd.Series(closes_arr).ewm(span=20, adjust=False).mean().iloc[-1]
            rsi = _basit_rsi(closes_arr, 14)
            
            hacim_artis = volumes_arr[-3:].mean() > volumes_arr[-6:-3].mean() if len(volumes) >= 6 else True
            
            if ema5 > ema20 and rsi > 45 and hacim_artis:
                return "AL"
            elif ema5 < ema20 and rsi < 55:
                return "SAT"
            else:
                return "NOTR"
        
        return "NOTR"
        
    except Exception as e:
        logger.warning(f"TF sinyal hesap hatası: {e}")
        return "NOTR"


def _basit_rsi(closes, period=14):
    """Basit RSI hesaplama (numpy ile, pandas-ta gerekmez)."""
    import numpy as np
    if len(closes) < period + 1:
        return 50.0
    
    deltas = np.diff(closes)
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    
    avg_gain = gains[-period:].mean()
    avg_loss = losses[-period:].mean()
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def teyitli_kripto_tara(semboller, ui_progress=None, ui_text=None):
    """
    Multi-timeframe teyitli kripto tarama.
    Sadece GÜÇLÜ ve ORTA teyit alan sinyalleri döndürür.
    
    Parametreler:
        semboller: Taranacak kripto listesi
        ui_progress: Streamlit progress bar
        ui_text: Streamlit text objesi
    
    Dönüş: Sadece teyitli fırsatlar listesi
    """
    ham_firsatlar = kripto_canli_tara(semboller, ui_progress, ui_text)
    
    teyitli_firsatlar = []
    
    for firsat in ham_firsatlar:
        sembol = firsat['Sembol']
        teyit = coklu_zaman_dilimi_teyit(sembol, "AL")
        
        if teyit['teyit_seviyesi'] in ("GÜÇLÜ TEYİT", "ORTA TEYİT"):
            firsat['Teyit_Skoru'] = teyit['teyit_skoru']
            firsat['Teyit_Seviyesi'] = teyit['teyit_seviyesi']
            firsat['Teyit_Agirlik'] = teyit['teyit_agirlik']
            firsat['Teyit_Tavsiye'] = teyit['tavsiye']
            teyitli_firsatlar.append(firsat)
        elif teyit['teyit_seviyesi'] == "ZAYIF TEYİT":
            firsat['Teyit_Skoru'] = teyit['teyit_skoru']
            firsat['Teyit_Seviyesi'] = teyit['teyit_seviyesi']
            firsat['Teyit_Agirlik'] = teyit['teyit_agirlik']
            firsat['Teyit_Tavsiye'] = teyit['tavsiye']
            # Zayıf teyitlileri de ekle ama uyarıyla
            teyitli_firsatlar.append(firsat)
        # TEYİTSİZ olanlar tamamen filtrelenir
    
    return sorted(teyitli_firsatlar, key=lambda x: x.get('Teyit_Skoru', 0), reverse=True)
