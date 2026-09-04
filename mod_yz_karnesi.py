# ══════════════════════════════════════════════════════════════════════
#  mod_yz_karnesi.py — YZ İşlem Karnesi · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import sqlite3
import os
import numpy as np
from mod_yapay_zeka_karar import strateji_analiz_et, strateji_guncelle
from mod_animasyon import bolum_baslik
from mod_hafiza import bekleyenleri_kontrol_et

# ── Sinyal kalite entegrasyonu (Tavsiye #4) ─────────────────────────
try:
    from mod_sinyal_kalite import kalite_raporu_olustur, devre_disi_indikatorleri_uygula
    SINYAL_KALITE_AKTIF = True
except ImportError:
    SINYAL_KALITE_AKTIF = False
from mod_egitim_kontrol import (
    eski_sistemi_arka_planda_baslat, agir_egitimi_arka_planda_baslat,
    egitim_durumu_oku, egitim_durdur
)

DB_ISMI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")

# ══════════════════════════════════════════════════════════════════════
#  COİN TESPİT ALGORİTMASI
# ══════════════════════════════════════════════════════════════════════

def is_crypto(kod: str) -> bool:
    if not kod or not isinstance(kod, str):
        return False
    ust = kod.upper().strip()
    return ('USDT' in ust or 'USD' in ust or 'BTC' in ust) and '.IS' not in ust
# ══════════════════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════════

def _hesapla(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            'toplam': 0, 'basarili': 0, 'basarisiz': 0, 'bekleyen': 0,
            'zaman_asimi': 0, 'kapanan': 0, 'win_rate': 0, 'stop_rate': 0,
            'bekleyen_pct': 0
        }
    basarili = int(len(df[df['durum'].str.contains('BAŞARILI', na=False)]))
    basarisiz = int(len(df[df['durum'].str.contains('BAŞARISIZ', na=False)]))
    bekleyen = int(len(df[df['durum'] == 'BEKLIYOR'])) if 'BEKLIYOR' in df['durum'].values else 0
    zaman_asimi = int(len(df[df['durum'].str.contains('ZAMAN AŞIMI', na=False)]))
    toplam = int(len(df))
    kapanan = basarili + basarisiz + zaman_asimi
    return {
        'toplam': toplam, 'basarili': basarili, 'basarisiz': basarisiz,
        'bekleyen': bekleyen, 'zaman_asimi': zaman_asimi, 'kapanan': kapanan,
        'win_rate': round((basarili / kapanan * 100), 1) if kapanan > 0 else 0,
        'stop_rate': round((basarisiz / kapanan * 100), 1) if kapanan > 0 else 0,
        'bekleyen_pct': round((bekleyen / toplam * 100), 1) if toplam > 0 else 0
    }


def _metric_html(deger, etiket, renk="#d1d4dc"):
    return f"""
    <div style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                border:1px solid rgba(30,51,85,0.3);border-radius:10px;
                padding:14px 16px;text-align:center;backdrop-filter:blur(8px);">
        <div style="font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:800;
                    color:{renk};letter-spacing:-.02em;">{deger}</div>
        <div style="font-family:'Sora',sans-serif;font-size:9px;color:#8a9bb5;
                    letter-spacing:.12em;text-transform:uppercase;margin-top:4px;">{etiket}</div>
    </div>"""


def _metrik_satiri(stats: dict):
    c1, c2, c3, c4, c5 = st.columns(5)
    wc = "#0fdb7a" if stats['win_rate'] >= 50 else "#ff3b5c"
    with c1: st.markdown(_metric_html(str(stats['toplam']), "Toplam İşlem"), unsafe_allow_html=True)
    with c2: st.markdown(_metric_html(str(stats['bekleyen']), "Bekleyen", "#f5cc6a"), unsafe_allow_html=True)
    with c3: st.markdown(_metric_html(f"%{stats['win_rate']:.1f}", "Başarı Oranı", wc), unsafe_allow_html=True)
    with c4: st.markdown(_metric_html(str(stats['basarili']), "✅ Başarılı", "#0fdb7a"), unsafe_allow_html=True)
    with c5: st.markdown(_metric_html(str(stats['basarisiz']), "❌ Stop", "#ff3b5c"), unsafe_allow_html=True)


