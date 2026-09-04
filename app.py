# ══════════════════════════════════════════════════════════════════════
#  app.py — BorsaSinyal Pro Terminal · v3.0 (EKSİKSİZ TAM SÜRÜM)
# ══════════════════════════════════════════════════════════════════════
#
#  Modüller:
#    mod_gorsel.py       — Global CSS, tema
#    mod_haberler.py     — Haber çekme, çeviri, okuyucu
#    mod_teknik_analiz.py— Teknik indikatör değerleri
#    mod_sirket.py       — Şirket bilgileri
#    mod_tahminler.py    — Analist tahminleri
#    mod_gostergeler.py  — Gösterge rehberi
#    mod_portfoy.py      — Portföy takibi
#    mod_sinyaller.py    — Sinyal görselleştirme
#    mod_filtreleme.py   — Piyasa taraması
#    mod_arama.py        — Hızlı arama
#    mod_yardim.py       — Yardım sekmesi
#    mod_guvenlik.py     — Session, rate limit
#    mod_animasyon.py    — Geçiş efektleri
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import yfinance as yf
import pandas as pd
import json, os
import threading
import time as _time
from mod_dashboard import render_dashboard

# ══════════════════════════════════════════════════════════════════════
#  ARKA PLAN TARAMA MOTORU — Web paneli açık kaldığı sürece çalışır
#  Modül seviyesinde flag sayesinde Streamlit her rerun'da tekrar başlatmaz
# ══════════════════════════════════════════════════════════════════════
_TARAMA_MOTORU_BASLATILDI = False

def _arka_plan_taramayi_baslat():
    """Arka planda sürekli tarama motorunu (daemon thread) 1 kere başlatır."""
    global _TARAMA_MOTORU_BASLATILDI
    if _TARAMA_MOTORU_BASLATILDI:
        return
    _TARAMA_MOTORU_BASLATILDI = True
    try:
        from otomatik_tarayici import surekli_tarama_dongusu
        _th = threading.Thread(target=surekli_tarama_dongusu, daemon=True, name="scanner-daemon")
        _th.start()
        from mod_logger import yapilandirilmis_logger
        yapilandirilmis_logger("App").info("✅ Tarama motoru arka planda başlatıldı (daemon thread — web paneli açık kaldıkça çalışır)")
    except Exception as e:
        from mod_logger import yapilandirilmis_logger
        yapilandirilmis_logger("App").warning(f"⚠️ Tarama motoru yüklenemedi: {e}")

from mod_tarama_sekmesi import render_tarama_sekmesi
from mod_yz_arayuz import render_yz_arayuz
from mod_yz_karnesi import render_yz_karnesi 
from mod_bt_arayuz import render_bt_arayuz
from datetime import datetime
from mod_detay_paneli import hisse_analiz_paneli
import analiz
from analiz import tum_hisseleri_tara, tek_hisse_detay, piyasa_havasini_olc
from mod_logger import yapilandirilmis_logger, guvenli_blok
from mod_ortak import (
    hisse_arama_listesi_olustur, render_hisse_arama,
    degisim_renk_ve_ok, degisim_arkaplan,
    session_guvenli_get, session_guvenli_set,
    POPULER_HISSELER, POPULER_HABER_SEMBOLLERI
)
from mod_config import config_al

_app_logger = yapilandirilmis_logger("App")

# Hemen başlat (logger tanımlandıktan sonra)
_arka_plan_taramayi_baslat()

# Çeviri modülü - güvenli import
CEVIRI_AKTIF = guvenli_blok(
    lambda: __import__('deep_translator', fromlist=['GoogleTranslator']) or True,
    varsayilan_donus=False, modul_adi="App", log_seviyesi="warning"
)

# ── Veri & Grafik ─────────────────────────────────────────────────────
from hisseler_bist   import BIST
from hisseler_sp500  import SP500
from hisseler_nasdaq import NASDAQ
import backtest
from hisse_isimleri  import HISSE_ISIMLERI
from grafik          import (
    tablo_goster, yukselenler_grafik, dusenler_grafik,
    rsi_dagilim_grafik, sinyal_pasta_grafik,
    portfoy_performans_grafik, guclu_al_grafik, ana_grafik
)
import plotly.graph_objects as go

