# ══════════════════════════════════════════════════════════════════════
#  mod_ortak.py — Ortak UI Bileşenleri, Hesaplama Yardımcıları
#  DRY prensibi: Tekrar eden kodları burada topla.
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional, Any, Callable

# ── Logger ──
from mod_logger import yapilandirilmis_logger
_ortak_logger = yapilandirilmis_logger("Ortak")


# ══════════════════════════════════════════════════════════════════════
#  A. HİSSE ARAMA BİLEŞENİ (Tekrar eden kodları tek yerden yönet)
# ══════════════════════════════════════════════════════════════════════

POPULER_HISSELER = [
    "THYAO.IS - Türk Hava Yolları",
    "AAPL - Apple Inc.",
    "GARAN.IS - Garanti BBVA Bankası",
    "NVDA - NVIDIA Corporation",
    "KCHOL.IS - Koç Holding"
]

POPULER_HABER_SEMBOLLERI = [
    "THYAO.IS", "GARAN.IS", "AAPL", "NVDA", "TSLA", "META",
    "AMZN", "MSFT", "GOOGL", "PLTR", "COIN", "RBLX",
    "AMD", "NFLX", "SNOW", "CRWD", "BABA", "SHOP"
]


def hisse_arama_listesi_olustur(hisse_isimleri: Dict[str, str]) -> List[str]:
    """
    Popüler hisseleri başa koyarak sıralı arama listesi oluşturur.
    Bütün modüllerde aynı mantık tekrar ediyordu.
    """
    populer_semboller = [h.split(" - ")[0] for h in POPULER_HISSELER]
    
    # Popüler hisseleri başta göster
    populer_gosterim = []
    for ps in populer_semboller:
        if ps in hisse_isimleri:
            populer_gosterim.append(f"{ps} - {hisse_isimleri[ps]}")
    
    # Kalanları sırala
    kalanlar = [
        f"{sembol} - {isim}"
        for sembol, isim in hisse_isimleri.items()
        if sembol not in populer_semboller
    ]
    kalanlar.sort(key=lambda x: x.lower())
    
    return populer_gosterim + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar


def render_hisse_arama(hisse_isimleri: Dict[str, str], key_prefix: str = "ana",
                       placeholder: str = "🔍  Aramak için tıklayın veya yazın...",
                       genislik_orani: Tuple[int, int, int] = (1, 3, 1)) -> Optional[str]:
    """
    Standart hisse arama dropdown'ı render eder.
    Seçilen sembolü döndürür, seçim yoksa None.
    
    Artık app.py ve mod_dashboard.py'deki tekrarlı hisse arama kodları
    bu fonksiyon üzerinden çağrılacak.
    """
    _, ara_col, _ = st.columns(genislik_orani)
    with ara_col:
        arama_listesi = hisse_arama_listesi_olustur(hisse_isimleri)
        
        secim = st.selectbox(
            "Hisse Ara veya Seç:",
            options=arama_listesi,
            index=None,
            placeholder=placeholder,
            key=f"{key_prefix}_hisse_smart",
            label_visibility="collapsed"
        )
        
        if secim and "---" not in secim:
            secilen_sembol = secim.split(" - ")[0]
            if st.session_state.get("secilen_hisse") != secilen_sembol:
                st.session_state.secilen_hisse = secilen_sembol
                st.rerun()
            return secilen_sembol
    
    return None


# ══════════════════════════════════════════════════════════════════════
#  B. GRAFİK / GÖRSEL YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def degisim_renk_ve_ok(degisim: float) -> Tuple[str, str]:
    """Değişim değerine göre renk ve ok işareti döndürür."""
    if degisim >= 0:
        return "#22e691", "▲"
    return "#ff4f6d", "▼"


def degisim_arkaplan(degisim: float) -> str:
    """Değişim değerine göre arka plan rengi döndürür."""
    if degisim >= 0:
        return "rgba(8,40,22,0.35)"
    return "rgba(40,8,20,0.35)"


def fiyat_formatla(fiyat: float, para_birimi: str = "") -> str:
    """Fiyatı formatlar: para birimi + 2 ondalık."""
    if para_birimi:
        return f"{para_birimi}{fiyat:,.2f}"
    return f"{fiyat:,.2f}"


def hacim_formatla(hacim: float) -> str:
    """Hacim değerini okunaklı formata çevirir (1.5B, 350M, 1,234)."""
    if hacim >= 1e9:
        return f"{hacim/1e9:.1f}B"
    elif hacim >= 1e6:
        return f"{hacim/1e6:.0f}M"
    return f"{hacim:,.0f}"


# ══════════════════════════════════════════════════════════════════════
#  C. STREAMLIT SESSION STATE YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def session_guvenli_get(key: str, default: Any = None) -> Any:
    """Streamlit session_state'ten güvenli okuma."""
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def session_guvenli_set(key: str, value: Any):
    """Streamlit session_state'e güvenli yazma."""
    st.session_state[key] = value


# ══════════════════════════════════════════════════════════════════════
#  D. TEKNİK HESAPLAMA YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def rsi_hesapla(fiyat_serisi: pd.Series, periyot: int = 14) -> float:
    """
    RSI hesaplar. Projede 3+ yerde manuel yapılıyordu, hepsi buraya.
    Başarısız olursa 50.0 döner.
    """
    try:
        delta = fiyat_serisi.diff()
        gain = delta.clip(lower=0).rolling(window=periyot).mean()
        loss = (-delta.clip(upper=0)).rolling(window=periyot).mean()
        rs = gain / loss.replace(0, float('nan'))
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        return float(rsi) if not pd.isna(rsi) else 50.0
    except Exception:
        return 50.0


