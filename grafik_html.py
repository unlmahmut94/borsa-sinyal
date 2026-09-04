#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════
  grafik_html.py — TRADINGVIEW TARZI PROFESYONEL HTML GRAFİK
  Flet / Streamlit / herhangi bir uygulama için bağımsız Plotly HTML
══════════════════════════════════════════════════════════════════════
  Özellikler:
    • Mum grafiği (TradingView renkleri)
    • Hacim çubukları
    • MA20 / MA50 / MA200 / EMA9 / EMA21
    • Bollinger Bantları (BB)
    • PSAR (Parabolic SAR)
    • MACD + Histogram + Sinyal
    • RSI + aşırı alım/satım bölgeleri
    • Otomatik Destek / Direnç seviyeleri (etiketiyle)
    • Formasyonlar: İkili Dip, İkili Tepe, OBO, Ters OBO, Üçgenler
    • Fibonacci Retracement (0.236 → 0.886)
    • Trend Çizgileri (yükselen/alçalan)
    • BB Sıkışma uyarısı
    • Tam TradingView dark tema
    • Fiyat ekseni sağda, hover bilgisi
══════════════════════════════════════════════════════════════════════
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import os
import webbrowser
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ── RENK PALETİ (TradingView Dark Clone) ──────────────────────────
BG        = "#131722"
BG2       = "#1e222d"
BG3       = "#2a2e39"
GRID      = "rgba(255, 255, 255, 0.04)"
YESIL     = "#089981"
KIRMIZI   = "#f23645"
ALTIN     = "#f5cc6a"
MAVI      = "#2962FF"
MOR       = "#7e57c2"
TURUNCU   = "#FF6D00"
BEYAZ     = "#d1d4dc"
GRI       = "#787b86"
CYAN      = "#00bcd4"
PEMBE     = "#e91e63"


# ══════════════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════

def _find_pivot_points(high: pd.Series, low: pd.Series, window: int = 5) -> Tuple[List[int], List[int]]:
    """Lokal tepe (direnç) ve dip (destek) noktalarını bulur."""
    peaks = []
    troughs = []
    for i in range(window, len(high) - window):
        if high.iloc[i] == high.iloc[i-window:i+window+1].max():
            peaks.append(i)
        if low.iloc[i] == low.iloc[i-window:i+window+1].min():
            troughs.append(i)
    return peaks, troughs


def _kumele_ve_ortalama(seviyeler: List[float], tolerans: float = 0.015) -> List[float]:
    """Birbirine yakın seviyeleri kümeler ve ortalamasını alır."""
    if not seviyeler:
        return []
    seviyeler = sorted(seviyeler)
    kumeler = [[seviyeler[0]]]
    for s in seviyeler[1:]:
        if abs(s - np.mean(kumeler[-1])) / max(abs(np.mean(kumeler[-1])), 0.01) < tolerans:
            kumeler[-1].append(s)
        else:
            kumeler.append([s])
    return [np.mean(k) for k in kumeler]


def _destek_direnc_bul(high: pd.Series, low: pd.Series, close: pd.Series,
                       max_seviye: int = 5) -> Tuple[List[float], List[float]]:
    """Otomatik destek ve direnç seviyelerini bulur (fiyat etiketiyle gösterilecek)."""
    peaks, troughs = _find_pivot_points(high, low, window=5)
    
    destek = [float(low.iloc[i]) for i in troughs]
    direnc = [float(high.iloc[i]) for i in peaks]
    
    son_fiyat = float(close.iloc[-1])
    
    destek = [s for s in destek if s < son_fiyat and (son_fiyat - s) / son_fiyat < 0.12]
    direnc = [r for r in direnc if r > son_fiyat and (r - son_fiyat) / son_fiyat < 0.12]
    
    destek = _kumele_ve_ortalama(destek, tolerans=0.02)[:max_seviye]
    direnc = _kumele_ve_ortalama(direnc, tolerans=0.02)[:max_seviye]
    
    return destek, direnc


def _trend_cizgileri_bul(high: pd.Series, low: pd.Series, close: pd.Series, 
                          index: pd.Index) -> Dict:
    """Yükselen ve alçalan trend çizgilerini bulur."""
    sonuc = {'yukselen': None, 'alcalan': None}
    peaks, troughs = _find_pivot_points(high, low, window=3)
    
    if len(troughs) >= 2:
        son_dipler = [(troughs[-2], float(low.iloc[troughs[-2]])),
                      (troughs[-1], float(low.iloc[troughs[-1]]))]
        if son_dipler[1][1] > son_dipler[0][1]:
            sonuc['yukselen'] = {
                'baslangic': index[son_dipler[0][0]], 'bitis': index[son_dipler[1][0]],
                'bas_deger': son_dipler[0][1], 'bit_deger': son_dipler[1][1], 'tip': 'yukselen'
            }
    
    if len(peaks) >= 2:
        son_tepeler = [(peaks[-2], float(high.iloc[peaks[-2]])),
                       (peaks[-1], float(high.iloc[peaks[-1]]))]
        if son_tepeler[1][1] < son_tepeler[0][1]:
            sonuc['alcalan'] = {
                'baslangic': index[son_tepeler[0][0]], 'bitis': index[son_tepeler[1][0]],
                'bas_deger': son_tepeler[0][1], 'bit_deger': son_tepeler[1][1], 'tip': 'alcalan'
            }
    
    return sonuc


def _fibonacci_seviyeleri(dip: float, tepe: float) -> Dict[str, float]:
    """Fibonacci retracement seviyeleri."""
    fark = tepe - dip
    return {
        '0.0%': dip, '23.6%': tepe - 0.236 * fark,
        '38.2%': tepe - 0.382 * fark, '50.0%': tepe - 0.5 * fark,
        '61.8%': tepe - 0.618 * fark, '78.6%': tepe - 0.786 * fark,
        '100.0%': tepe, '127.2%': tepe + 0.272 * fark,
        '161.8%': tepe + 0.618 * fark,
    }


