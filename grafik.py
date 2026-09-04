import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple

# ──   RENK PALETİ (DARK MODE - TRADINGVIEW KLONU) ──────────
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
GRAYISH   = "#787b86"
CYAN      = "#00bcd4"
PEMBE     = "#e91e63"
LACIVERT  = "#1e3355"

# ── YARDIMCI FONKSİYONLAR ──────────────────────────────────

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


def _kumele_ve_ortalama(seviyeler: List[float], tolerans: float = 0.01) -> List[float]:
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
                       max_seviye: int = 6) -> Tuple[List[float], List[float]]:
    """Otomatik destek ve direnç seviyelerini bulur."""
    peaks, troughs = _find_pivot_points(high, low, window=5)
    
    destek = [float(low.iloc[i]) for i in troughs]
    direnc = [float(high.iloc[i]) for i in peaks]
    
    # Son kapanışa yakın olanları filtrele
    son_fiyat = float(close.iloc[-1])
    fiyat_araligi = float(high.max() - low.min())
    
    destek = [s for s in destek if s < son_fiyat and (son_fiyat - s) / son_fiyat < 0.15]
    direnc = [r for r in direnc if r > son_fiyat and (r - son_fiyat) / son_fiyat < 0.15]
    
    # Kümele
    destek = _kumele_ve_ortalama(destek, tolerans=0.02)[:max_seviye]
    direnc = _kumele_ve_ortalama(direnc, tolerans=0.02)[:max_seviye]
    
    return destek, direnc


def _trend_cizgileri_bul(high: pd.Series, low: pd.Series, close: pd.Series, 
                          index: pd.Index) -> Dict:
    """Yükselen ve alçalan trend çizgilerini bulur."""
    sonuc = {'yukselen': None, 'alcalan': None}
    
    peaks, troughs = _find_pivot_points(high, low, window=3)
    
    # Yükselen trend: artan dipler
    if len(troughs) >= 2:
        son_dipler = [(troughs[-2], float(low.iloc[troughs[-2]])),
                      (troughs[-1], float(low.iloc[troughs[-1]]))]
        if son_dipler[1][1] > son_dipler[0][1]:
            sonuc['yukselen'] = {
                'baslangic': index[son_dipler[0][0]],
                'bitis': index[son_dipler[1][0]],
                'bas_deger': son_dipler[0][1],
                'bit_deger': son_dipler[1][1],
                'tip': 'yukselen'
            }
    
    # Alçalan trend: azalan tepeler
    if len(peaks) >= 2:
        son_tepeler = [(peaks[-2], float(high.iloc[peaks[-2]])),
                       (peaks[-1], float(high.iloc[peaks[-1]]))]
        if son_tepeler[1][1] < son_tepeler[0][1]:
            sonuc['alcalan'] = {
                'baslangic': index[son_tepeler[0][0]],
                'bitis': index[son_tepeler[1][0]],
                'bas_deger': son_tepeler[0][1],
                'bit_deger': son_tepeler[1][1],
                'tip': 'alcalan'
            }
    
    return sonuc


def _fibonacci_seviyeleri(dip: float, tepe: float) -> Dict[str, float]:
    """Fibonacci retracement seviyelerini hesaplar."""
    fark = tepe - dip
    return {
        '0.0% (Dip)': dip,
        '23.6%': tepe - 0.236 * fark,
        '38.2%': tepe - 0.382 * fark,
        '50.0%': tepe - 0.5 * fark,
        '61.8%': tepe - 0.618 * fark,
        '78.6%': tepe - 0.786 * fark,
        '100.0% (Tepe)': tepe,
        '127.2%': tepe + 0.272 * fark,
        '161.8%': tepe + 0.618 * fark,
    }


def _formasyon_cizimleri(df: pd.DataFrame) -> Dict:
    """Grafiğe çizilebilecek formasyonları tespit eder ve koordinatlarını döndürür."""
    close = df['Close'].squeeze()
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    volume = df['Volume'].squeeze() if 'Volume' in df.columns else pd.Series(np.zeros(len(df)))
    idx = df.index
    n = len(df)
    
    cizimler = {}
    
    if n < 20:
        return cizimler
    
    # ── İKİLİ DİP (W) ──
    peaks, troughs = _find_pivot_points(high, low, window=5)
    if len(troughs) >= 2:
        son_2_dip = [float(low.iloc[troughs[-2]]), float(low.iloc[troughs[-1]])]
        dip_fark = abs(son_2_dip[0] - son_2_dip[1]) / max(son_2_dip[0], 0.01)
        if dip_fark < 0.03 and son_2_dip[0] < float(close.iloc[-1]) * 0.97:
            # İkili dip çizimi
            dip_indices = [troughs[-2], troughs[-1]]
            # Orta tepeyi bul
            aralik = low.iloc[dip_indices[0]:dip_indices[1]+1]
            orta_tepe_idx = aralik.idxmax()
            cizimler['ikili_dip'] = {
                'tip': 'success',
                'renk': YESIL,
                'indices': dip_indices,
                'seviye': np.mean(son_2_dip),
                'boyun': float(high.loc[orta_tepe_idx]),
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
                'tip': 'error',
                'renk': KIRMIZI,
                'indices': tepe_indices,
                'seviye': np.mean(son_2_tepe),
                'boyun': float(low.loc[orta_dip_idx]),
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
                'tip': 'error',
                'renk': KIRMIZI,
                'indices': son_3_tepe_idx,
                'sol_omuz': son_3_tepe[0],
                'bas': son_3_tepe[1],
                'sag_omuz': son_3_tepe[2],
                'boyun': boyun,
                'hedef': boyun - (son_3_tepe[1] - boyun),
                'label': 'Omuz-Baş-Omuz (OBO)'
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
                'tip': 'success',
                'renk': YESIL,
                'indices': son_3_dip_idx,
                'sol_omuz': son_3_dip[0],
                'bas': son_3_dip[1],
                'sag_omuz': son_3_dip[2],
                'boyun': boyun,
                'hedef': boyun + (boyun - son_3_dip[1]),
                'label': 'Ters OBO'
            }
    
    # ── YÜKSELEN ÜÇGEN ──
    if len(peaks) >= 3 and len(troughs) >= 3:
        son_tepeler = [float(high.iloc[i]) for i in peaks[-3:]]
        son_dipler = [float(low.iloc[i]) for i in troughs[-3:]]
        tepe_std = np.std(son_tepeler) / np.mean(son_tepeler) if np.mean(son_tepeler) > 0 else 0.1
        dip_egim = (son_dipler[-1] - son_dipler[0]) / max(son_dipler[0], 0.01) if len(son_dipler) >= 2 else 0
        if tepe_std < 0.03 and dip_egim > 0.01:
            cizimler['yukselen_ucgen'] = {
                'tip': 'success',
                'renk': YESIL,
                'direnc': np.mean(son_tepeler),
                'indices': [troughs[-1], peaks[-1]],
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
                'tip': 'error',
                'renk': KIRMIZI,
                'destek': np.mean(son_dipler),
                'indices': [peaks[-1], troughs[-1]],
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
            'dip_idx': dip_idx,
            'tepe_idx': fib_idx,
            'label': 'Fibonacci'
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
                'tip': 'warning',
                'renk': ALTIN,
                'ust': bb_ust,
                'alt': bb_alt,
                'orta': ma20,
                'label': '🔄 BB Sıkışması'
            }
    
    # ── DESTEK / DİRENÇ KÜMELERİ ──
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
            'baslangic': trend['yukselen']['baslangic'],
            'bitis': trend['yukselen']['bitis'],
            'bas_deger': trend['yukselen']['bas_deger'],
            'bit_deger': trend['yukselen']['bit_deger'],
            'label': '↗ Yükselen Trend'
        }
    if trend['alcalan']:
        cizimler['trend_alcalan'] = {
            'tip': 'error', 'renk': KIRMIZI,
            'baslangic': trend['alcalan']['baslangic'],
            'bitis': trend['alcalan']['bitis'],
            'bas_deger': trend['alcalan']['bas_deger'],
            'bit_deger': trend['alcalan']['bit_deger'],
            'label': '↘ Alçalan Trend'
        }
    
    return cizimler


