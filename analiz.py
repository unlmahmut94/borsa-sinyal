import yfinance as yf
import pandas as pd
import numpy as np
import logging
import concurrent.futures

# ── Logger (analiz modülü için) ─────────────────────────────────────
_analiz_logger = logging.getLogger("Analiz")
_analiz_logger.setLevel(logging.WARNING)
if not _analiz_logger.handlers:
    h = logging.StreamHandler()
    h.setLevel(logging.WARNING)
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    _analiz_logger.addHandler(h)

# ── yfinance gürültüsünü bastır ─────────────────────────────────────
yf_logger = logging.getLogger("yfinance")
yf_logger.setLevel(logging.CRITICAL)
for _name in ["peewee", "urllib3", "requests", "multitasking"]:
    logging.getLogger(_name).setLevel(logging.CRITICAL)

# ── IP Koruma Entegrasyonu ──────────────────────────────────────────
try:
    from mod_veri_kaynagi import _rate_limiter_al, batch_bol, batch_arasi_bekle
    IP_KORUMA_AKTIF = True
except ImportError:
    IP_KORUMA_AKTIF = False
    def _rate_limiter_al(): return None
    def batch_bol(liste, boyut): return [{"indeks": 0, "semboller": liste, "tur": "karma", "boyut": len(liste)}]
    def batch_arasi_bekle(idx): pass

# ── Ölü havuz entegrasyonu ──────────────────────────────────────────
try:
    from mod_veri_kaynagi import dead_liste_yukle, dead_listeye_ekle, dead_listeyi_temizle, delisted_mi
    OLI_HAVUZ_AKTIF = True
except ImportError:
    OLI_HAVUZ_AKTIF = False

# --- NLP SENTIMENT YAPILANDIRMASI ---
NLP_AKTIF = False
sentiment_pipeline = None

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
    VADER_AKTIF = True
    NLP_AKTIF = True
except ImportError:
    _vader = None
    VADER_AKTIF = False

_TRANSFORMERS_YUKLU = False
def _transformers_yukle():
    global _TRANSFORMERS_YUKLU, sentiment_pipeline
    if _TRANSFORMERS_YUKLU:
        return sentiment_pipeline is not None
    _TRANSFORMERS_YUKLU = True
    try:
        from transformers import pipeline
        import torch
        device = 0 if torch.cuda.is_available() else -1
        model_name = "dbmdz/bert-base-turkish-cased-sentiment"
        sentiment_pipeline = pipeline("sentiment-analysis", model=model_name, device=device)
        return True
    except Exception:
        return False

def piyasa_havasini_olc():
    try:
        tickers = {"Dolar": "USDTRY=X", "Altın": "GC=F", "Petrol": "BZ=F"}
        havadurumu = {}
        veri = yf.download(list(tickers.values()), period="5d", progress=False, group_by="ticker")
        for isim, ticker in tickers.items():
            try:
                temp_d = veri[ticker] if isinstance(veri.columns, pd.MultiIndex) else veri
                d = temp_d.dropna(subset=["Close"]) if "Close" in temp_d.columns else temp_d
                if len(d) >= 2:
                    close_series = d["Close"].squeeze()
                    # DÜZELTME: 5 günlük değil, son 1 günlük değişim
                    degisim = ((close_series.iloc[-1] - close_series.iloc[-2]) / close_series.iloc[-2]) * 100
                    havadurumu[isim] = round(float(degisim), 2)
                else:
                    havadurumu[isim] = 0.0
            except:
                havadurumu[isim] = 0.0
        return havadurumu
    except: 
        return {"Dolar": 0.0, "Altın": 0.0, "Petrol": 0.0}

def rsi_serisi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    return 100 - (100 / (1 + (gain / loss)))

def bollinger_bantlari(close, pencere=20, std_carpan=2):
    close = close.squeeze()
    orta = close.rolling(window=pencere).mean()
    sapma = close.rolling(window=pencere).std()
    ust = orta + std_carpan * sapma
    alt = orta - std_carpan * sapma
    return orta, ust, alt

def bollinger_bantlari_ekle(data, pencere=20, std_carpan=2):
    orta, ust, alt = bollinger_bantlari(data["Close"], pencere, std_carpan)
    data["MA20"] = orta
    data["BB_middle"] = orta
    data["BB_upper"] = ust
    data["BB_lower"] = alt
    return data

