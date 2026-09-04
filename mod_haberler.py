# ══════════════════════════════════════════════════════════════════════
#  mod_haberler.py — Haber çekme, çeviri, site-içi okuyucu v3.2 ✨
#  YENİ: Dashboard inline özet, beklenti analizi, haber-sinyal algoritması
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import yfinance as yf
from datetime import datetime
import concurrent.futures
import numpy as np

# Çeviri kütüphanesi (pip install deep-translator)
try:
    from deep_translator import GoogleTranslator
    CEVIRI_AKTIF = True
except ImportError:
    CEVIRI_AKTIF = False

try:
    import feedparser
    import requests
    SEC_AKTIF = True
except ImportError:
    SEC_AKTIF = False

# ── NLP Duyarlılık (analiz.py'deki pipeline'ı import et) ──────────────
try:
    from analiz import haber_skoru_hesapla
    NLP_AKTIF = True
except ImportError:
    NLP_AKTIF = False
    def haber_skoru_hesapla(x):
        return 0


def sec_8k_radar(sembol: str) -> list:
    """SEC EDGAR üzerinden şirketin son 8-K (Önemli Gelişme) formlarını saniyeler içinde çeker."""
    if not SEC_AKTIF:
        return []

    headers = {'User-Agent': 'BorsaSinyalPro Terminal (iletisim@borsasinyal.com)'}
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={sembol}&type=8-K&owner=exclude&start=0&count=3&output=atom"

    sec_haberleri = []
    try:
        cevap = requests.get(url, headers=headers, timeout=5)
        if cevap.status_code != 200:
            return []

        feed = feedparser.parse(cevap.content)

        for entry in feed.entries:
            baslik = entry.title
            link = entry.link
            zaman_str = entry.updated

            if "8-K" in baslik:
                sec_haberleri.append({
                    "sembol": sembol,
                    "baslik": "🚨 SEC BİLDİRİMİ (8-K): Şirketten Acil/Önemli Gelişme Raporu",
                    "ozet": baslik,
                    "url": link,
                    "zaman": zaman_str[:10],
                    "yayinci": "SEC EDGAR (Resmi Bildirim)",
                    "duyarlilik": 0
                })
        return sec_haberleri
    except Exception:
        return []


def haber_cevir(metin: str) -> str:
    """Haber başlığını Türkçeye çevirir."""
    if CEVIRI_AKTIF and metin:
        try:
            return GoogleTranslator(source="auto", target="tr").translate(metin)
        except Exception:
            return metin
    return metin


# ══════════════════════════════════════════════════════════════════════
#  YENİ: Tekil haber için duyarlılık (beklenti) analizi
# ══════════════════════════════════════════════════════════════════════
def haber_beklenti_analizi(haber_baslik: str, haber_ozet: str = "") -> dict:
    """
    Tek bir haberin hisseye olan beklenti etkisini analiz eder.
    Dönüş: {
        'skor': float (-1 ile +1 arası),
        'yon': 'POZİTİF' | 'NÖTR' | 'NEGATİF',
        'guven': float (0-100),
        'renk': str (CSS rengi),
        'ikon': str (emoji),
        'aciklama': str
    }
    """
    birlestirilmis_metin = f"{haber_baslik} {haber_ozet}" if haber_ozet else haber_baslik

    if not birlestirilmis_metin or not NLP_AKTIF:
        return {
            'skor': 0, 'yon': 'NÖTR', 'guven': 50,
            'renk': '#7a8fa8', 'ikon': '⚪',
            'aciklama': 'Analiz için yeterli veri yok veya NLP devre dışı.'
        }

    # NLP modeli ile duyarlılık analizi
    try:
        from analiz import sentiment_pipeline
        sonuc = sentiment_pipeline(birlestirilmis_metin[:512])[0]
        ham_skor = sonuc['score']
        label = sonuc['label']

        if label == 'positive':
            skor = ham_skor
            yon = 'POZİTİF'
            renk = '#0fdb7a'
            ikon = '🟢'
        elif label == 'negative':
            skor = -ham_skor
            yon = 'NEGATİF'
            renk = '#ff3b5c'
            ikon = '🔴'
        else:
            skor = 0
            yon = 'NÖTR'
            renk = '#f5cc6a'
            ikon = '🟡'

        guven = min(100, ham_skor * 100)

        # Açıklama metni
        if abs(skor) > 0.7:
            aciklama = f"Çok güçlü {yon.lower()} beklenti — hisse üzerinde belirgin etki beklenir"
        elif abs(skor) > 0.4:
            aciklama = f"{yon} beklenti — hisse üzerinde orta düzeyde etki beklenir"
        elif abs(skor) > 0.1:
            aciklama = f"Hafif {yon.lower()} beklenti — sınırlı etki"
        else:
            aciklama = "Nötr — hisse üzerinde belirgin bir etki beklenmiyor"

        return {
            'skor': round(skor, 2),
            'yon': yon,
            'guven': round(guven, 1),
            'renk': renk,
            'ikon': ikon,
            'aciklama': aciklama
        }
    except Exception:
        return {
            'skor': 0, 'yon': 'NÖTR', 'guven': 50,
            'renk': '#7a8fa8', 'ikon': '⚪',
            'aciklama': 'Analiz sırasında hata oluştu.'
        }


