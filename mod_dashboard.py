# ══════════════════════════════════════════════════════════════════════
#  TAB 0 — DASHBOARD · v3.2 ✨
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
from datetime import datetime
from hisse_isimleri import HISSE_ISIMLERI
from analiz import piyasa_havasini_olc
from mod_veri_servisi import canli_fiyat_hizli
from mod_haberler import tum_sistemi_haber_tara, haber_beklenti_analizi, haber_cevir
import yfinance as yf
import pandas as pd
import numpy as np
import math

@st.cache_data(ttl=300, show_spinner=False)
def _endeks_verileri_cek():
    endeksler = [
        ("^XU100","BIST 100","TR"),("^GSPC","S&P 500","US"),("^IXIC","NASDAQ","US"),
        ("^DJI","DOW JONES","US"),("GC=F","ALTIN","AU"),("DX-Y.NYB","DXY","$"),
    ]
    sonuclar = []
    for sym, label, flag in endeksler:
        try:
            h = yf.Ticker(sym).history(period="3d")
            if len(h) >= 2:
                son = float(h["Close"].iloc[-1])
                onceki = float(h["Close"].iloc[-2])
                deg = 0.0
                if onceki != 0 and not math.isnan(onceki):
                    deg = ((son - onceki) / onceki) * 100
                if math.isnan(son): son = 0
                if math.isnan(deg): deg = 0.0
                sonuclar.append((sym, label, flag, son, round(deg, 2)))
            else:
                sonuclar.append((sym, label, flag, 0, 0.0))
        except Exception:
            sonuclar.append((sym, label, flag, 0, 0.0))
    return sonuclar

@st.cache_data(ttl=300, show_spinner=False)
def _makro_veri_cek():
    return piyasa_havasini_olc()