def macd_sinyal_hesapla(data):
    try:
        close = data["Close"].squeeze()
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
            return "AL"
        if macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
            return "SAT"
        if macd.iloc[-1] > signal.iloc[-1]:
            return "AL"
        if macd.iloc[-1] < signal.iloc[-1]:
            return "SAT"
        return "NÖTR"
    except Exception:
        return "NÖTR"

def bollinger_sinyal_hesapla(data, fiyat):
    try:
        df = data if "BB_lower" in data.columns else bollinger_bantlari_ekle(data.copy())
        bb_alt = float(df["BB_lower"].iloc[-1])
        bb_ust = float(df["BB_upper"].iloc[-1])
        if pd.isna(bb_alt) or pd.isna(bb_ust):
            return "NÖTR"
        if fiyat < bb_alt:
            return "AL"
        if fiyat > bb_ust:
            return "SAT"
        return "NÖTR"
    except Exception:
        return "NÖTR"

def macd_deger_hesapla(data):
    try:
        close = data["Close"].squeeze()
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        return round(float(macd.iloc[-1]), 4)
    except Exception:
        return None

def tespit_order_block(data):
    try:
        for i in range(len(data)-3, len(data)-50, -1):
            if data['Close'].iloc[i] < data['Open'].iloc[i]:
                if data['Close'].iloc[i+1] > data['High'].iloc[i] and data['Close'].iloc[i+2] > data['High'].iloc[i]:
                    return round(float(data['Low'].iloc[i]), 2)
        return None
    except: return None

def kontrol_market_yapisi(data):
    try:
        son_fiyat = data['Close'].iloc[-1]
        zirve = data['High'].rolling(window=20).max().iloc[-11]
        dip = data['Low'].rolling(window=20).min().iloc[-11]
        if son_fiyat > zirve: return "BOS (Yukselis Onayli)"
        elif son_fiyat < dip: return "CHoCH (Dusus Basliyor)"
        return "Konsolidasyon (Yatay)"
    except: return "Veri Yetersiz"

def haber_skoru_hesapla(haber_listesi):
    if not NLP_AKTIF or not haber_listesi: return 0
    puanlar = []
    for hb in haber_listesi[:5]:
        baslik = hb.get('baslik', '')
        if baslik:
            res = sentiment_pipeline(baslik)[0]
            puan = 1 if res['label'] == 'positive' else -1
            puanlar.append(puan * res['score'])
    return round(np.mean(puanlar), 2) if puanlar else 0

def hesapla_piotroski_f_score(ticker):
    try:
        df_fin = ticker.financials
        df_bs = ticker.balance_sheet
        net_income = df_fin.loc['Net Income'].iloc[0]
        total_assets = df_bs.loc['Total Assets'].iloc[0]
        puan = 0
        if net_income > 0: puan += 1
        if (net_income / total_assets) > 0: puan += 1
        if len(df_fin.columns) > 1:
            if net_income > df_fin.loc['Net Income'].iloc[1]: puan += 1
        return puan
    except: return "-"

def hesapla_altman_z_score(ticker, info):
    try:
        bs = ticker.balance_sheet
        fin = ticker.financials
        total_assets = bs.loc['Total Assets'].iloc[0]
        total_liabilities = bs.loc['Total Liabilities Net Minority Interest'].iloc[0]
        working_capital = bs.loc['Working Capital'].iloc[0]
        retained_earnings = bs.loc['Retained Earnings'].iloc[0]
        ebit = fin.loc['EBIT'].iloc[0]
        sales = fin.loc['Total Revenue'].iloc[0]
        market_cap = info.get('marketCap', 1)
        A, B, C, D, E = working_capital/total_assets, retained_earnings/total_assets, ebit/total_assets, market_cap/total_liabilities, sales/total_assets
        return round(1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E, 2)
    except: return "-"

def tespit_kirilim_seviyeleri(data):
    try:
        high_5 = data['High'].tail(5).max()
        low_5 = data['Low'].tail(5).min()
        close = data['Close'].iloc[-1]
        pivot = (high_5 + low_5 + close) / 3
        r1 = (2 * pivot) - low_5      
        r2 = pivot + (high_5 - low_5) 
        s1 = (2 * pivot) - high_5     
        s2 = pivot - (high_5 - low_5) 
        return round(r1, 2), round(r2, 2), round(s1, 2), round(s2, 2)
    except:
        return 0, 0, 0, 0

