# ══════════════════════════════════════════════════════════════════════
#  mod_gorsel.py — Global CSS, tema renkleri, font tanımları · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════

import streamlit as st


def uygula_tema():
    """Tüm global CSS'i sayfaya enjekte eder — premium dark terminal teması."""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@200;300;400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Outfit:wght@300;400;600;700&display=swap');

header[data-testid="stHeader"]         { display: none !important; }
#MainMenu                              { display: none !important; }
footer                                 { display: none !important; }
div[data-testid="stToolbar"]           { display: none !important; }
div[data-testid="stDecoration"]        { display: none !important; }
div[data-testid="stStatusWidget"]      { display: none !important; }
.viewerBadge_container__1QSob          { display: none !important; }
.stDeployButton                        { display: none !important; }
[data-testid="manage-app-button"]      { display: none !important; }

.stApp {
  background: linear-gradient(rgba(6, 11, 20, 0.92), rgba(6, 11, 20, 0.97)), 
              url('https://ornek-resim-linki.com/bist_bina.jpg') !important;
  background-size: cover !important;
  background-position: center !important;
  background-attachment: fixed !important;
}
body {
  transition: none !important;
  animation: none !important;
  opacity: 1 !important;
}
section, div, main, .main, .block-container {
  transition: none !important;
}
[data-testid="stStatusWidget"] {
  display: none !important;
}
.stApp > div:first-child {
  opacity: 1 !important;
  transition: none !important;
}

:root {
  --bg0: #060b14;
  --bg1: #0a1222;
  --bg2: #0e182c;
  --bg3: #121f36;
  --bg-card: #080f1c;
  --border: #1e3355;
  --b2:     #2a4a78;
  --gold:   #f0c040;
  --gold-l: #f8d86a;
  --gold-d: #b8882a;
  --gold-glow: rgba(240, 192, 64, 0.18);
  --green:    #22e691;
  --green-l:  #4ff0aa;
  --green-d:  #0b793d;
  --green-glow: rgba(34, 230, 145, 0.15);
  --red:    #ff4f6d;
  --red-l:  #ff7b90;
  --red-d:  #9b1f35;
  --red-glow: rgba(255, 79, 109, 0.15);
  --blue:   #4db8ff;
  --blue-l: #7ccfff;
  --blue-d: #1a6aaa;
  --blue-glow: rgba(77, 184, 255, 0.15);
  --purple: #b57cf8;
  --purple-l: #d0aefb;
  --purple-glow: rgba(181, 124, 248, 0.15);
  --cyan: #2ee8d4;
  --cyan-glow: rgba(46, 232, 212, 0.12);
  --orange: #ff8c42;
  --orange-glow: rgba(255, 140, 66, 0.15);
  --txt1: #eef2f7;
  --txt2: #c4cdd9;
  --txt3: #8a9bb5;
  --txt-dim: #5a6d85;
}

* { box-sizing: border-box; }
html, body, [class*="css"], .stApp {
  font-family: 'Sora', 'Outfit', sans-serif !important;
  background: var(--bg0) !important;
  color: var(--txt1) !important;
  -webkit-font-smoothing: antialiased;
}

/* TUM BORDERLARI SIFIRLA */
div[data-testid="metric-container"],
div[data-testid="stDataFrame"],
.stDataFrame,
.glass-card,
.help-card,
.streamlit-expanderHeader,
.streamlit-expanderContent,
div[data-baseweb="tab-list"],
button[data-baseweb="tab"],
button[data-baseweb="tab"]:hover,
button[data-baseweb="tab"][aria-selected="true"],
button[data-key^="bist_r_"],
button[data-key^="abd_r_"],
.stButton > button,
.stButton > button[kind="secondary"],
.stDownloadButton > button,
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stTextInput input,
.stNumberInput input,
.news-card, .news-card *,
.stAlert, div[class*="stAlert"],
section[data-testid="stSidebar"],
div[data-testid="column"] > div {
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
}
div[data-testid="metric-container"]::before {
  display: none !important;
}

.stApp {
  background:
    linear-gradient(175deg, rgba(6,11,20,0.92) 0%, rgba(10,18,34,0.95) 50%, rgba(7,14,26,0.98) 100%),
    url('https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=2560&auto=format&fit=crop') center/cover fixed !important;
}
.main, .block-container {
  background: transparent !important;
  padding: 0 1.8rem 2.5rem 1.8rem !important;
  max-width: 100% !important;
}