def _formasyon_cizimleri(df: pd.DataFrame) -> Dict:
    """Grafiğe çizilebilecek formasyonları tespit eder."""
    close = df['Close'].squeeze()
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    volume = df['Volume'].squeeze() if 'Volume' in df.columns else pd.Series(np.zeros(len(df)))
    idx = df.index
    n = len(df)
    
    cizimler = {}
    if n < 20:
        return cizimler
    
    peaks, troughs = _find_pivot_points(high, low, window=5)
    
    # ── İKİLİ DİP (W) ──
    if len(troughs) >= 2:
        son_2_dip = [float(low.iloc[troughs[-2]]), float(low.iloc[troughs[-1]])]
        dip_fark = abs(son_2_dip[0] - son_2_dip[1]) / max(son_2_dip[0], 0.01)
        if dip_fark < 0.03 and son_2_dip[0] < float(close.iloc[-1]) * 0.97:
            dip_indices = [troughs[-2], troughs[-1]]
            aralik = low.iloc[dip_indices[0]:dip_indices[1]+1]
            orta_tepe_idx = aralik.idxmax()
            cizimler['ikili_dip'] = {
                'tip': 'success', 'renk': YESIL, 'indices': dip_indices,
                'seviye': np.mean(son_2_dip), 'boyun': float(high.loc[orta_tepe_idx]),
                'hedef': 2 * float(high.loc[orta_tepe_idx]) - np.mean(son_2_dip),
                'label': 'İkili Dip (W)'
            }
    
    # ── İKİLİ TEPE (M) ──
    if len(peaks) >= 2:
        son_2_tepe = [float(high.iloc[peaks[-2]]), float(high.iloc[peaks[-1]])]
        tepe_fark = abs(son_2_tepe[0] - son_2_tepe[1]) / max(son_2_tepe[0], 0.01)
        if tepe_fark < 0.03 and son_2_tepe[0] > float(close.iloc[-1]) * 1.03:
            tepe_indices = [peaks[-2], peaks[-1]]
            aralik = high.iloc[tepe_indices[0]:tepe_indices[1]+1]
            orta_dip_idx = aralik.idxmin()
            cizimler['ikili_tepe'] = {
                'tip': 'error', 'renk': KIRMIZI, 'indices': tepe_indices,
                'seviye': np.mean(son_2_tepe), 'boyun': float(low.loc[orta_dip_idx]),
                'hedef': np.mean(son_2_tepe) - (float(high.loc[orta_dip_idx]) - float(low.loc[orta_dip_idx])),
                'label': 'İkili Tepe (M)'
            }
    
    # ── OMOZ BAŞ OMOZ (OBO) ──
    if len(peaks) >= 3:
        son_3_tepe_idx = peaks[-3:]
        son_3_tepe = [float(high.iloc[i]) for i in son_3_tepe_idx]
        if (son_3_tepe[1] > son_3_tepe[0] * 1.02 and 
            son_3_tepe[1] > son_3_tepe[2] * 1.02 and
            abs(son_3_tepe[0] - son_3_tepe[2]) / max(son_3_tepe[0], 0.01) < 0.08):
            boyun = min(float(low.iloc[son_3_tepe_idx[0]]), float(low.iloc[son_3_tepe_idx[2]]))
            cizimler['obo'] = {
                'tip': 'error', 'renk': KIRMIZI, 'indices': son_3_tepe_idx,
                'sol_omuz': son_3_tepe[0], 'bas': son_3_tepe[1], 'sag_omuz': son_3_tepe[2],
                'boyun': boyun, 'hedef': boyun - (son_3_tepe[1] - boyun), 'label': 'Omuz-Baş-Omuz (OBO)'
            }
    
    # ── TERS OMOZ BAŞ OMOZ ──
    if len(troughs) >= 3:
        son_3_dip_idx = troughs[-3:]
        son_3_dip = [float(low.iloc[i]) for i in son_3_dip_idx]
        if (son_3_dip[1] < son_3_dip[0] * 0.98 and 
            son_3_dip[1] < son_3_dip[2] * 0.98 and
            abs(son_3_dip[0] - son_3_dip[2]) / max(son_3_dip[0], 0.01) < 0.08):
            boyun = max(float(high.iloc[son_3_dip_idx[0]]), float(high.iloc[son_3_dip_idx[2]]))
            cizimler['ters_obo'] = {
                'tip': 'success', 'renk': YESIL, 'indices': son_3_dip_idx,
                'sol_omuz': son_3_dip[0], 'bas': son_3_dip[1], 'sag_omuz': son_3_dip[2],
                'boyun': boyun, 'hedef': boyun + (boyun - son_3_dip[1]), 'label': 'Ters OBO'
            }
    
    # ── YÜKSELEN ÜÇGEN ──
    if len(peaks) >= 3 and len(troughs) >= 3:
        son_tepeler = [float(high.iloc[i]) for i in peaks[-3:]]
        son_dipler = [float(low.iloc[i]) for i in troughs[-3:]]
        tepe_std = np.std(son_tepeler) / np.mean(son_tepeler) if np.mean(son_tepeler) > 0 else 0.1
        dip_egim = (son_dipler[-1] - son_dipler[0]) / max(son_dipler[0], 0.01) if len(son_dipler) >= 2 else 0
        if tepe_std < 0.03 and dip_egim > 0.01:
            cizimler['yukselen_ucgen'] = {
                'tip': 'success', 'renk': YESIL,
                'direnc': np.mean(son_tepeler), 'indices': [troughs[-1], peaks[-1]],
                'label': 'Yükselen Üçgen'
            }
    
    # ── ALCALAN ÜÇGEN ──
    if len(peaks) >= 3 and len(troughs) >= 3:
        son_tepeler = [float(high.iloc[i]) for i in peaks[-3:]]
        son_dipler = [float(low.iloc[i]) for i in troughs[-3:]]
        dip_std = np.std(son_dipler) / np.mean(son_dipler) if np.mean(son_dipler) > 0 else 0.1
        tepe_egim = (son_tepeler[-1] - son_tepeler[0]) / max(son_tepeler[0], 0.01) if len(son_tepeler) >= 2 else 0
        if dip_std < 0.03 and tepe_egim < -0.01:
            cizimler['alcalan_ucgen'] = {
                'tip': 'error', 'renk': KIRMIZI,
                'destek': np.mean(son_dipler), 'indices': [peaks[-1], troughs[-1]],
                'label': 'Alçalan Üçgen'
            }
    
    # ── FIBONACCI ──
    if n >= 60:
        son_60_yuksek = float(high.iloc[-60:].max())
        son_60_dusuk = float(low.iloc[-60:].min())
        fib_idx = high.iloc[-60:].idxmax()
        dip_idx = low.iloc[-60:].idxmin()
        cizimler['fibonacci'] = {
            'dip': min(son_60_dusuk, float(low.iloc[-1])),
            'tepe': max(son_60_yuksek, float(high.iloc[-1])),
            'dip_idx': dip_idx, 'tepe_idx': fib_idx, 'label': 'Fibonacci'
        }
    
    # ── BOLLINGER BANDI SIKIŞMA ──
    if n >= 20:
        ma20 = float(close.iloc[-20:].mean())
        std20 = float(close.iloc[-20:].std())
        bb_ust = ma20 + 2 * std20
        bb_alt = ma20 - 2 * std20
        bant_genislik = (bb_ust - bb_alt) / ma20 if ma20 > 0 else 0
        if bant_genislik < 0.05:
            cizimler['bb_sikisma'] = {
                'tip': 'warning', 'renk': ALTIN,
                'ust': bb_ust, 'alt': bb_alt, 'orta': ma20, 'label': '🔄 BB Sıkışması'
            }
    
    # ── DESTEK / DİRENÇ ──
    destek, direnc = _destek_direnc_bul(high, low, close, max_seviye=4)
    if destek:
        cizimler['destekler'] = {'tip': 'destek', 'renk': YESIL, 'seviyeler': destek, 'label': 'Destek'}
    if direnc:
        cizimler['direncler'] = {'tip': 'direnc', 'renk': KIRMIZI, 'seviyeler': direnc, 'label': 'Direnç'}
    
    # ── TREND ÇİZGİLERİ ──
    trend = _trend_cizgileri_bul(high, low, close, idx)
    if trend['yukselen']:
        cizimler['trend_yukselen'] = {
            'tip': 'success', 'renk': YESIL,
            'baslangic': trend['yukselen']['baslangic'], 'bitis': trend['yukselen']['bitis'],
            'bas_deger': trend['yukselen']['bas_deger'], 'bit_deger': trend['yukselen']['bit_deger'],
            'label': '↗ Yükselen Trend'
        }
    if trend['alcalan']:
        cizimler['trend_alcalan'] = {
            'tip': 'error', 'renk': KIRMIZI,
            'baslangic': trend['alcalan']['baslangic'], 'bitis': trend['alcalan']['bitis'],
            'bas_deger': trend['alcalan']['bas_deger'], 'bit_deger': trend['alcalan']['bit_deger'],
            'label': '↘ Alçalan Trend'
        }
    
    return cizimler