def hesapla_hedef_suresi(data, guncel_fiyat, r2_hedef, periyot_kodu):
    try:
        mesafe = abs(r2_hedef - guncel_fiyat)
        hiz = abs(data['High'] - data['Low']).tail(14).mean()
        if hiz == 0 or pd.isna(hiz): return "Belirsiz"
        bar_sayisi = int(mesafe / hiz)
        if bar_sayisi > 21: return "Çok Uzun Vade (Belirsiz)"
        if bar_sayisi <= 0: return "Çok Yakın (An Meselesi)"
        if periyot_kodu in ["1h", "3h"]:
            if bar_sayisi == 1: return "1-2 Saat İçinde"
            return f"Tahmini {bar_sayisi} Saat"
        elif periyot_kodu in ["1d", "1wk", "1mo", "3mo", "6mo", "1y", "3y", "5y"]:
            if bar_sayisi == 1: return "1-2 Gün İçinde"
            return f"Tahmini {bar_sayisi} Gün"
        else:
            return f"~ {bar_sayisi} Bar Sonra"
    except:
        return "Hesaplanamadı"

def stochastic_hesapla(data, k_period=14, d_period=3):
    try:
        low_min = data['Low'].rolling(window=k_period).min()
        high_max = data['High'].rolling(window=k_period).max()
        stoch_k = ((data['Close'] - low_min) / (high_max - low_min)) * 100
        stoch_d = stoch_k.rolling(window=d_period).mean()
        return float(stoch_k.iloc[-1]), float(stoch_d.iloc[-1])
    except:
        return 50.0, 50.0

def cci_hesapla(data, period=20):
    try:
        tp = (data['High'] + data['Low'] + data['Close']) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        cci = (tp - sma) / (0.015 * mad)
        return float(cci.iloc[-1]) if not pd.isna(cci.iloc[-1]) else 0.0
    except:
        return 0.0

def williams_r_hesapla(data, period=14):
    try:
        high_max = data['High'].rolling(window=period).max()
        low_min = data['Low'].rolling(window=period).min()
        wr = ((high_max - data['Close']) / (high_max - low_min)) * -100
        return float(wr.iloc[-1]) if not pd.isna(wr.iloc[-1]) else -50.0
    except:
        return -50.0

def mfi_hesapla(data, period=14):
    try:
        tp = (data['High'] + data['Low'] + data['Close']) / 3
        mf = tp * data['Volume']
        positive_flow = mf.where(tp > tp.shift(1), 0).rolling(window=period).sum()
        negative_flow = mf.where(tp < tp.shift(1), 0).rolling(window=period).sum()
        mfi_val = 100 - (100 / (1 + positive_flow / negative_flow.replace(0, np.nan)))
        return float(mfi_val.iloc[-1]) if not pd.isna(mfi_val.iloc[-1]) else 50.0
    except:
        return 50.0

def adx_hesapla(data, period=14):
    try:
        high = data['High']
        low = data['Low']
        close = data['Close']
        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 20.0, float(plus_di.iloc[-1]) if not pd.isna(plus_di.iloc[-1]) else 0, float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 0
    except:
        return 20.0, 0, 0

def obv_hesapla(data):
    try:
        obv = (data['Volume'] * np.sign(data['Close'].diff())).fillna(0).cumsum()
        return float(obv.iloc[-1])
    except:
        return 0.0

def atr_hesapla(data, period=14):
    try:
        high = data['High']
        low = data['Low']
        close = data['Close']
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
    except:
        return 0.0

def ema_hesapla(data, period):
    try:
        return float(data['Close'].ewm(span=period, adjust=False).mean().iloc[-1])
    except:
        return 0.0

