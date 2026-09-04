# ══════════════════════════════════════════════════════════════════════
#  mod_sinyaller.py — Güçlü AL/SAT sinyal hesaplama ve görselleştirme

import streamlit as st
import plotly.graph_objects as go


def sinyal_ozet_karti(sinyal: str, skor: int):
    """Tek bir hisse için büyük sinyal kartı gösterir."""
    sinyal_map = {
        "GUCLU AL":  ("#064d2a", "#0fdb7a", "GUCLU AL"),
        "AL":         ("#2a3a00", "#f5cc6a", "AL"),
        "NOTR":      ("#1a2035", "#7a8fa8", "NOTR"),
        "SAT":        ("#3a1a00", "#ff8c42", "SAT"),
        "GUCLU SAT": ("#4d0f1a", "#ff3b5c", "GUCLU SAT"),
    }
    norm = sinyal.upper().replace("Ö", "O").replace("Ü", "U").replace("Ğ", "G")
    # Fuzzy match
    matched = "NOTR"
    for key in sinyal_map:
        if key in norm or norm in key:
            matched = key
            break

    bg, clr, lbl = sinyal_map[matched]
    st.markdown(f"""
    <div style="background:{bg};border:2px solid {clr}55;border-radius:12px;
                padding:20px 28px;margin:12px 0;display:flex;align-items:center;gap:20px;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:800;
                  color:{clr};letter-spacing:.04em;">{lbl}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:{clr}99;">
        Skor: <span style="color:{clr};font-weight:700;">{skor:+d}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def sinyal_pasta_grafigi(df):
    """Tarama sonucu sinyal dağılımı pasta grafiği."""
    if "Sinyal" not in df.columns or df.empty:
        return

    sinyal_sayilari = df["Sinyal"].value_counts()
    renk_map = {
        "GUCLU AL":  "#0fdb7a",
        "AL":         "#f5cc6a",
        "NOTR":      "#7a8fa8",
        "SAT":        "#ff8c42",
        "GUCLU SAT": "#ff3b5c",
    }
    renkler = []
    for lbl in sinyal_sayilari.index:
        norm = str(lbl).upper()
        matched_renk = "#4db8ff"
        for key, clr in renk_map.items():
            if key in norm:
                matched_renk = clr
                break
        renkler.append(matched_renk)

    fig = go.Figure(go.Pie(
        labels=sinyal_sayilari.index,
        values=sinyal_sayilari.values,
        marker=dict(colors=renkler, line=dict(color="#020408", width=2)),
        textinfo="label+percent",
        textfont=dict(family="JetBrains Mono, monospace", size=10, color="#edf0f7"),
        hole=0.45,
        hovertemplate="%{label}: %{value} hisse<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text="Sinyal Dağılımı", font=dict(color="#d4a843", size=13)),
        paper_bgcolor="#020408", plot_bgcolor="#020408",
        font=dict(color="#edf0f7"),
        showlegend=False,
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        annotations=[dict(text="SİNYAL", x=0.5, y=0.5, font=dict(
            size=10, color="#95aabf", family="JetBrains Mono"
        ), showarrow=False)]
    )
    st.plotly_chart(fig, use_container_width=True)


def guclu_al_tablosu(df):
    """Sadece GÜÇLÜ AL sinyalindeki hisseleri gösterir."""
    if "Sinyal" not in df.columns or df.empty:
        return

    guclu = df[df["Sinyal"].str.contains("GUCLU AL", case=False, na=False)]
    if guclu.empty:
        st.info("Güçlü AL sinyali bulunan hisse yok.")
        return

    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.15em;
                color:#0fdb7a;margin-bottom:8px;">
      {len(guclu)} HISSE — GUCLU AL SINYALI
    </div>
    """, unsafe_allow_html=True)

    for _, row in guclu.iterrows():
        deg   = row.get("Degisim %", 0) or 0
        rsi   = row.get("RSI", "-")
        hisse = row.get("Hisse", "-")
        fiyat = row.get("Son Fiyat", "-")
        renk  = "#0fdb7a" if deg >= 0 else "#ff4f6d"
        st.markdown(f"""
        <div style="background:rgba(6,77,42,0.25);border:1px solid #0fdb7a44;
                    border-radius:6px;padding:10px 14px;margin-bottom:6px;
                    display:flex;align-items:center;gap:16px;">
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;
                       font-weight:700;color:#0fdb7a;min-width:90px;">{hisse}</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#d1e0f0;">
            {fiyat}</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;
                       color:{renk};font-weight:600;">{deg:+.2f}%</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:10px;
                       color:#95aabf;margin-left:auto;">RSI: {rsi if rsi != '-' else '—'}</span>
        </div>
        """, unsafe_allow_html=True)


def guclu_sat_tablosu(df):
    """Sadece GÜÇLÜ SAT sinyalindeki hisseleri gösterir."""
    if "Sinyal" not in df.columns or df.empty:
        return

    guclu = df[df["Sinyal"].str.contains("GUCLU SAT", case=False, na=False)]
    if guclu.empty:
        st.info("Güçlü SAT sinyali bulunan hisse yok.")
        return

    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.15em;
                color:#ff3b5c;margin-bottom:8px;">
      {len(guclu)} HISSE — GUCLU SAT SINYALI
    </div>
    """, unsafe_allow_html=True)

    for _, row in guclu.iterrows():
        deg   = row.get("Degisim %", 0) or 0
        rsi   = row.get("RSI", "-")
        hisse = row.get("Hisse", "-")
        fiyat = row.get("Son Fiyat", "-")
        renk  = "#0fdb7a" if deg >= 0 else "#ff4f6d"
        st.markdown(f"""
        <div style="background:rgba(77,15,26,0.35);border:1px solid #ff3b5c44;
                    border-radius:6px;padding:10px 14px;margin-bottom:6px;
                    display:flex;align-items:center;gap:16px;">
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;
                       font-weight:700;color:#ff3b5c;min-width:90px;">{hisse}</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#d1e0f0;">
            {fiyat}</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;
                       color:{renk};font-weight:600;">{deg:+.2f}%</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:10px;
                       color:#95aabf;margin-left:auto;">RSI: {rsi if rsi != '-' else '—'}</span>
        </div>
        """, unsafe_allow_html=True)
