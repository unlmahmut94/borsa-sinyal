# ══════════════════════════════════════════════════════════════════════
#  HİSSE ANALİZ PANELİ (tam ekran) · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
import yfinance as yf
import analiz
from analiz import (
    tek_hisse_detay, macd_sinyal_hesapla, bollinger_sinyal_hesapla,
    macd_deger_hesapla
)
from grafik import ana_grafik, formasyon_bilgi_paneli, _formasyon_cizimleri
from mod_haberler import tum_sistemi_haber_tara
from mod_teknik_analiz import teknik_analiz_paneli
from hisse_isimleri import HISSE_ISIMLERI
from mod_formasyon import formasyon_analizi


def hisse_analiz_paneli(sembol: str, key_prefix: str = ""):
    if not sembol:
        return
    isim = HISSE_ISIMLERI.get(sembol, sembol)
    flag = "TR" if ".IS" in sembol else "US"

    # ── Üst bar: geri + hisse başlığı ───────────────────────────────
    h1, h2 = st.columns([1, 11])
    with h1:
        if st.button("← GERİ", key=f"{key_prefix}_geri_{sembol}", use_container_width=True):
            st.session_state.secilen_hisse = None
            st.rerun()
    with h2:
        st.markdown(f"""
        <div class="fade-in" style="padding:6px 0 10px 0;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
          <span style="font-family:'JetBrains Mono',monospace;font-size:24px;
                       font-weight:800;color:var(--txt1);letter-spacing:.04em;">{flag} {sembol}</span>
          <span style="font-family:'Sora',sans-serif;font-size:14px;
                       font-weight:300;color:var(--txt2);">{isim}</span>
          <span style="background:rgba(30,51,85,0.3);padding:3px 12px;border-radius:14px;
                       font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--txt3);
                       border:1px solid rgba(42,74,120,0.25);margin-left:auto;">
            {flag} PİYASA</span>
        </div>
        """, unsafe_allow_html=True)

    # ── YZ FORMASYON OKUYUCU ────────────────────────────────────────
    try:
        hist_data = yf.Ticker(sembol).history(period="3mo")
        bulunan_formasyonlar = formasyon_analizi(hist_data)
        if bulunan_formasyonlar:
            st.markdown(
                '<span class="section-label">🤖 YZ Grafik Formasyon Analizi</span>',
                unsafe_allow_html=True
            )
            for f in bulunan_formasyonlar:
                icon = {"success": "✅", "error": "🔴", "warning": "⚠️"}.get(f['tip'], "ℹ️")
                bg = {
                    "success": "rgba(34,230,145,0.06)",
                    "error": "rgba(255,79,109,0.06)",
                    "warning": "rgba(255,140,66,0.06)"
                }.get(f['tip'], "rgba(10,18,36,0.5)")
                border = {
                    "success": "rgba(34,230,145,0.2)",
                    "error": "rgba(255,79,109,0.2)",
                    "warning": "rgba(255,140,66,0.2)"
                }.get(f['tip'], "rgba(30,51,85,0.3)")
                st.markdown(f"""
                <div class="fade-in" style="background:{bg};border:1px solid {border};
                            border-radius:10px;padding:14px 18px;margin-bottom:8px;
                            backdrop-filter:blur(8px);">
                  <b style="color:var(--txt1);">{icon} {f['baslik']}</b>
                  <div style="font-size:12px;color:var(--txt2);margin-top:6px;line-height:1.6;">
                    {f['detay']}
                  </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    except:
        pass

    # ── 4 sekme ─────────────────────────────────────────────────────
    dtab1, dtab2, dtab3, dtab4 = st.tabs([
        "📋 GENEL BAKIŞ", "📈 GRAFİK", "🔬 TEMEL-TEKNİK ANALİZ", "📰 HABERLER"
    ])

    # ══ TAB 1 — GENEL BAKIŞ ══════════════════════════════════════════
    with dtab1:
        data_gb, info_gb = analiz.tek_hisse_detay(sembol)
        if data_gb is not None:
            son_gb = data_gb['Close'].iloc[-1]
            st.metric(
                "GÜNCEL FİYAT", f"{son_gb:,.4f}",
                f"{((son_gb - data_gb['Close'].iloc[0]) / data_gb['Close'].iloc[0]) * 100:.2f}%"
            )

            # NLP Haber Analizi
            with st.spinner("Haberler analiz ediliyor..."):
                ozel_haberler = tum_sistemi_haber_tara((sembol,))
                h_skor = analiz.haber_skoru_hesapla(ozel_haberler)
                skor_renk = "#0fdb7a" if h_skor > 0 else ("#ff3b5c" if h_skor < 0 else "#f5cc6a")
                st.markdown(f"""
                <div class="glass-card" style="padding:14px 18px;margin-top:8px;">
                  📢 <b style="color:{skor_renk};">Haber Duyarlılık Skoru: {h_skor}</b> (NLP)
                </div>
                """, unsafe_allow_html=True)

            # SMC Paneli
            st.markdown('<span class="section-label">Smart Money Concepts</span>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.info(f"📍 **Order Block (Destek):** {analiz.tespit_order_block(data_gb)}")
            c2.success(f"🏗️ **Market Yapısı:** {analiz.kontrol_market_yapisi(data_gb)}")

            # Temel Analiz
            st.markdown("---")
            st.markdown('<span class="section-label">Finansal Röntgen</span>', unsafe_allow_html=True)
            tk = yf.Ticker(sembol)
            t1, t2 = st.columns(2)
            t1.metric("Piotroski F-Score", f"{analiz.hesapla_piotroski_f_score(tk)} / 5")
            t2.metric("Altman Z-Score", analiz.hesapla_altman_z_score(tk, info_gb))

    # ══ TAB 2 — GRAFİK ═══════════════════════════════════════════════
    with dtab2:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        c_g1, c_g2, c_g3 = st.columns([2, 2, 2])
        with c_g1:
            ana_gostergeler = st.multiselect(
                "📈 Grafik Üstü Göstergeler",
                ["MA20", "MA50", "MA200", "EMA9", "EMA21", "BB", "PSAR", "VWAP"],
                default=["MA20", "MA50", "BB"], key=f"ana_g_{sembol}"
            )
        with c_g2:
            alt_gostergeler = st.multiselect(
                "📊 Alt Göstergeler",
                ["MACD", "RSI", "Stochastic", "ADX", "CCI", "MFI", "Momentum", "ATR"],
                default=["MACD", "RSI"], max_selections=2, key=f"alt_g_{sembol}"
            )
        with c_g3:
            st.markdown(
                '<div style="margin-top:28px;font-family:Sora,sans-serif;color:var(--txt3);'
                'font-size:12px;text-align:right;">💡 <i>Sınırsız Zoom için fare tekerleğini kullanın</i></div>',
                unsafe_allow_html=True
            )

        g_alt1 = alt_gostergeler[0] if len(alt_gostergeler) > 0 else None
        g_alt2 = alt_gostergeler[1] if len(alt_gostergeler) > 1 else None

        with st.spinner("Pro Grafik Hazırlanıyor..."):
            data_grafik, _ = tek_hisse_detay(sembol, "1y", "1d")

            if data_grafik is not None:
                # 🔥 Tüm otomatik çizimler AKTİF: formasyon, destek/direnç, fibonacci, trend çizgileri
                fig = ana_grafik(
                    data_grafik, sembol,
                    gosterge_alt=g_alt1,
                    gosterge_alt2=g_alt2,
                    overlay_list=ana_gostergeler,
                    show_volume=True,
                    otomatik_cizim=True,
                    destek_direnc=True,
                    formasyon_ciz=True,
                    fibonacci_ciz=True
                )

                # 📣 Formasyon bilgi panelini hesapla ve göster
                cizimler = _formasyon_cizimleri(data_grafik)
                formasyon_sayisi = len([k for k in cizimler.keys() 
                                        if k not in ['destekler', 'direncler', 'fibonacci']])
                destek_sayisi = len(cizimler.get('destekler', {}).get('seviyeler', []))
                direnc_sayisi = len(cizimler.get('direncler', {}).get('seviyeler', []))

                # 📊 Formasyon özet çubuğu
                if formasyon_sayisi > 0 or destek_sayisi > 0:
                    ozet_parcalar = []
                    if formasyon_sayisi > 0:
                        ozet_parcalar.append(f"📐 <b>{formasyon_sayisi}</b> formasyon tespit edildi")
                    if destek_sayisi > 0:
                        ozet_parcalar.append(f"🟢 <b>{destek_sayisi}</b> destek seviyesi")
                    if direnc_sayisi > 0:
                        ozet_parcalar.append(f"🔴 <b>{direnc_sayisi}</b> direnç seviyesi")
                    if 'fibonacci' in cizimler:
                        ozet_parcalar.append("📏 Fibonacci çizildi")
                    if 'trend_yukselen' in cizimler:
                        ozet_parcalar.append("↗ Yükselen trend")
                    if 'trend_alcalan' in cizimler:
                        ozet_parcalar.append("↘ Alçalan trend")

                    st.markdown(f"""
                    <div style="background:rgba(41,98,255,0.06);border:1px solid rgba(41,98,255,0.12);
                                border-radius:8px;padding:6px 14px;margin-bottom:8px;
                                font-size:11px;color:var(--txt2);display:flex;gap:16px;flex-wrap:wrap;">
                        {" · ".join(ozet_parcalar)}
                    </div>
                    """, unsafe_allow_html=True)

                # 🎯 İNDİKATÖR ANLAMI RENK KODLARI
                st.markdown("""
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:4px;font-size:10px;color:var(--txt3);">
                    <span style="background:rgba(41,98,255,0.15);padding:1px 8px;border-radius:4px;">🔵 MA/EMA</span>
                    <span style="background:rgba(255,109,0,0.15);padding:1px 8px;border-radius:4px;">🟠 MA50</span>
                    <span style="background:rgba(120,123,134,0.15);padding:1px 8px;border-radius:4px;">⚪ MA200</span>
                    <span style="background:rgba(8,153,129,0.15);padding:1px 8px;border-radius:4px;">🟢 Yükseliş/Destek</span>
                    <span style="background:rgba(242,54,69,0.15);padding:1px 8px;border-radius:4px;">🔴 Düşüş/Direnç</span>
                    <span style="background:rgba(245,204,106,0.15);padding:1px 8px;border-radius:4px;">🟡 BB Sıkışma</span>
                </div>
                """, unsafe_allow_html=True)

                pro_ayar = {
                    'displaylogo': False,
                    'scrollZoom': True,
                    'displayModeBar': True,
                    'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'],
                    'modeBarButtonsToRemove': ['sendDataToCloud', 'lasso2d', 'select2d'],
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': f'{sembol}_grafik',
                        'height': 800,
                        'width': 1400,
                        'scale': 2
                    }
                }
                st.plotly_chart(fig, use_container_width=True, config=pro_ayar)

                # 📋 FORMASYON DETAY KARTLARI
                if formasyon_sayisi > 0:
                    st.markdown(
                        '<span class="section-label">📋 Grafikte Tespit Edilen Formasyonlar</span>',
                        unsafe_allow_html=True
                    )
                    formasyon_bilgi_paneli(cizimler)
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            else:
                st.warning("Bu hisse için grafik verisi oluşturulamadı.")

    # ══ TAB 3 — TEMEL-TEKNİK ANALİZ ═══════════════════════════════════
    with dtab3:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        with st.spinner("Tüm teknik indikatörler, destek seviyeleri ve şirket bilançoları yükleniyor..."):
            data_ta, info_ta = analiz.tek_hisse_detay(sembol, "1y", "1d")

            if data_ta is not None and not data_ta.empty:
                import numpy as np
                son_fiyat = float(data_ta['Close'].iloc[-1])

                # ── HIZLI TEMEL ÇARPANLAR ──
                st.markdown('<span class="section-label">Hızlı Temel Çarpanlar</span>', unsafe_allow_html=True)
                fk = info_ta.get('trailingPE', 0)
                pddd = info_ta.get('priceToBook', 0)
                hedef_fiyat = info_ta.get('targetMeanPrice', 0)
                zirve_52 = info_ta.get('fiftyTwoWeekHigh', 0)
                dip_52 = info_ta.get('fiftyTwoWeekLow', 0)

                t_c1, t_c2, t_c3, t_c4, t_c5 = st.columns(5)
                t_c1.metric("F/K", f"{fk:.2f}" if fk else "N/A", "Yatırım Geri Dönüşü", delta_color="off")
                t_c2.metric("PD/DD", f"{pddd:.2f}" if pddd else "N/A", "Defter Değeri", delta_color="off")
                t_c3.metric(
                    "52 Hafta Zirve", f"{zirve_52:,.2f}" if zirve_52 else "N/A",
                    f"%{((son_fiyat-zirve_52)/zirve_52)*100:.1f} Uzaklıkta" if zirve_52 else "",
                    delta_color="inverse"
                )
                t_c4.metric(
                    "52 Hafta Dip", f"{dip_52:,.2f}" if dip_52 else "N/A",
                    f"%{((son_fiyat-dip_52)/dip_52)*100:.1f} Üzerinde" if dip_52 else ""
                )
                t_c5.metric(
                    "1 Yıllık Hedef", f"{hedef_fiyat:,.2f}" if hedef_fiyat else "N/A",
                    "Analist Ortalaması" if hedef_fiyat else "", delta_color="off"
                )

                # ── PİVOT SEVİYELERİ ──
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                st.markdown(
                    '<span class="section-label">Gelişmiş Destek ve Direnç Seviyeleri (Pivot)</span>',
                    unsafe_allow_html=True
                )

                high_prev = float(data_ta['High'].iloc[-2]) if len(data_ta) > 1 else float(data_ta['High'].iloc[-1])
                low_prev = float(data_ta['Low'].iloc[-2]) if len(data_ta) > 1 else float(data_ta['Low'].iloc[-1])
                close_prev = float(data_ta['Close'].iloc[-2]) if len(data_ta) > 1 else float(data_ta['Close'].iloc[-1])

                pivot = (high_prev + low_prev + close_prev) / 3
                r1 = (2 * pivot) - low_prev
                r2 = pivot + (high_prev - low_prev)
                s1 = (2 * pivot) - high_prev
                s2 = pivot - (high_prev - low_prev)

                def pivot_kutu(isim, fiyat, guncel, renk):
                    fark = ((fiyat - guncel) / guncel) * 100
                    ok = "▲" if fark > 0 else "▼"
                    return f"""
                    <div style="background:linear-gradient(160deg,rgba(10,18,36,0.9),rgba(6,12,26,0.8));
                                border-top:3px solid {renk};padding:14px 10px;border-radius:10px;
                                text-align:center;backdrop-filter:blur(8px);">
                        <div style="font-size:10px;color:var(--txt3);margin-bottom:6px;
                                    font-family:'JetBrains Mono',monospace;">{isim}</div>
                        <div style="font-size:17px;font-weight:800;color:#eef2f7;">{fiyat:,.2f}</div>
                        <div style="font-size:11px;color:{renk};margin-top:4px;">{ok} %{abs(fark):.1f}</div>
                    </div>
                    """

                p_c1, p_c2, p_c3, p_c4, p_c5 = st.columns(5)
                with p_c1: st.markdown(pivot_kutu("Direnç 2", r2, son_fiyat, "#ff3b5c"), unsafe_allow_html=True)
                with p_c2: st.markdown(pivot_kutu("Direnç 1", r1, son_fiyat, "#ff3b5c"), unsafe_allow_html=True)
                with p_c3: st.markdown(pivot_kutu("PIVOT (Nötr)", pivot, son_fiyat, "var(--gold)"), unsafe_allow_html=True)
                with p_c4: st.markdown(pivot_kutu("Destek 1", s1, son_fiyat, "#0fdb7a"), unsafe_allow_html=True)
                with p_c5: st.markdown(pivot_kutu("Destek 2", s2, son_fiyat, "#0fdb7a"), unsafe_allow_html=True)

                # ── TREND VE OSİLATÖRLER ──
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                st.markdown(
                    '<span class="section-label">Hareketli Ortalamalar ve Osilatörler</span>',
                    unsafe_allow_html=True
                )

                ma20 = float(data_ta['Close'].rolling(20).mean().iloc[-1]) if len(data_ta)>=20 else 0
                ma50 = float(data_ta['Close'].rolling(50).mean().iloc[-1]) if len(data_ta)>=50 else 0
                ma200 = float(data_ta['Close'].rolling(200).mean().iloc[-1]) if len(data_ta)>=200 else 0
                rsi = float(analiz.rsi_serisi(data_ta['Close']).iloc[-1])
                macd_sinyal = macd_sinyal_hesapla(data_ta)
                bb_sinyal = bollinger_sinyal_hesapla(data_ta, son_fiyat)
                macd_val = macd_deger_hesapla(data_ta)

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("MA 20 (Kısa Vade)", f"{ma20:,.2f}", f"%{(son_fiyat-ma20)/ma20*100:+.2f} Uzaklıkta")
                m2.metric("MA 50 (Orta Vade)", f"{ma50:,.2f}", f"%{(son_fiyat-ma50)/ma50*100:+.2f} Uzaklıkta")
                m3.metric("MA 200 (Uzun Vade)", f"{ma200:,.2f}", f"%{(son_fiyat-ma200)/ma200*100:+.2f} Uzaklıkta")
                r_renk = "normal" if 30 <= rsi <= 70 else "inverse"
                m4.metric(
                    "RSI (Aşırı Alım/Satım)", f"{rsi:.1f}",
                    "Aşırı Satım" if rsi<30 else "Aşırı Alım" if rsi>70 else "Nötr",
                    delta_color=r_renk
                )

                s1c, s2c, s3c = st.columns(3)
                s1c.metric("MACD", f"{macd_val:.4f}" if macd_val is not None else "N/A")
                s2c.metric(
                    "MACD Sinyal", macd_sinyal,
                    delta="Yukarı momentum" if macd_sinyal == "AL"
                    else ("Aşağı momentum" if macd_sinyal == "SAT" else "Nötr")
                )
                s3c.metric(
                    "BB Sinyal", bb_sinyal,
                    delta="Alt bant altı" if bb_sinyal == "AL"
                    else ("Üst bant üstü" if bb_sinyal == "SAT" else "Bantlar arası")
                )

                teknik_analiz_paneli(data_ta, info_ta, son_fiyat, sembol)
            else:
                st.warning("Teknik analiz verisi hesaplanamadı.")

        # ── ŞİRKET FİNANSALLARI ──
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown(
            '<span class="section-label">Şirket Finansalları ve Bilanço Özeti</span>',
            unsafe_allow_html=True
        )
        try:
            from mod_sirket import sirket_paneli
            sirket_paneli(sembol)
        except Exception as e:
            st.error(f"Şirket paneli yüklenemedi: {e}")

    # ══ TAB 4 — HABERLER ═════════════════════════════════════════════
    with dtab4:
        with st.spinner("Haberler taranıyor ve analiz ediliyor..."):
            ozel_haberler = tum_sistemi_haber_tara((sembol,))
            h_duyarlilik = analiz.haber_skoru_hesapla(ozel_haberler)

        duyarlilik_renk = "#0fdb7a" if h_duyarlilik > 0 else ("#ff3b5c" if h_duyarlilik < 0 else "#f5cc6a")
        st.markdown(f"""
        <div class="fade-in glass-card" style="padding:18px 20px;margin-bottom:20px;">
            <div style="font-size:11px;color:var(--txt3);margin-bottom:10px;
                        font-family:'JetBrains Mono',monospace;letter-spacing:.1em;">
              HABER DUYARLILIK SKORU (NLP)</div>
            <div style="height:12px;background:rgba(0,0,0,0.3);border-radius:6px;
                        position:relative;overflow:hidden;">
                <div style="position:absolute;left:50%;height:100%;width:2px;
                            background:var(--txt3);z-index:2;"></div>
                <div style="position:absolute;left:{50 + (h_duyarlilik * 50)}%;height:100%;
                            width:12px;background:{duyarlilik_renk};border-radius:3px;
                            filter:blur(3px);transform:translateX(-6px);"></div>
                <div style="position:absolute;left:{50 + (h_duyarlilik * 50)}%;height:100%;
                            width:4px;background:{duyarlilik_renk};border-radius:2px;
                            transform:translateX(-2px);z-index:1;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;margin-top:8px;
                        font-family:'JetBrains Mono',monospace;font-size:10px;">
                <span style="color:#ff3b5c;">NEGATİF</span>
                <span style="color:{duyarlilik_renk};font-weight:700;font-size:13px;">{h_duyarlilik}</span>
                <span style="color:#0fdb7a;">POZİTİF</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if ozel_haberler:
            for hb in ozel_haberler[:6]:
                st.markdown(f"""
                <div class="fade-in" style="background:linear-gradient(160deg,rgba(10,18,36,0.8),rgba(6,11,18,0.65));
                            border:1px solid rgba(255,255,255,0.04);
                            border-left:3px solid var(--gold);
                            border-radius:10px;padding:14px 16px;margin-bottom:8px;
                            backdrop-filter:blur(8px);">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--txt3);
                              margin-bottom:8px;">
                    ⏱ {hb.get('zaman', 'Az Önce')}
                    <span style="color:rgba(255,255,255,0.15)">|</span> {hb.get('yayinci', '')}
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:13px;font-weight:600;
                              color:var(--txt1);line-height:1.5;">
                    <a href="{hb.get('url', '#')}" target="_blank"
                       style="color:inherit;text-decoration:none;">
                      {hb.get('baslik', '')}
                    </a>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Bu hisse için son günlerde yayınlanmış önemli bir haber bulunamadı.")