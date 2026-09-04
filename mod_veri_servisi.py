import streamlit as st
import yfinance as yf
from hisse_isimleri import HISSE_ISIMLERI
from mod_haberler import tum_sistemi_haber_tara

# ── ÇOK KAYNAKLI VERİ MOTORU ──────────────────────────────────────
from mod_veri_kaynagi import canli_fiyat_cek, toplu_fiyat_cek

#  YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════════
def canli_fiyat(semboller):
    """Çok kaynaklı canlı fiyat çeker (yfinance + ccxt + stooq)."""
    # Önce yeni çok kaynaklı motoru dene
    sonuc = toplu_fiyat_cek(semboller)
    
    # Başarısız olanlar için eski yöntemi dene
    alinan_semboller = {s['sembol'] for s in sonuc}
    for sym in semboller:
        if sym in alinan_semboller:
            continue
        try:
            h = yf.Ticker(sym).history(period="5d")
            h = h.dropna(subset=["Close"])
            
            if len(h) >= 1:
                son = float(h["Close"].iloc[-1])
                acan = float(h["Open"].iloc[-1])
                yuk = float(h["High"].iloc[-1])
                dus = float(h["Low"].iloc[-1])
                hacim = float(h["Volume"].iloc[-1])
                deg = ((son - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100 if len(h) >= 2 else 0.0
                
                sonuc.append({
                    "sembol": sym,
                    "isim": HISSE_ISIMLERI.get(sym, sym.replace(".IS", "")),
                    "fiyat": son,
                    "acan": acan,
                    "yuksek": yuk,
                    "dusuk": dus,
                    "hacim": hacim,
                    "degisim": round(deg, 2)
                })
        except:
            pass
    
    # İsimleri ekle (çok kaynaklı motorda olmayabilir)
    for s in sonuc:
        if 'isim' not in s:
            s['isim'] = HISSE_ISIMLERI.get(s['sembol'], s['sembol'].replace(".IS", ""))
    
    return sonuc

# ── HIZLANDIRICI: Önbellekli Veri Çekme ──────────────────────────────
@st.cache_data(ttl=300)  # 5 dakika önbellekte tutar
def canli_fiyat_hizli(semboller: tuple):
    return canli_fiyat(list(semboller))
