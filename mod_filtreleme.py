# ══════════════════════════════════════════════════════════════════════
#  mod_filtreleme.py — Dinamik Filtre İnşası & Hazır Stratejiler · v4.2 ✨
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
from grafik import tablo_goster, yukselenler_grafik, rsi_dagilim_grafik
from datetime import datetime
import pandas as pd
import sqlite3
import os
import yfinance as yf
import time

from analiz import rsi_serisi, tum_hisseleri_tara
from hisseler_bist import BIST
from hisseler_kripto import KRIPTO_LISTESI
from hisseler_nasdaq import NASDAQ

try:
    from mod_haberler import tum_sistemi_haber_tara
    HABER_AKTIF = True
except ImportError:
    HABER_AKTIF = False

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")

def filtreleme_paneli(hisse_analiz_paneli_fn):
    st.markdown("""
    <div class="fade-in" style="padding:28px 0 4px 0;">
      <span style="font-family:'Sora','Outfit',sans-serif;font-size:28px;font-weight:800;
                   color:var(--txt1);letter-spacing:-.03em;">
        Piyasa <span style="color:var(--gold);">Taraması</span>
      </span>
      <div style="height:1px;background:linear-gradient(90deg,var(--gold-d),rgba(184,136,42,0.2),transparent);
                  margin:14px 0 22px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    # ── TARAMA KAYNAĞI ──
    st.markdown('<span class="section-label">1. Tarama Kaynağı ve Piyasası</span>', unsafe_allow_html=True)
    tarama_kaynagi = st.selectbox(
        "Taranacak Piyasa Havuzu",
        [
            "🚀 Hızlı Tarama (Arka Planda Yakalananlar)", 
            "🇹🇷 Canlı BIST Taraması", 
            "🪙 Canlı Kripto Taraması", 
            "🇺🇸 Canlı NASDAQ Taraması"
        ],
        key="ui_kaynak",
        label_visibility="collapsed"
    )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown('<span class="section-label">⚡ 2. Hazır Strateji Şablonları (Otomatik Kurulum)</span>', unsafe_allow_html=True)
    
    # ── HAZIR STRATEJİ BUTONLARI (TEK TIKLA KURULUM) ──
    c_btn1, c_btn2, c_btn3 = st.columns(3)
    
    def strateji_kur(strat):
        # Önce tüm filtreleri sıfırla
        for k in ["chk_sinyal", "chk_rsi", "chk_macd", "chk_bb", "chk_trend", "chk_formasyon", "chk_temel", "chk_nlp"]:
            st.session_state[k] = False
            
        if strat == "trend":
            st.session_state["chk_trend"] = True
            st.session_state["chk_rsi"] = True
            st.session_state["chk_macd"] = True
            st.session_state["ui_trend"] = "Fiyat MA50 Üzerinde (Boğa Eğilimi)"
            st.session_state["ui_macd"] = "AL (Yukarı Kesti / Momentum Pozitif)"
            # RSI sayısal değerleri tetiklendiğinde girilecek (aşağıda 40-60 varsayılan)
            
        elif strat == "dip":
            st.session_state["chk_temel"] = True
            st.session_state["chk_bb"] = True
            st.session_state["chk_formasyon"] = True
            st.session_state["ui_temel"] = "Sadece Ucuz Şirketler (F/K ve PD/DD Avantajlı)"
            st.session_state["ui_bb"] = "AL (Alt Banda Yakın / Aşırı Satım)"
            st.session_state["ui_formasyon"] = "İkili Dip (W)"
            
        elif strat == "momentum":
            st.session_state["chk_nlp"] = True
            st.session_state["chk_sinyal"] = True
            st.session_state["ui_nlp"] = "Sadece Pozitif Haber Akışı Olanlar"
            st.session_state["ui_sinyal"] = ["GÜÇLÜ AL", "AL"]

    with c_btn1:
        if st.button("📈 Trend İçi Düzeltme (Düşük Risk)", use_container_width=True):
            strateji_kur("trend")
    with c_btn2:
        if st.button("🐋 Kurumsal Dip Avı (Değer)", use_container_width=True):
            strateji_kur("dip")
    with c_btn3:
        if st.button("🚀 Momentum & Haber Sörfü", use_container_width=True):
            strateji_kur("momentum")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown('<span class="section-label">3. Filtre İnşası (Manuel Kontrol)</span>', unsafe_allow_html=True)

    # ── 2 SÜTUNLU DİNAMİK FİLTRE YAPISI ──
    col_sol, col_sag = st.columns([1, 2], gap="large")

    with col_sol:
        st.markdown("<div style='font-family:Sora,sans-serif;font-size:14px;font-weight:700;color:var(--txt1);margin-bottom:12px;'>🧰 Filtre Seçenekleri</div>", unsafe_allow_html=True)
        st.caption("Aramaya dahil etmek istediğiniz modülleri işaretleyin:")
        
        use_sinyal    = st.checkbox("🎯 Ana Sinyal Yönü (AL/SAT)", key="chk_sinyal")
        use_rsi       = st.checkbox("📈 RSI Seviyesi (Aşırı Alım/Satım)", key="chk_rsi")
        use_macd      = st.checkbox("⚡ MACD Kesişimi", key="chk_macd")
        use_bb        = st.checkbox("📉 Bollinger Bantları Konumu", key="chk_bb")
        use_trend     = st.checkbox("🛡️ Trend Onayı (MA50 & Market Yapısı)", key="chk_trend")
        use_formasyon = st.checkbox("📐 Grafik Formasyonları (Yapay Zeka)", key="chk_formasyon")
        use_temel     = st.checkbox("💼 Temel Analiz (F/K, PD/DD)", key="chk_temel")
        use_nlp       = st.checkbox("🧠 Haber Duyarlılığı (NLP)", key="chk_nlp")

    with col_sag:
        st.markdown("<div style='font-family:Sora,sans-serif;font-size:14px;font-weight:700;color:var(--txt1);margin-bottom:12px;'>📋 Aktif Filtre Ayarları</div>", unsafe_allow_html=True)
        
        if not any([use_sinyal, use_rsi, use_macd, use_bb, use_trend, use_formasyon, use_temel, use_nlp]):
            st.info("👈 Sol taraftan modül seçin veya üstten 'Hazır Strateji' butonlarına tıklayın. Hiçbir filtre seçilmezse tüm piyasa listelenir.")
            
        if use_sinyal:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #0fdb7a; margin-bottom:10px;'>", unsafe_allow_html=True)
                st.multiselect("🎯 İstenen Sinyal Durumu", ["GÜÇLÜ AL", "AL", "NÖTR", "SAT", "GÜÇLÜ SAT"], default=st.session_state.get("ui_sinyal", ["GÜÇLÜ AL", "AL"]), key="ui_sinyal")
                st.markdown("</div>", unsafe_allow_html=True)

        if use_rsi:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #4db8ff; margin-bottom:10px;'>", unsafe_allow_html=True)
                r1, r2 = st.columns(2)
                # Trend stratejisi tıklandıysa otomatik 40-60 gelir
                varsayilan_min = 40 if st.session_state.get("chk_trend") else 0
                varsayilan_max = 60 if st.session_state.get("chk_trend") else 40
                r1.number_input("RSI Alt Sınırı", 0, 100, st.session_state.get("ui_rsi_min", varsayilan_min), key="ui_rsi_min")
                r2.number_input("RSI Üst Sınırı", 0, 100, st.session_state.get("ui_rsi_max", varsayilan_max), key="ui_rsi_max")
                st.markdown("</div>", unsafe_allow_html=True)
            
        if use_macd:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #f5cc6a; margin-bottom:10px;'>", unsafe_allow_html=True)
                # Selectbox options index bulma
                idx = 0 if st.session_state.get("ui_macd", "AL")[:2] == "AL" else 1
                st.selectbox("⚡ MACD Durumu", ["AL (Yukarı Kesti / Momentum Pozitif)", "SAT (Aşağı Kesti / Momentum Negatif)"], index=idx, key="ui_macd")
                st.markdown("</div>", unsafe_allow_html=True)

        if use_bb:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #b57cf8; margin-bottom:10px;'>", unsafe_allow_html=True)
                idx = 0 if st.session_state.get("ui_bb", "AL")[:2] == "AL" else 1
                st.selectbox("📉 Bollinger Sinyali", ["AL (Alt Banda Yakın / Aşırı Satım)", "SAT (Üst Banda Yakın / Aşırı Alım)"], index=idx, key="ui_bb")
                st.markdown("</div>", unsafe_allow_html=True)
            
        if use_trend:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #ff8c42; margin-bottom:10px;'>", unsafe_allow_html=True)
                secenekler = ["Fiyat MA50 Üzerinde (Boğa Eğilimi)", "Market Yapısı: Yükseliş (BOS)"]
                idx = secenekler.index(st.session_state.get("ui_trend", secenekler[0])) if st.session_state.get("ui_trend") in secenekler else 0
                st.selectbox("🛡️ Trend Onayı", secenekler, index=idx, key="ui_trend")
                st.markdown("</div>", unsafe_allow_html=True)

        if use_formasyon:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #ff4f6d; margin-bottom:10px;'>", unsafe_allow_html=True)
                secenekler = ["Herhangi Bir Formasyon Bulunanlar", "İkili Dip (W)", "Ters OBO", "Yükselen Üçgen", "İkili Tepe (M)"]
                idx = secenekler.index(st.session_state.get("ui_formasyon", secenekler[0])) if st.session_state.get("ui_formasyon") in secenekler else 0
                st.selectbox("📐 Tespit Edilen Grafik Formasyonu", secenekler, index=idx, key="ui_formasyon")
                st.markdown("</div>", unsafe_allow_html=True)

        if use_temel:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #2ee8d4; margin-bottom:10px;'>", unsafe_allow_html=True)
                secenekler = ["Sadece Ucuz Şirketler (F/K ve PD/DD Avantajlı)", "Aşırı Şişkin Şirketler"]
                idx = secenekler.index(st.session_state.get("ui_temel", secenekler[0])) if st.session_state.get("ui_temel") in secenekler else 0
                st.selectbox("💼 Şirket Değerlemesi", secenekler, index=idx, key="ui_temel")
                st.markdown("</div>", unsafe_allow_html=True)
            
        if use_nlp:
            with st.container():
                st.markdown("<div style='background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border-left:3px solid #eef2f7; margin-bottom:10px;'>", unsafe_allow_html=True)
                secenekler = ["Sadece Pozitif Haber Akışı Olanlar", "Sadece Negatif Haberler"]
                idx = secenekler.index(st.session_state.get("ui_nlp", secenekler[0])) if st.session_state.get("ui_nlp") in secenekler else 0
                st.selectbox("🧠 NLP Haber Analizi", secenekler, index=idx, key="ui_nlp")
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    
    # ── TARAMA BUTONU VE VERİ ÇEKME MOTORU ──
    if st.button("🚀 SEÇİLİ FİLTRELERLE TARA", use_container_width=True, type="primary"):
        pb = st.progress(0)
        txt = st.empty()

        if "Hızlı" in tarama_kaynagi:
            txt.info("Veritabanındaki aktif sinyaller çekiliyor ve fiyatları güncelleniyor...")
            try:
                conn = sqlite3.connect(DB_YOLU)
                df = pd.read_sql_query("SELECT hisse as Hisse, sinyal_tipi as Sinyal, giris_fiyati as 'Son Fiyat' FROM ai_sinyaller WHERE durum='BEKLIYOR' ORDER BY id DESC", conn)
                conn.close()

                if not df.empty:
                    df["RSI"] = 50.0
                    df["Değişim %"] = 0.0
                    df["Sinyal Detay"] = "Arka plan motoru tarafından yakalanan aktif sinyal."

                    hisseler = list(df['Hisse'].unique())
                    if hisseler:
                        txt.info(f"{len(hisseler)} hissenin canlı fiyatı güncelleniyor...")
                        data = yf.download(hisseler, period="1mo", progress=False)
                        
                        if not data.empty and 'Close' in data.columns:
                            for i, (idx, row) in enumerate(df.iterrows()):
                                pb.progress((i + 1) / len(df))
                                hisse_kodu = row['Hisse']
                                close_s = pd.Series(dtype=float)
                                
                                if isinstance(data.columns, pd.MultiIndex):
                                    if hisse_kodu in data['Close'].columns:
                                        close_s = data['Close'][hisse_kodu].dropna()
                                else:
                                    if len(hisseler) == 1:
                                        close_s = data['Close'].dropna()

                                if len(close_s) >= 2:
                                    son_f = float(close_s.iloc[-1])
                                    onceki = float(close_s.iloc[-2])
                                    deg = ((son_f - onceki) / onceki) * 100
                                    try:
                                        r_val = float(rsi_serisi(close_s).iloc[-1])
                                        if pd.isna(r_val): r_val = 50.0
                                    except:
                                        r_val = 50.0

                                    df.at[idx, 'Son Fiyat'] = round(son_f, 4)
                                    df.at[idx, 'Değişim %'] = round(deg, 2)
                                    df.at[idx, 'RSI'] = round(r_val, 1)

                    txt.success("✅ Veritabanı taraması ve fiyat güncellemesi tamamlandı!")
                else:
                    txt.warning("⚠️ Veritabanında bekleyen hiçbir sinyal bulunamadı.")
                
                st.session_state.tarama_df = df
            except Exception as e:
                txt.error(f"Veri getirme hatası: {e}")
                
        else:
            if "BIST" in tarama_kaynagi:
                liste = BIST
                txt.info(f"🇹🇷 BIST piyasasındaki {len(liste)} hisse canlı olarak taranıyor...")
            elif "Kripto" in tarama_kaynagi:
                liste = [k.replace("USDT", "-USD") for k in KRIPTO_LISTESI]
                txt.info(f"🪙 Kripto piyasasındaki {len(liste)} coin canlı olarak taranıyor...")
            else:
                liste = NASDAQ
                txt.info(f"🇺🇸 NASDAQ piyasasındaki {len(liste)} hisse canlı olarak taranıyor...")
            
            try:
                canli_tablo = st.empty()
                sonuclar = tum_hisseleri_tara(liste, "1mo", pb, txt, max_workers=6, canli_ekran=canli_tablo)
                canli_tablo.empty()
                
                if sonuclar:
                    df = pd.DataFrame(sonuclar)
                    if "Değişim %" not in df.columns and "Degisim %" in df.columns:
                        df.rename(columns={"Degisim %": "Değişim %"}, inplace=True)
                    st.session_state.tarama_df = df
                    txt.success(f"✅ Canlı piyasa taraması tamamlandı! Toplam {len(df)} hisse analiz edildi.")
                else:
                    st.session_state.tarama_df = pd.DataFrame()
                    txt.warning("⚠️ Tarama yapıldı ancak hiçbir veriye ulaşılamadı (Bağlantı veya Rate-Limit sorunu olabilir).")
            except Exception as e:
                txt.error(f"Canlı tarama sırasında hata oluştu: {e}")

        time.sleep(1.5)
        pb.empty()
        txt.empty()

    # ── SONUÇLARI FİLTRELEME VE GÖSTERME KISMI ──
    df = st.session_state.get("tarama_df", None)

    if df is None:
        st.markdown("""
        <div style="text-align:center;padding:40px 20px;">
          <img src="https://images.unsplash.com/photo-1464802686167-b939a6910659?q=80&w=800&auto=format&fit=crop" 
               style="width:320px; border-radius:16px; opacity:0.25; filter: grayscale(70%); 
                      margin-bottom:24px; border:1px solid rgba(255,255,255,0.05); box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
          <div style="font-family:'Sora','Outfit',sans-serif;font-size:32px;font-weight:800;
                      color:var(--txt1);letter-spacing:-.02em;opacity:.8;">
            Piyasanın Nabzını Tutun
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--txt3);
                      letter-spacing:.24em;margin-top:16px;text-transform:uppercase;">
            Gelişmiş filtreleri oluşturup · TARA butonuna basın
          </div>
          <div style="margin-top:24px;font-size:40px;opacity:.15;">◈</div>
        </div>
        """, unsafe_allow_html=True)
        return

    fdf = df.copy()

    # Filtreleri Uygulama
    if use_sinyal and st.session_state.ui_sinyal:
        if "Sinyal" in fdf.columns:
            fdf = fdf[fdf["Sinyal"].apply(lambda s: any(f in str(s) for f in st.session_state.ui_sinyal))]

    if use_rsi and st.session_state.ui_rsi_min is not None and st.session_state.ui_rsi_max is not None:
        if "RSI" in fdf.columns:
            fdf = fdf[fdf["RSI"].between(st.session_state.ui_rsi_min, st.session_state.ui_rsi_max, inclusive="both")]

    if use_macd and st.session_state.ui_macd:
        aranan_macd = "AL" if "AL" in st.session_state.ui_macd else "SAT"
        if "MACD Sinyal" in fdf.columns:
            fdf = fdf[fdf["MACD Sinyal"].astype(str).str.contains(aranan_macd, na=False)]

    if use_bb and st.session_state.ui_bb:
        aranan_bb = "AL" if "AL" in st.session_state.ui_bb else "SAT"
        if "BB Sinyal" in fdf.columns:
            fdf = fdf[fdf["BB Sinyal"].astype(str).str.contains(aranan_bb, na=False)]

    if use_trend and st.session_state.ui_trend:
        if "Sinyal Detay" in fdf.columns:
            aranan_trend = "MA50 Üzerinde" if "MA50" in st.session_state.ui_trend else "Market Yapısı"
            fdf = fdf[fdf["Sinyal Detay"].astype(str).str.contains(aranan_trend, na=False)]

    if use_formasyon and st.session_state.ui_formasyon:
        if "Sinyal Detay" in fdf.columns:
            if "Herhangi Bir" in st.session_state.ui_formasyon:
                fdf = fdf[fdf["Sinyal Detay"].astype(str).str.contains("Formasyon", na=False)]
            else:
                aranan_form = st.session_state.ui_formasyon.split(" ")[0]
                fdf = fdf[fdf["Sinyal Detay"].astype(str).str.contains(aranan_form, na=False)]

    if use_temel and st.session_state.ui_temel:
        if "Sinyal Detay" in fdf.columns:
            if "Ucuz" in st.session_state.ui_temel:
                fdf = fdf[fdf["Sinyal Detay"].astype(str).str.contains("F/K Cazip") | fdf["Sinyal Detay"].astype(str).str.contains("PD/DD Ucuz")]
            else:
                fdf = fdf[fdf["Sinyal Detay"].astype(str).str.contains("Aşırı Şişkin", na=False)]

    if use_nlp and st.session_state.ui_nlp:
        if "Sinyal Detay" in fdf.columns:
            aranan_nlp = "NLP: Pozitif" if "Pozitif" in st.session_state.ui_nlp else "NLP: Negatif"
            fdf = fdf[fdf["Sinyal Detay"].astype(str).str.contains(aranan_nlp, na=False)]

    degisim_col = "Değişim %" if "Değişim %" in fdf.columns else "Degisim %"
    if degisim_col in fdf.columns:
        fdf = fdf.sort_values(degisim_col, ascending=False).reset_index(drop=True)

    st.markdown("---")
    st.markdown('<span class="section-label">Fırsat Özeti (Tüm Filtreleri Geçenler)</span>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("🎯 Filtreyi Geçen", len(fdf))
    with m2: st.metric("📈 Yükseliş Trendi", len(fdf[fdf[degisim_col] > 0]) if degisim_col in fdf.columns else 0)
    with m3: st.metric("📉 Dipten Dönenler", len(fdf[fdf[degisim_col] < 0]) if degisim_col in fdf.columns else 0)
    with m4: st.metric("📊 Ortalama RSI", round(fdf["RSI"].mean(), 1) if "RSI" in fdf.columns and not fdf.empty else 0)

    st.markdown('<span class="section-label">Tarama Sonuçları</span>', unsafe_allow_html=True)

    if len(fdf) == 0:
        st.warning("🔍 Seçtiğiniz stratejiye (RSI, MACD, Trend vb.) aynı anda uyan hisse bulunamadı. Filtrelerinizi biraz esnetmeyi deneyin veya piyasanın oturmasını bekleyin.")
    else:
        tablo_goster(fdf)

        st.markdown('<span class="section-label">Hızlı Aksiyon → Seç ve Detaya Git</span>', unsafe_allow_html=True)
        hisseler_listesi = fdf["Hisse"].tolist() if "Hisse" in fdf.columns else []
        if hisseler_listesi:
            c_sec, c_btn = st.columns([3, 1])
            with c_sec:
                secim = st.selectbox("Grafiğini ve detayını görmek istediğiniz hisseyi seçin:", hisseler_listesi, label_visibility="collapsed", key="tarama_secim")
            with c_btn:
                if st.button("🔍 ANALİZ ET", key="tarama_analiz", use_container_width=True):
                    st.session_state.secilen_hisse = secim
                    st.session_state["tarama_panel_ac"] = True

        if st.session_state.get("tarama_panel_ac") and st.session_state.secilen_hisse:
            hisse_analiz_paneli_fn(st.session_state.secilen_hisse, key_prefix="tarama")

    if not fdf.empty:
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown(
            '<div class="fade-in" style="font-family:Sora,sans-serif;font-size:22px;font-weight:800;'
            'color:#0fdb7a;margin-bottom:4px;">🎯 Neden Öne Çıkıyor?</div>'
            '<div style="font-family:Sora,sans-serif;font-size:12px;color:var(--txt3);margin-bottom:20px;">'
            'Yapay Zeka & Temel-Teknik Gerekçeler</div>'
            '<div style="height:1px;background:linear-gradient(90deg,#0fdb7a,transparent);margin-bottom:20px;"></div>',
            unsafe_allow_html=True
        )

        for idx, row in fdf.iterrows():
            hisse = row.get("Hisse", "Bilinmiyor")
            fiyat = row.get("Son Fiyat", 0)
            detay = row.get("Sinyal Detay", "")
            rsi   = row.get("RSI", "-")

            son_haber_html = ""
            if HABER_AKTIF:
                try:
                    haberler = tum_sistemi_haber_tara((hisse,))
                    if haberler and len(haberler) > 0:
                        en_yeni_haber = haberler[0]['baslik']
                        kaynak = haberler[0].get('yayinci', 'KAP / Haber')
                        son_haber_html = (
                            f"<li><b>📰 Son Gelişme / KAP:</b> <i>\"{en_yeni_haber}\"</i> "
                            f"({kaynak}). Bu taze gelişme hisse üzerinde pozitif bir rüzgar "
                            f"yaratıyor ve fiyatlamayı yukarı taşıyor.</li>"
                        )
                except: pass

            maddeler_html = ""
            if detay:
                ham_maddeler = detay.split(" | ")
                for madde in ham_maddeler:
                    if "F/K Cazip" in madde: maddeler_html += "<li><b>💼 Değerleme (F/K Ucuzluğu):</b> Şirketin kazancına oranla hisse fiyatı şu an çok ucuz kalmış durumda.</li>"
                    elif "PD/DD Ucuz" in madde: maddeler_html += "<li><b>🏢 Defter Değeri (PD/DD):</b> Hissenin piyasa değeri, özkaynaklara göre makul seviyelerde.</li>"
                    elif "Market Yapısı Pozitif" in madde: maddeler_html += "<li><b>📈 Trend Onayı (Market Yapısı):</b> Düşüş trendi bitti, akıllı para (kurumsal alım) başladı.</li>"
                    elif "OB Alım Bölgesi" in madde: maddeler_html += "<li><b>🐋 Balina Desteği (Order Block):</b> Geçmişte balinaların yüklü alım girdiği destek bölgesine geriledi.</li>"
                    elif "Aşırı Satım" in madde: maddeler_html += f"<li><b>📉 Dip Tepkisi (RSI {rsi}):</b> Fiyat bir lastik gibi gerilmiş durumda, yukarı yönlü sert bir tepki alımı bekleniyor.</li>"
                    elif "MACD Yukarı Kesti" in madde: maddeler_html += "<li><b>⚡ İvme (MACD Kesişimi):</b> Hissede yeni bir alım iştahı ve ivmelenme başladı.</li>"
                    elif "BB Alt Bant Altı" in madde: maddeler_html += "<li><b>📉 Bollinger Aşırı Satım:</b> Fiyat istatistiksel olarak normalin çok altına düştü, tepki potansiyeli yüksek.</li>"
                    elif "Fiyat MA50 Üzerinde" in madde: maddeler_html += "<li><b>🛡️ Güvenli Bölge (MA50):</b> Hisse 50 günlük kritik hareketli ortalamasının üzerinde sağlam tutunuyor.</li>"
                    elif "NLP: Pozitif Haber" in madde: maddeler_html += "<li><b>🧠 Yapay Zeka (NLP) Onayı:</b> Sistemimiz haberleri analiz etti ve genel hissiyatı 'Pozitif' buldu.</li>"
                    elif "Formasyon:" in madde: maddeler_html += f"<li><b>📐 Grafik Algılayıcı:</b> {madde}</li>"
                    else: maddeler_html += f"<li><b>⚙️ Teknik Sinyal:</b> {madde}</li>"
            else: maddeler_html = "<li>Sistem bu hisse için pozitif hacim ve fiyat hareketi tespit etti.</li>"

            st.markdown(f"""
            <div class="fade-in" style="background:rgba(11,121,61,0.08);border:1px solid rgba(34,230,145,0.2);
                        border-left:5px solid #0fdb7a;border-radius:12px;padding:20px 24px;
                        margin-bottom:14px;backdrop-filter:blur(8px);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;
                            flex-wrap:wrap;gap:8px;">
                    <div style="font-family:'Sora',sans-serif;font-size:18px;font-weight:700;color:#0fdb7a;">
                      {hisse}</div>
                    <div style="background:rgba(15,219,122,0.12);color:#0fdb7a;padding:5px 14px;
                                border-radius:14px;font-family:'JetBrains Mono',monospace;
                                font-weight:700;font-size:13px;border:1px solid rgba(15,219,122,0.2);">
                      ₺ {fiyat}</div>
                </div>
                <p style="font-size:13px;color:var(--txt2);margin-bottom:14px;line-height:1.6;">
                  Bu hisse, kurduğunuz strateji filtrelerinden geçerek radara girdi. Yatırım kararını destekleyen ek detaylar:
                </p>
                <ul style="font-size:13px;color:var(--txt1);line-height:1.9;margin-bottom:0;padding-left:20px;">
                    {maddeler_html}
                    {son_haber_html}
                </ul>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<span class="section-label">Piyasa Görünümü (Filtrelenen Hisseler Arasında)</span>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: yukselenler_grafik(fdf)
    with c2: rsi_dagilim_grafik(fdf)

    st.markdown("---")
    csv = fdf.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 CSV Olarak İndir", data=csv,
        file_name=f"borsasinyal_tarama_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )