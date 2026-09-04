# ══════════════════════════════════════════════════════════════════════
#  mod_teknik_analiz.py — Teknik indikatör değerleri ve sinyal yorumu

import streamlit as st
from analiz import macd_sinyal_hesapla, bollinger_sinyal_hesapla


def teknik_analiz_paneli(data, info, son_fiyat, sembol):
    """Tüm indikatörlerin anlık değerleri + sinyal yorumu."""
    close = data["Close"].squeeze()

    st.markdown(f"### {sembol} Teknik Göstergeler")

    st.markdown('<span class="section-label">Trend Göstergeleri</span>', unsafe_allow_html=True)
    t1,t2,t3,t4,t5 = st.columns(5)
    cols_trend = [t1,t2,t3,t4,t5]
    trend_data = []
    if "MA20"  in data.columns: trend_data.append(("MA20",  round(float(data["MA20"].iloc[-1]),4)))
    if "MA50"  in data.columns: trend_data.append(("MA50",  round(float(data["MA50"].iloc[-1]),4)))
    if "MA200" in data.columns: trend_data.append(("MA200", round(float(data["MA200"].iloc[-1]),4)))
    if "EMA9"  in data.columns: trend_data.append(("EMA9",  round(float(data["EMA9"].iloc[-1]),4)))
    if "EMA21" in data.columns: trend_data.append(("EMA21", round(float(data["EMA21"].iloc[-1]),4)))
    for i,(lbl,val) in enumerate(trend_data[:5]):
        diff = round(((son_fiyat - val) / val * 100), 2) if val else None
        with cols_trend[i]: st.metric(lbl, f"{val:,.4f}", delta=f"{diff:+.2f}%" if diff else None)

    st.markdown('<span class="section-label">Osilatörler</span>', unsafe_allow_html=True)
    o1,o2,o3,o4,o5,o6 = st.columns(6)
    oscs = []
    if "RSI"        in data.columns: oscs.append(("RSI",        round(float(data["RSI"].iloc[-1]),2),       "30↓ Aşırı Satım · 70↑ Aşırı Alım"))
    if "Stoch_K"    in data.columns: oscs.append(("Stoch %K",   round(float(data["Stoch_K"].iloc[-1]),2),   "20↓ AS · 80↑ AA"))
    if "CCI"        in data.columns: oscs.append(("CCI",        round(float(data["CCI"].iloc[-1]),2),        "-100↓ AS · 100↑ AA"))
    if "Williams_R" in data.columns: oscs.append(("Williams %R",round(float(data["Williams_R"].iloc[-1]),2), "-80↓ AS · -20↑ AA"))
    if "MFI"        in data.columns: oscs.append(("MFI",        round(float(data["MFI"].iloc[-1]),2),        "20↓ AS · 80↑ AA"))
    if "ROC"        in data.columns: oscs.append(("ROC",        round(float(data["ROC"].iloc[-1]),2),         "0 Referans"))
    for idx,(lbl,val,_) in enumerate(oscs[:6]):
        with [o1,o2,o3,o4,o5,o6][idx]: st.metric(lbl, f"{val}")

    st.markdown('<span class="section-label">Trend Gücü &amp; Volatilite</span>', unsafe_allow_html=True)
    v1,v2,v3,v4 = st.columns(4)
    if "ADX" in data.columns:
        adx = round(float(data["ADX"].iloc[-1]),2)
        with v1: st.metric("ADX", adx, delta="Güçlü trend" if adx>25 else "Zayıf trend")
    if "ATR" in data.columns:
        with v2: st.metric("ATR(14)", round(float(data["ATR"].iloc[-1]),4))
    if "BB_upper" in data.columns:
        bw = round(float(data["BB_upper"].iloc[-1]) - float(data["BB_lower"].iloc[-1]), 4)
        with v3: st.metric("BB Genişliği", bw)
    if "PSAR" in data.columns:
        psar = round(float(data["PSAR"].iloc[-1]),4)
        psar_sig = "📈 Yükseliş" if psar < son_fiyat else "📉 Düşüş"
        with v4: st.metric("Parabolic SAR", psar, delta=psar_sig)

    # MACD detay
    if all(c in data.columns for c in ["MACD","MACD_signal","MACD_hist"]):
        st.markdown('<span class="section-label">MACD Detayı</span>', unsafe_allow_html=True)
        mc1,mc2,mc3 = st.columns(3)
        macd_v  = round(float(data["MACD"].iloc[-1]),4)
        macd_s  = round(float(data["MACD_signal"].iloc[-1]),4)
        macd_h  = round(float(data["MACD_hist"].iloc[-1]),4)
        crossover = "🟢 Yukarı Kesim" if macd_v > macd_s else "🔴 Aşağı Kesim"
        with mc1: st.metric("MACD",   macd_v)
        with mc2: st.metric("Sinyal", macd_s)
        with mc3: st.metric("Histogram", macd_h, delta=crossover)

    # Bollinger Bantları
    if all(c in data.columns for c in ["BB_upper","BB_middle","BB_lower"]):
        st.markdown('<span class="section-label">Bollinger Bantları</span>', unsafe_allow_html=True)
        b1,b2,b3,b4 = st.columns(4)
        bb_u = round(float(data["BB_upper"].iloc[-1]),4)
        bb_m = round(float(data["BB_middle"].iloc[-1]),4)
        bb_l = round(float(data["BB_lower"].iloc[-1]),4)
        bb_pos = round(((son_fiyat - bb_l)/(bb_u - bb_l))*100, 1) if (bb_u-bb_l)>0 else 50
        with b1: st.metric("Üst Bant", bb_u)
        with b2: st.metric("Orta (MA20)", bb_m)
        with b3: st.metric("Alt Bant", bb_l)
        with b4: st.metric("Pozisyon %", bb_pos, delta="Üst banta yakın" if bb_pos>75 else ("Alt banta yakın" if bb_pos<25 else "Orta"))

    # Elder Ray (Boğa/Ayı Gücü)
    if "Bull_Power" in data.columns and "Bear_Power" in data.columns:
        st.markdown('<span class="section-label">Boğa / Ayı Gücü (Elder Ray)</span>', unsafe_allow_html=True)
        e1,e2 = st.columns(2)
        bp  = round(float(data["Bull_Power"].iloc[-1]),4)
        bep = round(float(data["Bear_Power"].iloc[-1]),4)
        with e1: st.metric("🐂 Boğa Gücü", bp,  delta="Alıcılar güçlü" if bp>0  else "Alıcılar zayıf")
        with e2: st.metric("🐻 Ayı Gücü",  bep, delta="Satıcılar zayıf" if bep>-0.01 else "Satıcılar güçlü")

    # Hacim analizi
    if "OBV" in data.columns:
        st.markdown('<span class="section-label">Hacim Analizi</span>', unsafe_allow_html=True)
        h1,h2 = st.columns(2)
        obv      = float(data["OBV"].iloc[-1])
        obv_prev = float(data["OBV"].iloc[-5]) if len(data)>5 else obv
        obv_trend = "↑ Artıyor" if obv > obv_prev else "↓ Azalıyor"
        with h1: st.metric("OBV", f"{obv:,.0f}", delta=obv_trend)
        if "Volume" in data.columns:
            vol_avg   = float(data["Volume"].squeeze().iloc[-20:].mean())
            vol_son   = float(data["Volume"].squeeze().iloc[-1])
            vol_ratio = round(vol_son/vol_avg*100, 1) if vol_avg>0 else 100
            with h2: st.metric("Hacim / Ort. %", f"{vol_ratio}%",
                                delta="Yüksek hacim" if vol_ratio>120 else ("Düşük hacim" if vol_ratio<80 else "Normal"))

    # Sinyal özeti
    st.markdown('<span class="section-label">Sinyal Özeti</span>', unsafe_allow_html=True)
    sinyaller = []
    if "RSI" in data.columns:
        rsi = float(data["RSI"].iloc[-1])
        if rsi < 30:   sinyaller.append(("RSI", "🟢 AŞIRI SATIM", "#22e691"))
        elif rsi > 70: sinyaller.append(("RSI", "🔴 AŞIRI ALIM",  "#ff4f6d"))
        else:          sinyaller.append(("RSI", "⚪ NÖTR",         "#7a8fa8"))
    macd_sig = macd_sinyal_hesapla(data)
    macd_renk = {"AL": "#22e691", "SAT": "#ff4f6d", "NÖTR": "#7a8fa8"}
    macd_lbl = {"AL": "🟢 AL", "SAT": "🔴 SAT", "NÖTR": "⚪ NÖTR"}
    sinyaller.append(("MACD", macd_lbl.get(macd_sig, "⚪ NÖTR"), macd_renk.get(macd_sig, "#7a8fa8")))

    bb_sig = bollinger_sinyal_hesapla(data, son_fiyat)
    bb_renk = {"AL": "#22e691", "SAT": "#ff4f6d", "NÖTR": "#7a8fa8"}
    bb_lbl = {
        "AL": "🟢 AL (Aşırı Satım)",
        "SAT": "🔴 SAT (Aşırı Alım)",
        "NÖTR": "⚪ NÖTR",
    }
    sinyaller.append(("Bollinger", bb_lbl.get(bb_sig, "⚪ NÖTR"), bb_renk.get(bb_sig, "#7a8fa8")))
    if "MA20" in data.columns and "MA50" in data.columns:
        if float(data["MA20"].iloc[-1]) > float(data["MA50"].iloc[-1]):
            sinyaller.append(("MA20/50", "🟢 GOLDEN CROSS", "#22e691"))
        else:
            sinyaller.append(("MA20/50", "🔴 DEATH CROSS",  "#ff4f6d"))

    if sinyaller:
        cols = st.columns(len(sinyaller))
        for i,(ind,sig,renk) in enumerate(sinyaller):
            with cols[i]:
                st.markdown(f"""
                <div style="background:rgba(10,16,32,0.8);border:1px solid {renk}44;
                            border-radius:6px;padding:12px;text-align:center;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:8px;
                              color:var(--txt3);letter-spacing:.15em;margin-bottom:6px;">{ind}</div>
                  <div style="font-family:'Sora',sans-serif;font-size:12px;
                              font-weight:700;color:{renk};">{sig}</div>
                </div>
                """, unsafe_allow_html=True)
