# ══════════════════════════════════════════════════════════════════════
#  mod_guvenlik.py — Rate limit, session yönetimi, hata yakalama
import streamlit as st
import time
from datetime import datetime


# ── Rate limiter ──────────────────────────────────────────────────────
_son_istek: dict = {}
_BEKLEME = 0.5  # saniye — Yahoo Finance rate limit önlemi


def rate_limit_bekle(anahtar: str = "genel"):
    """Aynı anahtar için son istekten bu yana yeterli süre geçmemişse bekler."""
    simdi = time.time()
    gecen = simdi - _son_istek.get(anahtar, 0)
    if gecen < _BEKLEME:
        time.sleep(_BEKLEME - gecen)
    _son_istek[anahtar] = time.time()


# ── Session state başlatıcı ───────────────────────────────────────────
VARSAYILAN_SESSION = {
    "tarama_df":      None,
    "portfoy":        [],
    "secilen_hisse":  None,
    "haber_pop":      None,
    "secilen_haber":  None,
}


def session_baslat(portfoy_yukle_fn=None):
    """
    Uygulama başlangıcında session state değişkenlerini başlatır.
    portfoy_yukle_fn: portföy yükleme fonksiyonu (mod_portfoy.portfoy_yukle)
    """
    for k, v in VARSAYILAN_SESSION.items():
        if k not in st.session_state:
            if k == "portfoy" and portfoy_yukle_fn is not None:
                st.session_state[k] = portfoy_yukle_fn()
            else:
                st.session_state[k] = v

    # Gemini eklentisi — ek session değişkenleri
    if "secilen_hisse" not in st.session_state:
        st.session_state.secilen_hisse = None
    if "tarama_df" not in st.session_state:
        st.session_state.tarama_df = None
    if "secilen_haber" not in st.session_state:
        st.session_state.secilen_haber = None
    if "haber_pop" not in st.session_state:
        st.session_state.haber_pop = None


# ── Hata yakalayıcı dekoratör ─────────────────────────────────────────
def guvenli_calistir(fn, *args, hata_mesaji: str = "İşlem gerçekleştirilemedi.", **kwargs):
    """
    Verilen fonksiyonu try/except içinde çalıştırır.
    Hata olursa st.error gösterir, None döndürür.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        st.error(f"{hata_mesaji} ({type(e).__name__}: {e})")
        return None


# ── Veri tazeliğini kontrol ───────────────────────────────────────────
def veri_eski_mi(anahtar: str, dakika: int = 5) -> bool:
    """
    session_state'teki bir verinin son güncellenme zamanını kontrol eder.
    anahtar + '_zaman' key'i kullanır.
    """
    zaman_key = f"{anahtar}_zaman"
    if zaman_key not in st.session_state:
        return True
    gecen = (datetime.now() - st.session_state[zaman_key]).total_seconds() / 60
    return gecen >= dakika


def veri_zamani_guncelle(anahtar: str):
    """Veri güncellenme zamanını session_state'e yazar."""
    st.session_state[f"{anahtar}_zaman"] = datetime.now()