# ══════════════════════════════════════════════════════════════════════
#  YENİ: Haber + Teknik birleşik Güçlü AL sinyali algoritması
# ══════════════════════════════════════════════════════════════════════
def haber_guclu_al_sinyali(haber_skoru: float, teknik_sinyal: str, teknik_skor: int,
                           rsi: float = 50, fiyat_ma50_oran: float = 1.0) -> dict:
    """
    Haber duyarlılığı ile teknik sinyalleri birleştirerek algoritmik Güçlü AL kararı verir.

    Parametreler:
        haber_skoru: -1 ile +1 arası NLP duyarlılık skoru
        teknik_sinyal: 'GUCLU AL', 'AL', 'NOTR', 'SAT', 'GUCLU SAT'
        teknik_skor: Teknik analiz toplam puanı
        rsi: RSI değeri
        fiyat_ma50_oran: Fiyat / MA50 oranı

    Dönüş: {
        'sinyal': str,
        'guven_puani': int (0-100),
        'aciklama': str,
        'renk': str,
        'detaylar': list
    }
    """
    detaylar = []
    bilesik_puan = 0

    # ── 1. Haber Duyarlılık Katkısı (Max 40 puan) ─────────────────
    if haber_skoru > 0.6:
        bilesik_puan += 40
        detaylar.append(f"🔥 NLP: Çok güçlü pozitif haber akışı (+40)")
    elif haber_skoru > 0.3:
        bilesik_puan += 28
        detaylar.append(f"📈 NLP: Pozitif haber akışı (+28)")
    elif haber_skoru > 0.1:
        bilesik_puan += 15
        detaylar.append(f"📊 NLP: Hafif pozitif hava (+15)")
    elif haber_skoru < -0.3:
        bilesik_puan -= 25
        detaylar.append(f"⚠️ NLP: Negatif haber baskısı (-25)")
    elif haber_skoru < -0.1:
        bilesik_puan -= 10
        detaylar.append(f"📉 NLP: Hafif negatif sinyal (-10)")
    else:
        bilesik_puan += 5
        detaylar.append("⚪ NLP: Nötr haber akışı (+5)")

    # ── 2. Teknik Sinyal Katkısı (Max 35 puan) ────────────────────
    teknik_normalize = teknik_sinyal.upper().replace("Ö", "O").replace("Ü", "U").replace("Ğ", "G")
    if "GUCLU AL" in teknik_normalize:
        bilesik_puan += 35
        detaylar.append("🚀 Teknik: Güçlü AL sinyali (+35)")
    elif "AL" in teknik_normalize:
        bilesik_puan += 22
        detaylar.append("✅ Teknik: AL sinyali (+22)")
    elif "GUCLU SAT" in teknik_normalize:
        bilesik_puan -= 30
        detaylar.append("🛑 Teknik: Güçlü SAT sinyali (-30)")
    elif "SAT" in teknik_normalize:
        bilesik_puan -= 18
        detaylar.append("❌ Teknik: SAT sinyali (-18)")
    else:
        bilesik_puan += 5
        detaylar.append("📊 Teknik: Nötr (+5)")

    # ── 3. RSI Konum Katkısı (Max 15 puan) ────────────────────────
    if rsi < 30:
        bilesik_puan += 15
        detaylar.append(f"💎 RSI {rsi:.0f}: Aşırı satım — dip fırsatı (+15)")
    elif rsi < 40:
        bilesik_puan += 8
        detaylar.append(f"📉 RSI {rsi:.0f}: Satış bölgesine yakın (+8)")
    elif rsi > 70:
        bilesik_puan -= 15
        detaylar.append(f"⚠️ RSI {rsi:.0f}: Aşırı alım — tepe riski (-15)")
    elif rsi > 60:
        bilesik_puan -= 5
        detaylar.append(f"📈 RSI {rsi:.0f}: Alım bölgesinde (-5)")
    else:
        bilesik_puan += 3
        detaylar.append(f"⚖️ RSI {rsi:.0f}: Dengeli (+3)")

    # ── 4. Trend Konum Katkısı (Max 10 puan) ──────────────────────
    if fiyat_ma50_oran > 1.05:
        bilesik_puan += 10
        detaylar.append("📈 Fiyat MA50'nin %5+ üzerinde — güçlü trend (+10)")
    elif fiyat_ma50_oran > 1.0:
        bilesik_puan += 5
        detaylar.append("✅ Fiyat MA50 üzerinde (+5)")
    elif fiyat_ma50_oran > 0.95:
        bilesik_puan += 0
        detaylar.append("⚖️ Fiyat MA50'ye yakın (0)")
    else:
        bilesik_puan -= 8
        detaylar.append("❌ Fiyat MA50 altında (-8)")

    # ── Karar Mekanizması ─────────────────────────────────────────
    bilesik_puan = max(-70, min(100, bilesik_puan))

    if bilesik_puan >= 65:
        sinyal = "GÜÇLÜ AL"
        renk = "#0fdb7a"
        guven = min(100, bilesik_puan)
    elif bilesik_puan >= 40:
        sinyal = "AL"
        renk = "#f5cc6a"
        guven = bilesik_puan
    elif bilesik_puan >= -20:
        sinyal = "NÖTR"
        renk = "#7a8fa8"
        guven = 50 + bilesik_puan // 2
    elif bilesik_puan >= -50:
        sinyal = "SAT"
        renk = "#ff8c42"
        guven = abs(bilesik_puan)
    else:
        sinyal = "GÜÇLÜ SAT"
        renk = "#ff3b5c"
        guven = min(100, abs(bilesik_puan))

    aciklama = f"Haber+Teknik birleşik skor: {bilesik_puan}/100 — {sinyal}"

    return {
        'sinyal': sinyal,
        'guven_puani': guven,
        'bilesik_skor': bilesik_puan,
        'aciklama': aciklama,
        'renk': renk,
        'detaylar': detaylar
    }


