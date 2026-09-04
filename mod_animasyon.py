# ══════════════════════════════════════════════════════════════════════
#  mod_animasyon.py — Geçiş efektleri, loading animasyonları, UI utils · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════

import streamlit as st


def gecis_css():
    """Sayfa geçiş ve fade-in animasyon CSS'ini enjekte eder."""
    st.markdown("""
    <style>
    /* ── Genel fade-in ───────────────────────── */
    @keyframes fadeSlideIn {
      from { opacity: 0; transform: translateY(12px); }
      to   { opacity: 1; transform: translateY(0);    }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(20px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulseGlow {
      0%, 100% { box-shadow: 0 0 0px rgba(240,192,64,0); }
      50%       { box-shadow: 0 0 22px rgba(240,192,64,0.3); }
    }
    @keyframes borderGlow {
      0%, 100% { border-color: rgba(240,192,64,0.2); }
      50%       { border-color: rgba(240,192,64,0.5); }
    }
    @keyframes slideInRight {
      from { opacity: 0; transform: translateX(20px); }
      to   { opacity: 1; transform: translateX(0); }
    }

    .fade-in       { animation: fadeSlideIn .4s ease forwards; }
    .fade-only     { animation: fadeIn .3s ease forwards; }
    .fade-up       { animation: fadeInUp .4s ease forwards; }
    .pulse-gold    { animation: pulseGlow 2s ease-in-out infinite; }
    .border-glow   { animation: borderGlow 2s ease-in-out infinite; }
    .slide-right   { animation: slideInRight .35s ease forwards; }

    /* ── Staggered children ──────────────────── */
    .stagger > *:nth-child(1) { animation-delay: 0ms; }
    .stagger > *:nth-child(2) { animation-delay: 50ms; }
    .stagger > *:nth-child(3) { animation-delay: 100ms; }
    .stagger > *:nth-child(4) { animation-delay: 150ms; }
    .stagger > *:nth-child(5) { animation-delay: 200ms; }
    .stagger > *:nth-child(6) { animation-delay: 250ms; }

    /* ── Tab geçişi (hızlandırıldı — sönükleşme hissi vermez) ─── */
    div[data-testid="stTabContent"] {
      animation: fadeInUp .12s ease forwards;
    }

    /* ── Hisse satırı hover geçişi ───────────── */
    .hisse-satir {
      transition: all .2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    /* ── Metrik güncelleme flash ─────────────── */
    @keyframes metricFlash {
      0%   { background: rgba(240,192,64,0.15); }
      100% { background: transparent; }
    }
    .metric-flash {
      animation: metricFlash .7s ease forwards;
    }

    /* ── Buton ripple ────────────────────────── */
    .stButton > button {
      position: relative;
      overflow: hidden;
    }
    .stButton > button::after {
      content: '';
      position: absolute;
      top: 50%; left: 50%;
      width: 0; height: 0;
      background: rgba(255,255,255,0.18);
      border-radius: 50%;
      transform: translate(-50%, -50%);
      transition: width .4s, height .4s, opacity .4s;
      opacity: 0;
    }
    .stButton > button:active::after {
      width: 250px; height: 250px; opacity: 1;
      transition: width 0s, height 0s, opacity 0s;
    }

    /* ── Loading skeleton ────────────────────── */
    @keyframes shimmer {
      0%   { background-position: -500px 0; }
      100% { background-position:  500px 0; }
    }
    .skeleton {
      background: linear-gradient(90deg,
        rgba(30,51,85,0.4) 25%,
        rgba(42,74,120,0.5) 50%,
        rgba(30,51,85,0.4) 75%
      );
      background-size: 1000px 100%;
      animation: shimmer 1.5s infinite;
      border-radius: 8px;
      height: 14px;
      margin: 6px 0;
    }
    .skeleton-sm { height: 10px; width: 60%; }
    .skeleton-lg { height: 48px; width: 100%; }

    /* ── Grafik container ────────────────────── */
    .grafik-container {
      animation: fadeSlideIn .5s ease forwards;
    }

    /* ── Sayı sayma efekti ───────────────────── */
    @keyframes countUp {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .count-up {
      animation: countUp .5s ease forwards;
    }
    </style>
    """, unsafe_allow_html=True)


def yukleniyor_iskeleti(satir_sayisi: int = 5):
    """Veri yüklenirken gösterilen iskelet placeholder'lar."""
    for i in range(satir_sayisi):
        w = f"{85 + (i % 3) * 5}%"
        st.markdown(
            f'<div class="skeleton skeleton-lg" style="width:{w};"></div>'
            f'<div class="skeleton skeleton-sm" style="width:40%;margin-bottom:12px;"></div>',
            unsafe_allow_html=True
        )


def basarili_bildirim(mesaj: str, sure: float = 2.0):
    """Kısa süreli başarı mesajı."""
    st.markdown(f"""
    <div class="fade-in" style="background:rgba(11,121,61,0.25);border:1px solid rgba(34,230,145,0.3);
                border-left:3px solid var(--green);border-radius:10px;padding:12px 18px;margin:10px 0;
                font-family:'JetBrains Mono',monospace;font-size:11px;
                color:var(--green-l);letter-spacing:.06em;backdrop-filter:blur(8px);">
      <span style="font-size:14px;margin-right:8px;">✓</span> {mesaj}
    </div>
    """, unsafe_allow_html=True)


def hata_bildirimi(mesaj: str):
    """Özelleştirilmiş hata mesajı kutusu."""
    st.markdown(f"""
    <div class="fade-in" style="background:rgba(155,31,53,0.25);border:1px solid rgba(255,79,109,0.3);
                border-left:3px solid var(--red);border-radius:10px;padding:12px 18px;margin:10px 0;
                font-family:'JetBrains Mono',monospace;font-size:11px;
                color:var(--red-l);letter-spacing:.06em;backdrop-filter:blur(8px);">
      <span style="font-size:14px;margin-right:8px;">✗</span> {mesaj}
    </div>
    """, unsafe_allow_html=True)


def bolum_baslik(baslik: str, altyazi: str = "", bg_url: str = None):
    """Standart bölüm başlığı bileşeni — premium stil ve opsiyonel tematik banner."""
    
    if bg_url:
        bg_style = f"background: linear-gradient(90deg, rgba(6,11,20,1) 0%, rgba(6,11,20,0.7) 40%, rgba(6,11,20,0) 100%), url('{bg_url}') center/cover;"
        border_style = "border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 32px 24px;"
        cizgi = ""
    else:
        bg_style = "background: transparent;"
        border_style = "padding: 28px 0 4px 0;"
        cizgi = """<div style="height:1px;background:linear-gradient(90deg,var(--gold-d),rgba(184,136,42,0.2),transparent);
                  margin:14px 0 22px 0;"></div>"""

    st.markdown(f"""
    <div class="fade-in" style="{border_style} {bg_style} margin-bottom: 22px;">
      <span style="font-family:'Sora','Outfit',sans-serif;font-size:28px;font-weight:800;
                   color:var(--txt1);letter-spacing:-.03em;line-height:1.1;">{baslik}</span>
      {"<div style='font-family:Sora,sans-serif;font-size:13px;color:var(--txt3);margin-top:6px;font-weight:300;'>" + altyazi + "</div>" if altyazi else ""}
      {cizgi}
    </div>
    """, unsafe_allow_html=True)