# ── Modüller ──────────────────────────────────────────────────────────
from mod_gorsel       import uygula_tema, sidebar_gizle
from mod_haberler     import haber_paneli, dashboard_haber_paneli, haber_cevir, tum_sistemi_haber_tara
from mod_teknik_analiz import teknik_analiz_paneli
from mod_sirket       import sirket_paneli
from mod_tahminler    import tahminler_paneli
from mod_gostergeler  import gosterge_referansi
from mod_portfoy      import portfoy_yukle, portfoy_kaydet
from mod_yardim       import yardim_paneli
from mod_guvenlik     import session_baslat
from mod_animasyon    import gecis_css, bolum_baslik
try:
    from mod_telegram import telegram_mesaj_gonder
except ImportError:
    def telegram_mesaj_gonder(mesaj):
        pass

# ══════════════════════════════════════════════════════════════════════
#  SAYFA AYARLARI
# ══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="BorsaSinyal Pro",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 🔥 OPTIMIZE: 5 dakikada bir sessiz arka plan veri yenileme.
# Sayfa sönükleşmesini engellemek için sadece cache temizlenir,
# kullanıcı etkileşimi olmadan veriler güncellenir.


# ── CSS & Animasyonlar ────────────────────────────────────────────────
uygula_tema()
st.markdown("""
<style>
    /* 🔥 RERUN SÖNÜKLEŞMESİNİ ENGELLE */
    body { transition: none !important; }
    .stApp { transition: none !important; opacity: 1 !important; }
    iframe { transition: none !important; }
    
    /* Ana içerik tam genişlik */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
gecis_css()
st.markdown("""
<style>
/* --- BORSASİNYAL ÖZEL ARAMA KUTUSU TASARIMI --- */
div[data-baseweb="select"] > div {
    background-color: rgba(10, 18, 36, 0.8) !important;
    border: 1px solid rgba(77, 184, 255, 0.2) !important;
    border-radius: 8px !important;
    color: #d1d4dc !important;
}
div[data-baseweb="select"] > div:hover {
    border-color: rgba(77, 184, 255, 0.5) !important;
}
div[data-baseweb="select"] > div:focus-within {
    border-color: #f0c040 !important;
    box-shadow: 0 0 8px rgba(240, 192, 64, 0.3) !important;
}
div[data-baseweb="select"] [data-text="true"] {
    color: #787b86 !important;
}
div[data-baseweb="popover"] > div {
    background-color: #0f1c32 !important;
    border: 1px solid rgba(77, 184, 255, 0.2) !important;
    border-radius: 8px !important;
}
ul[role="listbox"] li {
    color: #d1d4dc !important;
    background-color: transparent !important;
    transition: background-color 0.2s ease;
}
ul[role="listbox"] li:hover, ul[role="listbox"] li[aria-selected="true"] {
    background-color: rgba(240, 192, 64, 0.15) !important;
    color: #f0c040 !important;
}
</style>
""", unsafe_allow_html=True)
# ══════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════
session_baslat(portfoy_yukle_fn=portfoy_yukle)
   
# ══════════════════════════════════════════════════════════════════════
#  BAŞLIK — Üst logo bar (st.sidebar KULLANILMAZ)
# ══════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="padding:16px 0 8px 0;border-bottom:1px solid rgba(30,51,85,0.25);
            background:linear-gradient(180deg,rgba(240,192,64,0.03) 0%,transparent 100%);
            margin-bottom:12px;">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div>
      <span style="font-family:'Sora','Outfit',sans-serif;font-size:22px;font-weight:800;
                  color:var(--txt1);letter-spacing:-.03em;">
        Borsa<span style="color:var(--gold);">Sinyal</span>
      </span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--txt3);
                  letter-spacing:.3em;margin-left:12px;text-transform:uppercase;">
        Pro Terminal · v3.1
      </span>
    </div>
    <div id="canli-saat-ust" style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--txt3);letter-spacing:.1em;">
      --:--:--
    </div>
  </div>
</div>
<script>
(function updateClockTop() {{
  var now = new Date();
  var h = now.getHours().toString().padStart(2,'0');
  var m = now.getMinutes().toString().padStart(2,'0');
  var s = now.getSeconds().toString().padStart(2,'0');
  var el = document.getElementById('canli-saat-ust');
  if(el) el.textContent = '🟢 SYS · ' + h + ':' + m + ':' + s + ' · LIVE';
  setTimeout(updateClockTop, 1000);
}})();
</script>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
#  HIZLI ARAMA ÇUBUĞU (üst bar altında inline) — Premium Selectbox
# ══════════════════════════════════════════════════════════════════════
c_ara1, c_ara2 = st.columns([1, 5])
with c_ara1:
    st.caption("🔎 Hızlı Arama")
with c_ara2:
    hisse_secenekleri = [f"{sembol} - {isim}" for sembol, isim in HISSE_ISIMLERI.items()]
    populerler = [
        "THYAO.IS - Türk Hava Yolları", "AAPL - Apple Inc.",
        "GARAN.IS - Garanti BBVA Bankası", "NVDA - NVIDIA Corporation",
        "KCHOL.IS - Koç Holding", "TSLA - Tesla Inc.",
        "META - Meta Platforms", "AMZN - Amazon.com",
        "MSFT - Microsoft Corp.", "GOOGL - Alphabet Inc."
    ]
    kalanlar = [h for h in hisse_secenekleri if h not in populerler]
    arama_listesi = populerler + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar

    sb_ara = st.selectbox(
        "Hızlı Arama",
        options=arama_listesi,
        index=None,
        placeholder="🔍 Hisse adı veya sembol yazın... (THYAO, AAPL, Garanti...)",
        key="sb_ara_smart",
        label_visibility="collapsed"
    )

    if sb_ara and "---" not in sb_ara:
        secilen_sembol = sb_ara.split(" - ")[0]
        if st.session_state.get("secilen_hisse") != secilen_sembol:
            st.session_state.secilen_hisse = secilen_sembol
            st.session_state.aktif_sekme = 2  # ANALİZ sekmesine otomatik geç
            st.rerun()

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
#  SEKMELER — 🔥 OPTİMİZE: Sadece aktif sekme render edilir
# ══════════════════════════════════════════════════════════════════════

TAB_ISIMLERI = [
    "DASHBOARD", "TARAMA", "ANALİZ", "YZ (ML)", 
    "KARNE", "TEST", "PORTFÖY", "HABER", "YARDIM"
]

# Session state'te aktif sekmeyi tut
if "aktif_sekme" not in st.session_state:
    st.session_state.aktif_sekme = 0

# Sekme butonlarını hızlı CSS-only yatay menü olarak göster
cols = st.columns(len(TAB_ISIMLERI))
for i, (col, isim) in enumerate(zip(cols, TAB_ISIMLERI)):
    with col:
        is_active = (st.session_state.aktif_sekme == i)
        btn_style = (
            "background:rgba(240,192,64,0.1);color:var(--gold);font-weight:700;"
            if is_active else
            "background:transparent;color:var(--txt3);"
        )
        st.markdown(f"""
        <style>
        div[data-testid="stElementContainer"]:has(button[key="tab_btn_{i}"]) {{
            margin-bottom: -1px !important;
        }}
        button[key="tab_btn_{i}"] {{
            width: 100% !important;
            {btn_style}
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
            border-radius: 6px !important;
            padding: 8px 2px !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 7px !important;
            letter-spacing: .04em !important;
            cursor: pointer !important;
            transition: all .15s ease !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }}
        button[key="tab_btn_{i}"]:hover {{
            border: none !important;
            color: var(--gold) !important;
            background: rgba(240,192,64,0.08) !important;
            outline: none !important;
            box-shadow: none !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        if st.button(isim, key=f"tab_btn_{i}", use_container_width=True):
            st.session_state.aktif_sekme = i
            st.rerun()

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# 🔥 SADECE AKTİF SEKMEYİ RENDER ET — Diğerleri hiç çalıştırılmaz
aktif = st.session_state.aktif_sekme

if aktif == 0:
    render_dashboard()

elif aktif == 1:
    render_tarama_sekmesi()

elif aktif == 2:
    # ── HİSSE ANALİZİ ──
    _, ara_col2, _ = st.columns([1, 3, 1])
    with ara_col2:
        hisse_secenekleri = [f"{sembol} - {isim}" for sembol, isim in HISSE_ISIMLERI.items()]
        populerler = ["THYAO.IS - Türk Hava Yolları", "AAPL - Apple Inc.", "GARAN.IS - Garanti BBVA Bankası", "NVDA - NVIDIA Corporation", "KCHOL.IS - Koç Holding"]
        kalanlar = [h for h in hisse_secenekleri if h not in populerler]
        arama_listesi = populerler + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar

        tab2_secim = st.selectbox("Hisse Ara veya Seç:", options=arama_listesi, index=None, placeholder="🔍 Analiz etmek istediğiniz hisseyi seçin...", key="tab2_hisse_smart", label_visibility="collapsed")
        
        if tab2_secim and "---" not in tab2_secim:
            secilen_sembol = tab2_secim.split(" - ")[0]
            if st.session_state.get("secilen_hisse") != secilen_sembol:
                st.session_state.secilen_hisse = secilen_sembol
                st.rerun()
    if st.session_state.secilen_hisse:
        hisse_analiz_paneli(st.session_state.secilen_hisse, key_prefix="tab2")
    else:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
          <div style="font-family:'Sora',sans-serif;font-size:44px;font-weight:800;color:var(--border);">
            HİSSE ANALİZİ
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--txt3);
                      letter-spacing:.2em;margin-top:12px;text-transform:uppercase;">
            Yukarıdan hisse ara veya dashboard'dan tıkla
          </div>
        </div>
        """, unsafe_allow_html=True)

elif aktif == 3:
    render_yz_arayuz()

elif aktif == 4:
    render_yz_karnesi()

elif aktif == 5:
    render_bt_arayuz()

elif aktif == 6:
    from mod_portfoy import portfoy_paneli
    portfoy_paneli()

elif aktif == 7:
    # ── HABERLER ──
    bolum_baslik("Piyasa Haberleri")
    h1, h2 = st.columns([4, 1])
    with h1:
        h_hisse = st.text_input("Hisse Sembolü", placeholder="Hisse sembolü girin... (Örn: AAPL, THYAO.IS)",
                                 label_visibility="collapsed", key="h_hisse")
    with h2:
        if st.button("HABERLERİ GETİR", use_container_width=True):
            if h_hisse:
                st.session_state.haber_pop = h_hisse.strip().upper()

    st.markdown("---")
    st.markdown('<span class="section-label">Hızlı Erişim</span>', unsafe_allow_html=True)
    pop_s = [
        "THYAO.IS","GARAN.IS","AAPL","NVDA","TSLA","META",
        "AMZN","MSFT","GOOGL","PLTR","COIN","RBLX",
        "AMD","NFLX","SNOW","CRWD","BABA","SHOP"
    ]
    for row in range(0, len(pop_s), 6):
        cols = st.columns(6)
        for i in range(6):
            idx = row + i
            if idx < len(pop_s):
                sym = pop_s[idx]
                with cols[i]:
                    if st.button(sym.replace(".IS",""), key=f"h_pop_{sym}", use_container_width=True):
                        st.session_state.haber_pop = sym

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    secili_sembol = st.session_state.get("haber_pop") or "AAPL"
    
    st.markdown(f'<span class="section-label" style="color:var(--gold);">{secili_sembol} - Genişletilmiş Haber Akışı</span>', unsafe_allow_html=True)
    
    # 🔥 OPTİMİZE: Haberleri cache'le (5dk)
    @st.cache_data(ttl=300, show_spinner=False)
    def _haber_cache(sembol):
        return tum_sistemi_haber_tara((sembol,))
    
    with st.spinner(f"{secili_sembol} için küresel kaynaklar taranıyor..."):
        ozel_haberler = _haber_cache(secili_sembol)
        
    if ozel_haberler:
        goruldu = set()
        h_cols = st.columns(2)
        kutu_sayaci = 0
        
        for hb in ozel_haberler:
            if not hb["baslik"] or hb["baslik"] in goruldu:
                continue
            goruldu.add(hb["baslik"])
            if kutu_sayaci >= 16: break
            
            with h_cols[kutu_sayaci % 2]:
                st.markdown(f"""
                <div style="background:rgba(10,18,36,0.6);border:1px solid rgba(255,255,255,0.05);
                            border-top:2px solid var(--blue);border-radius:8px;padding:16px;margin-bottom:14px;
                            height:140px; overflow:hidden; position:relative;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--gold);margin-bottom:8px;">
                    ⏱ {hb['zaman']} &nbsp;<span style="color:rgba(255,255,255,0.2)">|</span>&nbsp; <span style="color:var(--txt3)">{hb['yayinci']}</span>
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:13px;font-weight:600;color:var(--txt1);line-height:1.4;margin-bottom:8px;">
                    {hb['baslik']}
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:11px;color:var(--txt2);line-height:1.5; opacity:0.8;">
                    {hb.get('ozet', 'Haberin detaylarını okumak için kaynağa gidin.')[:90]}...
                  </div>
                  {'<a href="' + hb["url"] + '" target="_blank" style="position:absolute; bottom:12px; right:16px; font-family:JetBrains Mono,monospace;font-size:9px;color:var(--gold);text-decoration:none;letter-spacing:.1em; background:rgba(240,192,64,0.1); padding:4px 8px; border-radius:4px;">KAYNAĞA GİT ↗</a>' if hb.get("url") else ''}
                </div>
                """, unsafe_allow_html=True)
            kutu_sayaci += 1
    else:
        st.info("Bu hisse için şu anda yeni bir haber akışı bulunmuyor.")

elif aktif == 8:
    yardim_paneli()