def haber_beklenti_html(skor: float, yon: str, renk: str, ikon: str, aciklama: str) -> str:
    """Haber beklenti analizi için HTML badge."""
    guven_genislik = min(100, abs(skor) * 100)
    return f"""
    <div style="display:inline-flex;align-items:center;gap:6px;
                background:rgba({_renk_rgb(renk)},0.08);
                border:1px solid {renk}44;border-radius:6px;
                padding:3px 10px;font-size:9px;
                font-family:'JetBrains Mono',monospace;">
      <span>{ikon}</span>
      <span style="color:{renk};font-weight:700;">{yon}</span>
      <span style="color:var(--txt3);">|</span>
      <span style="color:{renk};opacity:.8;">%{guven_genislik:.0f} güven</span>
    </div>
    <div style="font-size:9px;color:var(--txt3);margin-top:2px;
                font-family:'Sora',sans-serif;font-style:italic;">
      {aciklama}
    </div>
    """


def _renk_rgb(hex_renk: str) -> str:
    """Hex rengi RGB formatına çevirir."""
    h = hex_renk.lstrip('#')
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    return "122,184,168"


@st.cache_data(ttl=600)
def tum_sistemi_haber_tara(hisse_listesi: tuple) -> list:
    """
    Verilen hisse listesini paralel olarak tarar, en güncel haberleri döner.
    YENİ: Her habere duyarlılık skoru eklenir.
    """
    tum_haberler = []

    def tek_hisse_cek(sym):
        try:
            h_data = yf.Ticker(sym).news or []
            sonuc = []
            for n in h_data[:2]:  # Her hisseden en yeni 2 haber
                z_raw = n.get("providerPublishTime", None)
                try:
                    zaman_str = datetime.fromtimestamp(z_raw).strftime("%d.%m %H:%M") if z_raw else ""
                    ts = z_raw or 0
                except Exception:
                    zaman_str = ""
                    ts = 0
                baslik_ori = n.get("content", {}).get("title", "") or n.get("title", "")
                ozet_ori = (n.get("content", {}).get("summary", "")
                            or n.get("content", {}).get("description", "") or "")
                baslik_ceviri = haber_cevir(baslik_ori) if baslik_ori else ""
                ozet_ceviri = haber_cevir(ozet_ori) if ozet_ori else ""

                # YENİ: Her haber için beklenti analizi
                beklenti = haber_beklenti_analizi(baslik_ceviri, ozet_ceviri)

                sonuc.append({
                    "sembol": sym.replace(".IS", ""),
                    "sembol_raw": sym,
                    "baslik": baslik_ceviri,
                    "baslik_ori": baslik_ori,
                    "ozet": ozet_ceviri,
                    "zaman": zaman_str,
                    "ts": ts,
                    "yayinci": n.get("publisher", ""),
                    "url": (n.get("content", {}).get("canonicalUrl", {}).get("url", "")
                            or n.get("link", "") or ""),
                    "duyarlilik": beklenti['skor'],
                    "beklenti_yon": beklenti['yon'],
                    "beklenti_renk": beklenti['renk'],
                    "beklenti_ikon": beklenti['ikon'],
                    "beklenti_aciklama": beklenti['aciklama'],
                    "beklenti_guven": beklenti['guven'],
                })

            if not sym.endswith(".IS"):
                sec_verileri = sec_8k_radar(sym)
                if sec_verileri:
                    import time
                    for sv in sec_verileri:
                        sv["ts"] = int(time.time())
                        sv["sembol_raw"] = sym
                        sv["duyarlilik"] = 0
                        sv["beklenti_yon"] = "NÖTR"
                        sv["beklenti_renk"] = "#7a8fa8"
                        sv["beklenti_ikon"] = "⚪"
                        sv["beklenti_aciklama"] = "SEC resmi bildirimi — duyarlılık analizi yapılmadı"
                        sv["beklenti_guven"] = 50
                    sonuc.extend(sec_verileri)

            return sonuc
        except Exception:
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(tek_hisse_cek, hisse_listesi))
        for r in results:
            tum_haberler.extend(r)

    return sorted(tum_haberler, key=lambda x: x.get("ts", 0), reverse=True)


