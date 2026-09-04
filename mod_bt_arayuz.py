# ══════════════════════════════════════════════════════════════════════
#  mod_bt_arayuz.py — Strateji Testi (Backtest) · v3.2 ✨
#  Gelişmiş metrikler: Sharpe, Sortino, Calmar, VaR, Benchmark, Buy&Hold
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
from mod_animasyon import bolum_baslik
from hisse_isimleri import HISSE_ISIMLERI


def _metric_html(deger, etiket, renk="#d1d4dc", alt_text=""):
    return f"""
    <div style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                border:1px solid rgba(30,51,85,0.3);border-radius:10px;
                padding:14px 16px;text-align:center;backdrop-filter:blur(8px);">
        <div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:800;
                    color:{renk};letter-spacing:-.02em;">{deger}</div>
        <div style="font-family:'Sora',sans-serif;font-size:9px;color:#8a9bb5;
                    letter-spacing:.12em;text-transform:uppercase;margin-top:4px;">{etiket}</div>
        {f'<div style="font-size:8px;color:#5a6d85;margin-top:2px;">{alt_text}</div>' if alt_text else ''}
    </div>"""


def render_bt_arayuz():
    bolum_baslik(
        "Strateji Testi (Backtest)",
        "Geçmiş verilere göre ticaret stratejinizin performansını ölçün · Sharpe · Sortino · VaR",
        bg_url="https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1200&auto=format&fit=crop"
    )
    bt_c1, bt_c2 = st.columns([1, 3])
    with bt_c1:
        hisse_secenekleri = [f"{sembol} - {isim}" for sembol, isim in HISSE_ISIMLERI.items()]
        populerler = [
            "THYAO.IS - Türk Hava Yolları", "AAPL - Apple Inc.",
            "GARAN.IS - Garanti BBVA Bankası", "NVDA - NVIDIA Corporation",
            "KCHOL.IS - Koç Holding"
        ]
        kalanlar = [h for h in hisse_secenekleri if h not in populerler]
        arama_listesi = populerler + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar

        bt_secim = st.selectbox(
            "Hisse Ara veya Seç:", options=arama_listesi,
            index=None, placeholder="🔍 Aramak için tıklayın veya yazın...",
            key="bt_hisse_smart"
        )
        bt_hisse = bt_secim.split(" - ")[0] if bt_secim and "---" not in bt_secim else None

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        bt_gun = st.number_input("Test Periyodu (Gün)", min_value=90, max_value=1825, value=365, step=90)
        bt_sermaye = st.number_input("Başlangıç Sermayesi (₺)", min_value=1000, max_value=1000000, value=10000, step=5000)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        bt_baslat = st.button(
            "🚀 TESTİ ÇALIŞTIR", use_container_width=True, type="primary", key="bt_baslat_btn"
        )

    with bt_c2:
        if bt_baslat:
            if not bt_hisse:
                st.warning("⚠️ Lütfen testi çalıştırmadan önce geçerli bir hisse seçin!")
            else:
                with st.spinner(f"{bt_hisse} için {bt_gun} günlük strateji testi yapılıyor..."):
                    import backtest
                    bt_sonuc = backtest.backtest_calistir(
                        bt_hisse.upper(),
                        periyot_gun=int(bt_gun),
                        sermaye_baslangic=float(bt_sermaye)
                    )

                    if bt_sonuc:
                        st.markdown(f"""
                        <div class="fade-in" style="font-family:'Sora',sans-serif;font-size:18px;
                                    font-weight:700;color:var(--txt1);margin-bottom:16px;">
                          📊 {bt_hisse.upper()} — Backtest Performansı ({bt_gun} gün)
                        </div>
                        """, unsafe_allow_html=True)

                        # ── PERFORMANS METRİKLERİ ──
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            getiri_renk = "#0fdb7a" if bt_sonuc['Getiri %'] >= 0 else "#ff3b5c"
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Getiri %']}", "Net Getiri", getiri_renk
                            ), unsafe_allow_html=True)
                        with c2:
                            st.markdown(_metric_html(
                                f"₺{bt_sonuc['Final']:,.0f}", "Final Bakiye", "#4db8ff",
                                f"Baş: ₺{bt_sonuc['Baslangic']:,}"
                            ), unsafe_allow_html=True)
                        with c3:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Win Rate %']}", "Win Rate", "#f0c040"
                            ), unsafe_allow_html=True)
                        with c4:
                            st.markdown(_metric_html(
                                str(bt_sonuc['İşlem Sayısı']), "Toplam İşlem", "#d1d4dc"
                            ), unsafe_allow_html=True)

                        # ── BUY & HOLD KARŞILAŞTIRMA ──
                        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                        c_bh1, c_bh2, c_bh3 = st.columns(3)
                        with c_bh1:
                            bh_renk = "#0fdb7a" if bt_sonuc['BuyHold %'] >= 0 else "#ff3b5c"
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['BuyHold %']}", "Buy & Hold", bh_renk
                            ), unsafe_allow_html=True)
                        with c_bh2:
                            bm_renk = "#0fdb7a" if bt_sonuc['Benchmark %'] >= 0 else "#ff3b5c"
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Benchmark %']}", "Benchmark Endeks", bm_renk,
                                "XU100 / S&P 500"
                            ), unsafe_allow_html=True)
                        with c_bh3:
                            alfa_renk = "#0fdb7a" if bt_sonuc['Alfa %'] >= 0 else "#ff3b5c"
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Alfa %']}", "Alfa (Fark)", alfa_renk,
                                "Strateji − Endeks"
                            ), unsafe_allow_html=True)

                        # ── RİSK METRİKLERİ ──
                        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                        st.markdown(
                            '<span class="section-label">⚖️ Risk Metrikleri</span>',
                            unsafe_allow_html=True
                        )
                        r1, r2, r3, r4 = st.columns(4)
                        with r1:
                            sharpe_renk = "#0fdb7a" if bt_sonuc['Sharpe Oranı'] >= 1 else ("#f0c040" if bt_sonuc['Sharpe Oranı'] >= 0 else "#ff3b5c")
                            st.markdown(_metric_html(
                                str(bt_sonuc['Sharpe Oranı']), "Sharpe Oranı", sharpe_renk,
                                "≥1 iyi, ≥2 çok iyi"
                            ), unsafe_allow_html=True)
                        with r2:
                            sortino_renk = "#0fdb7a" if bt_sonuc['Sortino Oranı'] >= 1 else ("#f0c040" if bt_sonuc['Sortino Oranı'] >= 0 else "#ff3b5c")
                            st.markdown(_metric_html(
                                str(bt_sonuc['Sortino Oranı']), "Sortino Oranı", sortino_renk,
                                "Sadece negatif risk"
                            ), unsafe_allow_html=True)
                        with r3:
                            calm_renk = "#0fdb7a" if bt_sonuc['Calmar Oranı'] >= 0.5 else "#f0c040"
                            st.markdown(_metric_html(
                                str(bt_sonuc['Calmar Oranı']), "Calmar Oranı", calm_renk,
                                "Getiri / Max DD"
                            ), unsafe_allow_html=True)
                        with r4:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Kelly Kriteri %']}", "Kelly Pozisyon", "#4db8ff",
                                "Optimal risk %"
                            ), unsafe_allow_html=True)

                        # ── DRAWDOWN & VaR ──
                        r5, r6, r7, r8 = st.columns(4)
                        with r5:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Max Drawdown %']}", "Max Drawdown", "#ff3b5c",
                                f"{bt_sonuc['Max DD Süresi (gün)']} gün sürdü"
                            ), unsafe_allow_html=True)
                        with r6:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['VaR %95']}", "VaR %95", "#ff8c42",
                                "Maksimum beklenen kayıp"
                            ), unsafe_allow_html=True)
                        with r7:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['CVaR %95']}", "CVaR %95", "#ff8c42",
                                "Ortalama kuyruk kaybı"
                            ), unsafe_allow_html=True)
                        with r8:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['İflas İhtimali %']}", "İflas İhtimali", "#ff3b5c",
                                "Monte Carlo 1000 sim"
                            ), unsafe_allow_html=True)

                        # ── ORTALAMA İŞLEM METRİKLERİ ──
                        r9, r10, r11 = st.columns(3)
                        with r9:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Ort. Kar %']}", "Ortalama Kar", "#0fdb7a"
                            ), unsafe_allow_html=True)
                        with r10:
                            st.markdown(_metric_html(
                                f"%{bt_sonuc['Ort. Zarar %']}", "Ortalama Zarar", "#ff3b5c"
                            ), unsafe_allow_html=True)
                        with r11:
                            st.markdown(_metric_html(
                                str(bt_sonuc['Kar/Zarar Oranı']), "Kar/Zarar Oranı", "#f0c040",
                                f"Yıllık ~{bt_sonuc.get('Yıllık İşlem', 0):.0f} işlem"
                            ), unsafe_allow_html=True)

                        # ── İŞLEM GEÇMİŞİ ──
                        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
                        st.markdown(
                            '<span class="section-label">📜 İşlem Geçmişi (Al-Sat Noktaları)</span>',
                            unsafe_allow_html=True
                        )

                        df_islemler = bt_sonuc.get("Islemler")
                        if df_islemler is not None and not df_islemler.empty:
                            def islem_renklendir(val):
                                if "AL" in str(val):
                                    return "color:#0fdb7a;font-weight:bold;background:rgba(15,219,122,0.08);border-radius:4px;padding:2px 6px;"
                                if "SAT" in str(val) or "STOP" in str(val):
                                    return "color:#ff3b5c;font-weight:bold;background:rgba(255,59,92,0.08);border-radius:4px;padding:2px 6px;"
                                if "KAR" in str(val):
                                    return "color:#f0c040;font-weight:bold;background:rgba(240,192,64,0.08);border-radius:4px;padding:2px 6px;"
                                return ""

                            st.dataframe(
                                df_islemler.style.map(islem_renklendir, subset=["İşlem"]),
                                use_container_width=True, height=280
                            )
                        else:
                            st.caption("Bu periyot içinde hiç işlem yapılmadı (RSI sinyali üretilmedi).")
                    else:
                        st.error("Bu hisse için yeterli veri bulunamadı veya bir hata oluştu.")
        else:
            # Boş durum placeholder
            st.markdown("""
            <div style="text-align:center;padding:50px 20px;">
              <div style="font-family:'JetBrains Mono',monospace;font-size:60px;color:var(--border);">◈</div>
              <div style="font-family:'Sora',sans-serif;font-size:16px;color:var(--txt3);
                          margin-top:16px;letter-spacing:.05em;">
                Hisse seçip "TESTİ ÇALIŞTIR" butonuna basın
              </div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--txt3);
                          letter-spacing:.15em;margin-top:8px;">
                SHARPE · SORTINO · CALMAR · VaR · BENCHMARK
              </div>
            </div>
            """, unsafe_allow_html=True)