def _progress_bar(stats: dict):
    k = stats['kapanan']
    if k == 0:
        return
    wp = stats['win_rate']
    sp = stats['stop_rate']
    zp = round((stats['zaman_asimi'] / k * 100), 1) if k > 0 else 0
    st.markdown(f"""
    <div class="fade-in" style="background:rgba(10,18,36,0.5);border-radius:10px;padding:14px 18px;
                border:1px solid rgba(255,255,255,0.04);margin:8px 0 10px 0;backdrop-filter:blur(8px);">
        <div style="font-size:9px;color:#8a9bb5;letter-spacing:.1em;margin-bottom:10px;
                    font-family:'JetBrains Mono',monospace;">
          KAPANAN İŞLEM DAĞILIMI</div>
        <div style="display:flex;height:26px;border-radius:13px;overflow:hidden;box-shadow:inset 0 1px 3px rgba(0,0,0,0.5);">
            <div style="width:{wp}%;background:linear-gradient(90deg,#0b793d,#0fdb7a);
                        display:flex;align-items:center;justify-content:center;
                        font-size:9px;font-weight:700;color:#000;font-family:'JetBrains Mono',monospace;">
              %{wp:.0f}</div>
            <div style="width:{sp}%;background:linear-gradient(90deg,#9b1f35,#ff4f6d);
                        display:flex;align-items:center;justify-content:center;
                        font-size:9px;font-weight:700;color:#fff;font-family:'JetBrains Mono',monospace;">
              %{sp:.0f}</div>
            <div style="width:{zp}%;background:linear-gradient(90deg,#b85c1a,#ff8c42);
                        display:flex;align-items:center;justify-content:center;
                        font-size:9px;font-weight:700;color:#fff;font-family:'JetBrains Mono',monospace;">
              %{zp:.0f}</div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:8px;color:#5a6d85;
                    margin-top:6px;font-family:'JetBrains Mono',monospace;">
            <span>🟢 Başarılı</span><span>🔴 Stop</span><span>🟠 Zaman Aşımı</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _durum_renklendir(val):
    if not isinstance(val, str):
        return ''
    if 'BAŞARILI' in val:
        return 'color:#0fdb7a;font-weight:700;background:rgba(15,219,122,0.08);border-radius:4px;padding:2px 8px;'
    if 'BAŞARISIZ' in val:
        return 'color:#ff3b5c;font-weight:700;background:rgba(255,59,92,0.08);border-radius:4px;padding:2px 8px;'
    if 'BEKLİYOR' in val:
        return 'color:#f5cc6a;font-weight:700;background:rgba(245,204,106,0.06);border-radius:4px;padding:2px 8px;'
    if 'ZAMAN' in val:
        return 'color:#ff8c42;font-weight:700;background:rgba(255,140,66,0.06);border-radius:4px;padding:2px 8px;'
    return ''


def _tablo_goster(df: pd.DataFrame, max_yukseklik: int = 350):
    if df.empty:
        st.caption("Henüz kayıt yok.")
        return

    g = df.copy()
    beklenen = ['tarih', 'hisse', 'sinyal_tipi', 'giris_fiyati', 'hedef_fiyat', 'stop_fiyat', 'durum', 'kapanis_fiyati']
    for c in beklenen:
        if c not in g.columns:
            g[c] = None
    g = g[beklenen]
    g.columns = ['Sinyal Zamanı', 'Sembol', 'Sinyal', 'Giriş $', 'Hedef $', 'Stop $', 'Durum', 'Kapanış $']
    for c in ['Giriş $', 'Hedef $', 'Stop $', 'Kapanış $']:
        g[c] = pd.to_numeric(g[c], errors='coerce')
        g[c] = g[c].apply(lambda x: f"{x:.2f}" if pd.notna(x) and x != 0 else "-")

    st.dataframe(
        g.style.map(_durum_renklendir, subset=['Durum']),
        use_container_width=True, hide_index=True,
        height=min(max_yukseklik, 35 * len(g) + 38)
    )


def _durum_gruplu_tablo(df: pd.DataFrame, grup_adi: str, emoji: str, badge_class: str, renk: str):
    if df.empty:
        return
    badge_colors = {
        "badge-green": "rgba(15,219,122,0.12)", "badge-red": "rgba(255,79,109,0.12)",
        "badge-yellow": "rgba(245,204,106,0.1)", "badge-blue": "rgba(255,140,66,0.1)"
    }
    badge_border = {
        "badge-green": "rgba(15,219,122,0.2)", "badge-red": "rgba(255,79,109,0.2)",
        "badge-yellow": "rgba(245,204,106,0.2)", "badge-blue": "rgba(255,140,66,0.2)"
    }
    st.markdown(f"""
    <div class="fade-in" style="display:flex;align-items:center;gap:10px;margin:14px 0 8px 0;">
        <span style="font-size:20px;">{emoji}</span>
        <span style="font-family:'Sora',sans-serif;font-size:13px;font-weight:600;color:{renk};">{grup_adi}</span>
        <span style="background:{badge_colors.get(badge_class,'rgba(10,18,36,0.5)')};
                     padding:2px 10px;border-radius:12px;font-family:'JetBrains Mono',monospace;
                     font-size:9px;font-weight:600;color:{renk};
                     border:1px solid {badge_border.get(badge_class,'rgba(30,51,85,0.3)')};">
          {len(df)} adet</span>
    </div>
    """, unsafe_allow_html=True)
    _tablo_goster(df.head(30), max_yukseklik=280)


# ══════════════════════════════════════════════════════════════════════
#  ANA RENDER
# ══════════════════════════════════════════════════════════════════════

def render_yz_karnesi():
    bolum_baslik(
        "📊 Yapay Zeka (ML) İşlem Karnesi",
        "Hisse ve Coin bazında başarı/stop analizi · Otonom strateji · ML eğitim kontrolü",
        bg_url="https://images.unsplash.com/photo-1535320903710-d993d3d77d29?q=80&w=1200&auto=format&fit=crop"
    )

    # ═══ BEKLEYENLERİ KONTROL ═══
    if "yz_karne_kontrol_edildi" not in st.session_state:
        st.session_state.yz_karne_kontrol_edildi = False

    cb1, cb2, cb3 = st.columns([1, 1, 1])
    with cb1:
        if st.button("🔄 BEKLEYENLERİ KONTROL ET", use_container_width=True):
            with st.spinner("Pozisyonlar kontrol ediliyor..."):
                k = bekleyenleri_kontrol_et() or 0
            st.session_state.yz_karne_kontrol_edildi = True
            if k > 0:
                st.success(f"✅ {k} pozisyon sonuçlandırıldı!")
            else:
                st.info("ℹ️ Henüz sonuçlanan pozisyon yok.")
            st.rerun()

    durum = egitim_durumu_oku()
    egitim_calisiyor = durum['calisiyor']
    
    # ── AKTİF EĞİTİM DURUM ÇUBUĞU ──
    if egitim_calisiyor:
        tip_adi = "🕙 STANDART (22:00)" if durum.get('tip') == 'eski' else "🔬 AĞIR EĞİTİM (Sürekli)"
        pid = durum.get('pid', '?')
        st.markdown(f"""
        <div class="fade-in" style="background:linear-gradient(90deg,rgba(15,219,122,0.08),rgba(15,219,122,0.02));
                    border:1px solid rgba(15,219,122,0.25);border-radius:8px;padding:10px 16px;
                    margin:8px 0 12px 0;display:flex;align-items:center;gap:10px;">
            <span style="font-size:12px;">🟢</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:#0fdb7a;">
                EĞİTİM AKTİF</span>
            <span style="color:#5a6d85;font-size:10px;">|</span>
            <span style="font-family:'Sora',sans-serif;font-size:12px;color:#c4cdd9;">{tip_adi}</span>
            <span style="color:#5a6d85;font-size:10px;">|</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:9px;color:#8a9bb5;">PID: {pid}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="fade-in" style="background:rgba(10,18,36,0.4);border:1px solid rgba(30,51,85,0.2);
                    border-radius:8px;padding:10px 16px;margin:8px 0 12px 0;display:flex;align-items:center;gap:10px;">
            <span style="font-size:12px;">⏸️</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:#8a9bb5;">
                EĞİTİM DURDU</span>
            <span style="color:#5a6d85;font-size:10px;">|</span>
            <span style="font-family:'Sora',sans-serif;font-size:11px;color:#5a6d85;">
                Başlatmak için aşağıdaki butonları kullanın</span>
        </div>
        """, unsafe_allow_html=True)

    with cb2:
        eski_aktif = egitim_calisiyor and durum['tip'] == 'eski'
        if st.button(
            "🕙 STANDART", use_container_width=True,
            type="primary" if eski_aktif else "secondary",
            help="Her gün saat 22:00'de hızlı eğitim + 2 günde bir derin Optuna."
                 + (" ✅ ÇALIŞIYOR" if eski_aktif else "")
        ):
            with st.spinner("Başlatılıyor..."):
                ok, msg = eski_sistemi_arka_planda_baslat()
            if ok:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()

    with cb3:
        akilli_aktif = egitim_calisiyor and durum['tip'] == 'akilli'
        if st.button(
            "🔬 AĞIR EĞİTİM", use_container_width=True,
            type="primary" if akilli_aktif else "secondary",
            help="Terminal kapanana kadar: Güçlü AL → YZ Karnesi → Tüm hisse/coin. Binance 5dk."
                 + (" ✅ ÇALIŞIYOR" if akilli_aktif else "")
        ):
            with st.spinner("Başlatılıyor..."):
                ok, msg = agir_egitimi_arka_planda_baslat()
            if ok:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()

    # ═══ VERİ ═══ 🔥 PERF: SQLite sorgusunu 2dk cache'le — sekme geçişlerinde tekrar okunmaz
    @st.cache_data(ttl=120, show_spinner=False)
    def _sinyal_verisi_oku():
        try:
            conn = sqlite3.connect(DB_ISMI)
            df = pd.read_sql_query("SELECT * FROM ai_sinyaller ORDER BY id DESC", conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"🚨 Veritabanı Hatası: {e}")
            return pd.DataFrame()
    
    df = _sinyal_verisi_oku()

    if df.empty:
        st.markdown("""
        <div class="fade-in" style="text-align:center;padding:40px 20px;
                    background:linear-gradient(160deg,rgba(10,18,36,0.7),rgba(6,12,26,0.5));
                    border:1px solid rgba(30,51,85,0.25);border-radius:14px;margin:20px 0;">
            <div style="font-size:48px;margin-bottom:16px;">🤖</div>
            <div style="font-family:'Sora',sans-serif;font-size:18px;font-weight:700;color:#c4cdd9;
                        margin-bottom:8px;">Henüz Kayıtlı İşlem Yok</div>
            <div style="font-family:'Sora',sans-serif;font-size:12px;color:#8a9bb5;line-height:1.6;
                        max-width:480px;margin:0 auto;">
                YZ Karnesi, üretilen sinyallerin geçmiş performansını gösterir.<br>
                İlk taramayı başlattığınızda GÜÇLÜ AL sinyalleri buraya kaydedilecek<br>
                ve başarı/stop oranlarınız otomatik hesaplanacaktır.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_b:
            if st.button("🚀 HEMEN TARAMA BAŞLAT", use_container_width=True, type="primary"):
                st.switch_page("main.py")  # fallback: bilgi ver
                st.info("💡 Terminalde şu komutu çalıştırın: python main.py --auto --borsa BIST")
        return

    # ═══ AYRIŞTIR ═══
    df['is_crypto'] = df['hisse'].apply(is_crypto)
    df_hisse = df[~df['is_crypto']].copy()
    df_coin = df[df['is_crypto']].copy()

    genel = _hesapla(df)
    h_st = _hesapla(df_hisse)
    c_st = _hesapla(df_coin)

    # ══════════════════════════════════════════════════════════════════
    #  ███ GENEL ÖZET ███
    # ══════════════════════════════════════════════════════════════════

    st.markdown("""
    <div class="fade-in" style="display:flex;align-items:center;gap:12px;margin:22px 0 14px 0;
                padding-bottom:10px;border-bottom:2px solid rgba(255,255,255,0.04);">
        <span style="font-size:24px;">🏆</span>
        <span style="font-family:'Sora','Outfit',sans-serif;font-size:17px;font-weight:700;color:#c4cdd9;">
          GENEL PERFORMANS ÖZETİ</span>
        <span style="background:rgba(15,219,122,0.1);padding:3px 12px;border-radius:12px;
                     font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;color:#0fdb7a;
                     border:1px solid rgba(15,219,122,0.2);">
          HİSSE + COİN</span>
    </div>
    """, unsafe_allow_html=True)

    # 3'lü karşılaştırma kartı
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"""
        <div class="fade-in" style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                    border:1px solid rgba(30,51,85,0.3);border-radius:10px;padding:14px 16px;
                    backdrop-filter:blur(8px);">
            <div style="font-size:9px;color:#4db8ff;letter-spacing:.1em;font-family:'JetBrains Mono',monospace;
                        margin-bottom:10px;">📈 HİSSE SENETLERİ</div>
            <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:6px;">
                <div>
                  <div style="font-size:20px;font-weight:800;color:#c4cdd9;">{h_st['toplam']}</div>
                  <div style="font-size:7px;color:#5a6d85;">İşlem</div>
                </div>
                <div>
                  <div style="font-size:17px;font-weight:700;color:#0fdb7a;">%{h_st['win_rate']:.1f}</div>
                  <div style="font-size:7px;color:#5a6d85;">Başarı</div>
                </div>
                <div>
                  <div style="font-size:17px;font-weight:700;color:#ff3b5c;">%{h_st['stop_rate']:.1f}</div>
                  <div style="font-size:7px;color:#5a6d85;">Stop</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""
        <div class="fade-in" style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                    border:1px solid rgba(30,51,85,0.3);border-radius:10px;padding:14px 16px;
                    backdrop-filter:blur(8px);">
            <div style="font-size:9px;color:#f0c040;letter-spacing:.1em;font-family:'JetBrains Mono',monospace;
                        margin-bottom:10px;">🪙 KRİPTO COİNLER</div>
            <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:6px;">
                <div>
                  <div style="font-size:20px;font-weight:800;color:#c4cdd9;">{c_st['toplam']}</div>
                  <div style="font-size:7px;color:#5a6d85;">İşlem</div>
                </div>
                <div>
                  <div style="font-size:17px;font-weight:700;color:#0fdb7a;">%{c_st['win_rate']:.1f}</div>
                  <div style="font-size:7px;color:#5a6d85;">Başarı</div>
                </div>
                <div>
                  <div style="font-size:17px;font-weight:700;color:#ff3b5c;">%{c_st['stop_rate']:.1f}</div>
                  <div style="font-size:7px;color:#5a6d85;">Stop</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with sc3:
        better = "📈 HİSSELER" if h_st['win_rate'] >= c_st['win_rate'] else "🪙 COİNLER"
        bc = "#4db8ff" if better.startswith("📈") else "#f0c040"
        diff = abs(h_st['win_rate'] - c_st['win_rate']) if (h_st['kapanan'] > 0 or c_st['kapanan'] > 0) else 0
        st.markdown(f"""
        <div class="fade-in" style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                    border:1px solid rgba(30,51,85,0.3);border-radius:10px;padding:14px 16px;
                    backdrop-filter:blur(8px);">
            <div style="font-size:9px;color:#0fdb7a;letter-spacing:.1em;font-family:'JetBrains Mono',monospace;
                        margin-bottom:10px;">🔝 EN İYİ PERFORMANS</div>
            <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:6px;">
                <div>
                  <div style="font-size:16px;font-weight:700;color:{bc};">{better}</div>
                  <div style="font-size:7px;color:#5a6d85;">Lider</div>
                </div>
                <div>
                  <div style="font-size:17px;font-weight:700;color:#f0c040;">%{diff:.1f}</div>
                  <div style="font-size:7px;color:#5a6d85;">Fark</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    _metrik_satiri(genel)
    _progress_bar(genel)

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════
    #  ███ TAB'LI BÖLÜM: HİSSELER & COİNLER ███
    # ══════════════════════════════════════════════════════════════════

    tab_hisse, tab_coin = st.tabs([
        f"📈 HİSSE SENETLERİ ({len(df_hisse)})",
        f"🪙 KRİPTO COİNLER ({len(df_coin)})"
    ])

    with tab_hisse:
        _metrik_satiri(h_st)
        _progress_bar(h_st)

        if df_hisse.empty:
            st.info("📈 Henüz hisse senedi işlemi kaydedilmemiş.")
        else:
            hisse_basarili = df_hisse[df_hisse['durum'].str.contains('BAŞARILI', na=False)].copy()
            hisse_basarisiz = df_hisse[df_hisse['durum'].str.contains('BAŞARISIZ', na=False)].copy()
            hisse_bekleyen = df_hisse[df_hisse['durum'] == 'BEKLIYOR'].copy()
            hisse_zaman = df_hisse[df_hisse['durum'].str.contains('ZAMAN AŞIMI', na=False)].copy()

            st.markdown("---")
            _durum_gruplu_tablo(hisse_basarili, "BAŞARILI HİSSELER", "✅", "badge-green", "#0fdb7a")
            _durum_gruplu_tablo(hisse_basarisiz, "STOP OLAN HİSSELER", "❌", "badge-red", "#ff3b5c")
            _durum_gruplu_tablo(hisse_bekleyen, "BEKLEYEN HİSSELER", "⏳", "badge-yellow", "#f5cc6a")
            _durum_gruplu_tablo(hisse_zaman, "ZAMAN AŞIMI HİSSELER", "⏰", "badge-blue", "#ff8c42")

    with tab_coin:
        _metrik_satiri(c_st)
        _progress_bar(c_st)

        if df_coin.empty:
            st.info("🪙 Henüz kripto coin işlemi kaydedilmemiş.")
        else:
            coin_basarili = df_coin[df_coin['durum'].str.contains('BAŞARILI', na=False)].copy()
            coin_basarisiz = df_coin[df_coin['durum'].str.contains('BAŞARISIZ', na=False)].copy()
            coin_bekleyen = df_coin[df_coin['durum'] == 'BEKLIYOR'].copy()
            coin_zaman = df_coin[df_coin['durum'].str.contains('ZAMAN AŞIMI', na=False)].copy()

            st.markdown("---")
            _durum_gruplu_tablo(coin_basarili, "BAŞARILI COİNLER", "✅", "badge-green", "#0fdb7a")
            _durum_gruplu_tablo(coin_basarisiz, "STOP OLAN COİNLER", "❌", "badge-red", "#ff3b5c")
            _durum_gruplu_tablo(coin_bekleyen, "BEKLEYEN COİNLER", "⏳", "badge-yellow", "#f5cc6a")
            _durum_gruplu_tablo(coin_zaman, "ZAMAN AŞIMI COİNLER", "⏰", "badge-blue", "#ff8c42")

    # ── Sinyal Kalite Raporu (Tavsiye #4) ────────────────────────────
    if SINYAL_KALITE_AKTIF:
        with st.expander("📊 Sinyal Kalite Raporu (İndikatör Bazında Win Rate)", expanded=False):
            c_sq1, c_sq2 = st.columns([3, 1])
            with c_sq1:
                st.caption("Her indikatörün geçmiş AL sinyallerindeki başarı oranı. "
                          "2 ardışık raporda ZAYIF çıkanlar otomatik devre dışı bırakılır.")
            with c_sq2:
                if st.button("🔄 Raporu Oluştur", use_container_width=True):
                    with st.spinner("Sinyal kalite raporu oluşturuluyor..."):
                        try:
                            rapor = kalite_raporu_olustur(son_gun=90)
                            st.session_state.sinyal_kalite_raporu = rapor
                            st.success("Rapor oluşturuldu!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Rapor oluşturulamadı: {e}")

            # Rapor varsa göster
            rapor = st.session_state.get('sinyal_kalite_raporu', None)
            if rapor is None:
                try:
                    from mod_sinyal_kalite import _onceki_raporu_yukle
                    rapor = _onceki_raporu_yukle()
                except:
                    rapor = None

            if rapor and rapor.get('indikatorler'):
                wr = rapor['genel_win_rate']
                wr_renk = "#0fdb7a" if wr >= 50 else "#ff3b5c"
                st.markdown(f"""
                <div style="background:linear-gradient(160deg,rgba(10,18,36,0.92),rgba(6,12,26,0.85));
                            border:1px solid rgba(30,51,85,0.3);border-radius:10px;padding:14px 16px;margin:10px 0;">
                    <div style="font-size:12px;color:#c4cdd9;">📈 Genel Win Rate: 
                        <span style="font-size:22px;font-weight:800;color:{wr_renk};">
                            %{wr:.1f}</span>
                        <span style="font-size:10px;color:#8a9bb5;"> ({rapor['toplam_islem']} işlem)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                ind_data = []
                for ind in rapor['indikatorler']:
                    renk_ikon = {"GÜÇLÜ": "🟢", "ORTA": "🟡", "ZAYIF": "🔴", "YETERSIZ": "⚪"}.get(ind['kalite'], "⚪")
                    ind_data.append({
                        "İndikatör": f"{renk_ikon} {ind['isim']}",
                        "Win Rate": f"%{ind['win_rate']:.1f}",
                        "Başarılı": ind['basarili_sinyal'],
                        "Toplam AL": ind['toplam_al_sinyali'],
                        "Kalite": ind['kalite'],
                        "Devre Dışı": "⚠️ EVET" if ind['devre_disi'] else "HAYIR"
                    })
                ind_df = pd.DataFrame(ind_data)
                st.dataframe(ind_df, use_container_width=True, hide_index=True)

                if rapor['devre_disi_onerilen']:
                    st.warning(f"⚠️ {len(rapor['devre_disi_onerilen'])} indikatör 2 ardışık ZAYIF: "
                             f"{', '.join(rapor['devre_disi_onerilen'])}")
                    if st.button("🔧 ZAYIF İndikatörleri Devre Dışı Bırak", type="primary"):
                        devre_disi = devre_disi_indikatorleri_uygula()
                        if devre_disi:
                            st.success(f"✅ {len(devre_disi)} indikatör devre dışı: "
                                     f"{', '.join(devre_disi)}")
                            st.rerun()
                        else:
                            st.info("ℹ️ Devre dışı bırakılacak indikatör yok.")
            else:
                st.info("Henüz sinyal kalite raporu yok. 'Raporu Oluştur'a tıklayın.")
        st.markdown("---")

    # ═══ YZ STRATEJİ ═══
    st.subheader("🤖 YZ Otonom Strateji Önerisi")
    onerilen = strateji_analiz_et()

    if "UYARI" in onerilen:
        st.warning(f"⚠️ {onerilen}")
        if st.button("🚀 Parametreleri Güncelle ve Sisteme İşle", type="primary"):
            sonuc = strateji_guncelle(0.05)
            st.success(sonuc)
            st.balloons()
            st.rerun()
    else:
        st.success(f"**Sistemin Analizi:** {onerilen}")

    # Lejant
    st.markdown("""
    <div style="display:flex;gap:20px;font-family:'JetBrains Mono',monospace;font-size:9px;
                color:#8a9bb5;margin-top:12px;flex-wrap:wrap;padding:12px 16px;
                background:rgba(10,18,36,0.4);border-radius:8px;border:1px solid rgba(30,51,85,0.2);">
        <span>🟢 <span style="color:#0fdb7a;font-weight:600;">BAŞARILI</span> = Hedefe ulaştı</span>
        <span>🔴 <span style="color:#ff3b5c;font-weight:600;">BAŞARISIZ</span> = Stop oldu</span>
        <span>🟡 <span style="color:#f5cc6a;font-weight:600;">BEKLİYOR</span> = Hedef/stop arasında</span>
        <span>🟠 <span style="color:#ff8c42;font-weight:600;">ZAMAN AŞIMI</span> = 30 gün</span>
    </div>
    """, unsafe_allow_html=True)