def haber_paneli(sembol: str):
    """Haberleri çeker, Türkçeye çevirir, site içi okuyucu ile gösterir.
    YENİ: Beklenti analizi badge'leri eklendi."""
    st.markdown(f'<span class="section-label">{sembol} — Son Haberler</span>',
                unsafe_allow_html=True)

    haber_key = f"haber_detay_{sembol}"
    if haber_key not in st.session_state:
        st.session_state[haber_key] = None

    # ── Detay okuyucu görünümü ────────────────────────────────────
    if st.session_state[haber_key] is not None:
        hb = st.session_state[haber_key]
        if st.button("← Haberlere Dön", key=f"hb_geri_{sembol}"):
            st.session_state[haber_key] = None
            st.rerun()

        # Beklenti analizi
        beklenti = haber_beklenti_analizi(hb.get('baslik', ''), hb.get('ozet', ''))

        st.markdown(f"""
        <div style="background:rgba(8,14,28,0.97);border:1px solid var(--border);
                    border-left:3px solid var(--gold);border-radius:10px;padding:24px 26px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;
                         color:var(--blue);background:rgba(77,184,255,0.12);
                         padding:2px 9px;border-radius:3px;letter-spacing:.1em;">
              {sembol.replace('.IS','')}</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--txt3);">
              ⏱ {hb['zaman']}</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:10px;
                         color:var(--txt3);margin-left:auto;">{hb['yayinci']}</span>
          </div>
          <div style="font-family:'Sora',sans-serif;font-size:18px;font-weight:700;
                      color:var(--txt1);line-height:1.45;margin-bottom:16px;">
            {hb['baslik']}
          </div>
          <div style="margin-bottom:14px;">
            {haber_beklenti_html(beklenti['skor'], beklenti['yon'], beklenti['renk'],
                                 beklenti['ikon'], beklenti['aciklama'])}
          </div>
          <div style="font-family:'Sora',sans-serif;font-size:13px;color:var(--txt2);
                      line-height:1.8;padding:16px;background:rgba(15,25,45,0.6);
                      border-radius:6px;border-left:2px solid var(--border);margin-bottom:16px;">
            {hb.get('ozet') or '<span style="color:var(--txt3);font-style:italic;">Özet mevcut değil.</span>'}
          </div>
          {'<a href="' + hb["url"] + '" target="_blank" style="font-family:JetBrains Mono,monospace;font-size:10px;color:var(--gold);text-decoration:none;letter-spacing:.1em;">↗ KAYNAK SİTEDE OKU</a>' if hb.get("url") else ''}
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Kart listesi ──────────────────────────────────────────────
    with st.spinner("Haberler yükleniyor ve çevriliyor..."):
        try:
            haberler = yf.Ticker(sembol).news
            if haberler:
                for idx, haber in enumerate(haberler[:15]):
                    orijinal = (haber.get("content", {}).get("title", "") or haber.get("title", ""))
                    ozet_ori = (haber.get("content", {}).get("summary", "")
                                or haber.get("content", {}).get("description", "") or "")
                    baslik = haber_cevir(orijinal) if orijinal else ""
                    ozet = haber_cevir(ozet_ori) if ozet_ori else ""
                    link = (haber.get("content", {}).get("canonicalUrl", {}).get("url", "")
                            or haber.get("link", "") or "#")
                    yayinci = haber.get("publisher", "")
                    z_raw = haber.get("providerPublishTime", None)
                    try:
                        zs = datetime.fromtimestamp(z_raw).strftime("%d.%m.%Y - %H:%M") if z_raw else ""
                    except Exception:
                        zs = ""

                    # Beklenti analizi
                    beklenti = haber_beklenti_analizi(baslik, ozet)

                    haber_obj = {
                        "baslik": baslik, "ozet": ozet, "url": link,
                        "yayinci": yayinci, "zaman": zs
                    }

                    st.markdown(f"""
                    <div class="news-card" style="background:rgba(13,22,42,0.7);
                          border:1px solid var(--border);
                          border-left:3px solid {beklenti['renk']};
                          border-radius:6px; padding:14px 16px; margin-bottom:0;">
                      <div style="display:flex;align-items:center;margin-bottom:7px;">
                        {haber_beklenti_html(beklenti['skor'], beklenti['yon'],
                                             beklenti['renk'], beklenti['ikon'],
                                             beklenti['aciklama'])}
                        <span style="font-family:'JetBrains Mono',monospace;font-size:9px;
                                     color:var(--txt3);margin-left:auto;">⏱ {zs}</span>
                      </div>
                      <div style="font-family:'Sora',sans-serif;font-size:13px;font-weight:600;
                                  color:var(--txt1);line-height:1.45;margin-bottom:6px;">
                        {baslik[:120]}{'...' if len(baslik)>120 else ''}</div>
                      <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--txt3);">
                        {yayinci}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    btn_key = f"hbr_{sembol}_{idx}"
                    st.markdown(f"""<style>
                    button[data-key="{btn_key}"] {{
                      background:transparent!important;border:none!important;
                      box-shadow:none!important;color:transparent!important;
                      font-size:0!important;height:82px!important;padding:0!important;
                      margin-top:-84px!important;position:relative!important;
                      z-index:9!important;cursor:pointer!important;
                    }}
                    button[data-key="{btn_key}"]:hover {{
                      background:rgba(77,184,255,0.06)!important;
                      box-shadow:none!important;transform:none!important;
                    }}
                    </style>""", unsafe_allow_html=True)
                    if st.button("\u200c", key=btn_key, use_container_width=True):
                        st.session_state[haber_key] = haber_obj
                        st.rerun()

                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            else:
                st.info("Haber bulunamadı.")
        except Exception as e:
            st.error(f"Haberler yüklenemedi: {e}")


