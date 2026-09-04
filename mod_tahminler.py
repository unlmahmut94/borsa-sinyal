# ══════════════════════════════════════════════════════════════════════
#  mod_tahminler.py — Analist tahminleri, hedef fiyat, kazanç takvimi

import streamlit as st
import yfinance as yf
import plotly.graph_objects as go


def tahminler_paneli(sembol: str):
    """Analist tahminleri ve hedef fiyat."""
    st.markdown(f'<span class="section-label">{sembol} — Analist Tahminleri</span>',
                unsafe_allow_html=True)
    with st.spinner("Tahminler yükleniyor..."):
        try:
            ticker = yf.Ticker(sembol)
            info   = ticker.info
        except:
            st.error("Bilgi alınamadı.")
            return

    if not info:
        st.info("Tahmin bilgisi bulunamadı.")
        return

    # Hedef fiyat kartı
    son_fiyat = info.get("regularMarketPrice") or info.get("currentPrice", 0)
    hedef     = info.get("targetMeanPrice", None)
    hedef_yuk = info.get("targetHighPrice", None)
    hedef_dus = info.get("targetLowPrice", None)
    analist_s = info.get("numberOfAnalystOpinions", 0) or 0
    tavsiye   = info.get("recommendationKey","N/A")
    tavsiye_s = info.get("recommendationMean", None)

    if hedef and son_fiyat:
        potansiyel = round(((hedef - son_fiyat) / son_fiyat) * 100, 2)
        renk_pot   = "#0fdb7a" if potansiyel >= 0 else "#ff3b5c"
        ok_pot     = "▲" if potansiyel >= 0 else "▼"
    else:
        potansiyel = None
        renk_pot   = "#7a8fa8"
        ok_pot     = "—"

    h1, h2, h3, h4 = st.columns(4)
    with h1:
        st.metric("Mevcut Fiyat", f"{son_fiyat:,.4f}" if son_fiyat else "-")
    with h2:
        st.metric("Ortalama Hedef", f"{hedef:,.2f}" if hedef else "-",
                  delta=f"{ok_pot} {abs(potansiyel):.1f}%" if potansiyel is not None else None)
    with h3:
        st.metric("Analist Sayısı", str(analist_s))
    with h4:
        st.metric("Konsensüs Skoru", f"{tavsiye_s:.1f}/5" if tavsiye_s else "-")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Tavsiye görseli
    tavsiye_map = {
        "strong_buy":  ("🟢 GÜÇLÜ AL",  "#064d2a", "#0fdb7a"),
        "buy":         ("🟡 AL",         "#2a3a00", "#f5cc6a"),
        "hold":        ("⚪ TUTE",       "#1a2035", "#7a8fa8"),
        "sell":        ("🟠 SAT",        "#3a1a00", "#ff8c42"),
        "strong_sell": ("🔴 GÜÇLÜ SAT", "#4d0f1a", "#ff3b5c"),
    }
    lbl, bg_t, clr_t = tavsiye_map.get(str(tavsiye).lower(), (str(tavsiye).upper(), "#1a2035", "#7a8fa8"))

    st.markdown(f"""
    <div style="background:{bg_t};border:1px solid {clr_t}44;border-radius:10px;
                padding:24px 32px;margin:8px 0 16px 0;display:flex;align-items:center;gap:20px;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:800;
                  color:{clr_t};letter-spacing:.03em;">{lbl}</div>
      <div>
        <div style="font-family:'Sora',sans-serif;font-size:11px;color:var(--txt3);">
          {analist_s} analistin konsensüsü
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--txt2);
                    margin-top:4px;">
          Hedef: <span style="color:{clr_t};font-weight:700;">
          {f"{hedef_dus:,.2f}" if hedef_dus else "?"} — {f"{hedef_yuk:,.2f}" if hedef_yuk else "?"}
          </span>
          &nbsp;|&nbsp; Ortalama: <span style="color:{clr_t};font-weight:700;">
          {f"{hedef:,.2f}" if hedef else "?"}
          </span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # EPS ve gelir tahminleri
    try:
        earnings = ticker.earnings_dates
        if earnings is not None and not earnings.empty:
            st.markdown('<span class="section-label">Kazanç Takvimi</span>', unsafe_allow_html=True)
            earnings_show = earnings.head(6).reset_index()
            st.dataframe(earnings_show.style.set_properties(**{
                'font-family': 'JetBrains Mono, monospace',
                'font-size': '11px',
                'background-color': 'rgba(10,16,32,0.8)',
                'color': '#edf0f7',
            }), use_container_width=True, height=220)
    except:
        pass

    # EPS geçmişi grafiği
    try:
        eps_hist = ticker.earnings
        if eps_hist is not None and not eps_hist.empty:
            fig_eps = go.Figure()
            fig_eps.add_trace(go.Bar(
                x=eps_hist.index.astype(str), y=eps_hist.get("Earnings", eps_hist.iloc[:,0]),
                marker_color="#d4a843", name="Net Kar",
                hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>"
            ))
            fig_eps.update_layout(
                paper_bgcolor="#020408", plot_bgcolor="#0a1020",
                font=dict(color="#edf0f7", size=10, family="JetBrains Mono"),
                title=dict(text="Yıllık Kazanç", font=dict(color="#d4a843", size=13)),
                xaxis=dict(gridcolor="#0e1826"), yaxis=dict(gridcolor="#0e1826"),
                height=250, margin=dict(l=0,r=0,t=40,b=0)
            )
            st.plotly_chart(fig_eps, use_container_width=True)
    except:
        pass