def sinyal_hesapla(data, rsi, fiyat, ma50, haber_skoru=0, fk=None, pddd=None, hisse_kodu=None):
    puanlar = []
    detaylar = []
    close = data['Close'].squeeze()
    
    ms = kontrol_market_yapisi(data)
    if "BOS" in ms: 
        puanlar.append(3)
        detaylar.append("✅ Market Yapısı: Yükseliş (BOS)")
    elif "CHoCH" in ms:
        puanlar.append(-3)
        detaylar.append("❌ Market Yapısı: Düşüş (CHoCH)")
        
    ob = tespit_order_block(data)
    if ob and ob * 0.985 <= fiyat <= ob * 1.015: 
        puanlar.append(4)
        detaylar.append("✅ Order Block: Kurumsal Alım Bölgesi")

    if rsi < 30:
        puanlar.append(3)
        detaylar.append(f"✅ RSI {rsi:.0f}: Aşırı Satım (Dip Fırsatı)")
    elif rsi < 40:
        puanlar.append(1)
        detaylar.append(f"✅ RSI {rsi:.0f}: Satış Bölgesine Yakın")
    elif rsi > 70:
        puanlar.append(-2)
        detaylar.append(f"❌ RSI {rsi:.0f}: Aşırı Alım (Tepe Riski)")
    elif rsi > 60:
        puanlar.append(-1)
        detaylar.append(f"⚠️ RSI {rsi:.0f}: Alım Bölgesinde")

    ema9 = ema_hesapla(data, 9)
    ema21 = ema_hesapla(data, 21)
    ma20 = float(close.rolling(20).mean().iloc[-1])
    
    if fiyat > ma50:
        puanlar.append(2)
        detaylar.append("✅ Fiyat MA50 Üzerinde (Boğa Trendi)")
    else:
        puanlar.append(-2)
        detaylar.append("❌ Fiyat MA50 Altında (Ayı Trendi)")
    
    if ema9 > 0 and ema21 > 0:
        if ema9 > ema21:
            puanlar.append(2)
            detaylar.append("✅ EMA9 > EMA21 (Kısa Vadeli Yükseliş)")
        else:
            puanlar.append(-1)
            detaylar.append("⚠️ EMA9 < EMA21 (Kısa Vadeli Zayıf)")

    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else ma50
    if fiyat > ma20 > ma50:
        puanlar.append(1)
        detaylar.append("✅ MA20 > MA50 (Yükseliş Onaylı)")

    try:
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        
        if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
            puanlar.append(3)
            detaylar.append("✅ MACD: Yukarı Kesişim (AL Sinyali)")
        elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
            puanlar.append(-3)
            detaylar.append("❌ MACD: Aşağı Kesişim (SAT Sinyali)")
        elif macd_line.iloc[-1] > signal_line.iloc[-1]:
            puanlar.append(1)
            detaylar.append("✅ MACD: Yükseliş Bölgesinde")
        else:
            puanlar.append(-1)
            detaylar.append("⚠️ MACD: Düşüş Bölgesinde")
        
        if len(macd_hist) >= 3:
            if macd_hist.iloc[-1] > macd_hist.iloc[-2] > macd_hist.iloc[-3]:
                puanlar.append(1)
                detaylar.append("✅ MACD Histogram: Güçleniyor")
            elif macd_hist.iloc[-1] < macd_hist.iloc[-2] < macd_hist.iloc[-3]:
                puanlar.append(-1)
                detaylar.append("⚠️ MACD Histogram: Zayıflıyor")
    except:
        pass

    try:
        df_bb = data if "BB_lower" in data.columns else bollinger_bantlari_ekle(data.copy())
        bb_sig = bollinger_sinyal_hesapla(df_bb, fiyat)
        bb_alt = float(df_bb["BB_lower"].iloc[-1])
        bb_ust = float(df_bb["BB_upper"].iloc[-1])
        bb_orta = float(df_bb["BB_middle"].iloc[-1])
        bb_genislik = ((bb_ust - bb_alt) / bb_orta) * 100
        
        if bb_sig == "AL":
            puanlar.append(3)
            detaylar.append(f"✅ BB Alt Bant ({bb_alt:.2f}): Aşırı Satım")
        elif bb_sig == "SAT":
            puanlar.append(-2)
            detaylar.append(f"❌ BB Üst Bant ({bb_ust:.2f}): Aşırı Alım")
        
        if bb_genislik < 5:
            puanlar.append(1)
            detaylar.append("⚡ BB Daralması: Kırılım Yakın")
    except Exception:
        pass

    try:
        stoch_k, stoch_d = stochastic_hesapla(data)
        if stoch_k < 20 and stoch_d < 20:
            puanlar.append(2)
            detaylar.append(f"✅ Stoch %K {stoch_k:.0f}: Aşırı Satım")
        elif stoch_k > 80 and stoch_d > 80:
            puanlar.append(-1)
            detaylar.append(f"⚠️ Stoch %K {stoch_k:.0f}: Aşırı Alım Bölgesi")
        elif stoch_k > stoch_d and stoch_k < 50:
            puanlar.append(1)
            detaylar.append("✅ Stoch: Yukarı Kesişim Başlangıcı")
    except:
        pass

    try:
        cci_val = cci_hesapla(data)
        if cci_val < -150:
            puanlar.append(2)
            detaylar.append(f"✅ CCI {cci_val:.0f}: Derin Aşırı Satım")
        elif cci_val < -100:
            puanlar.append(1)
            detaylar.append(f"✅ CCI {cci_val:.0f}: Aşırı Satım Bölgesi")
        elif cci_val > 150:
            puanlar.append(-1)
            detaylar.append(f"⚠️ CCI {cci_val:.0f}: Aşırı Alım Zirvesi")
        elif cci_val > 100:
            puanlar.append(-1)
            detaylar.append(f"⚠️ CCI {cci_val:.0f}: Aşırı Alım Bölgesi")
    except:
        pass

    try:
        wr = williams_r_hesapla(data)
        if wr < -80:
            puanlar.append(2)
            detaylar.append(f"✅ Williams %R {wr:.0f}: Dip Bölgesi")
        elif wr > -20:
            puanlar.append(-1)
            detaylar.append(f"⚠️ Williams %R {wr:.0f}: Tepe Bölgesi")
    except:
        pass

    try:
        mfi_val = mfi_hesapla(data)
        if mfi_val < 20:
            puanlar.append(2)
            detaylar.append(f"✅ MFI {mfi_val:.0f}: Para Girişi Başlayabilir")
        elif mfi_val > 80:
            puanlar.append(-1)
            detaylar.append(f"⚠️ MFI {mfi_val:.0f}: Aşırı Para Girişi (Dağıtım)")
        elif mfi_val > 50 and rsi < 40:
            puanlar.append(2)
            detaylar.append("✅ MFI/RSI Uyumsuzluğu: Gizli Alım")
        elif mfi_val < 50 and rsi > 60:
            puanlar.append(-1)
            detaylar.append("⚠️ MFI/RSI Uyumsuzluğu: Gizli Satış")
    except:
        pass

    try:
        adx_val, plus_di, minus_di = adx_hesapla(data)
        if adx_val > 25 and plus_di > minus_di:
            puanlar.append(2)
            detaylar.append(f"✅ ADX {adx_val:.0f}: Güçlü Yükseliş Trendi")
        elif adx_val > 25 and minus_di > plus_di:
            puanlar.append(-2)
            detaylar.append(f"❌ ADX {adx_val:.0f}: Güçlü Düşüş Trendi")
        elif adx_val < 20:
            puanlar.append(0)
            detaylar.append(f"📊 ADX {adx_val:.0f}: Trendsiz (Sıkışma)")
        elif plus_di > minus_di:
            puanlar.append(1)
            detaylar.append("✅ DI+ > DI-: Yükseliş Eğilimi")
        if adx_val > 35 and plus_di > minus_di:
            puanlar.append(3)
            detaylar.append(f"🔥 ADX {adx_val:.0f}: Çok Güçlü Boğa Trendi (Bonus)")
    except:
        pass

    try:
        obv_son = obv_hesapla(data)
        obv_onceki = float((data['Volume'] * np.sign(data['Close'].diff())).fillna(0).cumsum().iloc[-5])
        if obv_son > obv_onceki * 1.02:
            puanlar.append(2)
            detaylar.append("✅ OBV: Hacim Artışı (Alıcılar Güçlü)")
        elif obv_son < obv_onceki * 0.98:
            puanlar.append(-1)
            detaylar.append("⚠️ OBV: Hacim Düşüşü (Satıcılar Aktif)")
    except:
        pass

    try:
        atr_val = atr_hesapla(data)
        atr_yuzde = (atr_val / fiyat) * 100
        if atr_yuzde > 4:
            puanlar.append(-1)
            detaylar.append(f"⚠️ ATR Yüksek (%{atr_yuzde:.1f}): Riskli Volatilite")
        elif atr_yuzde < 1.5:
            puanlar.append(1)
            detaylar.append("✅ ATR Düşük: Sıkışma (Patlama Öncesi)")
    except:
        pass

    if fk is not None and isinstance(fk, (int, float)):
        if 0 < fk < 10:
            puanlar.append(2)
            detaylar.append(f"✅ F/K {fk:.1f}: Çok Ucuz")
        elif 0 < fk < 15:
            puanlar.append(1)
            detaylar.append(f"✅ F/K {fk:.1f}: Cazip")
        elif fk > 40:
            puanlar.append(-2)
            detaylar.append(f"❌ F/K {fk:.1f}: Aşırı Şişkin")
        elif fk > 30:
            puanlar.append(-1)
            detaylar.append(f"⚠️ F/K {fk:.1f}: Pahalı")

    if pddd is not None and isinstance(pddd, (int, float)):
        if 0 < pddd < 1.5:
            puanlar.append(2)
            detaylar.append(f"✅ PD/DD {pddd:.2f}: Defter Değeri Altı")
        elif 0 < pddd < 2.5:
            puanlar.append(1)
            detaylar.append(f"✅ PD/DD {pddd:.2f}: Ucuz")
        elif pddd > 8:
            puanlar.append(-2)
            detaylar.append(f"❌ PD/DD {pddd:.2f}: Aşırı Primli")

    if haber_skoru > 0.6: 
        puanlar.append(3)
        detaylar.append("✅ NLP: Çok Pozitif Haber Akışı")
    elif haber_skoru > 0.3: 
        puanlar.append(2)
        detaylar.append("✅ NLP: Pozitif Haberler")
    elif haber_skoru < -0.6: 
        puanlar.append(-3)
        detaylar.append("❌ NLP: Çok Negatif Haber Akışı")
    elif haber_skoru < -0.3: 
        puanlar.append(-2)
        detaylar.append("❌ NLP: Negatif Haberler")

    try:
        from mod_formasyon import formasyon_skoru_hesapla
        formasyon_skor, formasyon_ozet = formasyon_skoru_hesapla(data, hisse_kodu)
        if formasyon_skor > 6:
            puanlar.append(8)
            detaylar.append(f"📐 Formasyon: Güçlü Yükseliş (+{formasyon_skor:.1f}p) {formasyon_ozet}")
        elif formasyon_skor > 3:
            puanlar.append(5)
            detaylar.append(f"📐 Formasyon: Yükseliş (+{formasyon_skor:.1f}p) {formasyon_ozet}")
        elif formasyon_skor > 1:
            puanlar.append(3)
            detaylar.append(f"📐 Formasyon: Hafif Yükseliş (+{formasyon_skor:.1f}p) {formasyon_ozet}")
        elif formasyon_skor < -6:
            puanlar.append(-8)
            detaylar.append(f"📐 Formasyon: Güçlü Düşüş ({formasyon_skor:.1f}p) {formasyon_ozet}")
        elif formasyon_skor < -3:
            puanlar.append(-5)
            detaylar.append(f"📐 Formasyon: Düşüş ({formasyon_skor:.1f}p) {formasyon_ozet}")
        elif formasyon_skor < -1:
            puanlar.append(-3)
            detaylar.append(f"📐 Formasyon: Hafif Düşüş ({formasyon_skor:.1f}p) {formasyon_ozet}")
        elif formasyon_skor != 0 and formasyon_ozet:
            puanlar.append(1)
            detaylar.append(f"📐 Formasyon: {formasyon_ozet}")
    except ImportError:
        pass
    except Exception:
        pass
        
    toplam = sum(puanlar)
    if toplam >= 2:
        s, r = "GUCLU AL", "#0fdb7a"
    elif toplam == 1:
        s, r = "AL", "#f5cc6a"
    elif -2 <= toplam <= 0:
        s, r = "NOTR", "#7a8fa8"
    elif toplam <= -3:
        s, r = "SAT", "#ff8c42"
    else:
        s, r = "GUCLU SAT", "#ff3b5c"
        
    return s, toplam, " | ".join(detaylar), r