def render_dashboard():

    st.markdown(f"""
    <div class="fade-in" style="padding:32px 0 0 0;">
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
        <span style="font-family:'Sora','Outfit',sans-serif;font-size:32px;font-weight:800;
                     color:var(--txt1);letter-spacing:-.04em;line-height:1;">
          Piyasa <span style="background:linear-gradient(135deg,var(--gold),var(--gold-l));
          -webkit-background-clip:text;-webkit-text-fill-color:transparent;">Dashboard</span>
        </span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:10px;
                     color:var(--txt3);letter-spacing:.14em;padding:5px 14px;
                     background:rgba(30,51,85,0.3);border:none;
                     border-radius:20px;backdrop-filter:blur(8px);">
          {datetime.now().strftime('%d.%m.%Y  %H:%M')}
        </span>
        <span style="display:inline-flex;align-items:center;gap:6px;
                     font-family:'JetBrains Mono',monospace;font-size:8px;
                     color:var(--green);letter-spacing:.12em;margin-left:auto;">
          <span style="width:8px;height:8px;background:var(--green);border-radius:50%;
                       box-shadow:0 0 8px var(--green-glow);display:inline-block;"></span>
          LİVE
        </span>
      </div>
      <div style="font-family:'Sora',sans-serif;font-size:13px;font-weight:300;
                  color:var(--txt2);margin-top:8px;letter-spacing:.01em;opacity:.85;">
        Küresel piyasaların anlık durumu · Satıra tıklayın — detaylı analiz
      </div>
    </div>
    <div style="height:1px;background:linear-gradient(90deg,var(--blue),rgba(77,184,255,0.08),transparent);
                margin:18px 0 24px 0;opacity:.5;"></div>
    """, unsafe_allow_html=True)

    # ── Hisse Arama ──────────────────────────────────────────────────
    _, ara_col, _ = st.columns([1, 3, 1])
    with ara_col:
        hisse_secenekleri = [f"{sembol} - {isim}" for sembol, isim in HISSE_ISIMLERI.items()]
        populerler = [
            "THYAO.IS - Türk Hava Yolları",
            "AAPL - Apple Inc.",
            "GARAN.IS - Garanti BBVA Bankası",
            "NVDA - NVIDIA Corporation",
            "KCHOL.IS - Koç Holding"
        ]
        kalanlar = [h for h in hisse_secenekleri if h not in populerler]
        arama_listesi = populerler + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar

        ana_secim = st.selectbox(
            "Hisse Ara veya Seç:",
            options=arama_listesi,
            index=None,
            placeholder="🔍  Aramak için tıklayın veya yazın...",
            key="ana_hisse_smart",
            label_visibility="collapsed"
        )

        if ana_secim and "---" not in ana_secim:
            secilen_sembol = ana_secim.split(" - ")[0]
            if st.session_state.get("secilen_hisse") != secilen_sembol:
                st.session_state.secilen_hisse = secilen_sembol
                st.rerun()

    # ── MAKRO ────────────────────────────────────────────────────────
    st.markdown("""<div style="font-family:'JetBrains Mono',monospace;font-size:9px;
        color:var(--txt3);letter-spacing:.18em;text-transform:uppercase;
        margin:20px 0 12px 0;display:flex;align-items:center;gap:10px;">
        <span style="width:20px;height:2px;background:var(--gold);display:inline-block;
                     border-radius:1px;opacity:.6;"></span>
        PİYASA HAVA DURUMU (MAKRO)
        <span style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent);
                     display:inline-block;"></span>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Makro veriler yükleniyor..."):
        havadurumu = _makro_veri_cek()

    m_cols = st.columns(3)
    makro_items = [
        ("💵 DOLAR/TL",     havadurumu.get("Dolar",  0),
         "İhracatçılar için avantaj" if havadurumu.get("Dolar",  0) > 0
         else "İç piyasa odaklılar pozitif"),
        ("🟡 ONS ALTIN",    havadurumu.get("Altın",  0),
         "Madencilik (KOZAL vb.) takibi" if havadurumu.get("Altın",  0) > 0
         else "Emtia baskısı"),
        ("🛢️ BRENT PETROL", havadurumu.get("Petrol", 0),
         "Havacılık (THYAO) için risk" if havadurumu.get("Petrol", 0) > 0
         else "Ulaşım maliyeti düşüyor"),
    ]
    for i, (label, deg, notu) in enumerate(makro_items):
        renk = "inverse" if deg < 0 else "normal"
        with m_cols[i]:
            st.metric(label, f"%{deg:+.2f}", help=notu, delta_color=renk)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── KÜRESEL ENDEKSLER ─────────────────────────────────────────────
    st.markdown("""<div style="font-family:'JetBrains Mono',monospace;font-size:9px;
        color:var(--txt3);letter-spacing:.18em;text-transform:uppercase;
        margin-bottom:12px;display:flex;align-items:center;gap:10px;">
        <span style="width:20px;height:2px;background:var(--blue);display:inline-block;
                     border-radius:1px;opacity:.6;"></span>
        KÜRESEL ENDEKSLER
        <span style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent);
                     display:inline-block;"></span>
    </div>""", unsafe_allow_html=True)

    endeks_veri = _endeks_verileri_cek()
    temiz_endeks = [v for v in endeks_veri if v[3] != 0]
    if temiz_endeks:
        ekols = st.columns(len(temiz_endeks))
        for i, (sym, label, flag, son, deg) in enumerate(temiz_endeks):
            if i >= 6: break
            renk_ok = "#22e691" if deg >= 0 else "#ff4f6d"
            ok_sim  = "▲" if deg >= 0 else "▼"
            bg_r    = "rgba(8,40,22,0.4)" if deg >= 0 else "rgba(40,8,16,0.4)"
            with ekols[i]:
                st.markdown(f"""
                <div style="background:linear-gradient(160deg,rgba(10,18,36,0.6),rgba(6,11,18,0.5));
                            padding:16px 14px;text-align:center;backdrop-filter:blur(8px);">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:8px;
                              color:var(--txt3);letter-spacing:.16em;text-transform:uppercase;
                              margin-bottom:10px;">{flag} {label}</div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:18px;
                              font-weight:800;color:var(--txt1);margin-bottom:6px;
                              letter-spacing:-.02em;">{son:,.1f}</div>
                  <div style="display:inline-block;font-family:'JetBrains Mono',monospace;
                              font-size:11px;color:{renk_ok};font-weight:700;
                              background:{bg_r};padding:3px 12px;border-radius:14px;">
                    {ok_sim} {abs(deg):.2f}%</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    #  HİSSE TABLOLARI (SOL) + HABER (SAĞ)
    # ═══════════════════════════════════════════════════════════════════
    col_liste, col_haberler = st.columns([3, 2], gap="large")

    with st.spinner("Fiyatlar yükleniyor..."):
        bist_list = canli_fiyat_hizli(("THYAO.IS", "GARAN.IS", "ASELS.IS", "KCHOL.IS", "TUPRS.IS"))
        abd_list  = canli_fiyat_hizli(("AAPL", "NVDA", "TSLA", "MSFT", "AMZN"))
        bist_list.sort(key=lambda x: abs(x['degisim']), reverse=True)
        abd_list.sort(key=lambda x: abs(x['degisim']), reverse=True)

    # ── Hisse satırı: st.columns ile mükemmel hizalı, renkli, tıklanabilir ──
    def _hisse_satir(h, para="", idx=0, prefix="bist"):
        """Tek bir hisse satırını st.columns ile basar — renkler, oklar, hizalama garantili."""
        is_pos  = h["degisim"] >= 0
        renk    = "#22e691" if is_pos else "#ff4f6d"
        ok_is   = "▲" if is_pos else "▼"
        bg_b    = "rgba(8,40,22,0.25)" if is_pos else "rgba(40,8,20,0.25)"
        sembol  = h["sembol"].replace(".IS","")
        isim    = h['isim'][:22]
        fiyat   = f"{para}{h['fiyat']:,.2f}"
        degisim = f"{ok_is} {abs(h['degisim']):.2f}%"
        yuksek  = f"↑ {para}{h['yuksek']:,.2f}"
        dusuk   = f"↓ {para}{h['dusuk']:,.2f}"
        hacim_s = (f"{h['hacim']/1e9:.1f}B" if h['hacim'] >= 1e9
                   else f"{h['hacim']/1e6:.0f}M" if h['hacim'] >= 1e6
                   else f"{h['hacim']:,.0f}")
        btn_key = f"sr_{prefix}_{idx}"

        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([70, 130, 85, 105, 85, 85, 75, 30])
        with c1:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:13px;font-weight:700;color:#eef2f7;'>{sembol}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='font-family:Sora,sans-serif;font-size:11px;color:#c4cdd9;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>{isim}</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:13px;font-weight:700;color:#eef2f7;text-align:right;'>{fiyat}</div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:11px;font-weight:700;color:{renk};background:{bg_b};padding:3px 10px;border-radius:14px;display:inline-block;white-space:nowrap;'>{degisim}</div>", unsafe_allow_html=True)
        with c5:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:11px;color:#22e691;text-align:right;white-space:nowrap;'>{yuksek}</div>", unsafe_allow_html=True)
        with c6:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:11px;color:#ff4f6d;text-align:right;white-space:nowrap;'>{dusuk}</div>", unsafe_allow_html=True)
        with c7:
            st.markdown(f"<div style='font-family:JetBrains Mono,monospace;font-size:10px;color:#8a9bb5;text-align:right;'>{hacim_s}</div>", unsafe_allow_html=True)
        with c8:
            if st.button("▶", key=btn_key, type="secondary", use_container_width=True):
                st.session_state.secilen_hisse = h["sembol"]
                st.session_state.aktif_sekme = 2
                st.rerun()

    def _tablo_baslik():
        """st.columns ile başlık satırı — verilerle birebir aynı kolon oranları."""
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([70, 130, 85, 105, 85, 85, 75, 30])
        stl = "font-family:JetBrains Mono,monospace;font-size:9px;color:#8a9bb5;letter-spacing:.1em;font-weight:600;"
        with c1: st.markdown(f"<span style='{stl}'>SEMBOL</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='{stl}'>ŞİRKET</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='{stl};text-align:right;display:block;'>FİYAT</span>", unsafe_allow_html=True)
        with c4: st.markdown(f"<span style='{stl};text-align:center;display:block;'>DEĞİŞİM</span>", unsafe_allow_html=True)
        with c5: st.markdown(f"<span style='{stl};text-align:right;display:block;'>YÜKSEK</span>", unsafe_allow_html=True)
        with c6: st.markdown(f"<span style='{stl};text-align:right;display:block;'>DÜŞÜK</span>", unsafe_allow_html=True)
        with c7: st.markdown(f"<span style='{stl};text-align:right;display:block;'>HACİM</span>", unsafe_allow_html=True)
        with c8: st.markdown("", unsafe_allow_html=True)

    def _hisse_liste_blok(hisse_list, baslik, renk_cizgi="var(--gold)", para=""):
        """Bir hisse listesini başlık + tablo olarak render eder."""
        st.markdown(f"""<div style="font-family:'JetBrains Mono',monospace;font-size:9px;
            color:var(--txt3);letter-spacing:.18em;text-transform:uppercase;
            margin:0 0 10px 0;display:flex;align-items:center;gap:10px;">
            <span style="width:20px;height:2px;background:{renk_cizgi};display:inline-block;
                         border-radius:1px;opacity:.6;"></span>
            {baslik}
            <span style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent);
                         display:inline-block;"></span>
        </div>""", unsafe_allow_html=True)
        # Çizgi ayırıcı
        st.markdown("<div style='height:1px;background:rgba(255,255,255,0.04);margin-bottom:4px;'></div>", unsafe_allow_html=True)
        _tablo_baslik()
        for idx, h in enumerate(hisse_list):
            _hisse_satir(h, para=para, idx=idx, prefix=baslik[:4])

    # ══════════════════════════════════════════════════════
    #  SOL KOLON: BIST + US TABLOLARI
    # ══════════════════════════════════════════════════════
    with col_liste:
        _hisse_liste_blok(bist_list, "🔥 TR BIST - GÜNÜN ÖNE ÇIKANLARI", "var(--gold)", para="")
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        _hisse_liste_blok(abd_list, "🔥 US ABD - GÜNÜN ÖNE ÇIKANLARI", "var(--blue)", para="$")

    # ══════════════════════════════════════════════════════
    #  SAĞ KOLON: HABER + SİNYAL RADARI
    # ══════════════════════════════════════════════════════
    with col_haberler:
        # ── Haber Akışı ─────────────────────────────────
        st.markdown("""<div style="font-family:'JetBrains Mono',monospace;font-size:9px;
            color:var(--txt3);letter-spacing:.18em;text-transform:uppercase;
            margin:0 0 12px 0;display:flex;align-items:center;gap:10px;">
            <span style="width:20px;height:2px;background:var(--gold);display:inline-block;
                         border-radius:1px;opacity:.6;"></span>
            📰 HABER AKIŞI
            <span style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent);
                         display:inline-block;"></span>
        </div>""", unsafe_allow_html=True)

        @st.cache_data(ttl=300, show_spinner=False)
        def _dashboard_haberleri_getir():
            takip = [
                "THYAO.IS","GARAN.IS","ASELS.IS","KCHOL.IS",
                "AAPL","NVDA","TSLA","MSFT","AMZN","META","GOOGL",
                "PLTR","SNOW","COIN","RBLX","SOFI","MRNA",
            ]
            sonuc = []
            for sym in takip:
                try:
                    haberler = tum_sistemi_haber_tara((sym,))
                    if haberler:
                        goruldu = set()
                        for hb in haberler:
                            if hb["baslik"] and hb["baslik"] not in goruldu:
                                goruldu.add(hb["baslik"])
                                sonuc.append((
                                    sym.replace(".IS",""),
                                    hb["baslik"][:70],
                                    hb.get("zaman",""),
                                    hb.get("yayinci",""),
                                ))
                                if len(sonuc) >= 14:
                                    break
                    if len(sonuc) >= 14:
                        break
                except:
                    pass
            return sonuc

        haberler = _dashboard_haberleri_getir()
        if haberler:
            for sym, baslik, zaman, yayinci in haberler:
                st.markdown(f"""
                <div style="padding:8px 14px;border-left:2px solid rgba(240,192,64,0.3);
                            margin-bottom:6px;border-radius:0 6px 6px 0;
                            background:rgba(14,24,44,0.5);transition:all 0.15s;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:8px;
                              color:var(--gold);letter-spacing:.1em;margin-bottom:2px;">
                    {sym} <span style="color:#5a6d85;">· {zaman}</span>
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:11px;
                              color:var(--txt2);line-height:1.3;">
                    {baslik}
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Haber akışı şu anda boş. Veri kaynakları kontrol ediliyor...")

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        # ── HABER + SİNYAL RADARI ───────────────────────
        st.markdown("""<div style="font-family:'JetBrains Mono',monospace;font-size:9px;
            color:var(--txt3);letter-spacing:.18em;text-transform:uppercase;
            margin:0 0 12px 0;display:flex;align-items:center;gap:10px;">
            <span style="width:20px;height:2px;background:var(--blue);display:inline-block;
                         border-radius:1px;opacity:.6;"></span>
            📡 SİNYAL RADARI
            <span style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent);
                         display:inline-block;"></span>
        </div>""", unsafe_allow_html=True)

        # Teknik sinyal hesaplama
        def _teknik_sinyal_hesapla(sym):
            try:
                data = yf.Ticker(sym).history(period="1mo")
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                if len(data) >= 20 and 'Close' in data.columns:
                    close_series = data['Close']
                    son_fiyat = float(close_series.iloc[-1])
                    ma50 = float(close_series.rolling(50).mean().iloc[-1]) if len(close_series) >= 50 else son_fiyat
                    delta = close_series.diff()
                    gain = delta.clip(lower=0).rolling(window=14).mean()
                    loss = (-delta.clip(upper=0)).rolling(window=14).mean()
                    rs = gain / loss.replace(0, float('nan'))
                    rsi_val = float(100 - (100 / (1 + rs.iloc[-1]))) if not pd.isna(rs.iloc[-1]) else 50.0
                    if not isinstance(rsi_val, (int, float)) or pd.isna(rsi_val):
                        rsi_val = 50.0
                    if rsi_val < 35 and son_fiyat > ma50:
                        t_sin, t_skor = "AL", 4
                    elif rsi_val > 65 and son_fiyat < ma50:
                        t_sin, t_skor = "SAT", -4
                    else:
                        t_sin, t_skor = "NOTR", 0
                    return t_sin, t_skor, round(rsi_val, 1)
            except:
                pass
            return "NOTR", 0, 50.0

        # BIST sinyalleri
        st.markdown("<div style='font-family:Sora,sans-serif;font-size:12px;font-weight:600;color:var(--gold);margin-bottom:6px;'>🔥 BIST</div>", unsafe_allow_html=True)
        for h in bist_list:
            sym = h["sembol"]
            t_sin, t_skor, rsi = _teknik_sinyal_hesapla(sym)
            sin_renk = {"AL": "#22e691", "SAT": "#ff4f6d", "NOTR": "#8a9bb5"}.get(t_sin, "#8a9bb5")
            sin_bg   = {"AL": "rgba(8,40,22,0.3)", "SAT": "rgba(40,8,20,0.3)", "NOTR": "rgba(255,255,255,0.04)"}.get(t_sin, "")
            sembol_t = sym.replace(".IS","")
            st.markdown(f"""
            <div style="display:flex;align-items:center;padding:5px 12px;margin:2px 0;border-radius:6px;">
              <span style="width:50px;font-family:JetBrains Mono,monospace;font-size:12px;font-weight:600;color:#eef2f7;">{sembol_t}</span>
              <span style="width:40px;font-family:JetBrains Mono,monospace;font-size:11px;font-weight:700;color:{sin_renk};background:{sin_bg};padding:2px 8px;border-radius:10px;text-align:center;">{t_sin}</span>
              <span style="width:40px;font-family:JetBrains Mono,monospace;font-size:10px;color:#8a9bb5;text-align:right;">RSI:{rsi}</span>
              <span style="flex:1;font-family:JetBrains Mono,monospace;font-size:11px;font-weight:600;color:{'#22e691' if h['degisim'] >= 0 else '#ff4f6d'};text-align:right;">{'▲' if h['degisim'] >= 0 else '▼'} {abs(h['degisim']):.2f}%</span>
            </div>
            """, unsafe_allow_html=True)

        # US sinyalleri
        st.markdown("<div style='font-family:Sora,sans-serif;font-size:12px;font-weight:600;color:var(--blue);margin:10px 0 6px 0;'>🏛️ US</div>", unsafe_allow_html=True)
        for h in abd_list:
            sym = h["sembol"]
            t_sin, t_skor, rsi = _teknik_sinyal_hesapla(sym)
            sin_renk = {"AL": "#22e691", "SAT": "#ff4f6d", "NOTR": "#8a9bb5"}.get(t_sin, "#8a9bb5")
            sin_bg   = {"AL": "rgba(8,40,22,0.3)", "SAT": "rgba(40,8,20,0.3)", "NOTR": "rgba(255,255,255,0.04)"}.get(t_sin, "")
            st.markdown(f"""
            <div style="display:flex;align-items:center;padding:5px 12px;margin:2px 0;border-radius:6px;">
              <span style="width:50px;font-family:JetBrains Mono,monospace;font-size:12px;font-weight:600;color:#eef2f7;">{sym}</span>
              <span style="width:40px;font-family:JetBrains Mono,monospace;font-size:11px;font-weight:700;color:{sin_renk};background:{sin_bg};padding:2px 8px;border-radius:10px;text-align:center;">{t_sin}</span>
              <span style="width:40px;font-family:JetBrains Mono,monospace;font-size:10px;color:#8a9bb5;text-align:right;">RSI:{rsi}</span>
              <span style="flex:1;font-family:JetBrains Mono,monospace;font-size:11px;font-weight:600;color:{'#22e691' if h['degisim'] >= 0 else '#ff4f6d'};text-align:right;">{'▲' if h['degisim'] >= 0 else '▼'} {abs(h['degisim']):.2f}%</span>
            </div>
            """, unsafe_allow_html=True)