def macd_hesapla(fiyat_serisi: pd.Series, hizli: int = 12, yavas: int = 26, sinyal: int = 9) -> Dict[str, float]:
    """
    MACD hesaplar. MACD, Sinyal, Histogram değerlerini dict olarak döndürür.
    """
    try:
        exp1 = fiyat_serisi.ewm(span=hizli, adjust=False).mean()
        exp2 = fiyat_serisi.ewm(span=yavas, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=sinyal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': float(macd_line.iloc[-1]),
            'signal': float(signal_line.iloc[-1]),
            'histogram': float(histogram.iloc[-1])
        }
    except Exception:
        return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}


def bollinger_hesapla(fiyat_serisi: pd.Series, periyot: int = 20, std_carpan: int = 2) -> Dict[str, float]:
    """Bollinger Bantları hesaplar."""
    try:
        ma = fiyat_serisi.rolling(periyot).mean()
        std = fiyat_serisi.rolling(periyot).std()
        return {
            'orta': float(ma.iloc[-1]),
            'ust': float(ma.iloc[-1] + std_carpan * std.iloc[-1]),
            'alt': float(ma.iloc[-1] - std_carpan * std.iloc[-1]),
            'genislik': float((2 * std_carpan * std.iloc[-1]) / ma.iloc[-1] * 100)
        }
    except Exception:
        return {'orta': 0.0, 'ust': 0.0, 'alt': 0.0, 'genislik': 0.0}


def atr_hesapla(high: pd.Series, low: pd.Series, close: pd.Series, periyot: int = 14) -> float:
    """ATR hesaplar."""
    try:
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        return float(tr.rolling(periyot).mean().iloc[-1])
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════════
#  E. VERİ YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def guvenli_float_cevir(deger: Any, varsayilan: float = 0.0) -> float:
    """Herhangi bir değeri güvenli şekilde float'a çevirir."""
    try:
        val = float(deger)
        return val if not pd.isna(val) else varsayilan
    except (ValueError, TypeError):
        return varsayilan


def dataframe_sutun_duzelt(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance MultiIndex sütunlarını düzeltir.
    Bazı durumlarda yfinance MultiIndex döndürür, bu düzeltir.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def json_güvenli_yukle(dosya_yolu: str, varsayilan: Any = None) -> Any:
    """JSON dosyasını güvenli şekilde yükler."""
    import json
    try:
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return varsayilan if varsayilan is not None else {}


def json_güvenli_kaydet(dosya_yolu: str, veri: Any, indent: int = 2):
    """JSON dosyasına güvenli şekilde kaydeder."""
    import json
    try:
        with open(dosya_yolu, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=indent)
        return True
    except IOError as e:
        _ortak_logger.error(f"JSON kaydedilemedi: {dosya_yolu}", hata_tipi="IOError")
        return False


# ══════════════════════════════════════════════════════════════════════
#  F. CACHE YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def akilli_cache_ttl(sembol_sayisi: int) -> int:
    """
    Hisse sayısına göre akıllı cache TTL belirler.
    Az hisse → daha uzun cache, çok hisse → daha kısa cache.
    """
    if sembol_sayisi <= 5:
        return 300  # 5 dakika
    elif sembol_sayisi <= 50:
        return 180  # 3 dakika
    elif sembol_sayisi <= 200:
        return 120  # 2 dakika
    return 60  # 1 dakika


# ══════════════════════════════════════════════════════════════════════
#  G. STRATEJİ / PİYASA YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def piyasa_tipi_belirle(hisse: str) -> str:
    """Hisse sembolüne göre piyasa tipini belirler."""
    if ".IS" in hisse:
        return "bist"
    kripto_list = ["BTC", "ETH", "XRP", "ADA", "SOL", "DOGE", "DOT", "AVAX", "LINK", "MATIC", "UNI"]
    if any(x in hisse for x in kripto_list):
        return "kripto"
    nasdaq_list = ["QQQ", "TQQQ", "SOXL", "NVDA", "AMD", "TSLA", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "NFLX"]
    if any(x in hisse for x in nasdaq_list):
        return "nasdaq"
    return "sp500"


def piyasa_tipine_gore_hedef(hisse: str) -> float:
    """Piyasa tipine göre varsayılan hedef yüzdesi döndürür. (ESNETILDI)"""
    piyasa = piyasa_tipi_belirle(hisse)
    hedefler = {"bist": 0.015, "kripto": 0.02, "nasdaq": 0.02, "sp500": 0.015}
    return hedefler.get(piyasa, 0.015)


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("mod_ortak.py - Ortak Yardımcılar Testi")
    print("=" * 50)
    
    # RSI testi
    import numpy as np
    fiyatlar = pd.Series(np.random.randn(100).cumsum() + 100)
    rsi = rsi_hesapla(fiyatlar)
    print(f"RSI(14): {rsi:.2f}")
    
    # MACD testi
    macd = macd_hesapla(fiyatlar)
    print(f"MACD: {macd}")
    
    # Format testleri
    print(f"Hacim 1500000000 → {hacim_formatla(1500000000)}")
    print(f"Hacim 350000000 → {hacim_formatla(350000000)}")
    print(f"Hacim 1234 → {hacim_formatla(1234)}")
    
    # Piyasa tipi testi
    for hisse in ["THYAO.IS", "BTC-USD", "AAPL", "NVDA"]:
        print(f"{hisse}: {piyasa_tipi_belirle(hisse)} → %{piyasa_tipine_gore_hedef(hisse)*100:.1f}")