def hisse_analiz(hisse, periyot, makro_veriler=None):
    try:
        data = yf.download(hisse, period="1y", progress=False)
        if isinstance(data.columns, pd.MultiIndex): 
            data.columns = data.columns.get_level_values(0)
        if "Close" not in data.columns: return None
        data = data.dropna(subset=['Close'])
        if data.empty or len(data) < 50: return None
        close = data["Close"].squeeze()
        son_fiyat = round(float(close.iloc[-1]), 4)
        gun_haritasi = {"1d": 1, "2d": 2, "5d": 5, "1wk": 5, "1mo": 21, "3mo": 63, "6mo": 126, "1y": 252, "3y": 756}
        bakilacak_gun = gun_haritasi.get(periyot, 21) 
        if len(close) > bakilacak_gun:
            eski_fiyat = float(close.iloc[-bakilacak_gun - 1])
        else:
            eski_fiyat = float(close.iloc[0])
        degisim_yuzde = ((son_fiyat - eski_fiyat) / eski_fiyat) * 100
        rsi_val = round(float(rsi_serisi(close).iloc[-1]), 2)
        ma50_val = float(close.rolling(50).mean().iloc[-1])
        df_bb = bollinger_bantlari_ekle(data.copy())
        sinyal, skor, detay, renk = sinyal_hesapla(data, rsi_val, son_fiyat, ma50_val, hisse_kodu=hisse)
        return {
            "Hisse": hisse, "Son Fiyat": son_fiyat, "Değişim %": round(degisim_yuzde, 2), 
            "RSI": rsi_val, "MACD": macd_deger_hesapla(data),
            "MACD Sinyal": macd_sinyal_hesapla(data), "BB Sinyal": bollinger_sinyal_hesapla(df_bb, son_fiyat),
            "Sinyal": sinyal, "Sinyal Skor": skor, 
            "Sinyal Renk": renk, "Sinyal Detay": detay, "Borsa": "BIST" if ".IS" in hisse else "ABD"
        }
    except: return None

