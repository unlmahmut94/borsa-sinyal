# ══════════════════════════════════════════════════════════════════════
#  mod_portfoy.py — Portföy ekleme, silme, takip, performans grafiği

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json, os

# ── Korelasyon entegrasyonu (Tavsiye #3) ─────────────────────────────
try:
    from mod_korelasyon import korelasyon_raporu, portfoy_diversifikasyon_skoru, portfoy_optimize_et
    KORELASYON_AKTIF = True
except ImportError:
    KORELASYON_AKTIF = False

PORTFOY_DOSYA = "portfoy.json"


def portfoy_yukle() -> list:
    """portfoy.json dosyasından portföy listesi yükler."""
    if os.path.exists(PORTFOY_DOSYA):
        with open(PORTFOY_DOSYA, "r") as f:
            return json.load(f)
    return []


def portfoy_kaydet(portfoy_listesi: list):
    """Portföy listesini portfoy.json'a kaydeder."""
    with open(PORTFOY_DOSYA, "w") as f:
        json.dump(portfoy_listesi, f, ensure_ascii=False, indent=2)


def portfoy_paneli():
    """Portföy sekmesi: ekleme, silme, anlık takip, grafik."""
    st.markdown("""
    <div style="padding:24px 0 0 0;">
      <span style="font-family:'Sora',sans-serif;font-size:26px;font-weight:800;
                   color:var(--txt1);letter-spacing:-.03em;">
        Portföy <span style="color:var(--gold);">Takibi</span>
      </span>
      <div style="height:1px;background:linear-gradient(90deg,var(--goldd),transparent);
                  margin:12px 0 20px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("➕ Portföye Hisse Ekle", expanded=len(st.session_state.portfoy) == 0):
        p1, p2, p3, p4 = st.columns([2, 1, 1, 1])
        with p1: p_h = st.text_input("Sembol", placeholder="THYAO.IS", key="p_h")
        with p2: p_a = st.number_input("Adet", min_value=0.0001, value=1.0, step=1.0, key="p_a")
        with p3: p_m = st.number_input("Alış Fiyatı", min_value=0.0001, value=1.0, step=0.01, key="p_m")
        with p4: p_t = st.date_input("Tarih", key="p_t")
        if st.button("Ekle"):
            if p_h:
                st.session_state.portfoy.append({
                    "hisse": p_h.strip().upper(),
                    "adet": p_a,
                    "maliyet": p_m,
                    "tarih": str(p_t)
                })
                portfoy_kaydet(st.session_state.portfoy)
                st.success("Eklendi!")
                st.rerun()

    if not st.session_state.portfoy:
        st.markdown("""<div style="text-align:center;padding:60px 20px;">
          <div style="font-family:'Sora',sans-serif;font-size:40px;font-weight:800;color:var(--border);">PORTFOY</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--txt3);
                      letter-spacing:.2em;margin-top:10px;text-transform:uppercase;">Henüz hisse eklenmedi</div>
        </div>""", unsafe_allow_html=True)
        return

    with st.spinner("Güncelleniyor..."):
        rows = []
        for p in st.session_state.portfoy:
            try:
                tk = yf.download(p["hisse"], period="5d", progress=False, auto_adjust=True)
                if isinstance(tk.columns, pd.MultiIndex):
                    tk.columns = tk.columns.get_level_values(0)
                if len(tk) > 0:
                    g   = round(float(tk["Close"].squeeze().iloc[-1]), 4)
                    gd  = round(g * p["adet"], 2)
                    mt  = round(p["maliyet"] * p["adet"], 2)
                    kz  = round(gd - mt, 2)
                    kzy = round(((g - p["maliyet"]) / p["maliyet"]) * 100, 2)
                    rows.append({
                        "Hisse": p["hisse"], "Adet": p["adet"], "Alis": p["maliyet"],
                        "Guncel": g, "Deger": gd, "Maliyet": mt,
                        "KZ_TL": kz, "KZ_PCT": kzy, "Tarih": p.get("tarih", "-")
                    })
            except:
                pass

    if not rows:
        st.warning("Fiyat verisi alınamadı.")
        return

    p_df = pd.DataFrame(rows)

    td   = p_df["Deger"].sum()
    tm   = p_df["Maliyet"].sum()
    tkz  = p_df["KZ_TL"].sum()
    tkzy = round(((td - tm) / tm) * 100, 2) if tm else 0

    pm1, pm2, pm3, pm4 = st.columns(4)
    with pm1: st.metric("Portföy Değeri",  f"{td:,.2f}")
    with pm2: st.metric("Toplam Maliyet",  f"{tm:,.2f}")
    with pm3: st.metric("Toplam K/Z",      f"{tkz:+,.2f}", delta=f"{tkzy:+.2f}%")
    with pm4: st.metric("Hisse Sayısı",    len(p_df))

    def kz_r(v):
        try:
            return "color:#0fdb7a;font-weight:600" if float(v) >= 0 else "color:#ff3b5c;font-weight:600"
        except:
            return ""

    st.dataframe(
        p_df.rename(columns={"KZ_TL": "K/Z TL", "KZ_PCT": "K/Z %", "Alis": "Alış",
                              "Guncel": "Güncel", "Deger": "Değer"})
            .style.map(kz_r, subset=["K/Z TL", "K/Z %"])
            .format({"Alış": "{:.4f}", "Güncel": "{:.4f}", "Değer": "{:,.2f}",
                     "Maliyet": "{:,.2f}", "K/Z TL": "{:+,.2f}", "K/Z %": "{:+.2f}%"}),
        use_container_width=True, height=300
    )

    st.markdown("---")

    from grafik import portfoy_performans_grafik
    pc1, pc2 = st.columns(2)
    with pc1:
        portfoy_performans_grafik(p_df.rename(columns={"Deger": "Güncel Değer"}))
    with pc2:
        fig_kz = go.Figure(go.Bar(
            x=p_df["Hisse"], y=p_df["KZ_PCT"],
            marker_color=["#0fdb7a" if v >= 0 else "#ff3b5c" for v in p_df["KZ_PCT"]],
            text=[f"{v:+.2f}%" for v in p_df["KZ_PCT"]], textposition="outside"
        ))
        fig_kz.update_layout(
            title=dict(text="K/Z Dağılımı (%)", font=dict(color="#d4a843", size=13)),
            paper_bgcolor="#020408", plot_bgcolor="#0a1020",
            font=dict(color="#edf0f7"),
            yaxis=dict(gridcolor="#0e1826", ticksuffix="%"),
            xaxis=dict(gridcolor="#0e1826"),
            height=300, margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig_kz, use_container_width=True)

    # ── Korelasyon & Diversifikasyon Analizi (Tavsiye #3) ───────────
    if KORELASYON_AKTIF and len(p_df) >= 2:
        st.markdown("---")
        with st.expander("📊 Korelasyon & Diversifikasyon Analizi", expanded=False):
            semboller = list(p_df["Hisse"])
            
            with st.spinner("Korelasyon matrisi hesaplanıyor..."):
                try:
                    rapor = korelasyon_raporu(semboller)
                    
                    # Diversifikasyon skoru
                    skor = rapor['diversifikasyon_skoru']
                    skor_renk = "#0fdb7a" if skor >= 75 else ("#f5cc6a" if skor >= 50 else "#ff3b5c")
                    skor_etiket = "✅ İYİ" if skor >= 75 else ("🟡 ORTA" if skor >= 50 else "🔴 ZAYIF")
                    
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.markdown(f"""
                        <div style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                                    border:1px solid rgba(30,51,85,0.3);border-radius:10px;padding:14px 16px;">
                            <div style="font-size:9px;color:#8a9bb5;letter-spacing:.1em;">DİVERSİFİKASYON SKORU</div>
                            <div style="font-size:32px;font-weight:800;color:{skor_renk};margin:6px 0;">
                                {skor}/100 <span style="font-size:14px;">{skor_etiket}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with c2:
                        # Sektör dağılımı
                        if rapor['sektor_analizi']['sektor_dagilimi']:
                            dagilim = rapor['sektor_analizi']['sektor_dagilimi']
                            dag_str = " | ".join([f"{s}: %{a*100:.0f}" for s, a in sorted(dagilim.items(), key=lambda x: -x[1])])
                            st.markdown(f"""
                            <div style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                                        border:1px solid rgba(30,51,85,0.3);border-radius:10px;padding:14px 16px;">
                                <div style="font-size:9px;color:#8a9bb5;letter-spacing:.1em;">SEKTÖR DAĞILIMI</div>
                                <div style="font-size:13px;color:#c4cdd9;margin:6px 0;">{dag_str}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Yüksek korelasyon uyarıları
                    if rapor['yuksek_korelasyonlu']:
                        st.markdown("### ⚠️ Yüksek Korelasyonlu Çiftler")
                        for c in rapor['yuksek_korelasyonlu'][:5]:
                            uyari_ikon = "🔴" if c['ayni_sektor'] else "🟡"
                            st.markdown(
                                f"{uyari_ikon} **{c['hisse1']}** ↔ **{c['hisse2']}**: "
                                f"%{c['korelasyon']*100:.1f} {c['uyari']}"
                            )
                    
                    # Tavsiyeler
                    if rapor['tavsiyeler']:
                        st.markdown("### 📋 Tavsiyeler")
                        for t in rapor['tavsiyeler']:
                            st.markdown(f"- {t}")
                    
                    # Optimize önerisi
                    if len(semboller) >= 3:
                        optimize = portfoy_optimize_et(semboller)
                        if len(optimize) < len(semboller):
                            cikanlar = [s for s in semboller if s not in optimize]
                            st.info(f"💡 **Optimizasyon Önerisi:** {', '.join(cikanlar)} hisseleri "
                                   f"yüksek korelasyonlu, portföyden çıkarılması önerilir.")
                
                except Exception as e:
                    st.warning(f"Korelasyon analizi yapılamadı: {e}")
    
    st.markdown("---")
    sil_h = st.selectbox("Portföyden Çıkar", [p["hisse"] for p in st.session_state.portfoy])
    if st.button("Sil"):
        st.session_state.portfoy = [p for p in st.session_state.portfoy if p["hisse"] != sil_h]
        portfoy_kaydet(st.session_state.portfoy)
        st.rerun()