div[data-testid="metric-container"] {
  background: linear-gradient(160deg, rgba(10, 18, 36, 0.6), rgba(6, 12, 26, 0.5)) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  padding: 18px 20px !important;
  transition: all 0.2s ease !important;
}
div[data-testid="metric-container"]:hover {
  background: linear-gradient(160deg, rgba(10, 18, 36, 0.8), rgba(6, 12, 26, 0.65)) !important;
  box-shadow: none !important;
  border: none !important;
  outline: none !important;
}
div[data-testid="metric-container"] label {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 8px !important;
  font-weight: 600 !important;
  color: var(--txt3) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.22em !important;
}
div[data-testid="metric-container"] [data-testid="metric-value"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 22px !important;
  font-weight: 800 !important;
  color: var(--txt1) !important;
  letter-spacing: -0.02em !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 10px !important;
  font-weight: 600 !important;
}

div[data-baseweb="tab-list"] {
  background: transparent !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  gap: 2px !important;
  padding: 4px 0 0 0 !important;
}
button[data-baseweb="tab"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 8px !important;
  font-weight: 500 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: var(--txt3) !important;
  background: transparent !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  padding: 8px 12px !important;
  margin-bottom: 0px !important;
  transition: all 0.15s ease !important;
}
button[data-baseweb="tab"]:hover {
  color: var(--gold) !important;
  background: transparent !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
  color: var(--gold) !important;
  background: transparent !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
}

button[data-key^="bist_r_"],
button[data-key^="abd_r_"],
button[data-key^="bist_r_"]:hover,
button[data-key^="abd_r_"]:hover,
button[data-key^="bist_r_"]:active,
button[data-key^="abd_r_"]:active,
button[data-key^="bist_r_"]:focus,
button[data-key^="abd_r_"]:focus {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  color: transparent !important;
  outline: none !important;
  font-size: 0 !important;
  height: 50px !important;
  margin-top: -50px !important;
  padding: 0 !important;
  position: relative !important;
  z-index: 99 !important;
  cursor: pointer !important;
  display: block !important;
  width: 100% !important;
}
.hisse-satir {
  transition: all 0.15s ease !important;
  border-radius: 0px !important;
}
.hisse-satir:hover {
  background: linear-gradient(90deg, rgba(77, 184, 255, 0.04), rgba(240, 192, 64, 0.02)) !important;
}

.js-plotly-plot .plotly .modebar {
  left: 0 !important; right: auto !important;
  top: 20px !important; flex-direction: column !important;
  background: rgba(10, 18, 36, 0.8) !important;
  border: none !important;
  border-radius: 0px !important;
  padding: 4px !important;
  backdrop-filter: blur(8px) !important;
}

.stButton > button {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 9px !important;
  font-weight: 700 !important;
  letter-spacing: 0.18em !important;
  text-transform: uppercase !important;
  color: var(--gold) !important;
  background: rgba(240, 192, 64, 0.08) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  padding: 10px 18px !important;
  transition: all 0.15s ease !important;
}
.stButton > button:hover {
  background: rgba(240, 192, 64, 0.15) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
}
.stButton > button[kind="secondary"] {
  background: rgba(240, 192, 64, 0.04) !important;
  color: var(--txt2) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
}
.stButton > button[kind="secondary"]:hover {
  color: var(--gold) !important;
  background: rgba(240, 192, 64, 0.1) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
}

.stTextInput input,
.stNumberInput input {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12px !important;
  color: var(--txt1) !important;
  background: rgba(8, 16, 30, 0.5) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-bottom: 1px solid rgba(77, 184, 255, 0.15) !important;
  border-radius: 0px !important;
  padding: 10px 14px !important;
  transition: all 0.2s ease !important;
}
.stTextInput input:focus,
.stNumberInput input:focus {
  border-bottom: 1px solid var(--gold) !important;
  background: rgba(8, 16, 30, 0.7) !important;
  box-shadow: none !important;
  outline: none !important;
}
.stTextInput input::placeholder {
  color: var(--txt-dim) !important;
  font-size: 11px !important;
}
.stSelectbox > div > div {
  background: rgba(8, 16, 30, 0.5) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  color: var(--txt1) !important;
  border-bottom: 1px solid rgba(77, 184, 255, 0.15) !important;
}
.stSelectbox > div > div:hover {
  border-bottom: 1px solid rgba(240, 192, 64, 0.3) !important;
}
.stMultiSelect > div > div {
  background: rgba(8, 16, 30, 0.5) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
}