def tum_hisseleri_tara(liste, periyot, progress_bar, durum, max_workers=None, canli_ekran=None):
    sonuclar = []
    
    # Hızlandırma ve batch ayarları
    if IP_KORUMA_AKTIF:
        ayarlar = {"tarama_batch_boyutu": 25}
        try:
            from mod_veri_kaynagi import rate_limit_ayarlari_al
            ayarlar = rate_limit_ayarlari_al()
        except:
            pass
        batch_boyutu = ayarlar.get("tarama_batch_boyutu", 25)
    else:
        batch_boyutu = 50

    bar_haritasi = {
        "1h": 1, "3h": 3, "1d": 1, "1wk": 5, "2wk": 10, 
        "1mo": 21, "3mo": 63, "6mo": 126, "1y": 252, "3y": 756, "5y": 1260
    }
    bakilacak_bar = bar_haritasi.get(periyot, 21) 
    is_intraday = periyot in ["1h", "3h"]
    fetch_period = "1mo" if is_intraday else ("5y" if periyot in ["3y", "5y"] else "1y")
    fetch_interval = "1h" if is_intraday else "1d"
    
    if IP_KORUMA_AKTIF and len(liste) > batch_boyutu:
        batches = batch_bol(liste, batch_boyutu)
        durum.text(f"🛡️ IP Korumalı Tarama: {len(batches)} batch x ~{batch_boyutu} hisse")
    else:
        batches = [{"indeks": 0, "semboller": liste, "tur": "karma", "boyut": len(liste)}]
        durum.text(f"{len(liste)} Hisse Paralel Olarak Taranıyor... Lütfen Bekleyin.")
        
    tamamlanan = 0
    toplam_hisse = len(liste)
    
    def tek_hisse_isle(hisse):
        hisse_turu = "bist" if ".IS" in hisse else ("kripto" if hisse.upper().endswith("USDT") else "us")
        if IP_KORUMA_AKTIF:
            rl = _rate_limiter_al()
            if rl:
                try:
                    rl.bekle_ve_ilerle(kaynak=f"yfinance:{hisse}", borsa_turu=hisse_turu)
                except RuntimeError as e:
                    return None
        try:
            tk = yf.Ticker(hisse)
            df = tk.history(period=fetch_period, interval=fetch_interval)
            if IP_KORUMA_AKTIF:
                rl = _rate_limiter_al()
                if rl:
                    rl.basari_kaydet()
            if df is None or df.empty or "Close" not in df.columns:
                if OLI_HAVUZ_AKTIF and (df is not None and df.empty):
                    try:
                        info = tk.info
                        if info and info.get("tradeable") is False:
                            dead_listeye_ekle(hisse, "tradeable=False (taramada net onay)")
                        else:
                            _analiz_logger.debug(f"{hisse}: boş veri - ölü havuza eklenmedi")
                    except Exception:
                        pass
                return None
            df = df.dropna(subset=["Close"])
            if len(df) < 50: return None
            try:
                info = tk.info
                fk_val = info.get('trailingPE', None)
                pddd_val = info.get('priceToBook', None)
            except:
                fk_val = None
                pddd_val = None
            close = df["Close"].squeeze()
            son_fiyat = round(float(close.iloc[-1]), 4)
            if len(close) > bakilacak_bar:
                eski_fiyat = float(close.iloc[-bakilacak_bar - 1])
            else:
                eski_fiyat = float(close.iloc[0])
            degisim_yuzde = ((son_fiyat - eski_fiyat) / eski_fiyat) * 100
            rsi_val = round(float(rsi_serisi(close).iloc[-1]), 2)
            ma50_val = float(close.rolling(50).mean().iloc[-1])
            r1, r2, s1, s2 = tespit_kirilim_seviyeleri(df)
            hedef_zaman = hesapla_hedef_suresi(df, son_fiyat, r2, periyot)
            df_bb = bollinger_bantlari_ekle(df.copy())
            sinyal, skor, detay, renk = sinyal_hesapla(df, rsi_val, son_fiyat, ma50_val, 0, fk_val, pddd_val, hisse_kodu=hisse)
            return {
                "Hisse": hisse, "Son Fiyat": son_fiyat, "Değişim %": round(degisim_yuzde, 2), 
                "RSI": rsi_val, "MACD": macd_deger_hesapla(df),
                "MACD Sinyal": macd_sinyal_hesapla(df), "BB Sinyal": bollinger_sinyal_hesapla(df_bb, son_fiyat),
                "Sinyal": sinyal, "Sinyal Skor": skor, 
                "Sinyal Renk": renk, "Sinyal Detay": detay, "Borsa": "BIST" if ".IS" in hisse else "ABD",
                "Hedef_R1": r1, "Hedef_R2": r2, "Short_S1": s1, "Short_S2": s2,
                "Hedef_Suresi": hedef_zaman
            }
        except Exception as e:
            hata_str = str(e).lower()
            if any(kw in hata_str for kw in ['rate limit', 'too many', '429', 'forbidden']):
                if IP_KORUMA_AKTIF:
                    rl = _rate_limiter_al()
                    if rl:
                        rl.ban_kaydet(f"{hisse}: {str(e)[:80]}")
            return None

    for batch in batches:
        batch_idx = batch["indeks"]
        batch_semboller = batch["semboller"]
        if IP_KORUMA_AKTIF:
            batch_arasi_bekle(batch_idx)
        durum.text(f"📦 Batch {batch_idx+1}/{len(batches)} — {len(batch_semboller)} hisse taranıyor...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            gelecekler = {executor.submit(tek_hisse_isle, hisse): hisse for hisse in batch_semboller}
            for gelecek in concurrent.futures.as_completed(gelecekler):
                tamamlanan += 1
                oran = tamamlanan / toplam_hisse
                progress_bar.progress(min(oran, 1.0))
                
                if IP_KORUMA_AKTIF:
                    rl = _rate_limiter_al()
                    durum_ek = f" | 🛡️ {rl.durum_raporu()['gunluk_kalan']} istek kaldı" if rl else ""
                    durum.text(f"Taranıyor: %{int(oran*100)} ({tamamlanan}/{toplam_hisse}){durum_ek}")
                else:
                    durum.text(f"Taranıyor: %{int(oran*100)} Tamamlandı ({tamamlanan}/{toplam_hisse})")
                    
                try:
                    sonuc = gelecek.result()
                    if sonuc:
                        sonuclar.append(sonuc)
                        # Canlı ekrana basma (Beklemeden)
                        if canli_ekran is not None:
                            temp_df = pd.DataFrame(sonuclar)
                            if "Degisim %" in temp_df.columns:
                                temp_df.rename(columns={"Degisim %": "Değişim %"}, inplace=True)
                            gosterilecek = temp_df[["Hisse", "Son Fiyat", "Sinyal", "Değişim %", "Sinyal Skor"]]
                            canli_ekran.dataframe(gosterilecek.sort_values(by="Sinyal Skor", ascending=False), use_container_width=True)
                except Exception:
                    pass

    return sonuclar  

def tek_hisse_detay(hisse, periyot="1y", interval="1d"):
    try:
        raw = yf.download(hisse, period=periyot, interval=interval, progress=False)
        if isinstance(raw.columns, pd.MultiIndex): 
            raw.columns = raw.columns.get_level_values(0)
        if raw is None or "Close" not in raw.columns: return None, None
        data = raw.dropna(subset=['Close']).copy()
        if len(data) < 5: return None, None
        data["RSI"] = rsi_serisi(data["Close"].squeeze())
        data = bollinger_bantlari_ekle(data)
        info = yf.Ticker(hisse).info
        return data, info
    except: return None, None