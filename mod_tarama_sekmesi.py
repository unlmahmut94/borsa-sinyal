# ══════════════════════════════════════════════════════════════════════
#  mod_tarama_sekmesi.py — Canlı Radar · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
import pandas as pd
import sqlite3
import os
import yfinance as yf
import numpy as np
from mod_animasyon import bolum_baslik
from mod_kripto_scalp import kripto_canli_tara
from hisseler_kripto import KRIPTO_LISTESI
from mod_formasyon import formasyon_analizi
from mod_filtreleme import filtreleme_paneli
from mod_detay_paneli import hisse_analiz_paneli

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")


def get_market_threshold(hisse_adi):
    """Piyasaya göre minimum hedef yüzdesi döndürür. (ESNETILDI)"""
    if ".IS" in hisse_adi:
        return 1.5
    elif any(x in hisse_adi.upper() for x in ["USD", "USDT", "BTC", "ETH", "SOL", "AVAX", "LINK", "ADA", "DOGE", "XRP", "DOT", "MATIC", "UNI", "ATOM"]):
        return 2.0
    elif hisse_adi in ["^IXIC", "QQQ"] or any(h in hisse_adi.upper() for h in ["NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "NFLX", "AMD", "INTC"]):
        return 2.0
    else:
        return 1.5


def render_teknik_ozet_kart(df_hisse, hisse_adi):
    """Bir hisse için özet teknik indikatör skor kartı döndürür (kompakt)."""
    try:
        if df_hisse.empty or 'Close' not in df_hisse.columns:
            return None

        close = df_hisse['Close'].dropna()
        if len(close) < 20:
            return None

        fiyat = float(close.iloc[-1])

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_val = float(macd_line.iloc[-1])
        macd_sig = float(signal_line.iloc[-1])
        macd_hist = macd_val - macd_sig

        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else ma20

        bb_orta = ma20
        bb_std = close.rolling(20).std().iloc[-1]
        bb_ust = bb_orta + 2 * bb_std
        bb_alt = bb_orta - 2 * bb_std
        bb_pos = ((fiyat - bb_alt) / (bb_ust - bb_alt)) * 100 if (bb_ust - bb_alt) > 0 else 50

        low_14 = df_hisse['Low'].rolling(14).min().iloc[-1]
        high_14 = df_hisse['High'].rolling(14).max().iloc[-1]
        stoch_k = ((fiyat - low_14) / (high_14 - low_14)) * 100 if (high_14 - low_14) > 0 else 50

        hacim_son = float(df_hisse['Volume'].iloc[-1]) if 'Volume' in df_hisse.columns else 0
        hacim_ort = float(df_hisse['Volume'].tail(20).mean()) if 'Volume' in df_hisse.columns else 0
        hacim_oran = (hacim_son / hacim_ort * 100) if hacim_ort > 0 else 100

        tr = pd.concat([
            df_hisse['High'] - df_hisse['Low'],
            (df_hisse['High'] - df_hisse['Close'].shift()).abs(),
            (df_hisse['Low'] - df_hisse['Close'].shift()).abs()
        ], axis=1).max(axis=1)
        atr_val = float(tr.rolling(14).mean().iloc[-1])
        atr_yuzde = (atr_val / fiyat) * 100 if fiyat > 0 else 0

        return {
            'fiyat': fiyat,
            'degisim_5': ((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6]) * 100 if len(close) >= 6 else 0,
            'rsi': rsi_val,
            'macd_val': macd_val,
            'macd_hist': macd_hist,
            'ma20': ma20,
            'ma50': ma50,
            'bb_pos': bb_pos,
            'bb_ust': bb_ust,
            'bb_alt': bb_alt,
            'stoch_k': stoch_k,
            'hacim_oran': hacim_oran,
            'atr_yuzde': atr_yuzde
        }
    except:
        return None


def render_sinyal_analiz_karti_kompakt(hisse_adi, fiyat, giris_fiyat, hedef, stop, sinyal_tipi, tarih, df_hisse, formasyon_metni):
    """Premium kompakt sinyal kartı."""
    anlik_fiyat = fiyat if fiyat and fiyat > 0 else giris_fiyat
    anlik_kar_yuzde = ((anlik_fiyat - giris_fiyat) / giris_fiyat) * 100 if giris_fiyat > 0 else 0

    renk_fiyat = "#0fdb7a" if anlik_kar_yuzde >= 0 else "#ff3b5c"
    renk_sinyal = (
        "#0fdb7a" if "GÜÇLÜ" in str(sinyal_tipi).upper()
        else ("#f5cc6a" if "AL" in str(sinyal_tipi).upper() else "#ff3b5c")
    )

    teknik = render_teknik_ozet_kart(df_hisse, hisse_adi)
    hedef_yuzde = ((hedef - giris_fiyat) / giris_fiyat) * 100 if giris_fiyat > 0 else 0
    risk_kazanc = ((hedef - giris_fiyat) / (giris_fiyat - stop)) if (giris_fiyat - stop) > 0 and giris_fiyat > 0 else 0

    rsi_val = teknik['rsi'] if teknik else 50
    rsi_color = "#0fdb7a" if rsi_val < 40 else ("#ff3b5c" if rsi_val > 70 else "#f5cc6a")

    hacim_oran = teknik['hacim_oran'] if teknik else 100
    hacim_color = "#0fdb7a" if hacim_oran > 120 else ("#7a8fa8" if hacim_oran > 80 else "#ff3b5c")

    pazar = "BIST" if ".IS" in hisse_adi else "US"
    pazar_icon = "TR" if ".IS" in hisse_adi else "US"

    st.markdown(f"""
    <div class="fade-in" style="background:linear-gradient(160deg, rgba(10,18,36,0.92), rgba(6,12,26,0.88)); 
                border: 1px solid rgba(255,255,255,0.06); border-left:3px solid {renk_sinyal}; 
                padding:10px 14px; border-radius:10px; margin-bottom:5px;
                display:flex; align-items:center; gap:12px; flex-wrap:wrap;
                font-family:'JetBrains Mono',monospace; backdrop-filter:blur(8px);
                transition:all .2s ease;">
        <div style="min-width:72px;">
            <span style="font-size:9px; color:#7a8fa8; background:rgba(122,143,168,0.12); 
                         padding:2px 7px; border-radius:10px;">{pazar_icon}</span>
            <span style="font-size:12px; font-weight:700; color:#eef2f7; margin-left:6px;
                         letter-spacing:-.02em;">{hisse_adi.replace('.IS','')}</span>
        </div>
        <div style="text-align:center; min-width:80px;">
            <span style="font-size:13px; font-weight:700; color:{renk_fiyat};
                         letter-spacing:-.02em;">₺{anlik_fiyat:.2f}</span>
            <span style="font-size:9px; color:{renk_fiyat}; display:block;">{anlik_kar_yuzde:+.1f}%</span>
        </div>
        <div style="text-align:center; min-width:42px;">
            <span style="font-size:9px; color:#8a9bb5;">RSI</span>
            <span style="font-size:11px; font-weight:600; color:{rsi_color}; display:block;">{rsi_val:.0f}</span>
        </div>
        <div style="text-align:center; min-width:48px;">
            <span style="font-size:9px; color:#8a9bb5;">Hacim</span>
            <span style="font-size:11px; font-weight:600; color:{hacim_color}; display:block;">%{hacim_oran:.0f}</span>
        </div>
        <div style="text-align:center; min-width:68px;">
            <span style="font-size:8px; font-weight:700; color:{renk_sinyal}; 
                         background:{renk_sinyal}18; padding:4px 10px; border-radius:12px;
                         letter-spacing:0.5px; border:1px solid {renk_sinyal}33;">
              {sinyal_tipi.replace('GÜÇLÜ AL','G.AL')}</span>
        </div>
        <div style="text-align:center; min-width:58px;">
            <span style="font-size:9px; color:#8a9bb5;">Hedef</span>
            <span style="font-size:11px; font-weight:600; color:#0fdb7a; display:block;">%{hedef_yuzde:.1f}</span>
        </div>
        <div style="text-align:center; min-width:48px;">
            <span style="font-size:9px; color:#8a9bb5;">R/K</span>
            <span style="font-size:11px; font-weight:600; color:#f5cc6a; display:block;">{risk_kazanc:.1f}</span>
        </div>
        <div style="font-size:8px; color:#5a6d85; min-width:58px; text-align:right;">
            {str(tarih)[:10]}
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"📋 {hisse_adi} — Detaylı Analiz", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Giriş", f"₺{giris_fiyat:.2f}",
                      delta=f"{((anlik_fiyat-giris_fiyat)/giris_fiyat*100):+.1f}%")
        with c2:
            st.metric("Hedef", f"₺{hedef:.2f}", delta=f"%{hedef_yuzde:.1f}")
        with c3:
            st.metric("Stop", f"₺{stop:.2f}",
                      delta=f"%{((stop-giris_fiyat)/giris_fiyat*100):.1f}")

        # 📊 GRAFİKTE GÖRÜNTÜLE BUTONU (Otomatik formasyon çizimli + ANALİZ sekmesine yönlendir)
        if st.button(f"📈 Grafikte Görüntüle — {hisse_adi}", key=f"grafik_{hisse_adi}_{tarih}", use_container_width=True):
            st.session_state.secilen_hisse = hisse_adi
            st.session_state.aktif_sekme = 2  # ANALİZ sekmesine geç
            st.rerun()

        if formasyon_metni:
            st.markdown(f"""
            <div class="glass-card" style="padding:14px 18px;margin-top:8px;
                        font-size:12px;color:var(--txt2);line-height:1.6;">
                {formasyon_metni}
            </div>
            """, unsafe_allow_html=True)


def render_tarama_sekmesi():
    bolum_baslik(
        "Canlı Piyasa Radarı",
        "Otomatik yakalanan fırsatlar · Teknik & Temel Analiz · YZ Formasyonları",
        bg_url="https://images.unsplash.com/photo-1642543492481-44e81e3914a1?q=80&w=1200&auto=format&fit=crop"
    )
    tab1, tab_manuel, tab2 = st.tabs([
        "🎯 YAKALANAN HİSSELER", "🔍 MANUEL TARAMA", "⚡ CANLI KRİPTO SCALP"
    ])

    with tab_manuel:
        filtreleme_paneli(hisse_analiz_paneli)

    # ══ TAB 1: OTOMATİK YAKALANAN HİSSELER ══
    with tab1:
        st.info(
            "🔬 Arka plan YZ motoru 7/24 piyasayı tarar. "
            "Güçlü AL sinyali veren hisseleri otomatik yakalar ve burada listeler."
        )

        try:
            conn = sqlite3.connect(DB_YOLU)
            query = (
                "SELECT tarih, hisse, sinyal_tipi, giris_fiyati, hedef_fiyat, stop_fiyat "
                "FROM ai_sinyaller WHERE durum='BEKLIYOR' "
                "ORDER BY id DESC LIMIT 24"
            )
            df_hisse = pd.read_sql_query(query, conn)
            conn.close()

            if df_hisse.empty:
                st.warning(
                    "🚫 Arka plan motoru henüz taze bir fırsat yakalamadı. "
                    "Sistem batch'ler halinde sürekli tarama yapar "
                    "(her hisse ~15-20dk'da bir taranır)."
                )
            else:
                threshold_msgs = []
                filtered_rows = []
                for _, row in df_hisse.iterrows():
                    hisse_adi = row['hisse']
                    giris = row['giris_fiyati']
                    hedef = row['hedef_fiyat']
                    min_hedef_pct = get_market_threshold(hisse_adi)
                    hedef_pct = ((hedef - giris) / giris) * 100 if giris > 0 else 0

                    # Küsürat ve yuvarlama hatalarına karşı %0.2 tolerans eklendi
                    if hedef_pct >= (min_hedef_pct - 0.2):
                        filtered_rows.append(row)
                    else:
                        threshold_msgs.append(
                            f"{hisse_adi}: Hedef %{hedef_pct:.1f} < min %{min_hedef_pct} (pas geçildi)"
                        )

                if not filtered_rows:
                    st.warning(
                        f"Veritabanında sinyal var ancak hiçbiri piyasa hedef eşiğini "
                        f"({get_market_threshold('BIST')}% BIST / {get_market_threshold('AAPL')}% SP500 / "
                        f"{get_market_threshold('NVDA')}% NASDAQ / {get_market_threshold('BTC-USD')}% Kripto) geçmedi."
                    )
                    if threshold_msgs:
                        with st.expander("⚠️ Elenen Sinyaller"):
                            for m in threshold_msgs:
                                st.caption(m)
                else:
                    hisse_listesi = [r['hisse'] for r in filtered_rows]

                    # 🔥 PERF: yf.download'ı 5dk cache'le — her sekme geçişinde tekrar çağrılmaz
                    @st.cache_data(ttl=300, show_spinner=False)
                    def _toplu_veri_cek(hisse_tuple):
                        try:
                            return yf.download(list(hisse_tuple), period="3mo", progress=False)
                        except:
                            return pd.DataFrame()
                    
                    with st.spinner("Canlı fiyatlar ve YZ grafik formasyonları hesaplanıyor..."):
                        veri = _toplu_veri_cek(tuple(hisse_listesi))

                    st.markdown(f"""
                    <div class="fade-in" style="display:flex;align-items:center;gap:12px;
                                padding:12px 16px;background:rgba(34,230,145,0.06);
                                border:1px solid rgba(34,230,145,0.15);border-radius:10px;
                                margin-bottom:16px;">
                      <span style="font-size:22px;">🎯</span>
                      <span style="font-family:'Sora',sans-serif;font-size:14px;font-weight:600;
                                   color:var(--green);">
                        <b>{len(filtered_rows)} hisse</b> yüksek getiri eşiğini geçti
                      </span>
                      <span style="font-size:10px;color:var(--txt3);margin-left:auto;">
                        BIST >%1.5 · SP500 >%1.5 · NASDAQ >%2 · Kripto >%2
                      </span>
                    </div>
                    """, unsafe_allow_html=True)

                    for row in filtered_rows:
                        giris = row['giris_fiyati']
                        hedef = row['hedef_fiyat']
                        stop = row['stop_fiyat']
                        hisse_adi = row['hisse']
                        sinyal_tipi = row['sinyal_tipi']
                        tarih = row['tarih']

                        anlik_fiyat = giris
                        formasyon_metni = "Bu hissede agresif bir hacim artışı (Momentum) tespit edildi."
                        df_h = pd.DataFrame()

                        if not veri.empty:
                            try:
                                if isinstance(veri.columns, pd.MultiIndex):
                                    if hisse_adi in veri.columns.get_level_values(1):
                                        df_h = veri.xs(hisse_adi, level=1, axis=1)
                                else:
                                    df_h = veri

                                if not df_h.empty and 'Close' in df_h.columns:
                                    df_h = df_h.dropna(subset=['Close'])
                                    if len(df_h) > 0:
                                        anlik_fiyat = float(df_h['Close'].iloc[-1])

                                        f_sonuclar = formasyon_analizi(df_h)
                                        if f_sonuclar:
                                            metinler = []
                                            for f in f_sonuclar:
                                                metinler.append(
                                                    f"<b style='color:#4db8ff;'>{f['baslik']}</b><br>{f['detay']}"
                                                )
                                            formasyon_metni = "<br><br>".join(metinler)
                                        else:
                                            teknik = render_teknik_ozet_kart(df_h, hisse_adi)
                                            if teknik:
                                                sebepler = []
                                                if teknik['rsi'] < 40:
                                                    sebepler.append(f"RSI {teknik['rsi']:.0f} aşırı satım")
                                                if teknik['macd_hist'] > 0:
                                                    sebepler.append("MACD histogramı pozitif")
                                                if teknik['bb_pos'] < 30:
                                                    sebepler.append(
                                                        f"Bollinger alt banda yakın (%{teknik['bb_pos']:.0f})"
                                                    )
                                                if teknik['hacim_oran'] > 120:
                                                    sebepler.append(
                                                        f"Hacim ortalamanın %{teknik['hacim_oran']:.0f} üzerinde"
                                                    )
                                                if teknik['fiyat'] > teknik['ma50']:
                                                    sebepler.append("Fiyat MA50 üzerinde")
                                                if teknik['stoch_k'] < 25:
                                                    sebepler.append(
                                                        f"Stochastic %K {teknik['stoch_k']:.0f} aşırı satım"
                                                    )

                                                if sebepler:
                                                    formasyon_metni = (
                                                        "<b style='color:#f5cc6a;'>TEKNİK ANALİZ:</b><br>+ "
                                                        + "<br>+ ".join(sebepler)
                                                    )
                                                else:
                                                    formasyon_metni = "Teknik göstergeler nötr seyrediyor."
                            except:
                                pass

                        render_sinyal_analiz_karti_kompakt(
                            hisse_adi=hisse_adi,
                            fiyat=anlik_fiyat,
                            giris_fiyat=giris,
                            hedef=hedef,
                            stop=stop,
                            sinyal_tipi=sinyal_tipi,
                            tarih=tarih,
                            df_hisse=df_h,
                            formasyon_metni=formasyon_metni
                        )
        except Exception as e:
            st.error(f"Veritabanı okunamadı: {e}")

    # ══ TAB 2: CANLI KRİPTO SCALP ══
    with tab2:
        st.info(
            "🔌 Binance üzerinden saniyelik canlı verilerle kripto paralar taranıyor. "
            "Anlık hacim patlaması yaşayan coin'ler Telegram'a da bildirilir."
        )

        ilerleme = st.progress(0)
        durum = st.empty()
        firsatlar = kripto_canli_tara(KRIPTO_LISTESI, ilerleme, durum)

        ilerleme.empty()
        durum.empty()

        if firsatlar:
            st.success(f"🔥 {len(firsatlar)} Adet Harekete Geçen Coin Yakalandı!")

            for f in firsatlar:
                artis_renk = (
                    "#0fdb7a" if f['Artis %'] >= 2
                    else ("#f5cc6a" if f['Artis %'] >= 1 else "#ff8c42")
                )
                hacim_artis = f.get('Hacim_Artis', 0)
                fiyat = f['Fiyat']
                hedef = f['Hedef']
                stop_val = f['Stop']
                hedef_pct = ((hedef - fiyat) / fiyat) * 100 if fiyat > 0 else 0

                if hedef_pct < 2.0:
                    continue

                with st.container():
                    st.markdown(f"""
                    <div class="fade-in" style="background:linear-gradient(160deg, rgba(10,18,36,0.94), rgba(6,12,26,0.88)); 
                                border: 1px solid rgba(245,204,106,0.25); border-left:4px solid #f5cc6a; 
                                padding:12px 16px; border-radius:10px; margin-bottom:4px;
                                display:flex; justify-content:space-between; align-items:center;
                                flex-wrap:wrap; gap:10px; backdrop-filter:blur(8px);">
                        <div style="min-width:90px;">
                            <span style="font-size:14px; font-weight:700; color:#eef2f7;">{f['Sembol']}</span>
                            <span style="font-size:9px; color:#8a9bb5; display:block;">5dk Scalp</span>
                        </div>
                        <div style="text-align:right;min-width:100px;">
                            <span style="font-size:15px; font-weight:700; color:#f5cc6a; 
                                         font-family:'JetBrains Mono',monospace;">${fiyat:.6f}</span>
                            <span style="font-size:10px; color:{artis_renk}; font-weight:600; display:block;">
                              +%{f['Artis %']:.2f}</span>
                        </div>
                        <div style="text-align:center;min-width:70px;">
                            <span style="font-size:9px; color:#8a9bb5;">Hedef</span>
                            <span style="font-size:12px; font-weight:600; color:#0fdb7a; display:block;">
                              %{hedef_pct:.1f}</span>
                        </div>
                        <div style="text-align:center; min-width:55px;">
                            <span style="font-size:9px; font-weight:700; color:#0fdb7a; 
                                         background:rgba(15,219,122,0.12); padding:4px 8px; 
                                         border-radius:12px; border:1px solid rgba(15,219,122,0.2);">
                              AL</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.expander(f"⚡ {f['Sembol']} Scalp Detay", expanded=False):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.metric("Hızlı Kar Al (+%3)", f"${hedef:.6f}")
                            st.metric("Ani Zarar Kes (-%2)", f"${stop_val:.6f}")
                        with c2:
                            risk_val = (
                                (hedef - fiyat) / (fiyat - stop_val)
                                if (fiyat - stop_val) > 0 else 0
                            )
                            st.metric("R/K Oranı", f"1:{risk_val:.1f}")
                            st.caption(
                                f"Hacim Artışı: %{hacim_artis:.0f} · "
                                f"Son 5 dk momentum kırılımı"
                            )
        else:
            st.warning("🌊 Şu an hacim patlaması yaşayan coin yok. Piyasalar sakin.")

            with st.expander("📖 Kripto Scalp Taraması Hakkında"):
                st.markdown("""
                **Nasıl Çalışır?**
                - Binance borsasından 5 dakikalık mum verileri canlı çekilir
                - Her coin için son mumdaki fiyat değişimi ve hacim artışı kontrol edilir
                - Hacmi %20'den fazla artan ve fiyatı %0.5'ten fazla yükselen coin'ler yakalanır
                - Yakalanan her fırsat **anında Telegram** kanalınıza bildirilir
                - **Minimum %2 hedef** filtresi uygulanır (esnetilmiş eşik)

                **Strateji:** Kısa vadeli vur-kaç (scalping) işlemleri için uygundur.
                """)