def _cizimleri_ekle(fig: go.Figure, cizimler: Dict, data: pd.DataFrame):
    """Tespit edilen tüm formasyon ve seviyeleri grafiğe ekler."""
    idx = data.index
    
    # ── DESTEK / DİRENÇ ÇİZGİLERİ ──
    if 'destekler' in cizimler:
        for s in cizimler['destekler']['seviyeler']:
            fig.add_hline(y=s, line_color=cizimler['destekler']['renk'], 
                         line_width=0.8, line_dash="dash", opacity=0.5,
                         annotation_text=f"Destek {s:.2f}", 
                         annotation_position="bottom right",
                         annotation_font=dict(size=9, color=YESIL))
    
    if 'direncler' in cizimler:
        for r in cizimler['direncler']['seviyeler']:
            fig.add_hline(y=r, line_color=cizimler['direncler']['renk'],
                         line_width=0.8, line_dash="dash", opacity=0.5,
                         annotation_text=f"Direnç {r:.2f}",
                         annotation_position="top right",
                         annotation_font=dict(size=9, color=KIRMIZI))
    
    # ── TREND ÇİZGİLERİ ──
    if 'trend_yukselen' in cizimler:
        t = cizimler['trend_yukselen']
        fig.add_trace(go.Scatter(
            x=[t['baslangic'], t['bitis']],
            y=[t['bas_deger'], t['bit_deger']],
            mode="lines", line=dict(color=YESIL, width=1.5, dash="dash"),
            name="↗ Yükselen Trend", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
    
    if 'trend_alcalan' in cizimler:
        t = cizimler['trend_alcalan']
        fig.add_trace(go.Scatter(
            x=[t['baslangic'], t['bitis']],
            y=[t['bas_deger'], t['bit_deger']],
            mode="lines", line=dict(color=KIRMIZI, width=1.5, dash="dash"),
            name="↘ Alçalan Trend", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
    
    # ── İKİLİ DİP ──
    if 'ikili_dip' in cizimler:
        dd = cizimler['ikili_dip']
        dip_1_idx, dip_2_idx = dd['indices']
        # Dip noktalarını işaretle
        fig.add_trace(go.Scatter(
            x=[idx[dip_1_idx], idx[dip_2_idx]],
            y=[float(data['Low'].iloc[dip_1_idx]), float(data['Low'].iloc[dip_2_idx])],
            mode="markers", marker=dict(color=YESIL, size=12, symbol="circle", 
                                        line=dict(color="white", width=1)),
            name="İkili Dip", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        # Boyun çizgisi
        fig.add_hline(y=dd['boyun'], line_color=YESIL, line_width=1.5, 
                     line_dash="dot", opacity=0.6,
                     annotation_text=f"Boyun {dd['boyun']:.2f} → Hedef {dd['hedef']:.2f}",
                     annotation_position="bottom left",
                     annotation_font=dict(size=9, color=YESIL))
        # Hedef seviyesi
        fig.add_hline(y=dd['hedef'], line_color=YESIL, line_width=0.8,
                     line_dash="dashdot", opacity=0.4,
                     annotation_text=f"Hedef {dd['hedef']:.2f}",
                     annotation_position="top left",
                     annotation_font=dict(size=9, color=YESIL))
    
    # ── İKİLİ TEPE ──
    if 'ikili_tepe' in cizimler:
        dt = cizimler['ikili_tepe']
        tepe_1_idx, tepe_2_idx = dt['indices']
        fig.add_trace(go.Scatter(
            x=[idx[tepe_1_idx], idx[tepe_2_idx]],
            y=[float(data['High'].iloc[tepe_1_idx]), float(data['High'].iloc[tepe_2_idx])],
            mode="markers", marker=dict(color=KIRMIZI, size=12, symbol="circle",
                                        line=dict(color="white", width=1)),
            name="İkili Tepe", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        fig.add_hline(y=dt['boyun'], line_color=KIRMIZI, line_width=1.5,
                     line_dash="dot", opacity=0.6,
                     annotation_text=f"Boyun {dt['boyun']:.2f} → Hedef {dt['hedef']:.2f}",
                     annotation_position="top left",
                     annotation_font=dict(size=9, color=KIRMIZI))
        fig.add_hline(y=dt['hedef'], line_color=KIRMIZI, line_width=0.8,
                     line_dash="dashdot", opacity=0.4,
                     annotation_text=f"Hedef {dt['hedef']:.2f}",
                     annotation_position="bottom left",
                     annotation_font=dict(size=9, color=KIRMIZI))
    
    # ── OMOZ-BAŞ-OMUZ ──
    if 'obo' in cizimler:
        obo = cizimler['obo']
        indices = obo['indices']
        fig.add_trace(go.Scatter(
            x=list(idx[i] for i in indices),
            y=[obo['sol_omuz'], obo['bas'], obo['sag_omuz']],
            mode="markers", marker=dict(color=KIRMIZI, size=14, symbol="diamond",
                                        line=dict(color="white", width=1.5)),
            name="OBO", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        fig.add_hline(y=obo['boyun'], line_color=KIRMIZI, line_width=2,
                     line_dash="dot", opacity=0.7,
                     annotation_text=f"⚠ OBO Boyun {obo['boyun']:.2f}",
                     annotation_position="top left",
                     annotation_font=dict(size=10, color=KIRMIZI))
        if obo['hedef']:
            fig.add_hline(y=obo['hedef'], line_color=KIRMIZI, line_width=0.8,
                         line_dash="dashdot", opacity=0.3,
                         annotation_text=f"Hedef {obo['hedef']:.2f}",
                         annotation_position="bottom left",
                         annotation_font=dict(size=9, color=KIRMIZI))
    
    # ── TERS OBO ──
    if 'ters_obo' in cizimler:
        tobo = cizimler['ters_obo']
        indices = tobo['indices']
        fig.add_trace(go.Scatter(
            x=list(idx[i] for i in indices),
            y=[tobo['sol_omuz'], tobo['bas'], tobo['sag_omuz']],
            mode="markers", marker=dict(color=YESIL, size=14, symbol="diamond",
                                        line=dict(color="white", width=1.5)),
            name="Ters OBO", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        fig.add_hline(y=tobo['boyun'], line_color=YESIL, line_width=2,
                     line_dash="dot", opacity=0.7,
                     annotation_text=f"⚡ Ters OBO Boyun {tobo['boyun']:.2f}",
                     annotation_position="bottom left",
                     annotation_font=dict(size=10, color=YESIL))
    
    # ── YÜKSELEN ÜÇGEN ──
    if 'yukselen_ucgen' in cizimler:
        yt = cizimler['yukselen_ucgen']
        fig.add_hline(y=yt['direnc'], line_color=YESIL, line_width=1.2,
                     line_dash="dash", opacity=0.7,
                     annotation_text=f"▲ Yüks. Üçgen {yt['direnc']:.2f}",
                     annotation_position="top right",
                     annotation_font=dict(size=9, color=YESIL))
    
    # ── ALCALAN ÜÇGEN ──
    if 'alcalan_ucgen' in cizimler:
        at = cizimler['alcalan_ucgen']
        fig.add_hline(y=at['destek'], line_color=KIRMIZI, line_width=1.2,
                     line_dash="dash", opacity=0.7,
                     annotation_text=f"▼ Alç. Üçgen {at['destek']:.2f}",
                     annotation_position="bottom right",
                     annotation_font=dict(size=9, color=KIRMIZI))
    
    # ── BB SIKIŞMA ──
    if 'bb_sikisma' in cizimler:
        bb = cizimler['bb_sikisma']
        fig.add_hline(y=bb['ust'], line_color=ALTIN, line_width=0.8,
                     line_dash="dot", opacity=0.4,
                     annotation_text=f"BB Üst {bb['ust']:.2f}",
                     annotation_font=dict(size=8, color=ALTIN))
        fig.add_hline(y=bb['alt'], line_color=ALTIN, line_width=0.8,
                     line_dash="dot", opacity=0.4,
                     annotation_text=f"BB Alt {bb['alt']:.2f}",
                     annotation_font=dict(size=8, color=ALTIN))
    
    # ── FIBONACCI ──
    if 'fibonacci' in cizimler:
        fib = cizimler['fibonacci']
        dip = fib['dip']
        tepe = fib['tepe']
        seviyeler = _fibonacci_seviyeleri(dip, tepe)
        
        fib_renkler = ['#787b86', '#2962FF', '#FF6D00', '#089981', '#f23645', 
                       '#7e57c2', '#787b86', '#787b86']
        for i, (isim, seviye) in enumerate(seviyeler.items()):
            renk = fib_renkler[i % len(fib_renkler)]
            opacity = 0.6 if i == 4 else (0.4 if i in [2, 3] else 0.2)
            fig.add_hline(y=seviye, line_color=renk, line_width=0.6,
                         line_dash="dash", opacity=opacity,
                         annotation_text=f"{isim} {seviye:.2f}",
                         annotation_position="right",
                         annotation_font=dict(size=8, color=renk))
    
    # ── LEGEND AÇIKLAMASI ──
    efsane_items = []
    for key, val in cizimler.items():
        if 'label' in val:
            efsane_items.append(f"<span style='color:{val.get('renk', BEYAZ)}'>●</span> {val['label']}")
    
    if efsane_items:
        fig.add_annotation(
            xref="paper", yref="paper", x=0.0, y=1.0,
            text=" | ".join(efsane_items[:5]),  # İlk 5 tanesini göster
            showarrow=False,
            font=dict(size=9, color=GRAYISH),
            xanchor="left", yanchor="bottom",
            bgcolor="rgba(19, 23, 34, 0.8)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
            borderpad=4
        )


# ══════════════════════════════════════════════════════════════════════
# ANA GRAFİK (PROFESYONEL - TRADINGVIEW TARZI)
# ══════════════════════════════════════════════════════════════════════
def ana_grafik(data: pd.DataFrame, sembol: str,
               zaman_dilimi: str = "1d",
               gosterge_alt: Optional[str] = "MACD",
               gosterge_alt2: Optional[str] = "RSI",
               overlay_list: Optional[list] = None,
               show_volume: bool = True,
               otomatik_cizim: bool = True,
               destek_direnc: bool = True,
               formasyon_ciz: bool = True,
               fibonacci_ciz: bool = True):
    """
    PROFESYONEL TradingView tarzı grafik.
    
    Yeni parametreler:
        otomatik_cizim: Tüm otomatik çizimleri aç/kapa
        destek_direnc: Otomatik destek/direnç çizgileri
        formasyon_ciz: Formasyon çizimleri (ikili dip/tepe, OBO, üçgenler...)
        fibonacci_ciz: Fibonacci retracement çizgileri
    """
    if overlay_list is None: overlay_list = ["MA20", "MA50", "BB"]
    if gosterge_alt  in (None, "— Yok —", "None", ""): gosterge_alt  = None
    if gosterge_alt2 in (None, "— Yok —", "None", ""): gosterge_alt2 = None

    close  = data["Close"].squeeze()
    open_  = data["Open"].squeeze()
    high   = data["High"].squeeze()
    low    = data["Low"].squeeze()
    volume = data["Volume"].squeeze()

    n_alt = sum([1 for g in [gosterge_alt, gosterge_alt2] if g])
    rows = 1 + n_alt
    
    # ORANLARI (Boşluk bırakmadan)
    if rows == 1:
        row_heights = [1.0]
    elif rows == 2:
        row_heights = [0.75, 0.25]
    else:
        row_heights = [0.65, 0.175, 0.175]

    specs = [[{"secondary_y": True}]] + [[{"secondary_y": False}]] * n_alt

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        row_heights=row_heights, vertical_spacing=0.01, specs=specs)

    # ── 1. FİYAT MUM GRAFİĞİ ─────────────────────────────
    fig.add_trace(go.Candlestick(
        x=data.index, open=open_, high=high, low=low, close=close,
        increasing=dict(line=dict(color=YESIL, width=1), fillcolor=YESIL),
        decreasing=dict(line=dict(color=KIRMIZI, width=1), fillcolor=KIRMIZI),
        name="Fiyat", showlegend=False, hoverinfo="none"
    ), row=1, col=1, secondary_y=False)

    # Detaylı hover
    fig.add_trace(go.Scatter(
        x=data.index, y=close, mode="none",
        hovertemplate=(
            "<b>%{x|%d %b %Y}</b><br>"
            "<span style='color:#089981'>▲ A: %{customdata[0]:.2f}</span> "
            "<span style='color:#f23645'>▼ D: %{customdata[2]:.2f}</span><br>"
            "Açılış: %{customdata[1]:.2f} Kapanış: %{customdata[3]:.2f}<br>"
            "Hacim: %{customdata[4]:,.0f}"
            "<extra></extra>"
        ),
        customdata=list(zip(open_, high, low, close, volume)), showlegend=False,
    ), row=1, col=1, secondary_y=False)

    # ── 2. HACİM ÇUBUKLARI ───────────────────────────
    if show_volume:
        vol_renk = [YESIL if c >= o else KIRMIZI for c, o in zip(close, open_)]
        vol_opacity = 0.35
        fig.add_trace(go.Bar(
            x=data.index, y=volume, name="Hacim",
            opacity=vol_opacity,
            marker=dict(color=vol_renk,
                       line=dict(color=vol_renk, width=0)),
            hovertemplate="%{y:,.0f}<extra></extra>",
            showlegend=False
        ), row=1, col=1, secondary_y=True)


    # ── 3. FİYAT ÜSTÜ GÖSTERGELER ───────────────────────
    overlay_cfg = {
        "MA20": ("MA20", "#2962FF", 1.2, "MA 20"), 
        "MA50": ("MA50", "#FF6D00", 1.2, "MA 50"),
        "MA200": ("MA200", "#787b86", 1.5, "MA 200"), 
        "EMA9": ("EMA9", CYAN, 1.0, "EMA 9"),
        "EMA21": ("EMA21", PEMBE, 1.0, "EMA 21"), 
        "VWAP": ("VWAP", BEYAZ, 1.2, "VWAP"),
        "PSAR": ("PSAR", MAVI, 1.0, "PSAR")
    }
    
    for key, (col, renk, w, lbl) in overlay_cfg.items():
        if key in overlay_list and col in data.columns:
            if key == "PSAR":
                trend = data.get("PSAR_Trend", pd.Series(1, index=data.index))
                fig.add_trace(go.Scatter(
                    x=data.index[trend==1], y=data[col][trend==1], 
                    mode="markers", marker=dict(color=YESIL, size=3, symbol="triangle-up"), 
                    name="PSAR ↗", hoverinfo="skip"
                ), row=1, col=1, secondary_y=False)
                fig.add_trace(go.Scatter(
                    x=data.index[trend==-1], y=data[col][trend==-1], 
                    mode="markers", marker=dict(color=KIRMIZI, size=3, symbol="triangle-down"), 
                    name="PSAR ↘", hoverinfo="skip"
                ), row=1, col=1, secondary_y=False)
            else:
                fig.add_trace(go.Scatter(
                    x=data.index, y=data[col], mode="lines", 
                    line=dict(color=renk, width=w), name=lbl, hoverinfo="skip"
                ), row=1, col=1, secondary_y=False)

    # BB - Bollinger Bantları
    if "BB" in overlay_list and "BB_upper" in data.columns:
        bb_orta_idx = None
        for c in ['BB_middle', 'BB_orta', 'MA20']:
            if c in data.columns: 
                bb_orta_idx = c
                break
        
        fig.add_trace(go.Scatter(
            x=data.index, y=data["BB_upper"], mode="lines", 
            line=dict(color="#2962FF", width=0.8), name="BB Üst", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["BB_lower"], mode="lines",
            fill="tonexty", fillcolor="rgba(41, 98, 255, 0.04)",
            line=dict(color="#2962FF", width=0.8), name="BB Alt", hoverinfo="skip"
        ), row=1, col=1, secondary_y=False)
        
        if bb_orta_idx:
            fig.add_trace(go.Scatter(
                x=data.index, y=data[bb_orta_idx], mode="lines",
                line=dict(color="#2962FF", width=0.6, dash="dot"), 
                name="BB Orta", hoverinfo="skip"
            ), row=1, col=1, secondary_y=False)

    if "Ichimoku" in overlay_list:
        for col, renk, lbl in [("Ichimoku_A", "rgba(0,150,255,0.3)", "Bulut A"),
                               ("Ichimoku_B", "rgba(200,100,0,0.3)", "Bulut B"),
                               ("Tenkan", MAVI, "Tenkan"),
                               ("Kijun", KIRMIZI, "Kijun"),
                               ("Chikou", TURUNCU, "Chikou")]:
            if col in data.columns:
                fig.add_trace(go.Scatter(x=data.index, y=data[col], mode="lines",
                             line=dict(color=renk, width=1), name=lbl, hoverinfo="skip"),
                             row=1, col=1, secondary_y=False)

    # ── 4. OTOMATİK ÇİZİMLER (DESTEK/DİRENÇ/FORMASYON/FIBONACCI) ──
    if otomatik_cizim:
        cizimler = _formasyon_cizimleri(data)
        
        # Kullanıcının tercihlerine göre filtrele
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

    # ── 5. ALT GÖSTERGELER ───────────────────────────
    row_idx = 2
    if gosterge_alt:
        _ekle_alt_gosterge(fig, data, gosterge_alt, row_idx)
        row_idx += 1
    if gosterge_alt2:
        _ekle_alt_gosterge(fig, data, gosterge_alt2, row_idx)

    # ── 6. EKRAN VE IZGARA AYARLARI (Tam TV Klonu) ──
    layout_dict = dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(family="-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Arial, sans-serif", 
                 color=BEYAZ, size=11),
        margin=dict(l=0, r=55, t=10, b=10),
        legend=dict(visible=False), 
        height=850, 
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#131722", bordercolor="#363a45", font=dict(color=BEYAZ, size=12)),
        dragmode="pan",
    )

    for i in range(1, rows + 1):
        ax = f"xaxis{i if i > 1 else ''}"
        ay = f"yaxis{i if i > 1 else ''}"
        
        layout_dict[ax] = dict(
            gridcolor=GRID, showgrid=True, zeroline=False, 
            rangeslider=dict(visible=False),
            showspikes=True, spikemode="across+toaxis", 
            spikecolor=GRAYISH, spikethickness=0.5, spikedash="dot",
            tickfont=dict(color=GRAYISH, size=10)
        )
        
        if i == 1:
            layout_dict[ay] = dict(
                gridcolor=GRID, showgrid=True, zeroline=False, 
                side="right", autorange=True, fixedrange=False,
                showspikes=True, spikemode="across", 
                spikecolor=GRAYISH, spikethickness=0.5, spikedash="dot",
                tickfont=dict(color=BEYAZ, size=11)
            )
        else:
            layout_dict[ay] = dict(
                gridcolor=GRID, showgrid=True, zeroline=False, side="right",
                tickfont=dict(color=GRAYISH, size=10)
            )

    if show_volume:
        max_vol = float(volume.max()) if not volume.empty else 1
        layout_dict["yaxis2"] = dict(
            showgrid=False, zeroline=False, showticklabels=False, 
            range=[0, max_vol * 4.5], overlaying="y", side="left"
        )

    fig.update_layout(**layout_dict)
    
    # Piyasalar Kapalı / Açık Filigranı
    fig.add_annotation(
        text=f"{sembol}",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(size=120, color="rgba(255, 255, 255, 0.02)", family="Arial, sans-serif"),
        textangle=0, xanchor="center", yanchor="middle"
    )

    return fig


# ══════════════════════════════════════════════════════════════════════
# ALT GÖSTERGELER (Gelişmiş)
# ══════════════════════════════════════════════════════════════════════
def _ekle_alt_gosterge(fig, data, gosterge, row):
    close = data["Close"].squeeze()
    idx = data.index

    TV_MAVI    = "#2962FF"
    TV_TURUNCU = "#FF6D00"
    TV_MOR     = "#7e57c2"
    TV_YESIL   = "#089981"
    TV_KIRMIZI = "#f23645"
    TV_GRI     = "#787b86"

    # ALT GÖSTERGE ARKA PLAN RENGİ
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
                name="MACD Hist", opacity=1.0, hovertemplate="MACD Hist: %{y:.4f}<extra></extra>",
            ), row=row, col=1)
            macd_col = "MACD" if "MACD" in data.columns else None
            signal_col = "MACD_Signal" if "MACD_Signal" in data.columns else None
            if macd_col:
                fig.add_trace(go.Scatter(x=idx, y=data[macd_col], mode="lines", 
                            name="MACD", line=dict(color=TV_MAVI, width=1.5),
                            hovertemplate="MACD: %{y:.4f}<extra></extra>"), row=row, col=1)
            if signal_col:
                fig.add_trace(go.Scatter(x=idx, y=data[signal_col], mode="lines",
                            name="Sinyal", line=dict(color=TV_TURUNCU, width=1.5),
                            hovertemplate="Sinyal: %{y:.4f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=0, line_color=TV_GRI, line_width=0.5, opacity=0.5, row=row, col=1)

    elif gosterge == "RSI":
        if "RSI" in data.columns:
            # Arka plan bölgeleri
            fig.add_hrect(y0=30, y1=70, fillcolor="rgba(126, 87, 194, 0.05)", line_width=0, row=row, col=1)
            fig.add_hrect(y0=0, y1=30, fillcolor="rgba(8, 153, 129, 0.03)", line_width=0, row=row, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="rgba(242, 54, 69, 0.03)", line_width=0, row=row, col=1)
            
            rsi_values = data["RSI"]
            rsi_renk = [TV_YESIL if v < 30 else (TV_KIRMIZI if v > 70 else TV_MOR) for v in rsi_values]
            
            fig.add_trace(go.Scatter(x=idx, y=rsi_values, mode="lines",
                        name="RSI", line=dict(color=TV_MOR, width=1.5),
                        fill="tozeroy", fillcolor="rgba(126, 87, 194, 0.1)",
                        hovertemplate="RSI: %{y:.2f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=70, line_color=TV_KIRMIZI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=30, line_color=TV_YESIL, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=50, line_color=TV_GRI, line_width=0.5, line_dash="dot", opacity=0.3, row=row, col=1)
            fig.update_yaxes(range=[0, 100], row=row, col=1)

    elif gosterge == "Stochastic":
        if "Stoch_K" in data.columns:
            fig.add_hrect(y0=20, y1=80, fillcolor="rgba(41, 98, 255, 0.05)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(x=idx, y=data["Stoch_K"], mode="lines", 
                        name="%K", line=dict(color=TV_MAVI, width=1.5),
                        hovertemplate="%K: %{y:.2f}<extra></extra>"), row=row, col=1)
            if "Stoch_D" in data.columns:
                fig.add_trace(go.Scatter(x=idx, y=data["Stoch_D"], mode="lines",
                            name="%D", line=dict(color=TV_TURUNCU, width=1.5, dash="dot"),
                            hovertemplate="%D: %{y:.2f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=80, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=20, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.update_yaxes(range=[0, 100], row=row, col=1)

    elif gosterge == "ADX":
        if "ADX" in data.columns:
            fig.add_trace(go.Scatter(x=idx, y=data["ADX"], mode="lines", 
                        name="ADX", line=dict(color=TV_TURUNCU, width=1.5),
                        fill="tozeroy", fillcolor="rgba(255,109,0,0.08)",
                        hovertemplate="ADX: %{y:.1f}<extra></extra>"), row=row, col=1)
            if "DI_Pos" in data.columns:
                fig.add_trace(go.Scatter(x=idx, y=data["DI_Pos"], mode="lines",
                            name="+DI", line=dict(color=TV_YESIL, width=1),
                            hovertemplate="+DI: %{y:.1f}<extra></extra>"), row=row, col=1)
            if "DI_Neg" in data.columns:
                fig.add_trace(go.Scatter(x=idx, y=data["DI_Neg"], mode="lines",
                            name="-DI", line=dict(color=TV_KIRMIZI, width=1),
                            hovertemplate="-DI: %{y:.1f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=25, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, 
                         annotation_text="Güçlü Trend", annotation_font=dict(size=8, color=TV_GRI), row=row, col=1)

    elif gosterge == "CCI":
        if "CCI" in data.columns:
            fig.add_hrect(y0=-100, y1=100, fillcolor="rgba(126, 87, 194, 0.04)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(x=idx, y=data["CCI"], mode="lines", 
                        name="CCI", line=dict(color=TV_MOR, width=1.5),
                        hovertemplate="CCI: %{y:.1f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=100, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=-100, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)

    elif gosterge == "Williams %R":
        if "Williams_R" in data.columns:
            fig.add_hrect(y0=-80, y1=-20, fillcolor="rgba(126, 87, 194, 0.04)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(x=idx, y=data["Williams_R"], mode="lines",
                        name="W%R", line=dict(color=TV_MOR, width=1.5),
                        fill="tozeroy", fillcolor="rgba(126,87,194,0.08)",
                        hovertemplate="Williams %R: %{y:.1f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=-20, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=-80, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.update_yaxes(range=[-100, 0], row=row, col=1)

    elif gosterge == "MFI":
        if "MFI" in data.columns:
            fig.add_hrect(y0=20, y1=80, fillcolor="rgba(8, 153, 129, 0.04)", line_width=0, row=row, col=1)
            fig.add_trace(go.Scatter(x=idx, y=data["MFI"], mode="lines",
                        name="MFI", line=dict(color=TV_YESIL, width=1.5),
                        fill="tozeroy", fillcolor="rgba(8,153,129,0.08)",
                        hovertemplate="MFI: %{y:.1f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=80, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.add_hline(y=20, line_color=TV_GRI, line_width=1, line_dash="dash", opacity=0.5, row=row, col=1)
            fig.update_yaxes(range=[0, 100], row=row, col=1)

    elif gosterge == "ROC":
        if "ROC" in data.columns:
            fig.add_trace(go.Scatter(x=idx, y=data["ROC"], mode="lines",
                        name="ROC", line=dict(color=TV_MAVI, width=1.5),
                        fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
                        hovertemplate="ROC: %{y:.2f}%<extra></extra>"), row=row, col=1)
            fig.add_hline(y=0, line_color=TV_GRI, line_width=0.5, opacity=0.5, row=row, col=1)

    elif gosterge == "Momentum":
        if "Momentum" in data.columns:
            fig.add_trace(go.Scatter(x=idx, y=data["Momentum"], mode="lines",
                        name="Mom", line=dict(color=TV_TURUNCU, width=1.5),
                        fill="tozeroy", fillcolor="rgba(255,109,0,0.08)",
                        hovertemplate="Momentum: %{y:.4f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=0, line_color=TV_GRI, line_width=0.5, opacity=0.5, row=row, col=1)

    elif gosterge == "Boğa/Ayı Gücü":
        if "Bull_Power" in data.columns:
            fig.add_trace(go.Bar(x=idx, y=data["Bull_Power"], name="Boğa",
                        marker_color="rgba(8, 153, 129, 0.6)",
                        hovertemplate="Boğa Gücü: %{y:.4f}<extra></extra>"), row=row, col=1)
        if "Bear_Power" in data.columns:
            fig.add_trace(go.Bar(x=idx, y=data["Bear_Power"], name="Ayı",
                        marker_color="rgba(242, 54, 69, 0.6)",
                        hovertemplate="Ayı Gücü: %{y:.4f}<extra></extra>"), row=row, col=1)
        fig.add_hline(y=0, line_color=TV_GRI, line_width=1, opacity=0.5, row=row, col=1)

    elif gosterge == "OBV":
        if "OBV" in data.columns:
            fig.add_trace(go.Scatter(x=idx, y=data["OBV"], mode="lines",
                        name="OBV", line=dict(color=TV_MAVI, width=1.5),
                        fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
                        hovertemplate="OBV: %{y:,.0f}<extra></extra>"), row=row, col=1)

    elif gosterge == "ATR":
        if "ATR" in data.columns:
            fig.add_trace(go.Scatter(x=idx, y=data["ATR"], mode="lines",
                        name="ATR", line=dict(color="#9c27b0", width=1.5),
                        fill="tozeroy", fillcolor="rgba(156,39,176,0.08)",
                        hovertemplate="ATR: %{y:.4f}<extra></extra>"), row=row, col=1)

    elif gosterge == "PV/Trend Gücü":
        if "PV_Strength" in data.columns:
            fig.add_trace(go.Scatter(x=idx, y=data["PV_Strength"], mode="lines",
                        name="PV Gücü", line=dict(color=TV_MAVI, width=1.5),
                        fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
                        hovertemplate="PV Gücü: %{y:.4f}<extra></extra>"), row=row, col=1)
            fig.add_hline(y=0, line_color=TV_GRI, line_width=0.5, opacity=0.5, row=row, col=1)


# ══════════════════════════════════════════════════════════════════════
# FORMASYON BİLGİ PANELİ
# ══════════════════════════════════════════════════════════════════════
def formasyon_bilgi_paneli(cizimler: Dict):
    """Grafikte tespit edilen formasyonları bilgi kartı olarak gösterir."""
    if not cizimler:
        return
    
    for key, val in cizimler.items():
        if key in ['destekler', 'direncler', 'fibonacci']:
            continue
        
        renk = val.get('renk', BEYAZ)
        tip = val.get('tip', 'info')
        label = val.get('label', key)
        
        ikon = {"success": "✅", "error": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(tip, "ℹ️")
        bg = {"success": "rgba(8,153,129,0.08)", "error": "rgba(242,54,69,0.08)", 
              "warning": "rgba(245,204,106,0.08)", "info": "rgba(120,123,134,0.08)"}.get(tip, "rgba(10,18,36,0.5)")
        
        hedef_str = ""
        if 'hedef' in val:
            hedef_str = f" · 🎯 Hedef: {val['hedef']:.2f}"
        
        st.markdown(f"""
        <div style="background:{bg};border-left:3px solid {renk};
                    border-radius:6px;padding:8px 12px;margin-bottom:4px;
                    font-size:11px;line-height:1.5;">
          <span style="font-weight:600;color:{renk};">{ikon} {label}</span>{hedef_str}
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TABLO FONKSİYONU
# ══════════════════════════════════════════════════════════════════════
def tablo_goster(df: pd.DataFrame):
    if df is None or df.empty:
        return

    cols_show = [c for c in [
        "Hisse","Sinyal","Son Fiyat","Değişim %","RSI","MACD","MACD Sinyal","BB Sinyal",
        "MA20","MA50","Stoch K","ATR","ADX","CCI","Boğa Gücü","Ayı Gücü","Hacim","Borsa"
    ] if c in df.columns]

    display = df[cols_show].copy()

    def fmt_sinyal(v):
        if "GÜÇLÜ AL" in str(v):  return "background:#064d2a;color:#089981;font-weight:700;border-radius:3px;padding:2px 6px"
        if "AL" in str(v):         return "background:#2a3a00;color:#f5cc6a;font-weight:700"
        if "GÜÇLÜ SAT" in str(v): return "background:#4d0f1a;color:#f23645;font-weight:700;border-radius:3px;padding:2px 6px"
        if "SAT" in str(v):        return "background:#3a1a00;color:#FF6D00;font-weight:700"
        return "color:#787b86"

    def fmt_pct(v):
        try:
            f = float(v)
            return f"color:#089981;font-weight:600" if f >= 0 else f"color:#f23645;font-weight:600"
        except: return ""

    def fmt_strateji_sinyal(v):
        v = str(v)
        if v == "AL":
            return "background:#064d2a;color:#089981;font-weight:700;border-radius:3px;padding:2px 6px"
        if v == "SAT":
            return "background:#4d0f1a;color:#f23645;font-weight:700;border-radius:3px;padding:2px 6px"
        return "color:#787b86"

    strateji_cols = [c for c in ["MACD Sinyal", "BB Sinyal"] if c in cols_show]
    styled = display.style\
        .map(fmt_sinyal, subset=["Sinyal"] if "Sinyal" in cols_show else [])\
        .map(fmt_strateji_sinyal, subset=strateji_cols)\
        .map(fmt_pct, subset=["Değişim %"] if "Değişim %" in cols_show else [])\
        .format({
            "Son Fiyat": "{:.4f}", "Değişim %": "{:+.2f}%",
            "RSI": "{:.1f}", "MACD": "{:.4f}",
            "MA20": "{:.2f}", "MA50": "{:.2f}",
            "Stoch K": "{:.1f}", "ATR": "{:.4f}",
            "ADX": "{:.1f}", "CCI": "{:.1f}",
            "Boğa Gücü": "{:.4f}", "Ayı Gücü": "{:.4f}",
            "Hacim": "{:,.0f}",
        }, na_rep="-")

    st.dataframe(styled, use_container_width=True, height=650)


# ══════════════════════════════════════════════════════════════════════
# MİNİ GRAFİKLER (Tarama Sayfası)
# ══════════════════════════════════════════════════════════════════════
def yukselenler_grafik(df):
    if df is None or "Değişim %" not in df.columns: return
    top = df.nlargest(10, "Değişim %")
    fig = go.Figure(go.Bar(
        y=top["Hisse"], x=top["Değişim %"], orientation="h",
        marker_color=[f"rgba(8,153,129,{0.5 + v/top['Değişim %'].max()*0.5})" for v in top["Değişim %"]],
        text=[f"+{v:.2f}%" for v in top["Değişim %"]], textposition="outside",
        textfont=dict(size=10, color=YESIL)
    ))
    fig.update_layout(title=dict(text="Top 10 Yükselenler", font=dict(color=ALTIN, size=13)),
                      paper_bgcolor=BG, plot_bgcolor=BG2, font=dict(color=BEYAZ, size=10),
                      xaxis=dict(gridcolor=GRID, ticksuffix="%"), yaxis=dict(gridcolor=GRID),
                      height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def dusenler_grafik(df):
    if df is None or "Değişim %" not in df.columns: return
    bot = df.nsmallest(10, "Değişim %")
    fig = go.Figure(go.Bar(
        y=bot["Hisse"], x=bot["Değişim %"], orientation="h",
        marker_color=[f"rgba(242,54,69,{0.5 + abs(v)/abs(bot['Değişim %'].min())*0.5})" for v in bot["Değişim %"]],
        text=[f"{v:.2f}%" for v in bot["Değişim %"]], textposition="outside",
        textfont=dict(size=10, color=KIRMIZI)
    ))
    fig.update_layout(title=dict(text="Top 10 Düşenler", font=dict(color=ALTIN, size=13)),
                      paper_bgcolor=BG, plot_bgcolor=BG2, font=dict(color=BEYAZ, size=10),
                      xaxis=dict(gridcolor=GRID, ticksuffix="%"), yaxis=dict(gridcolor=GRID),
                      height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def rsi_dagilim_grafik(df):
    if df is None or "RSI" not in df.columns: return
    rsi_vals = df["RSI"].dropna()
    fig = go.Figure(go.Histogram(
        x=rsi_vals, nbinsx=20, marker_color=ALTIN, opacity=0.8,
        hovertemplate="RSI: %{x}<br>Sayı: %{y}<extra></extra>"
    ))
    fig.add_vline(x=30, line_color=YESIL, line_dash="dot", line_width=1)
    fig.add_vline(x=70, line_color=KIRMIZI, line_dash="dot", line_width=1)
    fig.update_layout(title=dict(text="RSI Dağılımı", font=dict(color=ALTIN, size=13)),
                      paper_bgcolor=BG, plot_bgcolor=BG2, font=dict(color=BEYAZ, size=10),
                      xaxis=dict(gridcolor=GRID, range=[0,100]), yaxis=dict(gridcolor=GRID),
                      height=280, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def sinyal_pasta_grafik(df):
    if df is None or "Sinyal" not in df.columns: return
    cnts  = df["Sinyal"].value_counts()
    renkler = {"🟢 GÜÇLÜ AL": YESIL, "🟡 AL": "#f5cc6a", "⚪ NÖTR": GRAYISH, "🟠 SAT": TURUNCU, "🔴 GÜÇLÜ SAT": KIRMIZI}
    fig = go.Figure(go.Pie(
        labels=cnts.index, values=cnts.values, hole=0.55, textfont=dict(size=10),
        marker=dict(colors=[renkler.get(s, MAVI) for s in cnts.index], line=dict(color=BG, width=2)),
        hovertemplate="%{label}<br>%{value} hisse (%{percent})<extra></extra>"
    ))
    fig.update_layout(title=dict(text="Sinyal Dağılımı", font=dict(color=ALTIN, size=13)),
                      paper_bgcolor=BG, font=dict(color=BEYAZ), legend=dict(font=dict(size=9)),
                      height=280, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def portfoy_performans_grafik(df):
    if df is None or df.empty: return
    fig = go.Figure(go.Pie(
        labels=df["Hisse"], values=df["Güncel Değer"] if "Güncel Değer" in df.columns else df["Değer"],
        marker=dict(colors=[ALTIN, MAVI, YESIL, MOR, TURUNCU, CYAN, PEMBE, KIRMIZI][:len(df)], line=dict(color=BG, width=2)),
        hole=0.5, textfont=dict(size=10), hovertemplate="%{label}<br>%{value:,.2f} TL (%{percent})<extra></extra>"
    ))
    fig.update_layout(title=dict(text="Portföy Dağılımı", font=dict(color=ALTIN, size=13)),
                      paper_bgcolor=BG, font=dict(color=BEYAZ), legend=dict(font=dict(size=9)),
                      height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def guclu_al_grafik(df):
    if df is None or "Sinyal" not in df.columns: return
    flt = df[df["Sinyal"].str.contains("GÜÇLÜ AL|AL", na=False)]
    if flt.empty: return
    top = flt.nlargest(10, "Değişim %")
    fig = go.Figure(go.Bar(
        x=top["Hisse"], y=top["Değişim %"], marker_color=YESIL, opacity=0.8,
        text=[f"{v:+.2f}%" for v in top["Değişim %"]], textposition="outside"
    ))
    fig.update_layout(title=dict(text="Güçlü AL Sinyali Alanlar", font=dict(color=ALTIN, size=13)),
                      paper_bgcolor=BG, plot_bgcolor=BG2, font=dict(color=BEYAZ, size=10),
                      yaxis=dict(gridcolor=GRID, ticksuffix="%"), xaxis=dict(gridcolor=GRID),
                      height=280, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# Geriye dönük uyumluluk için alias
def candlestick_grafik(data, sembol, info=None):
    if data is None: return
    fig = ana_grafik(data, sembol, overlay_list=["MA20","MA50","BB"],
                     gosterge_alt="MACD", gosterge_alt2="RSI")
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