def _cizimleri_ekle(fig: go.Figure, cizimler: Dict, data: pd.DataFrame):
    """Tespit edilen tüm formasyon ve seviyeleri grafiğe ekler."""
    idx = data.index
    
    # ── DESTEK ÇİZGİLERİ (YEŞİL) ──
    if 'destekler' in cizimler:
        for s in cizimler['destekler']['seviyeler']:
            fig.add_hline(
                y=s, line_color=YESIL, line_width=0.8, line_dash="dash", opacity=0.5,
                annotation_text=f"🟢 D {s:.2f}", annotation_position="bottom right",
                annotation_font=dict(size=10, color=YESIL, family="monospace")
            )
    
    # ── DİRENÇ ÇİZGİLERİ (KIRMIZI) ──
    if 'direncler' in cizimler:
        for r in cizimler['direncler']['seviyeler']:
            fig.add_hline(
                y=r, line_color=KIRMIZI, line_width=0.8, line_dash="dash", opacity=0.5,
                annotation_text=f"🔴 R {r:.2f}", annotation_position="top right",
                annotation_font=dict(size=10, color=KIRMIZI, family="monospace")
            )
    
    # ── TREND ÇİZGİLERİ ──
    if 'trend_yukselen' in cizimler:
        t = cizimler['trend_yukselen']
        fig.add_trace(go.Scatter(
            x=[t['baslangic'], t['bitis']], y=[t['bas_deger'], t['bit_deger']],
            mode="lines", line=dict(color=YESIL, width=1.5, dash="dash"),
            name="↗ Yükselen Trend", hoverinfo="skip"
        ))
    
    if 'trend_alcalan' in cizimler:
        t = cizimler['trend_alcalan']
        fig.add_trace(go.Scatter(
            x=[t['baslangic'], t['bitis']], y=[t['bas_deger'], t['bit_deger']],
            mode="lines", line=dict(color=KIRMIZI, width=1.5, dash="dash"),
            name="↘ Alçalan Trend", hoverinfo="skip"
        ))
    
    # ── İKİLİ DİP (W) ──
    if 'ikili_dip' in cizimler:
        dd = cizimler['ikili_dip']
        dip_1_idx, dip_2_idx = dd['indices']
        fig.add_trace(go.Scatter(
            x=[idx[dip_1_idx], idx[dip_2_idx]],
            y=[float(data['Low'].iloc[dip_1_idx]), float(data['Low'].iloc[dip_2_idx])],
            mode="markers", marker=dict(color=YESIL, size=14, symbol="star", line=dict(color="white", width=1.5)),
            name="🌟 İkili Dip", hoverinfo="skip"
        ))
        fig.add_hline(
            y=dd['boyun'], line_color=YESIL, line_width=1.5, line_dash="dot", opacity=0.7,
            annotation_text=f"📊 Boyun {dd['boyun']:.2f} 🎯 {dd['hedef']:.2f}",
            annotation_position="bottom left", annotation_font=dict(size=10, color=YESIL, family="monospace")
        )
        fig.add_hline(
            y=dd['hedef'], line_color=YESIL, line_width=0.8, line_dash="dashdot", opacity=0.4,
            annotation_text=f"🎯 {dd['hedef']:.2f}", annotation_position="top left",
            annotation_font=dict(size=9, color=YESIL)
        )
    
    # ── İKİLİ TEPE (M) ──
    if 'ikili_tepe' in cizimler:
        dt = cizimler['ikili_tepe']
        tepe_1_idx, tepe_2_idx = dt['indices']
        fig.add_trace(go.Scatter(
            x=[idx[tepe_1_idx], idx[tepe_2_idx]],
            y=[float(data['High'].iloc[tepe_1_idx]), float(data['High'].iloc[tepe_2_idx])],
            mode="markers", marker=dict(color=KIRMIZI, size=14, symbol="star", line=dict(color="white", width=1.5)),
            name="🌟 İkili Tepe", hoverinfo="skip"
        ))
        fig.add_hline(
            y=dt['boyun'], line_color=KIRMIZI, line_width=1.5, line_dash="dot", opacity=0.7,
            annotation_text=f"📊 Boyun {dt['boyun']:.2f} 🎯 {dt['hedef']:.2f}",
            annotation_position="top left", annotation_font=dict(size=10, color=KIRMIZI, family="monospace")
        )
        fig.add_hline(
            y=dt['hedef'], line_color=KIRMIZI, line_width=0.8, line_dash="dashdot", opacity=0.4,
            annotation_text=f"🎯 {dt['hedef']:.2f}", annotation_position="bottom left",
            annotation_font=dict(size=9, color=KIRMIZI)
        )
    
    # ── OMOZ-BAŞ-OMUZ (OBO) ──
    if 'obo' in cizimler:
        obo = cizimler['obo']
        indices = obo['indices']
        fig.add_trace(go.Scatter(
            x=list(idx[i] for i in indices),
            y=[obo['sol_omuz'], obo['bas'], obo['sag_omuz']],
            mode="markers", marker=dict(color=KIRMIZI, size=16, symbol="diamond", line=dict(color="white", width=2)),
            name="♦ OBO", hoverinfo="skip"
        ))
        fig.add_hline(
            y=obo['boyun'], line_color=KIRMIZI, line_width=2, line_dash="dot", opacity=0.8,
            annotation_text=f"⚠ OBO Boyun {obo['boyun']:.2f}",
            annotation_position="top left", annotation_font=dict(size=11, color=KIRMIZI, family="monospace")
        )
        if obo['hedef']:
            fig.add_hline(
                y=obo['hedef'], line_color=KIRMIZI, line_width=0.8, line_dash="dashdot", opacity=0.3,
                annotation_text=f"🎯 {obo['hedef']:.2f}", annotation_position="bottom left",
                annotation_font=dict(size=9, color=KIRMIZI)
            )
    
    # ── TERS OBO ──
    if 'ters_obo' in cizimler:
        tobo = cizimler['ters_obo']
        indices = tobo['indices']
        fig.add_trace(go.Scatter(
            x=list(idx[i] for i in indices),
            y=[tobo['sol_omuz'], tobo['bas'], tobo['sag_omuz']],
            mode="markers", marker=dict(color=YESIL, size=16, symbol="diamond", line=dict(color="white", width=2)),
            name="♦ Ters OBO", hoverinfo="skip"
        ))
        fig.add_hline(
            y=tobo['boyun'], line_color=YESIL, line_width=2, line_dash="dot", opacity=0.8,
            annotation_text=f"⚡ Ters OBO Boyun {tobo['boyun']:.2f}",
            annotation_position="bottom left", annotation_font=dict(size=11, color=YESIL, family="monospace")
        )
    
    # ── YÜKSELEN ÜÇGEN ──
    if 'yukselen_ucgen' in cizimler:
        yt = cizimler['yukselen_ucgen']
        fig.add_hline(
            y=yt['direnc'], line_color=YESIL, line_width=1.2, line_dash="dash", opacity=0.7,
            annotation_text=f"▲ Yüks. Üçgen {yt['direnc']:.2f}",
            annotation_position="top right", annotation_font=dict(size=10, color=YESIL, family="monospace")
        )
    
    # ── ALCALAN ÜÇGEN ──
    if 'alcalan_ucgen' in cizimler:
        at = cizimler['alcalan_ucgen']
        fig.add_hline(
            y=at['destek'], line_color=KIRMIZI, line_width=1.2, line_dash="dash", opacity=0.7,
            annotation_text=f"▼ Alç. Üçgen {at['destek']:.2f}",
            annotation_position="bottom right", annotation_font=dict(size=10, color=KIRMIZI, family="monospace")
        )
    
    # ── BB SIKIŞMA ──
    if 'bb_sikisma' in cizimler:
        bb = cizimler['bb_sikisma']
        fig.add_hline(
            y=bb['ust'], line_color=ALTIN, line_width=0.8, line_dash="dot", opacity=0.4,
            annotation_text=f"BB Üst {bb['ust']:.2f}", annotation_font=dict(size=8, color=ALTIN)
        )
        fig.add_hline(
            y=bb['alt'], line_color=ALTIN, line_width=0.8, line_dash="dot", opacity=0.4,
            annotation_text=f"BB Alt {bb['alt']:.2f}", annotation_font=dict(size=8, color=ALTIN)
        )
    
    # ── FIBONACCI ──
    if 'fibonacci' in cizimler:
        fib = cizimler['fibonacci']
        dip = fib['dip']
        tepe = fib['tepe']
        seviyeler = _fibonacci_seviyeleri(dip, tepe)
        
        fib_renkler = [GRI, MAVI, TURUNCU, YESIL, KIRMIZI, MOR, GRI, GRI]
        for i, (isim, seviye) in enumerate(seviyeler.items()):
            renk = fib_renkler[i % len(fib_renkler)]
            opacity = 0.6 if '61.8' in isim else (0.4 if '38.2' in isim or '50.0' in isim else 0.2)
            fig.add_hline(
                y=seviye, line_color=renk, line_width=0.6, line_dash="dash", opacity=opacity,
                annotation_text=f"Fib {isim} {seviye:.2f}", annotation_position="right",
                annotation_font=dict(size=8, color=renk)
            )


# ══════════════════════════════════════════════════════════════════
#  ANA GRAFİK OLUŞTURMA
# ══════════════════════════════════════════════════════════════════