# ══════════════════════════════════════════════════════════════════════
#  YENİ: Dashboard inline haber paneli — tıklayınca özet + beklenti
#  Ayrı sayfaya ATMADAN, expand/collapse ile gösterir.
# ══════════════════════════════════════════════════════════════════════
def _haber_oncelik_skoru(beklenti_skor: float) -> int:
    """Habere öncelik skoru verir: 0=Güçlü AL, 1=Önemli Haber, 2=Özensiz Haber"""
    if beklenti_skor >= 0.5:
        return 0  # Güçlü AL
    elif abs(beklenti_skor) >= 0.3:
        return 1  # Önemli Haber
    else:
        return 2  # Özensiz Haber


def _haber_oncelik_etiketi(oncelik: int) -> str:
    """Öncelik seviyesinin Türkçe etiketini döndürür."""
    return {0: "🔥 GÜÇLÜ AL", 1: "📰 ÖNEMLİ HABER", 2: "📋 DİĞER HABER"}.get(oncelik, "")


def dashboard_haber_paneli(takip_listesi: list):
    """Dashboard sağ kolonunda tüm takip edilen hisseler için interaktif haber akışı.
    ÖNCELİK: Güçlü AL > Önemli Haber > Özensiz Haber (her grupta en yeni üstte)."""
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;
                letter-spacing:.22em;text-transform:uppercase;color:var(--txt3);
                border-bottom:1px solid var(--goldd);padding-bottom:3px;margin-bottom:12px;">
      📡 Piyasa Haberleri
    </div>
    """, unsafe_allow_html=True)

    # Session state: hangi haberin detayı açık?
    if "dashboard_acik_haber" not in st.session_state:
        st.session_state.dashboard_acik_haber = None
    if "dashboard_acik_haber_beklenti" not in st.session_state:
        st.session_state.dashboard_acik_haber_beklenti = {}

    try:
        tum_haberler = []
        for sym in takip_listesi[:30]:
            try:
                haberler = yf.Ticker(sym).news
                if haberler:
                    for h in haberler[:2]:
                        orijinal = (h.get("content", {}).get("title", "") or h.get("title", ""))
                        ozet_ori = (h.get("content", {}).get("summary", "")
                                    or h.get("content", {}).get("description", "") or "")
                        baslik = haber_cevir(orijinal) if orijinal else ""
                        ozet = haber_cevir(ozet_ori) if ozet_ori else ""
                        yayinci = h.get("publisher", "")
                        link = (h.get("content", {}).get("canonicalUrl", {}).get("url", "")
                                or h.get("link", "") or "")
                        z_raw = h.get("providerPublishTime", None)
                        try:
                            zs = datetime.fromtimestamp(z_raw).strftime("%d.%m %H:%M") if z_raw else ""
                            ts = z_raw or 0
                        except Exception:
                            zs = ""
                            ts = 0

                        # Beklenti analizi
                        beklenti = haber_beklenti_analizi(baslik, ozet)

                        haber_id = f"{sym}_{ts}_{hash(baslik) % 100000}"
                        oncelik = _haber_oncelik_skoru(beklenti['skor'])

                        tum_haberler.append({
                            "id": haber_id,
                            "sembol": sym,
                            "baslik": baslik,
                            "ozet": ozet,
                            "yayinci": yayinci,
                            "zaman": zs,
                            "ts": ts,
                            "url": link,
                            "beklenti_skor": beklenti['skor'],
                            "beklenti_yon": beklenti['yon'],
                            "beklenti_renk": beklenti['renk'],
                            "beklenti_ikon": beklenti['ikon'],
                            "beklenti_aciklama": beklenti['aciklama'],
                            "beklenti_guven": beklenti['guven'],
                            "oncelik": oncelik,
                            "oncelik_etiket": _haber_oncelik_etiketi(oncelik),
                        })
            except Exception:
                pass

        # ÖNCE önceliğe göre (Güçlü AL > Önemli > Özensiz), SONRA zamana göre (en yeni üstte) sırala
        tum_haberler.sort(key=lambda x: (x["oncelik"], -x["ts"]))

        for h in tum_haberler[:20]:
            renk = "#f0c040" if ".IS" in h["sembol"] else "#4db8ff"
            acik_mi = st.session_state.dashboard_acik_haber == h["id"]

            # Ana kart
            st.markdown(f"""
            <div style="padding:10px 12px;border-bottom:1px solid rgba(38,59,94,0.4);
                        transition:background .15s;border-radius:4px;
                        {'background:rgba(77,184,255,0.06);' if acik_mi else ''}"
                 id="haber-{h['id']}">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;
                             color:{renk};background:rgba(77,184,255,0.08);padding:1px 7px;
                             border-radius:3px;">{h['sembol'].replace('.IS','')}</span>
                <span style="display:flex;align-items:center;gap:6px;">
                  <span style="font-size:10px;">{h['beklenti_ikon']}</span>
                  <span style="font-family:'JetBrains Mono',monospace;font-size:7px;
                               color:{h['beklenti_renk']};font-weight:600;">
                    {h['beklenti_yon']}</span>
                  <span style="font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--txt3);">
                    ⏱ {h['zaman']}</span>
                </span>
              </div>
              <div style="font-family:'Sora',sans-serif;font-size:11px;color:var(--txt2);
                          line-height:1.5;margin-bottom:3px;">
                {h['baslik'][:90]}{'...' if len(h['baslik'])>90 else ''}
              </div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--txt3);">
                {h['yayinci']}
              </div>
            </div>
            <span class="haber-btn-marker"></span>
            """, unsafe_allow_html=True)

            # Tıklama butonu (görünmez, kartın üzerine biner)
            btn_key = f"dash_haber_{h['id']}"
            if st.button("\u200c", key=btn_key, use_container_width=True):
                if st.session_state.dashboard_acik_haber == h["id"]:
                    st.session_state.dashboard_acik_haber = None
                else:
                    st.session_state.dashboard_acik_haber = h["id"]
                    st.session_state.dashboard_acik_haber_beklenti = {
                        'skor': h['beklenti_skor'],
                        'yon': h['beklenti_yon'],
                        'renk': h['beklenti_renk'],
                        'ikon': h['beklenti_ikon'],
                        'aciklama': h['beklenti_aciklama'],
                        'guven': h['beklenti_guven'],
                    }
                st.rerun()

            # ── AÇIK HABER İNLINE DETAY ────────────────────────────
            if acik_mi:
                bk = st.session_state.dashboard_acik_haber_beklenti
                guven_genislik = min(100, abs(bk['skor']) * 100)
                st.markdown(f"""
                <div class="fade-in" style="background:linear-gradient(160deg,rgba(10,18,36,0.95),rgba(6,11,18,0.9));
                            border:1px solid rgba(77,184,255,0.15);
                            border-left:3px solid {bk['renk']};
                            border-radius:8px;padding:14px 16px;margin:4px 0 8px 8px;
                            backdrop-filter:blur(8px);">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap;">
                    <span style="font-size:12px;">{bk['ikon']}</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:10px;
                                 font-weight:700;color:{bk['renk']};">
                      {bk['yon']} BEKLENTİ
                    </span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:9px;
                                 color:var(--txt3);background:rgba(255,255,255,0.03);
                                 padding:2px 8px;border-radius:3px;">
                      %{guven_genislik:.0f} güven</span>
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:11px;color:var(--txt2);
                              line-height:1.5;margin-bottom:8px;font-style:italic;">
                    {bk['aciklama']}
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:12px;color:var(--txt1);
                              line-height:1.7;padding:10px;background:rgba(15,25,45,0.5);
                              border-radius:6px;margin-bottom:6px;">
                    {h['ozet'][:300] if h.get('ozet') else '<span style="color:var(--txt3);font-style:italic;">Bu haber için özet bulunmuyor.</span>'}
                  </div>
                  {'<a href="' + h["url"] + '" target="_blank" style="font-family:JetBrains Mono,monospace;font-size:9px;color:var(--gold);text-decoration:none;letter-spacing:.1em;">↗ KAYNAĞA GİT</a>' if h.get("url") else ''}
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Haberler yüklenemedi: {e}")


