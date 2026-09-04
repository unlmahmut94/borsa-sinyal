# ══════════════════════════════════════════════════════════════════════
#  mod_ml_feature_engineer.py — Feature Mühendisliği (mod_ml_egitim'den ayrıldı)
#  130+ teknik indikatör ve özellik çıkarımı
# ══════════════════════════════════════════════════════════════════════

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from mod_logger import yapilandirilmis_logger, guvenli_blok
_f_logger = yapilandirilmis_logger("FeatureEngineer")

# pandas-ta kontrolü
try:
    import pandas_ta as ta
    PANDAS_TA_AKTIF = True
except ImportError:
    PANDAS_TA_AKTIF = False


class FeatureEngineer:
    """
    Ham OHLCV verisinden 130+ teknik indikatör ve özellik çıkarır.
    pandas-ta kullanır, yoksa manuel hesaplar.
    
    v3.2: mod_ml_egitim.py'den ayrıldı, bağımsız modül.
    """
    
    @staticmethod
    def tum_ozellikleri_olustur(data: pd.DataFrame) -> pd.DataFrame:
        """
        Giriş: OHLCV DataFrame
        Çıkış: 130+ özellik içeren DataFrame (NaN satırları temizlenmiş)
        """
        df = data.copy()
        close = df['Close'].squeeze()
        high = df['High'].squeeze()
        low = df['Low'].squeeze()
        open_ = df['Open'].squeeze()
        volume = df['Volume'].squeeze() if 'Volume' in df.columns else pd.Series(0, index=df.index)
        
        # ═══════════════════════════════════════════════════════════════
        #  BÖLÜM A: Temel Fiyat Özellikleri
        # ═══════════════════════════════════════════════════════════════
        df['return_1d'] = close.pct_change(1)
        df['return_5d'] = close.pct_change(5)
        df['return_10d'] = close.pct_change(10)
        df['return_20d'] = close.pct_change(20)
        df['return_3d'] = close.pct_change(3)
        df['return_15d'] = close.pct_change(15)
        df['return_30d'] = close.pct_change(30)
        df['return_60d'] = close.pct_change(60)
        df['log_return'] = np.log(close / close.shift(1))
        df['high_low_ratio'] = high / low
        df['close_open_ratio'] = close / open_
        df['high_close_ratio'] = high / close
        df['low_close_ratio'] = low / close
        
        # ── Mum Yapısı Oranları ──
        df['candle_body'] = (close - open_).abs()
        df['candle_body_pct'] = df['candle_body'] / open_ * 100
        df['upper_wick'] = high - close.clip(lower=open_)
        df['lower_wick'] = close.clip(upper=open_) - low
        df['wick_to_body'] = (df['upper_wick'] + df['lower_wick']) / (df['candle_body'] + 1e-10)
        df['upper_wick_pct'] = df['upper_wick'] / (high - low + 1e-10)
        df['lower_wick_pct'] = df['lower_wick'] / (high - low + 1e-10)
        df['doji'] = (df['candle_body'] / ((high - low) + 1e-10) < 0.1).astype(int)
        df['marubozu'] = (df['wick_to_body'] < 0.1).astype(int)
        
        # ═══════════════════════════════════════════════════════════════
        #  BÖLÜM B: Hareketli Ortalamalar
        # ═══════════════════════════════════════════════════════════════
        for per in [3, 5, 7, 10, 20, 50, 100, 200]:
            ma = close.rolling(per).mean()
            df[f'ma_{per}'] = ma
            df[f'price_to_ma_{per}'] = (close - ma) / ma * 100
            df[f'ma_{per}_slope'] = ma.pct_change(per) * 100
        
        ema_spans = [3, 5, 9, 12, 20, 21, 26, 50, 100, 200]
        for span in ema_spans:
            df[f'ema_{span}'] = close.ewm(span=span, adjust=False).mean()
        
        df['ema_9_21_cross'] = (df['ema_9'] / df['ema_21'] - 1) * 100
        df['ema_21_50_cross'] = (df['ema_21'] / df['ema_50'] - 1) * 100
        df['ema_5_20_cross'] = (df['ema_5'] / df['ema_20'] - 1) * 100
        df['ema_12_26_cross'] = (df['ema_12'] / df['ema_26'] - 1) * 100
        df['ema_50_200_cross'] = (df['ema_50'] / df['ema_200'] - 1) * 100
        
        df['golden_cross'] = ((df['ema_50'] > df['ema_200']) & 
                              (df['ema_50'].shift(1) <= df['ema_200'].shift(1))).astype(int)
        df['death_cross'] = ((df['ema_50'] < df['ema_200']) & 
                            (df['ema_50'].shift(1) >= df['ema_200'].shift(1))).astype(int)
        
        df['price_above_ma20'] = (close > df['ma_20']).astype(int)
        df['price_above_ma50'] = (close > df['ma_50']).astype(int)
        df['price_above_ma200'] = (close > df['ma_200']).astype(int)
        df['ma_alignment'] = df['price_above_ma20'] + df['price_above_ma50'] + df['price_above_ma200']
        
        # ═══════════════════════════════════════════════════════════════
        #  BÖLÜM C: Volatilite
        # ═══════════════════════════════════════════════════════════════
        df['volatility_5d'] = df['return_1d'].rolling(5).std()
        df['volatility_10d'] = df['return_1d'].rolling(10).std()
        df['volatility_20d'] = df['return_1d'].rolling(20).std()
        df['volatility_50d'] = df['return_1d'].rolling(50).std()
        df['volatility_ratio'] = df['volatility_5d'] / df['volatility_20d'].replace(0, np.nan)
        
        df['atr_7'] = FeatureEngineer._atr(high, low, close, 7)
        df['atr_14'] = FeatureEngineer._atr(high, low, close, 14)
        df['atr_21'] = FeatureEngineer._atr(high, low, close, 21)
        df['atr_percent'] = df['atr_14'] / close * 100
        
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        df['true_range'] = tr
        df['true_range_pct'] = tr / close * 100
        
        # ═══════════════════════════════════════════════════════════════
        #  BÖLÜM D: Momentum Osilatörleri (pandas-ta)
        # ═══════════════════════════════════════════════════════════════
        if PANDAS_TA_AKTIF:
            df['rsi_14'] = guvenli_blok(lambda: ta.rsi(close, length=14), varsayilan_donus=pd.Series([50.0]*len(close), index=close.index))
            df['rsi_7'] = guvenli_blok(lambda: ta.rsi(close, length=7), varsayilan_donus=pd.Series([50.0]*len(close), index=close.index))
            
            macd_df = guvenli_blok(lambda: ta.macd(close, fast=12, slow=26, signal=9), varsayilan_donus=pd.DataFrame())
            if not macd_df.empty:
                df['macd'] = macd_df.get('MACD_12_26_9', 0)
                df['macd_signal'] = macd_df.get('MACDs_12_26_9', 0)
                df['macd_hist'] = macd_df.get('MACDh_12_26_9', 0)
            
            stoch_df = guvenli_blok(lambda: ta.stoch(high, low, close, k=14, d=3), varsayilan_donus=pd.DataFrame())
            if not stoch_df.empty:
                df['stoch_k'] = stoch_df.get('STOCHk_14_3_3', 50)
                df['stoch_d'] = stoch_df.get('STOCHd_14_3_3', 50)
                df['stoch_diff'] = df['stoch_k'] - df['stoch_d']
            
            df['cci_20'] = guvenli_blok(lambda: ta.cci(high, low, close, length=20), varsayilan_donus=pd.Series([0.0]*len(close)))
            df['williams_r'] = guvenli_blok(lambda: ta.willr(high, low, close, length=14), varsayilan_donus=pd.Series([-50.0]*len(close)))
            
            # Bollinger Bands
            bb_df = guvenli_blok(lambda: ta.bbands(close, length=20, std=2), varsayilan_donus=pd.DataFrame())
            if not bb_df.empty and len(bb_df.columns) >= 3:
                bb_cols = bb_df.columns.tolist()
                df['bb_upper'] = bb_df[bb_cols[0]] if len(bb_cols) > 0 else close
                df['bb_middle'] = bb_df[bb_cols[1]] if len(bb_cols) > 1 else close
                df['bb_lower'] = bb_df[bb_cols[2]] if len(bb_cols) > 2 else close
                df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (df['bb_middle'] + 1e-10) * 100
                df['bb_position'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
            else:
                FeatureEngineer._manuel_bb(df, close)
        else:
            FeatureEngineer._manuel_bb(df, close)
        
        # ═══════════════════════════════════════════════════════════════
        #  BÖLÜM E: Hacim + Piyasa Yapısı
        # ═══════════════════════════════════════════════════════════════
        df['volume_sma_5'] = volume.rolling(5).mean()
        df['volume_sma_20'] = volume.rolling(20).mean()
        df['volume_ratio_5'] = volume / df['volume_sma_5'].replace(0, np.nan)
        df['volume_ratio_20'] = volume / df['volume_sma_20'].replace(0, np.nan)
        
        df['vwap'] = ((close * volume).rolling(20).sum()) / (volume.rolling(20).sum() + 1e-10)
        df['price_to_vwap'] = (close - df['vwap']) / (df['vwap'] + 1e-10) * 100
        
        df['higher_high'] = (high > high.shift(1)) & (high.shift(1) > high.shift(2))
        df['lower_low'] = (low < low.shift(1)) & (low.shift(1) < low.shift(2))
        
        df['resistance_dist'] = high.rolling(50).max()
        df['support_dist'] = low.rolling(50).min()
        df['price_to_resist'] = (df['resistance_dist'] - close) / (close + 1e-10) * 100
        df['price_to_support'] = (close - df['support_dist']) / (close + 1e-10) * 100
        
        # ═══════════════════════════════════════════════════════════════
        #  BÖLÜM F: Fiyat Konumları + Zaman
        # ═══════════════════════════════════════════════════════════════
        for per in [10, 20, 50, 100, 200]:
            mn = close.rolling(per).min()
            mx = close.rolling(per).max()
            df[f'price_min_{per}'] = mn
            df[f'price_max_{per}'] = mx
            df[f'price_position_{per}'] = (close - mn) / (mx - mn + 1e-10)
        
        if hasattr(df.index, 'dayofweek'):
            df['day_of_week'] = df.index.dayofweek
            df['month'] = df.index.month
            df['quarter'] = df.index.quarter
            df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
            df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
            df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
            df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        # ═══════════════════════════════════════════════════════════════
        #  BÖLÜM G: Hedef Değişkenler
        # ═══════════════════════════════════════════════════════════════
        for horizon in [1, 3, 5, 10, 15, 20, 30]:
            df[f'target_return_{horizon}d'] = close.pct_change(-horizon) * 100
            df[f'target_return_{horizon}d'] = df[f'target_return_{horizon}d'].fillna(0)
        
        df['target_binary_5d'] = (df['target_return_5d'] > 2).astype(int)
        df['target_binary_10d'] = (df['target_return_10d'] > 3).astype(int)
        df['target_binary_20d'] = (df['target_return_20d'] > 5).astype(int)
        df['target_volatile'] = (df['target_return_5d'].abs() > 5).astype(int)
        
        # ═══════════════════════════════════════════════════════════════
        #  TEMİZLEME
        # ═══════════════════════════════════════════════════════════════
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna(thresh=5)
        df = df.fillna(0)
        
        return df
    
    @staticmethod
    def _manuel_bb(df, close):
        """Manuel Bollinger Bantları."""
        ma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        df['bb_middle'] = ma20
        df['bb_upper'] = ma20 + 2 * std20
        df['bb_lower'] = ma20 - 2 * std20
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (ma20 + 1e-10) * 100
        df['bb_position'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
    
    @staticmethod
    def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """ATR (Average True Range) hesaplar."""
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()


# ══════════════════════════════════════════════════════════════════════
#  PİYASA REJİMİ TESPİTİ
# ══════════════════════════════════════════════════════════════════════
class PiyasaRejimi:
    """Trend, Yatay, Volatil piyasa ayrımı yapar."""
    
    TREND = "TREND"
    YATAY = "YATAY"
    VOLATIL = "VOLATIL"
    
    @staticmethod
    def tespit_et(data: pd.DataFrame) -> str:
        """ADX + ATR + MA eğimi ile piyasa rejimini belirler."""
        try:
            close = data['Close'].squeeze()
            
            if PANDAS_TA_AKTIF and len(data) >= 20:
                adx_df = ta.adx(data['High'], data['Low'], close, length=14)
                adx_val = float(adx_df.iloc[-1].get('ADX_14', 20))
            else:
                adx_val = 20
            
            if PANDAS_TA_AKTIF and len(data) >= 14:
                atr_ser = ta.atr(data['High'], data['Low'], close, length=14)
                atr_val = float(atr_ser.iloc[-1]) if atr_ser is not None else 0
            else:
                atr_val = FeatureEngineer._atr(data['High'], data['Low'], close, 14).iloc[-1]
            
            atr_yuzde = (atr_val / float(close.iloc[-1])) * 100 if float(close.iloc[-1]) > 0 else 0
            
            ma20 = close.rolling(20).mean()
            ma20_son = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else float(close.iloc[-1])
            ma20_once = float(ma20.iloc[-20]) if len(ma20) >= 20 and not pd.isna(ma20.iloc[-20]) else ma20_son
            ma_egim = (ma20_son - ma20_once) / abs(ma20_once) * 100 if abs(ma20_once) > 0 else 0
            
            if atr_yuzde > 4:
                return PiyasaRejimi.VOLATIL
            elif adx_val > 25 and abs(ma_egim) > 3:
                return PiyasaRejimi.TREND
            else:
                return PiyasaRejimi.YATAY
                
        except Exception:
            return PiyasaRejimi.YATAY


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("FeatureEngineer Testi")
    print("=" * 50)
    
    # Sentetik veri
    np.random.seed(42)
    dates = pd.date_range('2025-01-01', periods=200, freq='D')
    df = pd.DataFrame({
        'Open': np.random.randn(200).cumsum() + 100,
        'High': np.random.randn(200).cumsum() + 102,
        'Low': np.random.randn(200).cumsum() + 98,
        'Close': np.random.randn(200).cumsum() + 100,
        'Volume': np.random.randint(1000000, 10000000, 200)
    }, index=dates)
    
    featured = FeatureEngineer.tum_ozellikleri_olustur(df)
    print(f"Özellik sayısı: {len(featured.columns)}")
    print(f"Satır: {len(featured)}")
    print(f"Rejim: {PiyasaRejimi.tespit_et(df)}")