def tradingview_grafik_html(
    data: pd.DataFrame,
    sembol: str,
    gosterge_alt: str = "MACD",
    gosterge_alt2: str = "RSI",
    overlay_list: list = None,
    show_volume: bool = True,
    formasyon_ciz: bool = True,
    destek_direnc: bool = True,
    fibonacci_ciz: bool = True,
) -> str:
    """
    TradingView tarzı profesyonel grafik oluşturur ve HTML olarak döndürür.
    
    Parametreler:
        data: OHLCV verilerini içeren DataFrame
        sembol: Hisse sembolü (örn: "THYAO.IS")
        gosterge_alt: Alt gösterge 1 (MACD/RSI/Stochastic/ADX/CCI/Williams %R/MFI/ROC/Momentum/OBV/ATR/None)
        gosterge_alt2: Alt gösterge 2
        overlay_list: Fiyat üstü göstergeler (MA20, MA50, MA200, EMA9, EMA21, BB, PSAR, VWAP)
        show_volume: Hacim gösterme
        formasyon_ciz: Formasyon çizimleri
        destek_direnc: Destek/direnç seviyeleri
        fibonacci_ciz: Fibonacci çizgileri
    
    Returns:
        HTML string (Plotly grafiği)
    """
    if overlay_list is None:
        overlay_list = ["MA20", "MA50", "BB"]
    if gosterge_alt in (None, "— Yok —", "None", ""):
        gosterge_alt = None
    if gosterge_alt2 in (None, "— Yok —", "None", ""):
        gosterge_alt2 = None
    
    close = data["Close"].squeeze()
    open_ = data["Open"].squeeze()
    high = data["High"].squeeze()
    low = data["Low"].squeeze()
    volume = data["Volume"].squeeze()
    
    n_alt = sum([1 for g in [gosterge_alt, gosterge_alt2] if g])
    rows = 1 + n_alt
    
    if rows == 1:
        row_heights = [1.0]
    elif rows == 2:
        row_heights = [0.75, 0.25]
    else:
        row_heights = [0.65, 0.175, 0.175]
    
    specs = [[{"secondary_y": True}]] + [[{"secondary_y": False}]] * n_alt
    
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        row_heights=row_heights, vertical_spacing=0.02, specs=specs
    )
    
    # ── 1. MUM GRAFİĞİ (TradingView renkleri) ──
    fig.add_trace(go.Candlestick(
        x=data.index, open=open_, high=high, low=low, close=close,
        increasing=dict(line=dict(color=YESIL, width=1), fillcolor=YESIL),
        decreasing=dict(line=dict(color=KIRMIZI, width=1), fillcolor=KIRMIZI),
        name=f"{sembol}", showlegend=False,
        hoverinfo="none"
    ), row=1, col=1, secondary_y=False)
    
    # Detaylı hover bilgisi
    hovertmpl = (
        "<b style='font-size:14px'>%{x|%d %b %Y}</b><br>"
        "<b style='font-size:16px;color:#d1d4dc'>%{customdata[0]:.2f}</b><br>"
        "<span style='color:#089981'>▲ Y: %{customdata[1]:.2f}</span> "
        "<span style='color:#f23645'>▼ D: %{customdata[2]:.2f}</span><br>"
        "Aç: %{customdata[3]:.2f} Ka: %{customdata[4]:.2f}<br>"
        "📊 Hacim: %{customdata[5]:,.0f}<br>"
        "📈 Değişim: %{customdata[6]:+.2f}%"
        "<extra></extra>"
    )
    fig.add_trace(go.Scatter(
        x=data.index, y=close, mode="none",
        hovertemplate=hovertmpl,

        customdata=list(zip(
            close, high, low, open_, close,
            volume,
            [(c / close.iloc[max(0,i-1)] - 1) * 100 if i > 0 else 0 for i, c in enumerate(close)]
        )),
        showlegend=False,
    ), row=1, col=1, secondary_y=False)
    
    # ── 2. HACİM ÇUBUKLARI ──
    if show_volume:
        vol_renk = [YESIL if c >= o else KIRMIZI for c, o in zip(close, open_)]
        fig.add_trace(go.Bar(
            x=data.index, y=volume, name="Hacim",
            opacity=0.35,
            marker=dict(color=vol_renk, line=dict(color=vol_renk, width=0)),
            hovertemplate="📊 Hacim: %{y:,.0f}<extra></extra>",
            showlegend=False
        ), row=1, col=1, secondary_y=True)
    
    # ── 3. FİYAT ÜSTÜ GÖSTERGELER ──
    overlay_cfg = {
        "MA20": ("MA20", MAVI, 1.2, "MA 20"),
        "MA50": ("MA50", TURUNCU, 1.2, "MA 50"),
        "MA200": ("MA200", GRI, 1.5, "MA 200"),
        "EMA9": ("EMA9", CYAN, 1.0, "EMA 9"),
        "EMA21": ("EMA21", PEMBE, 1.0, "EMA 21"),
    }
    
    for key, (col, renk, w, lbl) in overlay_cfg.items():
        if key in overlay_list and col in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index, y=data[col], mode="lines",
                line=dict(color=renk, width=w), name=lbl, hoverinfo="skip"
            ), row=1, col=1, secondary_y=False)
    
    # PSAR
    if "PSAR" in overlay_list and "PSAR" in data.columns:
        trend = data.get("PSAR_Trend", pd.Series(1, index=data.index))
        fig.add_trace(go.Scatter(
            x=data.index[trend == 1], y=data["PSAR"][trend == 1],
            mode="markers", marker=dict(color=YESIL, size=4, symbol="triangle-up"),
            name="PSAR ↗", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=data.index[trend == -1], y=data["PSAR"][trend == -1],
            mode="markers", marker=dict(color=KIRMIZI, size=4, symbol="triangle-down"),
            name="PSAR ↘", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
    
    # Bollinger Bantları
    if "BB" in overlay_list and "BB_upper" in data.columns:
        bb_orta_idx = None
        for c in ['BB_middle', 'BB_orta', 'MA20']:
            if c in data.columns:
                bb_orta_idx = c
                break
        
        fig.add_trace(go.Scatter(
            x=data.index, y=data["BB_upper"], mode="lines",
            line=dict(color=MAVI, width=0.8), name="BB Üst", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["BB_lower"], mode="lines",
            fill="tonexty", fillcolor="rgba(41, 98, 255, 0.04)",
            line=dict(color=MAVI, width=0.8), name="BB Alt", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        
        if bb_orta_idx:
            fig.add_trace(go.Scatter(
                x=data.index, y=data[bb_orta_idx], mode="lines",
                line=dict(color=MAVI, width=0.6, dash="dot"),
                name="BB Orta", hoverinfo="skip"
            ), row=1, col=1, secondary_y=False)
    
    # VWAP
    if "VWAP" in overlay_list and "VWAP" in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["VWAP"], mode="lines",
            line=dict(color=BEYAZ, width=1.2, dash="dot"),
            name="VWAP", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
    
    # ── 4. FORMASYON / DESTEK/DİRENÇ / FIBONACCI ÇİZİMLERİ ──
    cizimler = _formasyon_cizimleri(data)
    aktif_cizimler = {}
    for key, val in cizimler.items():
        if key in ['destekler', 'direncler'] and not destek_direnc:
            continue
        if key in ['fibonacci'] and not fibonacci_ciz:
            continue
        if key in ['yukselen_ucgen', 'alcalan_ucgen', 'ikili_dip', 'ikili_tepe',
                   'obo', 'ters_obo', 'bb_sikisma', 'trend_yukselen', 'trend_alcalan'] and not formasyon_ciz:
            continue
        aktif_cizimler[key] = val
    
    _cizimleri_ekle(fig, aktif_cizimler, data)
    
    # ── 5. ALT GÖSTERGELER ──
    row_idx = 2
    if gosterge_alt:
        _alt_gosterge_ekle(fig, data, gosterge_alt, row_idx)
        row_idx += 1
    if gosterge_alt2:
        _alt_gosterge_ekle(fig, data, gosterge_alt2, row_idx)
    
    # ── 6. LAYOUT (TradingView Dark Clone) ──
    son_fiyat = float(close.iloc[-1])
    ilk_fiyat = float(close.iloc[0])
    toplam_degisim = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100
    degisim_renk = YESIL if toplam_degisim >= 0 else KIRMIZI
    degisim_ikon = "▲" if toplam_degisim >= 0 else "▼"
    
    layout_dict = dict(
        paper_bgcolor=BG,
        plot_bgcolor=BG2,
        font=dict(
            family="-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Arial, sans-serif",
            color=BEYAZ, size=11
        ),
        margin=dict(l=4, r=60, t=50, b=8),
        legend=dict(visible=False),
        height=800,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#131722", bordercolor="#363a45",
            font=dict(color=BEYAZ, size=12, family="monospace")
        ),
        dragmode="pan",
        xaxis=dict(
            gridcolor=GRID, showgrid=True, zeroline=False,
            rangeslider=dict(visible=False),
            showspikes=True, spikemode="across+toaxis",
            spikecolor=GRI, spikethickness=0.5, spikedash="dot",
            tickfont=dict(color=GRI, size=10)
        ),
        yaxis=dict(
            gridcolor=GRID, showgrid=True, zeroline=False,
            side="right", autorange=True, fixedrange=False,
            showspikes=True, spikemode="across",
            spikecolor=GRI, spikethickness=0.5, spikedash="dot",
            tickfont=dict(color=BEYAZ, size=11)
        ),
        # TradingView tarzı başlık
        title=dict(
            text=(
                f"<b style='font-size:18px;color:{BEYAZ}'>{sembol.replace('.IS','')}</b> "
                f"<span style='font-size:16px;color:{BEYAZ};font-weight:300'>"
                f"<b style='font-size:22px;color:{BEYAZ}'>{son_fiyat:.2f}</b> "
                f"<span style='color:{degisim_renk};font-size:14px'>"
                f"{degisim_ikon} {abs(toplam_degisim):.2f}%</span>"
                f"</span>"
            ),
            font=dict(size=14),
            x=0.01, y=0.99,
            xanchor="left", yanchor="top",
        ),
    )
    
    # Hacim için ikinci Y ekseni
    if show_volume:
        max_vol = float(volume.max()) if not volume.empty else 1
        layout_dict["yaxis2"] = dict(
            showgrid=False, zeroline=False, showticklabels=False,
            range=[0, max_vol * 4.5], overlaying="y", side="left"
        )
    
    # Alt gösterge eksenleri
    for i in range(2, rows + 1):
        ax = f"xaxis{i}"
        ay = f"yaxis{i}"
        layout_dict[ax] = dict(
            gridcolor=GRID, showgrid=True, zeroline=False,
            showspikes=True, spikemode="across+toaxis",
            spikecolor=GRI, spikethickness=0.5, spikedash="dot",
            tickfont=dict(color=GRI, size=10)
        )
        layout_dict[ay] = dict(
            gridcolor=GRID, showgrid=True, zeroline=False, side="right",
            tickfont=dict(color=GRI, size=10)
        )
    
    fig.update_layout(**layout_dict)
    
    # Arka plan filigran
    fig.add_annotation(
        text=f"{sembol.replace('.IS','')}",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(size=120, color="rgba(255, 255, 255, 0.015)", family="Arial, sans-serif"),
        textangle=0, xanchor="center", yanchor="middle"
    )
    
    # Sol üst formasyon lejantı
    formasyon_listesi = []
    for key, val in aktif_cizimler.items():
        if 'label' in val and key not in ('destekler', 'direncler', 'fibonacci'):
            renk = val.get('renk', BEYAZ)
            formasyon_listesi.append(
                f"<span style='display:inline-block;width:8px;height:8px;"
                f"border-radius:50%;background:{renk};margin-right:4px'></span>"
                f"<span style='color:{renk}'>{val['label']}</span>"
            )
    
    if formasyon_listesi:
        fig.add_annotation(
            xref="paper", yref="paper", x=0.0, y=1.0,
            text="<span style='font-size:9px'>" + " &nbsp;|&nbsp; ".join(formasyon_listesi[:6]) + "</span>",
            showarrow=False,
            font=dict(size=10, color=GRI),
            xanchor="left", yanchor="bottom",
            bgcolor="rgba(19, 23, 34, 0.85)",
            bordercolor="rgba(255,255,255,0.08)",
            borderwidth=1, borderpad=6
        )
    
    # Sağ alt "BorsaSinyal Pro" logosu
    fig.add_annotation(
        text="BorsaSinyal Pro • TradingView",
        xref="paper", yref="paper", x=1.0, y=0.0, showarrow=False,
        font=dict(size=8, color="rgba(120,123,134,0.4)"),
        xanchor="right", yanchor="bottom"
    )
    
    # HTML'e çevir
    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'autoScale2d'],
            'modeBarButtonsToAdd': ['drawline', 'drawrect', 'eraseshape'],
            'scrollZoom': True,
            'responsive': True,
        }
    )
    
    return html


