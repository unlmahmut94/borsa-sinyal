import streamlit as st
import yfinance as yf
from mod_animasyon import bolum_baslik
from mod_formasyon import formasyon_analizi # YENİ YZ GÖZÜNÜ İÇERİ AKTARDIK

def hisse_analiz_paneli(hisse, key_prefix=""):
    if not hisse:
        st.warning("⚠️ Lütfen analiz etmek için sol taraftaki menüden bir hisse yazın (Örn: ASELS.IS veya AAPL)")
        return
        
    bolum_baslik(f"🔍 {hisse} Analiz Paneli", "Anlık fiyat, grafik ve YZ Formasyon Algılayıcı")
    
    with st.spinner(f"{hisse} verileri çekiliyor ve YZ grafiği okuyor..."):
        try:
            tk = yf.Ticker(hisse)
            hist = tk.history(period="3mo")
            
            if hist.empty:
                st.error("❌ Bu hisse için piyasa verisi bulunamadı. Lütfen sembolü kontrol edin.")
                return
                
            son_fiyat = float(hist['Close'].iloc[-1])
            onceki_fiyat = float(hist['Close'].iloc[-2])
            degisim = ((son_fiyat - onceki_fiyat) / onceki_fiyat) * 100
            
            renk = "#0fdb7a" if degisim >= 0 else "#ff3b5c"
            isaret = "+" if degisim >= 0 else ""
            
            # Siber Tasarımlı Fiyat Kutusu
            st.markdown(f"""
            <div style="background:rgba(15,25,45,0.8); border:1px solid rgba(255,255,255,0.1); border-left:6px solid {renk}; padding:20px; border-radius:10px; margin-bottom:20px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h2 style="margin:0; color:#fff;">{hisse}</h2>
                    <div style="text-align:right;">
                        <div style="font-size:28px; font-weight:bold; color:{renk};">{son_fiyat:.2f}</div>
                        <div style="color:{renk}; font-size:16px;">Günlük: {isaret}%{degisim:.2f}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # --- YZ FORMASYON OKUYUCU EKRANI ---
            st.markdown("#### 🤖 YZ Grafik Formasyon Yorumu")
            bulunan_formasyonlar = formasyon_analizi(hist)
            
            if not bulunan_formasyonlar:
                st.info("👁️ YZ bu grafikte belirgin bir formasyon (İkili Dip, Tepe veya Sıkışma) tespit edemedi. Trend olağan seyrinde.")
            else:
                for f in bulunan_formasyonlar:
                    if f['tip'] == 'success':
                        st.success(f"**{f['baslik']}**\n\n{f['detay']}")
                    elif f['tip'] == 'error':
                        st.error(f"**{f['baslik']}**\n\n{f['detay']}")
                    elif f['tip'] == 'warning':
                        st.warning(f"**{f['baslik']}**\n\n{f['detay']}")

            st.markdown("---")
            
            # Fiyat Grafiği
            st.markdown("#### 📊 3 Aylık Fiyat Trendi")
            st.line_chart(hist['Close'], color="#4db8ff")
            
        except Exception as e:
            st.error(f"⚠️ Sistem veriyi işlerken bir hata ile karşılaştı: {e}")