# ══════════════════════════════════════════════════════════════════════
#  YENİ: Dashboard sağ kolon — birleşik haber + sinyal paneli
# ══════════════════════════════════════════════════════════════════════
def dashboard_haber_sinyal_paneli(takip_listesi: list, teknik_veriler: dict = None):
    """
    Dashboard için birleşik haber + teknik sinyal paneli.
    Haber duyarlılığı ile teknik sinyalleri birleştirir, Güçlü AL fırsatlarını vurgular.

    teknik_veriler: {sembol: {'teknik_sinyal': str, 'teknik_skor': int, 'rsi': float, 'ma50_oran': float}}
    """
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;
                letter-spacing:.22em;text-transform:uppercase;color:var(--txt3);
                border-bottom:1px solid var(--goldd);padding-bottom:3px;margin-bottom:12px;">
      🔥 HABER + SİNYAL RADARI
    </div>
    """, unsafe_allow_html=True)

    try:
        tum_haberler = []
        for sym in takip_listesi[:25]:
            try:
                haberler = yf.Ticker(sym).news
                if haberler:
                    for h in haberler[:3]:
                        orijinal = (h.get("content", {}).get("title", "") or h.get("title", ""))
                        baslik = haber_cevir(orijinal) if orijinal else ""
                        z_raw = h.get("providerPublishTime", None)
                        try:
                            ts = z_raw or 0
                        except Exception:
                            ts = 0
                        # Beklenti analizi
                        beklenti = haber_beklenti_analizi(baslik)
                        oncelik = _haber_oncelik_skoru(beklenti['skor'])
                        tum_haberler.append({
                            "sembol": sym,
                            "baslik": baslik,
                            "ts": ts,
                            "beklenti_skor": beklenti['skor'],
                            "beklenti_yon": beklenti['yon'],
                            "oncelik": oncelik,
                        })
            except Exception:
                pass

        if not tum_haberler:
            st.info("Şu an için haber akışı bulunamadı.")
            return

        # ÖNCE önceliğe göre (Güçlü AL > Önemli > Özensiz), SONRA zamana göre (en yeni üstte) sırala
        tum_haberler.sort(key=lambda x: (x["oncelik"], -x["ts"]))

        # Sembol bazında grupla ve birleşik sinyal hesapla
        sembol_haber_skor = {}
        for h in tum_haberler:
            sym = h["sembol"]
            if sym not in sembol_haber_skor:
                sembol_haber_skor[sym] = []
            sembol_haber_skor[sym].append(h["beklenti_skor"])

        # Ortalama haber skoru hesapla
        sembol_ortalama_skor = {}
        for sym, skorlar in sembol_haber_skor.items():
            sembol_ortalama_skor[sym] = round(np.mean(skorlar), 2)

        # Birleşik sinyal hesapla ve göster
        guclu_al_listesi = []
        for sym, haber_ort in sembol_ortalama_skor.items():
            teknik = teknik_veriler.get(sym, {}) if teknik_veriler else {}
            t_sinyal = teknik.get('teknik_sinyal', 'NOTR')
            t_skor = teknik.get('teknik_skor', 0)
            t_rsi = teknik.get('rsi', 50)
            t_ma50_oran = teknik.get('ma50_oran', 1.0)

            bilesik = haber_guclu_al_sinyali(haber_ort, t_sinyal, t_skor, t_rsi, t_ma50_oran)

            if bilesik['sinyal'] in ['GÜÇLÜ AL', 'AL']:
                guclu_al_listesi.append({
                    'sembol': sym,
                    'bilesik': bilesik,
                    'haber_skor': haber_ort
                })

        # Güçlü AL sinyallerini vurgula
        if guclu_al_listesi:
            guclu_al_listesi.sort(key=lambda x: x['bilesik']['bilesik_skor'], reverse=True)

            st.markdown(f"""
            <div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.15em;
                        color:#0fdb7a;margin-bottom:8px;">
              🚀 {len(guclu_al_listesi)} HABER+TEMEL TABANLI GÜÇLÜ FIRSAT
            </div>
            """, unsafe_allow_html=True)

            for ga in guclu_al_listesi[:5]:
                bk = ga['bilesik']
                renk = bk['renk']
                bg_renk = "rgba(6,77,42,0.3)" if bk['sinyal'] == 'GÜÇLÜ AL' else "rgba(42,58,0,0.3)"
                st.markdown(f"""
                <div style="background:{bg_renk};border:1px solid {renk}44;
                            border-left:3px solid {renk};border-radius:8px;
                            padding:12px 14px;margin-bottom:8px;">
                  <div style="display:flex;align-items:center;justify-content:space-between;
                              margin-bottom:6px;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;
                                 font-weight:700;color:var(--txt1);">
                      {ga['sembol'].replace('.IS','')}
                    </span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:9px;
                                 font-weight:700;color:{renk};background:{renk}22;
                                 padding:2px 10px;border-radius:4px;">
                      {bk['sinyal']}
                    </span>
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:10px;color:var(--txt2);
                              line-height:1.5;margin-bottom:6px;">
                    📊 Bileşik Skor: <b style="color:{renk};">{bk['bilesik_skor']}/100</b>
                    &nbsp;|&nbsp; 📰 Haber Skoru: <b style="color:{renk};">
                    {ga['haber_skor']:+.2f}</b>
                  </div>
                  <div style="font-family:'Sora',sans-serif;font-size:9px;color:var(--txt3);
                              font-style:italic;">
                    {bk['aciklama']}
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Henüz haber+teknik birleşik güçlü al sinyali bulunamadı.")

        # Son haberleri öncelik sıralı göster (Güçlü AL > Önemli > Özensiz, her grupta en yeni üstte)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="font-family:'JetBrains Mono',monospace;font-size:7px;color:var(--txt3);
                    letter-spacing:.12em;margin-bottom:6px;">
          SON HABER AKIŞI
        </div>
        """, unsafe_allow_html=True)
        for h in tum_haberler[:8]:
            yon_renk = "#0fdb7a" if h['beklenti_skor'] > 0 else ("#ff3b5c" if h['beklenti_skor'] < 0 else "#7a8fa8")
            yon_ikon = "🟢" if h['beklenti_skor'] > 0 else ("🔴" if h['beklenti_skor'] < 0 else "⚪")
            oncelik_etiket = _haber_oncelik_etiketi(h.get('oncelik', 2))
            st.markdown(f"""
            <div style="padding:6px 8px;border-bottom:1px solid rgba(38,59,94,0.2);
                        font-size:9px;display:flex;align-items:center;gap:6px;">
              <span style="color:{yon_renk};">{yon_ikon}</span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:600;
                           color:var(--txt1);min-width:45px;">{h['sembol'].replace('.IS','')[:8]}</span>
              <span style="font-family:'Sora',sans-serif;font-size:9px;color:var(--txt2);
                           flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                {h['baslik'][:55]}{'...' if len(h['baslik'])>55 else ''}
              </span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:7px;
                           color:{'#0fdb7a' if h.get('oncelik')==0 else ('#f5cc6a' if h.get('oncelik')==1 else 'var(--txt3)')};">
                {oncelik_etiket}
              </span>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Haber radarı yüklenemedi: {e}")
