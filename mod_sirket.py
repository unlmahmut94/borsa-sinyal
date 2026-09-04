# ══════════════════════════════════════════════════════════════════════
#  mod_sirket.py — Temel Analiz ve Şirket Finansalları · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

try:
    from deep_translator import GoogleTranslator
    CEVIRI_AKTIF = True
except ImportError:
    CEVIRI_AKTIF = False


def sirket_paneli(sembol):
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    with st.spinner(f"{sembol} temel analiz ve bilanço verileri çekiliyor (Türkçeye Çevriliyor)..."):
        try:
            tk = yf.Ticker(sembol)
            info = tk.info
            fin = tk.financials

            isim = info.get('longName', sembol)
            calisan = info.get('fullTimeEmployees', 'Bilinmiyor')
            web = info.get('website', '#')

            sektor_ingilizce = info.get('sector', 'Bilinmiyor')
            endustri_ingilizce = info.get('industry', 'Bilinmiyor')
            ozet_ingilizce = info.get('longBusinessSummary', 'Şirket hakkında detaylı bilgi bulunamadı.')

            if CEVIRI_AKTIF:
                try:
                    sektor = GoogleTranslator(source='auto', target='tr').translate(sektor_ingilizce)
                    endustri = GoogleTranslator(source='auto', target='tr').translate(endustri_ingilizce)
                    ozet = GoogleTranslator(source='auto', target='tr').translate(ozet_ingilizce)
                except:
                    sektor, endustri, ozet = sektor_ingilizce, endustri_ingilizce, ozet_ingilizce
            else:
                sektor, endustri, ozet = sektor_ingilizce, endustri_ingilizce, ozet_ingilizce

            # ── ŞİRKET PROFİLİ ──
            st.markdown(f"""
            <div class="fade-in glass-card" style="padding:22px 24px;margin-bottom:20px;
                        border:1px solid rgba(77,184,255,0.15);border-left:4px solid var(--blue);">
                <div style="font-family:'Sora',sans-serif;font-size:20px;font-weight:700;
                            color:var(--txt1);margin-bottom:12px;">{isim}</div>
                <div style="display:flex;gap:18px;margin-bottom:16px;flex-wrap:wrap;
                            font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--gold);">
                    <span style="background:rgba(240,192,64,0.07);padding:4px 10px;border-radius:10px;
                                 border:1px solid rgba(240,192,64,0.15);">🏭 {sektor}</span>
                    <span style="background:rgba(240,192,64,0.07);padding:4px 10px;border-radius:10px;
                                 border:1px solid rgba(240,192,64,0.15);">🏢 {endustri}</span>
                    <span style="background:rgba(240,192,64,0.07);padding:4px 10px;border-radius:10px;
                                 border:1px solid rgba(240,192,64,0.15);">👥 {calisan}</span>
                    <a href="{web}" target="_blank"
                       style="background:rgba(77,184,255,0.07);padding:4px 12px;border-radius:10px;
                              border:1px solid rgba(77,184,255,0.2);color:#4db8ff;text-decoration:none;
                              font-size:11px;transition:all .2s;">
                      🌐 Web Sitesi</a>
                </div>
                <div style="font-family:'Sora',sans-serif;font-size:12px;color:var(--txt2);
                            line-height:1.7;opacity:.9;">
                    {ozet[:1000]}{'...' if len(ozet)>1000 else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── DEĞERLEME VE KARLILIK ──
            st.markdown('<span class="section-label">Değerleme ve Karlılık Oranları</span>', unsafe_allow_html=True)

            fk = info.get('trailingPE')
            pddd = info.get('priceToBook')
            roe = (info.get('returnOnEquity') or 0) * 100
            brut_marj = (info.get('grossMargins') or 0) * 100
            net_marj = (info.get('profitMargins') or 0) * 100
            borc_kaynak = info.get('debtToEquity')
            temettu = (info.get('dividendYield') or 0) * 100
            piyasa_degeri = info.get('marketCap') or 0

            if piyasa_degeri > 1e9: pd_str = f"{piyasa_degeri/1e9:.2f} Milyar"
            elif piyasa_degeri > 1e6: pd_str = f"{piyasa_degeri/1e6:.2f} Milyon"
            else: pd_str = f"{piyasa_degeri:,.0f}"
            para_birimi = "₺" if ".IS" in sembol else "$"

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Piyasa Değeri", f"{pd_str} {para_birimi}")
            c2.metric("F/K Oranı (P/E)", f"{fk:.2f}" if fk else "N/A", "Yatırımın geri dönüş süresi", delta_color="off")
            c3.metric("PD/DD (P/B)", f"{pddd:.2f}" if pddd else "N/A", "Defter değerinin kaç katı", delta_color="off")
            c4.metric("Özsermaye Karlılığı (ROE)", f"%{roe:.1f}" if roe else "N/A", "Yüksek olması istenir")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Brüt Kar Marjı", f"%{brut_marj:.1f}" if brut_marj else "N/A", "Satış maliyeti çıkarıldıktan sonra")
            c6.metric("Net Kar Marjı", f"%{net_marj:.1f}" if net_marj else "N/A", "Tüm giderler ve vergiler sonrası")
            c7.metric("Borç / Özsermaye", f"%{borc_kaynak:.1f}" if borc_kaynak else "N/A", "Finansal risk göstergesi")
            c8.metric("Temettü Verimi", f"%{temettu:.2f}" if temettu else "Temettü Yok", "Yıllık kâr payı ödemesi")

            # ── KARLILIK BÜYÜMESİ ──
            st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
            st.markdown('<span class="section-label">Geçmiş Yıllara Göre Karlılık Büyümesi</span>', unsafe_allow_html=True)

            if fin is not None and not fin.empty:
                istenen_veriler = ['Total Revenue', 'Gross Profit', 'Net Income']
                mevcut_veriler = [v for v in istenen_veriler if v in fin.index]

                if mevcut_veriler:
                    df_fin = fin.loc[mevcut_veriler].T
                    try:
                        df_fin.index = pd.to_datetime(df_fin.index).year
                    except:
                        pass
                    df_fin = df_fin.sort_index()

                    fig = go.Figure()
                    renkler = {'Total Revenue': '#2962FF', 'Gross Profit': '#f5cc6a', 'Net Income': '#0fdb7a'}
                    isimler = {'Total Revenue': 'Ciro (Toplam Satışlar)', 'Gross Profit': 'Brüt Kar', 'Net Income': 'Net Kar'}

                    for col in df_fin.columns:
                        fig.add_trace(go.Bar(
                            x=df_fin.index, y=df_fin[col],
                            name=isimler.get(col, col),
                            marker_color=renkler.get(col, '#ffffff'),
                            marker_line=dict(width=0)
                        ))

                    fig.update_layout(
                        barmode='group',
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#c4cdd9', family='Sora, sans-serif', size=11),
                        legend=dict(
                            orientation="h", yanchor="bottom", y=1.05,
                            xanchor="right", x=1, font=dict(size=10)
                        ),
                        yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
                        xaxis=dict(type='category', gridcolor="rgba(255,255,255,0.02)"),
                        margin=dict(l=0, r=0, t=30, b=0),
                        height=360
                    )

                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                    st.markdown(
                        '<div style="font-family:JetBrains Mono,monospace;font-size:10px;'
                        'color:var(--txt3);margin-bottom:4px;margin-top:8px;">'
                        'Rakamlar Para Birimi Cinsindendir (Milyar/Milyon)</div>',
                        unsafe_allow_html=True
                    )
                    df_tablo = df_fin.rename(columns=isimler).iloc[::-1]
                    for c in df_tablo.columns:
                        df_tablo[c] = df_tablo[c].apply(
                            lambda x: f"{x:,.0f} {para_birimi}" if pd.notnull(x) else "-"
                        )
                    st.dataframe(df_tablo, use_container_width=True)
                else:
                    st.info("Bu şirket için geçmiş gelir tablosu verileri bulunamadı.")
            else:
                st.info("Bu şirket için detaylı bilanço verileri çekilemedi.")

            # ── İŞ İLİŞKİLERİ ──
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            st.markdown(
                '<span class="section-label">İş İlişkileri, Sözleşmeler ve KAP / SEC Analizi</span>',
                unsafe_allow_html=True
            )
            st.markdown(f"""
            <div class="fade-in glass-card" style="padding:16px 20px;font-size:12px;
                        color:var(--txt2);line-height:1.7;">
                📌 <b>Bilgilendirme:</b> Şirketlerin ihaleleri kazanması, yeni anlaşmalar yapması
                veya sözleşme imzalaması doğrudan rakamsal veri olarak API sistemlerine
                (Yahoo Finance vb.) yansımaz.
                <br><br>
                Sistemin bu tür önemli gelişmeleri nasıl yorumladığını görmek için:
                <br>1. <b>Haberler Sekmesini Kullanın:</b> Yeni anlaşmalar haber olarak düştüğünde,
                Yapay Zeka Duyarlılık Motorumuz (NLP) o haberi anında okur ve
                <i>"Haber Duyarlılık Skoru"nu</i> pozitife çeker.
                <br>2. <b>BIST Hisseleri İçin:</b> KAP (Kamuyu Aydınlatma Platformu)
                bildirimlerindeki "Yeni İş İlişkisi" haberleri, o hissenin Taramalar'da
                "GÜÇLÜ AL" sinyaline girmesi için ek puan kazandırır.
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Şirket verileri yüklenirken sistemsel bir hata oluştu: {e}")