def _alt_gosterge_ekle(fig, data, gosterge, row):
    """Alt gösterge ekleme (MACD/RSI/Stochastic/ADX/CCI/Williams %R/MFI/ROC/Momentum/OBV/ATR)."""
    close = data["Close"].squeeze()
    idx = data.index
    
    TV_MAVI = "#2962FF"
    TV_TURUNCU = "#FF6D00"
    TV_MOR = "#7e57c2"
    TV_YESIL = "#089981"
    TV_KIRMIZI = "#f23645"
    TV_GRI = "#787b86"
    
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.03)", row=row, col=1)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.03)", row=row, col=1)
    
    if gosterge == "MACD":
        if "MACD" in data.columns:
            hist = data["MACD_Hist"]
            renkler = []
            for i in range(len(hist)):
                val = float(hist.iloc[i])
                prev = float(hist.iloc[i-1]) if i > 0 else 0.0
                if val >= 0:
                    renkler.append(TV_YESIL if val >= prev else "rgba(8, 153, 129, 0.3)")
                else:
                    renkler.append(TV_KIRMIZI if val <= prev else "rgba(242, 54, 69, 0.3)")
            
            fig.add_trace(go.Bar(
                x=idx, y=hist, marker_color=renkler,
                name="MACD Hist", opacity=1.0,
                hovertemplate="MACD Hist: %{y:.4f}<extra></extra>"
            ), row=row, col=1)
            
            if "MACD" in data.columns:
                fig.add_trace(go.Scatter(
                    x=idx, y=data["MACD"], mode="lines",
                    name="MACD", line=dict(color=TV_MAVI, width=1.5),
                    hovertemplate="MACD: %{y:.4f}<extra></extra>"
                ), row=row, col=1)
            if "MACD_Signal" in data.columns:
                fig.add_trace(go.Scatter(
                    x=idx, y=data["MACD_Signal"], mode="lines",
                    name="Sinyal", line=dict(color=TV_TURUNCU, width=1.5),
                    hovertemplate="Sinyal: %{y:.4f}<extra></extra>"
                ), row=row, col=1)
            fig.add_hline(y=0, line_color=TV_GRI, line_width=0.5, opacity=0.5, row=row, col=1)
    
    elif gosterge == "RSI":
        if "RSI" in data.columns:
            fig.add_hrect(y0=30, y1=70, fillcolor="rgba(126, 87, 194, 0.05)", line_width=0, row=row, col=1)
            fig.add_hrect(y0=0, y1=30, fillcolor="rgba(8, 153, 129, 0.03)", line_width=0, row=row, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="rgba(242, 54, 69, 0.03)", line_width=0, row=row, col=1)
            
            fig.add_trace(go.Scatter(
                x=idx, y=data["RSI"], mode="lines",
                name="RSI", line=dict(color=TV_MOR, width=1.5),
                fill="tozeroy", fillcolor="rgba(126, 87, 194, 0.1)",
                hovertemplate="RSI: %{y:.2f}<extra></extra>"
            ), row=row, col=1)
            fig.add_hline(y=70, line_color=TV_KIRMIZI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=30, line_color=TV_YESIL, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=50, line_color=TV_GRI, line_width=0.5, line_dash="dot", opacity=0.3, row=row, col=1)
            fig.update_yaxes(range=[0, 100], row=row, col=1)
    
    elif gosterge == "Stochastic":
        if "Stoch_K" in data.columns:
            fig.add_hrect(y0=20, y1=80, fillcolor="rgba(41, 98, 255, 0.05)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(
                x=idx, y=data["Stoch_K"], mode="lines",
                name="%K", line=dict(color=TV_MAVI, width=1.5),
                hovertemplate="%K: %{y:.2f}<extra></extra>"
            ), row=row, col=1)
            if "Stoch_D" in data.columns:
                fig.add_trace(go.Scatter(
                    x=idx, y=data["Stoch_D"], mode="lines",
                    name="%D", line=dict(color=TV_TURUNCU, width=1.5, dash="dot"),
                    hovertemplate="%D: %{y:.2f}<extra></extra>"
                ), row=row, col=1)
            fig.add_hline(y=80, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=20, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.update_yaxes(range=[0, 100], row=row, col=1)
    
    elif gosterge == "ADX":
        if "ADX" in data.columns:
            fig.add_trace(go.Scatter(
                x=idx, y=data["ADX"], mode="lines",
                name="ADX", line=dict(color=TV_TURUNCU, width=1.5),
                fill="tozeroy", fillcolor="rgba(255,109,0,0.08)",
                hovertemplate="ADX: %{y:.1f}<extra></extra>"
            ), row=row, col=1)
            if "DI_Pos" in data.columns:
                fig.add_trace(go.Scatter(
                    x=idx, y=data["DI_Pos"], mode="lines",
                    name="+DI", line=dict(color=TV_YESIL, width=1),
                    hovertemplate="+DI: %{y:.1f}<extra></extra>"
                ), row=row, col=1)
            if "DI_Neg" in data.columns:
                fig.add_trace(go.Scatter(
                    x=idx, y=data["DI_Neg"], mode="lines",
                    name="-DI", line=dict(color=TV_KIRMIZI, width=1),
                    hovertemplate="-DI: %{y:.1f}<extra></extra>"
                ), row=row, col=1)
            fig.add_hline(y=25, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5,
                         annotation_text="Güçlü Trend", annotation_font=dict(size=8, color=TV_GRI), row=row, col=1)
    
    elif gosterge == "CCI":
        if "CCI" in data.columns:
            fig.add_hrect(y0=-100, y1=100, fillcolor="rgba(126, 87, 194, 0.04)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(
                x=idx, y=data["CCI"], mode="lines",
                name="CCI", line=dict(color=TV_MOR, width=1.5),
                hovertemplate="CCI: %{y:.1f}<extra></extra>"
            ), row=row, col=1)
            fig.add_hline(y=100, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=-100, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
    
    elif gosterge == "Williams %R":
        if "Williams_R" in data.columns:
            fig.add_hrect(y0=-80, y1=-20, fillcolor="rgba(126, 87, 194, 0.04)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(
                x=idx, y=data["Williams_R"], mode="lines",
                name="W%R", line=dict(color=TV_MOR, width=1.5),
                fill="tozeroy", fillcolor="rgba(126,87,194,0.08)",
                hovertemplate="Williams %R: %{y:.1f}<extra></extra>"
            ), row=row, col=1)
            fig.add_hline(y=-20, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=-80, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.update_yaxes(range=[-100, 0], row=row, col=1)
    
    elif gosterge == "MFI":
        if "MFI" in data.columns:
            fig.add_hrect(y0=20, y1=80, fillcolor="rgba(8, 153, 129, 0.04)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(
                x=idx, y=data["MFI"], mode="lines",
                name="MFI", line=dict(color=TV_YESIL, width=1.5),
                fill="tozeroy", fillcolor="rgba(8,153,129,0.08)",
                hovertemplate="MFI: %{y:.1f}<extra></extra>"
            ), row=row, col=1)
            fig.add_hline(y=80, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=20, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.update_yaxes(range=[0, 100], row=row, col=1)
    
    elif gosterge == "Momentum":
        if "Momentum" in data.columns:
            fig.add_trace(go.Scatter(
                x=idx, y=data["Momentum"], mode="lines",
                name="Mom", line=dict(color=TV_TURUNCU, width=1.5),
                fill="tozeroy", fillcolor="rgba(255,109,0,0.08)",
                hovertemplate="Momentum: %{y:.4f}<extra></extra>"
            ), row=row, col=1)
            fig.add_hline(y=0, line_color=TV_GRI, line_width=0.5, opacity=0.5, row=row, col=1)
    
    elif gosterge == "OBV":
        if "OBV" in data.columns:
            fig.add_trace(go.Scatter(
                x=idx, y=data["OBV"], mode="lines",
                name="OBV", line=dict(color=TV_MAVI, width=1.5),
                fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
                hovertemplate="OBV: %{y:,.0f}<extra></extra>"
            ), row=row, col=1)
    
    elif gosterge == "ATR":
        if "ATR" in data.columns:
            fig.add_trace(go.Scatter(
                x=idx, y=data["ATR"], mode="lines",
                name="ATR", line=dict(color="#9c27b0", width=1.5),
                fill="tozeroy", fillcolor="rgba(156,39,176,0.08)",
                hovertemplate="ATR: %{y:.4f}<extra></extra>"
            ), row=row, col=1)
    
    elif gosterge == "Boğa/Ayı Gücü":
        if "Bull_Power" in data.columns:
            fig.add_trace(go.Bar(
                x=idx, y=data["Bull_Power"], name="Boğa",
                marker_color="rgba(8, 153, 129, 0.6)",
                hovertemplate="Boğa Gücü: %{y:.4f}<extra></extra>"
            ), row=row, col=1)
        if "Bear_Power" in data.columns:
            fig.add_trace(go.Bar(
                x=idx, y=data["Bear_Power"], name="Ayı",
                marker_color="rgba(242, 54, 69, 0.6)",
                hovertemplate="Ayı Gücü: %{y:.4f}<extra></extra>"
            ), row=row, col=1)
        fig.add_hline(y=0, line_color=TV_GRI, line_width=1, opacity=0.5, row=row, col=1)


# ══════════════════════════════════════════════════════════════════
#  VERİ ÇEKME + HTML OLUŞTURMA (KOLAY KULLANIM)
# ══════════════════════════════════════════════════════════════════

def veri_cek_ve_grafik_olustur(
    sembol: str,
    period: str = "6mo",
    interval: str = "1d",
    gosterge_alt: str = "MACD",
    gosterge_alt2: str = "RSI",
    overlay_list: list = None,
    output_dir: str = None,
    otomatik_ac: bool = False,
) -> str:
    """
    Tek fonksiyonda: Yahoo Finance'den veri çek → TradingView grafiği oluştur → HTML kaydet.
    
    Parametreler:
        sembol: Hisse sembolü (örn: "THYAO.IS", "AAPL")
        period: Veri periyodu ("1mo", "3mo", "6mo", "1y", "2y", "5y", "max")
        interval: Mum aralığı ("1d", "1wk", "1mo")
        gosterge_alt, gosterge_alt2: Alt göstergeler
        overlay_list: Fiyat üstü göstergeler
        output_dir: HTML çıktı dizini (None = Desktop/borsa-sinyal)
        otomatik_ac: True ise tarayıcıda otomatik açar
    
    Returns:
        HTML dosya yolu
    """
    if overlay_list is None:
        overlay_list = ["MA20", "MA50", "BB"]
    
    # Yahoo Finance'den veri çek
    ticker = yf.Ticker(sembol)
    data = ticker.history(period=period, interval=interval)
    
    if data.empty:
        raise ValueError(f"⚠️ {sembol} için veri bulunamadı!")
    
    # Teknik göstergeleri hesapla
    data = _teknik_gostergeleri_hesapla(data)
    
    # HTML oluştur
    html = tradingview_grafik_html(
        data=data,
        sembol=sembol,
        gosterge_alt=gosterge_alt,
        gosterge_alt2=gosterge_alt2,
        overlay_list=overlay_list,
        show_volume=True,
        formasyon_ciz=True,
        destek_direnc=True,
        fibonacci_ciz=True,
    )
    
    # Kaydet
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Eski HTML dosyalarını temizle (1 günden eski olanları sil)
    import glob, time
    for f in glob.glob(os.path.join(output_dir, "*.html")):
        if os.stat(f).st_mtime < time.time() - 86400:
            try: os.remove(f)
            except: pass

    safe_sembol = sembol.replace(".", "_").replace("^", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dosya_adi = f"grafik_{safe_sembol}_{timestamp}.html"
    dosya_yolu = os.path.join(output_dir, dosya_adi)    
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ Grafik kaydedildi: {dosya_yolu}")
    
    if otomatik_ac:
        webbrowser.open(f"file://{os.path.abspath(dosya_yolu)}")
    
    return dosya_yolu


def _teknik_gostergeleri_hesapla(df: pd.DataFrame) -> pd.DataFrame:
    """Eksik teknik göstergeleri hesaplar (grafik.py'deki hesaplamalar gibi)."""
    data = df.copy()
    close = data['Close'].squeeze()
    high = data['High'].squeeze()
    low = data['Low'].squeeze()
    volume = data['Volume'].squeeze() if 'Volume' in data.columns else pd.Series(0, index=data.index)
    
    # Hareketli ortalamalar
    if 'MA20' not in data.columns:
        data['MA20'] = close.rolling(window=20).mean()
    if 'MA50' not in data.columns:
        data['MA50'] = close.rolling(window=50).mean()
    if 'MA200' not in data.columns:
        data['MA200'] = close.rolling(window=200).mean()
    if 'EMA9' not in data.columns:
        data['EMA9'] = close.ewm(span=9, adjust=False).mean()
    if 'EMA21' not in data.columns:
        data['EMA21'] = close.ewm(span=21, adjust=False).mean()
    
    # Bollinger Bands
    if 'BB_upper' not in data.columns:
        ma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        data['BB_upper'] = ma20 + 2 * std20
        data['BB_middle'] = ma20
        data['BB_lower'] = ma20 - 2 * std20
    
    # MACD
    if 'MACD' not in data.columns:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        data['MACD'] = ema12 - ema26
        data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        data['MACD_Hist'] = data['MACD'] - data['MACD_Signal']
    
    # RSI
    if 'RSI' not in data.columns:
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        data['RSI'] = 100 - (100 / (1 + rs))
    
    # PSAR
    if 'PSAR' not in data.columns:
        try:
            af = 0.02
            max_af = 0.2
            psar = close.copy()
            trend = pd.Series(1, index=data.index)
            ep = high.iloc[0]
            af_val = af
            
            for i in range(1, len(data)):
                if trend.iloc[i-1] == 1:  # yükselen trend
                    psar.iloc[i] = psar.iloc[i-1] + af_val * (ep - psar.iloc[i-1])
                    if high.iloc[i] > ep:
                        ep = high.iloc[i]
                        af_val = min(af_val + af, max_af)
                    if low.iloc[i] < psar.iloc[i]:
                        trend.iloc[i] = -1
                        psar.iloc[i] = ep
                        ep = low.iloc[i]
                        af_val = af
                else:  # alçalan trend
                    psar.iloc[i] = psar.iloc[i-1] - af_val * (psar.iloc[i-1] - ep)
                    if low.iloc[i] < ep:
                        ep = low.iloc[i]
                        af_val = min(af_val + af, max_af)
                    if high.iloc[i] > psar.iloc[i]:
                        trend.iloc[i] = 1
                        psar.iloc[i] = ep
                        ep = high.iloc[i]
                        af_val = af
            
            data['PSAR'] = psar
            data['PSAR_Trend'] = trend
        except:
            pass
    
    # Stochastic
    if 'Stoch_K' not in data.columns:
        low14 = low.rolling(window=14).min()
        high14 = high.rolling(window=14).max()
        data['Stoch_K'] = 100 * ((close - low14) / (high14 - low14).replace(0, 0.001))
        data['Stoch_D'] = data['Stoch_K'].rolling(window=3).mean()
    
    # ADX
    if 'ADX' not in data.columns:
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        pos_di = 100 * (up_move.where((up_move > down_move) & (up_move > 0), 0).rolling(14).mean() / atr.replace(0, 0.001))
        neg_di = 100 * (down_move.where((down_move > up_move) & (down_move > 0), 0).rolling(14).mean() / atr.replace(0, 0.001))
        
        dx = 100 * ((pos_di - neg_di).abs() / (pos_di + neg_di).replace(0, 0.001))
        data['ADX'] = dx.rolling(window=14).mean()
        data['DI_Pos'] = pos_di
        data['DI_Neg'] = neg_di
    
    # CCI
    if 'CCI' not in data.columns:
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(window=20).mean()
        md = tp.rolling(window=20).apply(lambda x: np.abs(x - x.mean()).mean())
        data['CCI'] = (tp - sma_tp) / (0.015 * md.replace(0, 0.001))
    
    # Williams %R
    if 'Williams_R' not in data.columns:
        high14 = high.rolling(window=14).max()
        low14 = low.rolling(window=14).min()
        data['Williams_R'] = -100 * ((high14 - close) / (high14 - low14).replace(0, 0.001))
    
    # ATR
    if 'ATR' not in data.columns:
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        data['ATR'] = tr.rolling(window=14).mean()
    
    # OBV
    if 'OBV' not in data.columns:
        obv = (volume * ((close.diff() > 0).astype(int) * 2 - 1)).cumsum()
        data['OBV'] = obv
    
    # Momentum
    if 'Momentum' not in data.columns:
        data['Momentum'] = close - close.shift(10)
    
    # MFI
    if 'MFI' not in data.columns:
        tp = (high + low + close) / 3
        mf = tp * volume
        pos_mf = mf.where(tp > tp.shift(), 0).rolling(window=14).sum()
        neg_mf = mf.where(tp < tp.shift(), 0).rolling(window=14).sum()
        mfr = pos_mf / neg_mf.replace(0, 0.001)
        data['MFI'] = 100 - (100 / (1 + mfr))
    
    # ROC
    if 'ROC' not in data.columns:
        data['ROC'] = ((close - close.shift(12)) / close.shift(12).replace(0, 0.001)) * 100
    
    # Bull/Bear Power
    if 'Bull_Power' not in data.columns:
        ema13 = close.ewm(span=13, adjust=False).mean()
        data['Bull_Power'] = high - ema13
        data['Bear_Power'] = low - ema13
    
    # VWAP
    if 'VWAP' not in data.columns:
        data['VWAP'] = (volume * (high + low + close) / 3).rolling(window=20).sum() / volume.rolling(window=20).sum().replace(0, 0.001)
    
    return data


def formasyon_ozeti_al(data: pd.DataFrame) -> List[Dict]:
    """Grafikte tespit edilen formasyonların özet listesini döndürür."""
    cizimler = _formasyon_cizimleri(data)
    formasyonlar = []
    
    for key, val in cizimler.items():
        if key in ('destekler', 'direncler', 'fibonacci'):
            continue
        formasyonlar.append({
            'isim': val.get('label', key),
            'tip': val.get('tip', 'info'),
            'renk': val.get('renk', BEYAZ),
        })
    
    return formasyonlar


# ══════════════════════════════════════════════════════════════════
#  TRADINGVIEW WIDGET (GERÇEK TV) + FORMASYON OVERLAY
# ══════════════════════════════════════════════════════════════════

def tradingview_widget_html(
    sembol: str,
    exchange: str = "BIST",
    theme: str = "dark",
    width: str = "100%",
    height: int = 750,
    formasyonlar: Optional[list] = None,
    analiz_notlari: Optional[list] = None,
) -> str:
    """
    Gerçek TradingView widget'ı + altında formasyon/analiz paneli ile
    profesyonel bir grafik sayfası oluşturur.
    
    Parametreler:
        sembol: Hisse sembolü (örn: "THYAO", "AAPL", "BTCUSDT")
        exchange: Borsa adı ("BIST", "NASDAQ", "BITSTAMP" vb.)
        theme: "dark" veya "light"
        width, height: Widget boyutları
        formasyonlar: Tespit edilen formasyon listesi
        analiz_notlari: Ek analiz notları
    
    Returns:
        HTML string (TradingView widget + alt panel)
    """
    if formasyonlar is None:
        formasyonlar = []
    if analiz_notlari is None:
        analiz_notlari = []
    
    # Sembol dönüşümleri
    safe_sym = sembol.replace(".IS", "")
    
    # Borsa belirleme
    if exchange == "BIST" or sembol.endswith(".IS"):
        tv_symbol = f"BIST:{safe_sym}"
    elif exchange == "NASDAQ" or exchange == "US":
        tv_symbol = f"NASDAQ:{safe_sym}"
    elif exchange == "BITSTAMP" or "USDT" in sembol or "BTC" in sembol:
        tv_symbol = f"BITSTAMP:{safe_sym}"
    else:
        tv_symbol = f"{exchange}:{safe_sym}" if exchange else safe_sym
    
    # Formasyon HTML'i
    formasyon_html = ""
    if formasyonlar:
        formasyon_kartlari = ""
        for f in formasyonlar:
            renk = f.get('renk', '#787b86')
            isim = f.get('isim', f.get('label', ''))
            tip = f.get('tip', 'info')
            ikon = {"success": "✅", "error": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(tip, "ℹ️")
            formasyon_kartlari += f"""
            <div style="display:flex;align-items:center;gap:10px;background:rgba(30,34,45,0.8);
                        border-left:3px solid {renk};border-radius:6px;padding:8px 14px;margin-bottom:6px;">
                <span>{ikon}</span>
                <span style="color:{renk};font-weight:600;">{isim}</span>
            </div>"""
        
        formasyon_html = f"""
        <div style="margin-top:16px;">
            <div style="font-family:monospace;font-size:11px;color:#f0c040;letter-spacing:2px;
                        margin-bottom:12px;display:flex;align-items:center;gap:10px;">
                <span style="width:20px;height:2px;background:#f0c040;display:inline-block;border-radius:1px;"></span>
                📊 TESPİT EDİLEN FORMASYONLAR
                <span style="flex:1;height:1px;background:linear-gradient(90deg,rgba(30,51,85,0.5),transparent);"></span>
            </div>
            {formasyon_kartlari}
        </div>"""
    
    # Analiz notları HTML
    analiz_html = ""
    if analiz_notlari:
        notlar = "".join([f"<li style='padding:4px 0;color:#d1d4dc;font-size:13px;'>{n}</li>" for n in analiz_notlari])
        analiz_html = f"""
        <div style="margin-top:16px;">
            <div style="font-family:monospace;font-size:11px;color:#4db8ff;letter-spacing:2px;
                        margin-bottom:12px;display:flex;align-items:center;gap:10px;">
                <span style="width:20px;height:2px;background:#4db8ff;display:inline-block;border-radius:1px;"></span>
                📋 TEKNİK ANALİZ NOTLARI
                <span style="flex:1;height:1px;background:linear-gradient(90deg,rgba(30,51,85,0.5),transparent);"></span>
            </div>
            <ul style="margin:0;padding-left:20px;">{notlar}</ul>
        </div>"""
    
    # Tarih
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_sym} · BorsaSinyal TradingView</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    background:#0a1222;
    color:#d1d4dc;
    font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    padding:12px;
    overflow-x:hidden;
}}
.tv-container {{
    background:#131722;
    border-radius:12px;
    overflow:hidden;
    border:1px solid rgba(30,51,85,0.3);
    box-shadow:0 8px 32px rgba(0,0,0,0.4);
}}
.header {{
    display:flex;align-items:center;gap:16px;
    padding:14px 20px;
    background:linear-gradient(135deg,#0e182c,#131722);
    border-bottom:1px solid rgba(30,51,85,0.3);
}}
.header h1 {{
    font-size:18px;font-weight:800;letter-spacing:-0.5px;
    background:linear-gradient(135deg,#eef2f7,#f0c040);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}}
.header .time {{
    font-family:monospace;font-size:11px;color:#787b86;letter-spacing:1px;
    margin-left:auto;
}}
.header .live {{
    display:inline-flex;align-items:center;gap:6px;
    font-family:monospace;font-size:10px;color:#089981;letter-spacing:1px;
}}
.header .live::before {{
    content:'';width:8px;height:8px;background:#089981;border-radius:50%;
    box-shadow:0 0 8px rgba(8,153,129,0.6);
}}
.panel {{
    display:grid;
    grid-template-columns: 1fr 360px;
    gap:16px;
    margin-top:12px;
}}
@media (max-width:900px) {{
    .panel {{ grid-template-columns: 1fr; }}
}}
.sidebar {{
    background:rgba(14,24,44,0.6);
    border-radius:12px;
    padding:20px;
    border:1px solid rgba(30,51,85,0.2);
    max-height:800px;
    overflow-y:auto;
}}
.sidebar::-webkit-scrollbar {{ width:4px; }}
.sidebar::-webkit-scrollbar-thumb {{ background:rgba(30,51,85,0.5); border-radius:2px; }}
.footer {{
    text-align:center;padding:16px;margin-top:12px;
    font-family:monospace;font-size:10px;color:rgba(120,123,134,0.4);letter-spacing:1px;
}}
</style>
</head>
<body>

<div class="header">
    <h1>📊 {safe_sym} · TRADINGVIEW</h1>
    <span class="live">LIVE</span>
    <span class="time">{now}</span>
</div>

<div class="panel">
    <div class="tv-container" style="min-height:{height}px;">
        <!-- TradingView Widget BEGIN -->
        <div class="tradingview-widget-container" style="height:{height}px;width:100%;">
            <div id="tvchart" style="height:{height}px;width:100%;"></div>
            <script type="text/javascript" src="https://s3.tradingview.com/tv.js">
            </script>
            <script type="text/javascript">
            new TradingView.widget({{
                "container_id": "tvchart",
                "width": "100%",
                "height": "{height}",
                "symbol": "{tv_symbol}",
                "interval": "D",
                "timezone": "Europe/Istanbul",
                "theme": "{theme}",
                "style": "1",
                "locale": "tr_TR",
                "toolbar_bg": "#131722",
                "enable_publishing": false,
                "allow_symbol_change": true,
                "save_image": false,
                "studies": [
                    "RSI@tv-basicstudies",
                    "MACD@tv-basicstudies",
                    "Volume@tv-basicstudies"
                ],
                "studies_overrides": {{
                    "volume.volume.color.0": "#f23645",
                    "volume.volume.color.1": "#089981"
                }},
                "overrides": {{
                    "mainSeriesProperties.candleStyle.upColor": "#089981",
                    "mainSeriesProperties.candleStyle.downColor": "#f23645",
                    "mainSeriesProperties.candleStyle.drawWick": true,
                    "mainSeriesProperties.candleStyle.drawBody": true,
                    "mainSeriesProperties.candleStyle.borderUpColor": "#089981",
                    "mainSeriesProperties.candleStyle.borderDownColor": "#f23645",
                    "mainSeriesProperties.candleStyle.wickUpColor": "#089981",
                    "mainSeriesProperties.candleStyle.wickDownColor": "#f23645",
                    "paneProperties.background": "#131722",
                    "paneProperties.vertGridProperties.color": "rgba(255,255,255,0.04)",
                    "paneProperties.horzGridProperties.color": "rgba(255,255,255,0.04)",
                    "scalesProperties.textColor": "#787b86",
                    "scalesProperties.lineColor": "rgba(255,255,255,0.08)",
                }},
                "disabled_features": [
                    "header_symbol_search", "symbol_search_hot_key",
                    "header_volume", "header_saveload",
                    "header_indicators", "header_compare",
                    "header_chart_type", "header_undo_redo"
                ],
                "enabled_features": ["study_templates"],
                "loading_screen": {{ "backgroundColor": "#131722" }},
            }});
            </script>
        </div>
        <!-- TradingView Widget END -->
    </div>
    
    <div class="sidebar">
        <div style="font-family:monospace;font-size:10px;color:#787b86;letter-spacing:2px;
                    margin-bottom:16px;display:flex;align-items:center;gap:10px;">
            <span style="width:20px;height:2px;background:#f0c040;display:inline-block;border-radius:1px;"></span>
            BORSASİNYAL PRO · ANALİZ
            <span style="flex:1;height:1px;background:linear-gradient(90deg,rgba(30,51,85,0.5),transparent);"></span>
        </div>
        
        <!-- Hisse bilgisi -->
        <div style="background:rgba(30,34,45,0.5);border-radius:8px;padding:16px;margin-bottom:16px;
                    border:1px solid rgba(30,51,85,0.15);">
            <div style="font-family:monospace;font-size:22px;font-weight:800;color:#eef2f7;">
                {safe_sym}
            </div>
            <div style="font-family:monospace;font-size:11px;color:#787b86;margin-top:4px;">
                {exchange} · {sembol}
            </div>
        </div>
        
        <!-- Yardım -->
        <div style="background:rgba(240,192,64,0.06);border-radius:8px;padding:14px;margin-bottom:16px;
                    border:1px solid rgba(240,192,64,0.12);">
            <div style="font-family:monospace;font-size:10px;color:#f0c040;margin-bottom:6px;">
                💡 İPUÇLARI
            </div>
            <ul style="margin:0;padding-left:16px;font-size:11px;color:#8a9bb5;">
                <li style="margin-bottom:4px;">📈 Fare tekerleği ile yakınlaşma</li>
                <li style="margin-bottom:4px;">🔄 Sağ tık + sürükle = kaydırma</li>
                <li style="margin-bottom:4px;">📊 Alt göstergeler: RSI, MACD, Hacim</li>
                <li>⚙️ Üst menüden çizim araçları ekleyin</li>
            </ul>
        </div>
        
        {formasyon_html}
        {analiz_html}
    </div>
</div>

<div class="footer">
    BorsaSinyal Pro Terminal · TradingView Widget · {now}
</div>

</body>
</html>"""
    
    return html


def tradingview_veri_cek_ve_kaydet(
    sembol: str,
    exchange: str = "BIST",
    period: str = "6mo",
    interval: str = "1d",
    output_dir: str = None,
    otomatik_ac: bool = False,
) -> str:
    """
    TradingView widget'ı kullanarak profesyonel grafik sayfası oluşturur.
    Formasyon analizi de ekler.
    
    Parametreler:
        sembol: Hisse sembolü (örn: "THYAO.IS", "AAPL")
        exchange: Borsa ("BIST", "NASDAQ", vb.)
        period: Veri periyodu (formasyon analizi için)
        interval: Mum aralığı
        output_dir: Çıktı dizini
        otomatik_ac: True ise tarayıcıda açar
    
    Returns:
        HTML dosya yolu
    """
    # Veri çek (formasyon analizi için)
    try:
        ticker = yf.Ticker(sembol)
        data = ticker.history(period=period, interval=interval)
        if not data.empty:
            data = _teknik_gostergeleri_hesapla(data)
            formasyonlar = formasyon_ozeti_al(data)
        else:
            formasyonlar = []
    except:
        formasyonlar = []
    
    # Analiz notları
    analiz_notlari = []
    if formasyonlar:
        for f in formasyonlar:
            analiz_notlari.append(f"📌 {f['isim']} formasyonu tespit edildi")
    
    # Borsa belirleme
    safe_sym = sembol.replace(".IS", "")
    if exchange == "BIST" or sembol.endswith(".IS"):
        pass  # Varsayılan
    elif "." in sembol and not sembol.endswith(".IS"):
        parts = sembol.split(".")
        if len(parts) == 2:
            exchange = parts[1]
    
    html = tradingview_widget_html(
        sembol=sembol,
        exchange=exchange,
        theme="dark",
        height=750,
        formasyonlar=formasyonlar,
        analiz_notlari=analiz_notlari,
    )
    
    # Kaydet
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    os.makedirs(output_dir, exist_ok=True)
    safe_sym_file = sembol.replace(".", "_").replace("^", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dosya_adi = f"tv_{safe_sym_file}_{timestamp}.html"
    dosya_yolu = os.path.join(output_dir, dosya_adi)
    
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ TradingView grafik sayfası: {dosya_yolu}")
    print(f"   • {len(formasyonlar)} formasyon tespit edildi")
    
    if otomatik_ac:
        webbrowser.open(f"file://{os.path.abspath(dosya_yolu)}")
    
    return dosya_yolu


# ══════════════════════════════════════════════════════════════════
#  BAĞIMSIZ ÇALIŞTIRMA (TEST)
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    
    print("═" * 60)
    print("📊 BorsaSinyal · TradingView Grafik Oluşturucu")
    print("═" * 60)
    
    mode = input("Mod (1=Plotly HTML, 2=TradingView Widget): ").strip() or "2"
    
    sembol = input("Hisse sembolü (örn: THYAO.IS): ").strip() or "THYAO.IS"
    
    print(f"\n⏳ {sembol} için grafik oluşturuluyor...")
    try:
        if mode == "1":
            dosya = veri_cek_ve_grafik_olustur(
                sembol=sembol, period="6mo", interval="1d",
                gosterge_alt="MACD", gosterge_alt2="RSI",
                overlay_list=["MA20", "MA50", "BB"],
                otomatik_ac=True,
            )
        else:
            dosya = tradingview_veri_cek_ve_kaydet(
                sembol=sembol, exchange="BIST",
                period="6mo", interval="1d",
                otomatik_ac=True,
            )
        print(f"\n✅ Grafik hazır: {dosya}")
        print("🌐 Tarayıcıda açılıyor...")
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
