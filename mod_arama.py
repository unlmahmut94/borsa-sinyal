# ══════════════════════════════════════════════════════════════════════
#  mod_arama.py — Hızlı arama, öneri listesi, sembol çözümleme

import streamlit as st
from hisse_isimleri import HISSE_ISIMLERI


def arama_oneri(sorgu: str, max_sonuc: int = 5) -> list:
    """
    Verilen sorguya göre HISSE_ISIMLERI sözlüğünden eşleşen
    (sembol, isim) çiftlerini döndürür.
    """
    if not sorgu or len(sorgu) < 1:
        return []
    s = sorgu.upper()
    return [
        (sym, name)
        for sym, name in HISSE_ISIMLERI.items()
        if s in sym.upper() or s in name.upper()
    ][:max_sonuc]


def arama_kutusu(key_prefix: str = "ara"):
    """
    Arama kutusu widget'ı. Kullanıcı yazdıkça öneriler çıkar,
    tıklayınca secilen_hisse set edilir.
    Döndürdüğü değer: seçilen sembol stringi veya None.
    """
    sorgu = st.text_input(
        "",
        placeholder="Sembol veya şirket ara... (THYAO.IS · AAPL · Garanti)",
        label_visibility="collapsed",
        key=f"{key_prefix}_input"
    )

    if sorgu and len(sorgu) >= 2:
        eslesme = arama_oneri(sorgu, max_sonuc=5)
        if eslesme:
            st.markdown('<span class="section-label">Öneriler</span>',
                        unsafe_allow_html=True)
            ocols = st.columns(min(len(eslesme), 5))
            for idx, (sem, ism) in enumerate(eslesme):
                flag = "TR" if ".IS" in sem else "US"
                with ocols[idx]:
                    if st.button(f"{flag} {sem}", key=f"{key_prefix}_{sem}_{idx}",
                                  use_container_width=True):
                        st.session_state.secilen_hisse = sem
                        st.rerun()
                    st.markdown(
                        f"<div style='text-align:center;margin-top:-6px;margin-bottom:4px;"
                        f"font-family:Sora,sans-serif;font-size:9px;color:var(--txt3);'>"
                        f"{ism[:18]}</div>",
                        unsafe_allow_html=True
                    )


def sidebar_arama():
    """
    Sidebar içinde gösterilen hızlı arama bileşeni.
    Eşleşen semboller butona dönüşür; tıklayınca secilen_hisse set edilir.
    """
    st.markdown(
        '<div style="padding:12px 18px 0 18px;">'
        '<span class="section-label" style="margin-top:0;">Hızlı Arama</span>'
        '</div>',
        unsafe_allow_html=True
    )
    sb_ara = st.text_input(
        "", placeholder="THYAO.IS · AAPL · Garanti...",
        key="sb_ara", label_visibility="collapsed"
    )
    if sb_ara and len(sb_ara) >= 2:
        eslesme = arama_oneri(sb_ara, max_sonuc=4)
        for sem, ism in eslesme:
            flag = "TR" if ".IS" in sem else "US"
            if st.button(f"{flag} {sem}", key=f"sb_{sem}", use_container_width=True):
                st.session_state.secilen_hisse = sem
                st.rerun()