.streamlit-expanderHeader {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  color: var(--txt2) !important;
  background: rgba(10, 18, 36, 0.4) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  padding: 10px 16px !important;
}
.streamlit-expanderHeader:hover {
  background: rgba(15, 25, 45, 0.5) !important;
}
.streamlit-expanderContent {
  background: rgba(6, 12, 26, 0.3) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-top: none !important;
  border-radius: 0px !important;
  padding: 16px !important;
}

.stDataFrame {
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  overflow: hidden !important;
}
.stDataFrame [data-testid="stTable"] {
  font-family: 'JetBrains Mono', monospace !important;
}

.stSlider [data-testid="stThumbValue"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 10px !important;
  background: var(--bg2) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  padding: 2px 8px !important;
}

.stCheckbox label {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 10px !important;
  letter-spacing: 0.1em !important;
  color: var(--txt2) !important;
}

.stAlert {
  border-radius: 0px !important;
  border-left: none !important;
  font-family: 'Sora', sans-serif !important;
  font-size: 12px !important;
  backdrop-filter: blur(8px) !important;
}

.stSpinner > div {
  border-top-color: var(--gold) !important;
  border-width: 3px !important;
}

.stProgress > div > div {
  background: linear-gradient(90deg, var(--gold-d), var(--gold), var(--gold-l)) !important;
  border-radius: 0px !important;
}

.stDownloadButton > button {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 9px !important;
  font-weight: 700 !important;
  letter-spacing: 0.16em !important;
  text-transform: uppercase !important;
  background: rgba(77, 184, 255, 0.08) !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px !important;
  color: var(--blue) !important;
  padding: 10px 20px !important;
}
.stDownloadButton > button:hover {
  background: rgba(77, 184, 255, 0.15) !important;
}

.glass-card {
  background: linear-gradient(160deg, rgba(10, 18, 36, 0.5), rgba(6, 12, 26, 0.4));
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px;
  backdrop-filter: blur(12px);
}
.glass-card:hover {
  background: linear-gradient(160deg, rgba(10, 18, 36, 0.7), rgba(6, 12, 26, 0.55));
}

.help-card {
  background: linear-gradient(160deg, rgba(10, 18, 36, 0.5), rgba(6, 12, 26, 0.4));
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  border-radius: 0px;
  padding: 18px 20px;
  margin-bottom: 10px;
}
.help-card:hover {
  background: linear-gradient(160deg, rgba(10, 18, 36, 0.7), rgba(6, 12, 26, 0.55));
}
.help-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gold);
  margin-bottom: 10px;
}
.help-text {
  font-family: 'Sora', sans-serif;
  font-size: 12px;
  color: var(--txt2);
  line-height: 1.75;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
}
.stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--txt3);
  letter-spacing: 0.08em;
}
.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--txt2);
  font-weight: 600;
}

.section-label {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--gold);
  padding-bottom: 0px;
  margin: 18px 0 10px 0;
}

[data-testid="stTooltipIcon"] {
  color: var(--gold-d) !important;
}

section[data-testid="stSidebar"] {
  background: rgba(3, 7, 15, 0.97) !important;
  border-right: none !important;
  backdrop-filter: blur(24px) saturate(120%) !important;
  box-shadow: none !important;
}

hr {
  border: none !important;
  border-top: 1px solid rgba(30, 51, 85, 0.2) !important;
  margin: 20px 0 !important;
}

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(30, 51, 85, 0.4);
  border-radius: 2px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(42, 74, 120, 0.6); }

@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes glowPulse {
  0%, 100% { box-shadow: none; }
  50%      { box-shadow: 0 0 16px rgba(240, 192, 64, 0.08); }
}
.fade-in { animation: fadeSlideIn 0.35s ease forwards; }
.fade-up { animation: fadeSlideIn 0.35s ease forwards; }
</style>
""", unsafe_allow_html=True)


def sidebar_gizle():
    """Hisse detay sayfasinda sidebar'i gizler."""
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    .main .block-container { padding-left: 1.5rem !important; max-width: 100% !important; }
    </style>
    """, unsafe_allow_html=True)