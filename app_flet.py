# ══════════════════════════════════════════════════════════════════════
#  BorsaSinyal Pro Terminal v3.1 — FLET EDITION
#  %100 Python · Flutter tabanlı · Streamlit'ten çok daha tasarımsal
# ══════════════════════════════════════════════════════════════════════

import flet as ft
import threading
import time
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ── Veri modülleri ────────────────────────────────────────────────────
import yfinance as yf
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hisse_isimleri import HISSE_ISIMLERI
from mod_veri_servisi import canli_fiyat_hizli
from mod_grafik_yorumu import grafik_gorsel_analiz, canli_veriyi_guncelle, son_analizi_getir
from grafik_html import veri_cek_ve_grafik_olustur, formasyon_ozeti_al, _teknik_gostergeleri_hesapla, tradingview_grafik_html, _formasyon_cizimleri, tradingview_veri_cek_ve_kaydet
import webbrowser



# ══════════════════════════════════════════════════════════════════════
#  TEMA RENKLERİ
# ══════════════════════════════════════════════════════════════════════
BG0       = "#060b14"
BG1       = "#0a1222"
BG2       = "#0e182c"
BG3       = "#121f36"
BG_CARD   = "#080f1c"
BORDER    = "#1e3355"
GOLD      = "#f0c040"
GOLD_L    = "#f8d86a"
GOLD_D    = "#b8882a"
GREEN     = "#22e691"
GREEN_L   = "#4ff0aa"
RED       = "#ff4f6d"
RED_L     = "#ff7b90"
BLUE      = "#4db8ff"
BLUE_L    = "#7ccfff"
TXT1      = "#eef2f7"
TXT2      = "#c4cdd9"
TXT3      = "#8a9bb5"
TXT_DIM   = "#5a6d85"


# ══════════════════════════════════════════════════════════════════════
#  FONTS
# ══════════════════════════════════════════════════════════════════════
FONT_SORA   = "Sora, Outfit, sans-serif"
FONT_MONO   = "JetBrains Mono, monospace"


# ══════════════════════════════════════════════════════════════════════
#  VERİ YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def fetch_indices():
    """Küresel endeks verilerini çek."""
    endeksler = [
        ("^XU100","BIST 100","TR"),("^GSPC","S&P 500","US"),
        ("^IXIC","NASDAQ","US"),("^DJI","DOW JONES","US"),
        ("GC=F","ALTIN","AU"),("DX-Y.NYB","DXY","$"),
    ]
    results = []
    for sym, label, flag in endeksler:
        try:
            h = yf.Ticker(sym).history(period="2d")
            if len(h) >= 2:
                son = float(h["Close"].iloc[-1])
                deg = ((son - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100
                results.append((sym, label, flag, son, deg))
            else:
                results.append((sym, label, flag, 0, 0))
        except:
            results.append((sym, label, flag, 0, 0))
    return results


def fetch_macro():
    """Makro verileri çek."""
    try:
        tickers = {"Dolar": "USDTRY=X", "Altın": "GC=F", "Petrol": "BZ=F"}
        veri = yf.download(list(tickers.values()), period="5d", progress=False, group_by="ticker")
        macro = {}
        for isim, ticker in tickers.items():
            try:
                d = veri[ticker].dropna(subset=["Close"]) if isinstance(veri.columns, pd.MultiIndex) else veri.dropna(subset=["Close"])
                if not d.empty:
                    close_s = d["Close"].squeeze()
                    deg = ((close_s.iloc[-1] - close_s.iloc[0]) / close_s.iloc[0]) * 100
                    macro[isim] = round(float(deg), 2)
                else:
                    macro[isim] = 0.0
            except:
                macro[isim] = 0.0
        return macro
    except:
        return {"Dolar": 0.0, "Altın": 0.0, "Petrol": 0.0}


def get_price_list(syms):
    """Canlı fiyat listesi döndür."""
    results = []
    for sym in syms:
        try:
            t = yf.Ticker(sym)
            h = t.history(period="2d")
            if len(h) >= 2:
                fiyat = float(h["Close"].iloc[-1])
                deg = ((fiyat - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100
                yuksek = float(h["High"].iloc[-1])
                dusuk = float(h["Low"].iloc[-1])
                hacim = float(h.get("Volume", pd.Series([0])).iloc[-1]) if "Volume" in h.columns else 0
                results.append({
                    "sembol": sym,
                    "isim": HISSE_ISIMLERI.get(sym, sym.replace(".IS","")),
                    "fiyat": round(fiyat, 2),
                    "degisim": round(deg, 2),
                    "yuksek": round(yuksek, 2),
                    "dusuk": round(dusuk, 2),
                    "hacim": int(hacim),
                })
        except:
            pass
    return results


# ══════════════════════════════════════════════════════════════════════
#  BİLEŞENLER
# ══════════════════════════════════════════════════════════════════════

def make_section_header(label: str, accent: str = GOLD):
    """Bölüm başlığı."""
    return ft.Container(
        content=ft.Row([
            ft.Container(width=20, height=2, bgcolor=accent, border_radius=1, opacity=0.6),
            ft.Text(label, font_family=FONT_MONO, size=9, color=TXT3, letter_spacing=2, weight="w600"),
            ft.Container(expand=True, height=1, border=ft.border.only(bottom=ft.BorderSide(1, f"{BORDER}44"))),
        ], spacing=10, vertical_alignment="center"),
        margin=ft.margin.only(top=24, bottom=12),
    )


def make_change_badge(deg: float):
    """Değişim yüzdesi rozeti."""
    ok = "▲" if deg >= 0 else "▼"
    c = GREEN if deg >= 0 else RED
    bg = f"{GREEN}1a" if deg >= 0 else f"{RED}1a"
    return ft.Container(
        content=ft.Text(f"{ok} {abs(deg):.2f}%", font_family=FONT_MONO, size=11, weight="w700", color=c),
        bgcolor=bg, border_radius=14, padding=ft.padding.symmetric(horizontal=12, vertical=3),
    )


def make_index_card(sym, label, flag, son, deg):
    """Endeks kartı."""
    ok = "▲" if deg >= 0 else "▼"
    c = GREEN if deg >= 0 else RED
    bg = f"{GREEN}1a" if deg >= 0 else f"{RED}1a"
    return ft.Container(
        content=ft.Column([
            ft.Text(f"{flag} {label}", font_family=FONT_MONO, size=8, color=TXT3, letter_spacing=2, text_align="center"),
            ft.Text(f"{son:,.1f}", font_family=FONT_MONO, size=18, weight="w800", color=TXT1, letter_spacing=-1, text_align="center"),
            ft.Container(
                content=ft.Text(f"{ok} {abs(deg):.2f}%", font_family=FONT_MONO, size=11, weight="w700", color=c),
                bgcolor=bg, border_radius=14, padding=ft.padding.symmetric(horizontal=12, vertical=3),
            ),
        ], spacing=6, alignment="center", horizontal_alignment="center"),
        bgcolor=f"{BG2}99", border_radius=8, padding=ft.padding.all(16),
        expand=True,
    )


def make_stock_row(item: dict, prefix: str = "", suffix_clean: str = ".IS", on_click_callback=None):
    """Hisse satırı — tıklanabilir."""
    is_pos = item["degisim"] >= 0
    c = GREEN if is_pos else RED
    bg = f"{GREEN}14" if is_pos else f"{RED}14"
    ok = "▲" if is_pos else "▼"
    h = item.get("hacim", 0)
    if h >= 1e9: hs = f"{h/1e9:.1f}B"
    elif h >= 1e6: hs = f"{h/1e6:.0f}M"
    else: hs = f"{h:,.0f}"

    symbol_display = item["sembol"].replace(suffix_clean, "")

    def _on_click(e):
        if on_click_callback:
            on_click_callback(item["sembol"])

    def _on_hover(e):
        e.control.bgcolor = f"{GOLD}0a" if e.data == "true" else "transparent"
        e.control.update()

    return ft.Container(
        content=ft.Row([
            ft.Text(symbol_display, font_family=FONT_MONO, size=14, weight="w700", color=TXT1, width=76),
            ft.Text(item["isim"][:22], font_family=FONT_SORA, size=11, color=TXT2, expand=True, overflow="ellipsis", max_lines=1),
            ft.Text(f"{prefix}{item['fiyat']:,.2f}", font_family=FONT_MONO, size=14, weight="w700", color=TXT1, width=85, text_align="end"),
            ft.Container(
                content=ft.Text(f"{ok} {abs(item['degisim']):.2f}%", font_family=FONT_MONO, size=11, weight="w700", color=c),
                bgcolor=bg, border_radius=14, padding=ft.padding.symmetric(horizontal=10, vertical=3),
                width=90, alignment=ft.alignment.center,
            ),
            ft.Text(f"↑ {prefix}{item['yuksek']:,.2f}", font_family=FONT_MONO, size=11, color=GREEN, width=80, text_align="end", opacity=0.75),
            ft.Text(f"↓ {prefix}{item['dusuk']:,.2f}", font_family=FONT_MONO, size=11, color=RED, width=80, text_align="end", opacity=0.75),
            ft.Text(hs, font_family=FONT_MONO, size=10, color=TXT3, width=72, text_align="end"),
        ], spacing=0, vertical_alignment="center"),
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        border_radius=6,
        bgcolor="transparent",
        on_hover=_on_hover,
        on_click=_on_click,
        animate=ft.animation.Animation(150, "ease"),
    )


def make_stock_table_header():
    """Hisse tablosu başlığı."""
    h_style = {"font_family": FONT_MONO, "size": 9, "color": TXT3, "letter_spacing": 2, "weight": "w600"}
    return ft.Container(
        content=ft.Row([
            ft.Text("SEMBOL", **h_style, width=76),
            ft.Text("ŞİRKET", **h_style, expand=True),
            ft.Text("FİYAT", **h_style, width=85, text_align="end"),
            ft.Text("DEĞİŞİM", **h_style, width=90, text_align="center"),
            ft.Text("YÜKSEK", **h_style, width=80, text_align="end"),
            ft.Text("DÜŞÜK", **h_style, width=80, text_align="end"),
            ft.Text("HACİM", **h_style, width=72, text_align="end"),
        ], spacing=0, vertical_alignment="center"),
        padding=ft.padding.symmetric(horizontal=16, vertical=6),
    )


# ══════════════════════════════════════════════════════════════════════
#  FLET UYGULAMASI
# ══════════════════════════════════════════════════════════════════════

class BorsaSinyalApp:
    """Ana Flet uygulama sınıfı."""

    def __init__(self):
        self.active_tab = 0
        self.indices_data = []
        self.macro_data = {}
        self.bist_data = []
        self.us_data = []
        self.loading = True
        
        # ANALİZ Sekmesi için durum
        self.analiz_hisse_kodu = ""
        self.analiz_gorsel_yolu = ""
        self.analiz_sonuc = None
        self.analiz_calisiyor = False
        self.analiz_canli_timer = None

    def main(self, page: ft.Page):
        page.title = "BorsaSinyal Pro · FLET"
        page.padding = 0
        page.spacing = 0
        page.bgcolor = BG0
        page.theme_mode = "dark"
        page.window.width = 1400
        page.window.height = 900
        page.window.min_width = 1100
        page.window.min_height = 700
        page.fonts = {
            "Sora": "https://fonts.googleapis.com/css2?family=Sora:wght@200;300;400;500;600;700;800",
            "JetBrains Mono": "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800",
        }

        # ── Başlık ────────────────────────────────────────────────────
        self.header = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Text(
                        spans=[ft.TextSpan("Borsa", style=ft.TextStyle(color=TXT1, weight="w800", size=22, letter_spacing=-1)),
                               ft.TextSpan("Sinyal", style=ft.TextStyle(color=GOLD, weight="w800", size=22, letter_spacing=-1))],
                    ),
                    ft.Text("Pro Terminal · v3.1 · FLET", font_family=FONT_MONO, size=8, color=TXT3, letter_spacing=3),
                ], spacing=12, vertical_alignment="center"),
                ft.Row([
                    ft.Container(width=8, height=8, bgcolor=GREEN, border_radius=4),
                    ft.Text("LIVE", font_family=FONT_MONO, size=8, color=GREEN, letter_spacing=2),
                ], spacing=6, vertical_alignment="center"),
            ], alignment="spaceBetween", vertical_alignment="center"),
            padding=ft.padding.only(left=32, right=32, top=16, bottom=8),
            border=ft.border.only(bottom=ft.BorderSide(1, f"{BORDER}44")),
            bgcolor=f"{BG1}88",
        )

        # ── Sekme çubuğu ──────────────────────────────────────────────
        self.TAB_NAMES = ["DASHBOARD","TARAMA","ANALİZ","YZ (ML)","KARNE","TEST","PORTFÖY","HABER","YARDIM"]
        self.tab_buttons = []
        self.tab_row = ft.Row(spacing=2, scroll="never")
        for i, name in enumerate(self.TAB_NAMES):
            btn = ft.TextButton(
                text=name,
                style=ft.ButtonStyle(
                    color=TXT3, padding=ft.padding.symmetric(horizontal=8, vertical=10),
                    text_style=ft.TextStyle(font_family=FONT_MONO, size=9, letter_spacing=1, weight="w400"),
                    shape=ft.RoundedRectangleBorder(radius=6),
                ),
                on_click=lambda e, idx=i: self.switch_tab(idx),
            )
            self.tab_buttons.append(btn)
            self.tab_row.controls.append(btn)

        self.tab_container = ft.Container(
            content=self.tab_row,
            padding=ft.padding.only(left=28, right=28, top=4, bottom=8),
        )

        # ── Ayraç ─────────────────────────────────────────────────────
        self.divider = ft.Container(
            height=1,
            gradient=ft.LinearGradient(
                begin=ft.alignment.center_left, end=ft.alignment.center_right,
                colors=[f"{BLUE}66", f"{BLUE}14", "transparent"],
            ),
            margin=ft.margin.only(left=32, right=32, bottom=4),
            opacity=0.5,
        )

        # ── İçerik alanı ──────────────────────────────────────────────
        self.content_area = ft.Container(
            expand=True,
            padding=ft.padding.only(left=32, right=32, bottom=32),
        )

        # ── Birleştir ─────────────────────────────────────────────────
        page.add(
            ft.Container(
                content=ft.Column([
                    self.header,
                    self.tab_container,
                    self.divider,
                    self.content_area,
                ], spacing=0, expand=True),
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                    colors=[BG0, BG1, "#070e1a"],
                ),
                # --- YENİ EKLENEN ARKA PLAN GÖRSELİ ---
                image=ft.DecorationImage(
                    src="https://images.unsplash.com/photo-1618044733300-9472054094ee?q=80&w=2560&auto=format&fit=crop",
                    fit=ft.ImageFit.COVER,
                    opacity=0.04  # Sadece %4 görünürlük ile quant havası bozulmaz
                ),
            )
        )
        # ── İlk yüklemeyi başlat ──────────────────────────────────────
        self.switch_tab(0)
        threading.Thread(target=self._background_data_load, daemon=True).start()

    def switch_tab(self, idx):
        """Sekme değiştir."""
        self.active_tab = idx
        for i, btn in enumerate(self.tab_buttons):
            if i == idx:
                btn.style.color = GOLD
                btn.style.bgcolor = f"{GOLD}1a"
                btn.style.text_style = ft.TextStyle(font_family=FONT_MONO, size=9, letter_spacing=1, weight="w700")
            else:
                btn.style.color = TXT3
                btn.style.bgcolor = "transparent"
                btn.style.text_style = ft.TextStyle(font_family=FONT_MONO, size=9, letter_spacing=1, weight="w400")
        self.content_area.content = self.build_tab_content(idx)
        self.content_area.page.update() if self.content_area.page else None
        try:
            self.tab_row.update()
            self.content_area.update()
        except:
            pass

    def build_tab_content(self, idx):
        """Sekme içeriğini oluştur."""
        if idx == 0:
            return self._build_dashboard()
        elif idx == 2:
            return self._build_analiz()
        elif idx == 8:
            return self._build_placeholder(idx)
        else:
            return self._build_placeholder(idx)


    def _build_dashboard(self):
        """Dashboard sekmesi."""
        # Loading / veri yükleme
        if self.loading:
            return ft.Column([
                ft.ProgressBar(width=400, color=GOLD, bgcolor=f"{GOLD}22"),
                ft.Text("Piyasa verileri yükleniyor...", font_family=FONT_MONO, size=11, color=TXT3),
            ], alignment="center", horizontal_alignment="center", expand=True)

        # ── Başlık satırı ────────────────────────────────────────────
        title_row = ft.Row([
            ft.Column([
                ft.Row([
                    ft.Text("Piyasa ", size=32, weight="w800", color=TXT1, letter_spacing=-2),
                    ft.Text("Dashboard", size=32, weight="w800", color=GOLD, letter_spacing=-2),
                ], spacing=4),
                ft.Text("Küresel piyasaların anlık durumu · Satıra tıklayın — detaylı analiz",
                       font_family=FONT_SORA, size=12, color=TXT2, opacity=0.8),
            ], spacing=2),
            ft.Text(datetime.now().strftime("%d.%m.%Y %H:%M"), font_family=FONT_MONO, size=10, color=TXT3, letter_spacing=2),
        ], alignment="spaceBetween", vertical_alignment="start")

        sep = ft.Container(height=1,
            gradient=ft.LinearGradient(colors=[f"{BLUE}80", f"{BLUE}14", "transparent"]),
            margin=ft.margin.symmetric(vertical=18), opacity=0.5)

        # ── Makro kartlar ────────────────────────────────────────────
        macro = self.macro_data or {"Dolar": 0.0, "Altın": 0.0, "Petrol": 0.0}
        macro_cards = ft.Row([
            ft.Container(ft.Column([
                ft.Text("💵 DOLAR/TL", font_family=FONT_MONO, size=8, color=TXT3, letter_spacing=2, weight="w600"),
                ft.Text(f"%{macro['Dolar']:+.2f}", font_family=FONT_MONO, size=22, weight="w800", color=TXT1, letter_spacing=-1),
            ], spacing=4), bgcolor=f"{BG2}99", border_radius=8, padding=ft.padding.all(18), expand=True),
            ft.Container(ft.Column([
                ft.Text("🟡 ONS ALTIN", font_family=FONT_MONO, size=8, color=TXT3, letter_spacing=2, weight="w600"),
                ft.Text(f"%{macro['Altın']:+.2f}", font_family=FONT_MONO, size=22, weight="w800", color=TXT1, letter_spacing=-1),
            ], spacing=4), bgcolor=f"{BG2}99", border_radius=8, padding=ft.padding.all(18), expand=True),
            ft.Container(ft.Column([
                ft.Text("🛢️ BRENT PETROL", font_family=FONT_MONO, size=8, color=TXT3, letter_spacing=2, weight="w600"),
                ft.Text(f"%{macro['Petrol']:+.2f}", font_family=FONT_MONO, size=22, weight="w800", color=TXT1, letter_spacing=-1),
            ], spacing=4), bgcolor=f"{BG2}99", border_radius=8, padding=ft.padding.all(18), expand=True),
        ], spacing=16)

        # ── Endeks kartları ───────────────────────────────────────────
        idx_cards = ft.Row(
            [make_index_card(sym, label, flag, son, deg) for sym, label, flag, son, deg in self.indices_data if son != 0],
            spacing=16, wrap=True,
        )

        # Hisse satırı callback — tıklandığında ANALİZ sekmesine geçer ve otomatik grafiği açar
        def _hisse_click(sembol):
            self.analiz_hisse_kodu = sembol
            self.switch_tab(2)  # ANALİZ sekmesi
            # ANALİZ sekmesi yüklendikten sonra otomatik grafiği aç
            def _auto_load():
                time.sleep(0.5)  # UI'nin hazır olmasını bekle
                self._analiz_tv_ac(None)
            threading.Thread(target=_auto_load, daemon=True).start()


        # ── Hisse tabloları + Haberler (Yan Yana) ────────────────────
        bist_rows = [make_stock_row(h, suffix_clean=".IS", on_click_callback=_hisse_click) for h in self.bist_data]
        us_rows = [make_stock_row(h, prefix="$", suffix_clean="---NONE---", on_click_callback=_hisse_click) for h in self.us_data]

        # Hisse tabloları (sol)
        stock_col = ft.Column([
            make_section_header("🔥 TR BIST — GÜNÜN ÖNE ÇIKANLARI", GOLD),
            make_stock_table_header(),
            *bist_rows,
            ft.Container(height=24),
            make_section_header("🔥 US ABD — GÜNÜN ÖNE ÇIKANLARI", BLUE),
            make_stock_table_header(),
            *us_rows,
        ], spacing=0, expand=3, scroll="never")
        
        # Haber akışı (sağ)
        haber_col = ft.Column([
            make_section_header("📡 HABER AKIŞI", GOLD),
            ft.Container(
                content=ft.Column([
                    ft.Text("📰 Son Piyasa Haberleri", font_family=FONT_SORA, size=13, weight="w700", color=TXT1),
                    ft.Container(height=8),
                    ft.Text("• THYAO yeni hatlar için görüşmelere başladı", font_family=FONT_SORA, size=11, color=TXT2),
                    ft.Container(height=6),
                    ft.Text("• GARAN bilanço beklentileri yükseltildi", font_family=FONT_SORA, size=11, color=TXT2),
                    ft.Container(height=6),
                    ft.Text("• AAPL yapay zeka yatırımlarını artırıyor", font_family=FONT_SORA, size=11, color=TXT2),
                    ft.Container(height=6),
                    ft.Text("• NVDA yeni çip serisini tanıttı", font_family=FONT_SORA, size=11, color=TXT2),
                    ft.Container(height=6),
                    ft.Container(
                        content=ft.Text("📡 HABER + SİNYAL RADARI", font_family=FONT_MONO, size=10, weight="w700", color=GOLD),
                        border=ft.border.only(top=ft.BorderSide(1, f"{BORDER}44")),
                        padding=ft.padding.only(top=16),
                    ),
                    ft.Container(height=8),
                    *[ft.Row([
                        ft.Container(width=6, height=6, bgcolor=GREEN, border_radius=3),
                        ft.Text(f"{h.get('sembol','').replace('.IS','')}: {h.get('degisim',0):+.2f}%", 
                               font_family=FONT_MONO, size=11, color=TXT2),
                    ], spacing=8) for h in (self.bist_data + self.us_data)[:6]],
                ], spacing=0, scroll="always"),
                bgcolor=f"{BG2}99", border_radius=8, padding=ft.padding.all(20),
                expand=True, border=ft.border.all(1, f"{BORDER}33"),
            ),
        ], spacing=0, expand=2, scroll="never")

        # Ana satır: hisseler + haberler
        stock_section = ft.Row([
            stock_col,
            haber_col,
        ], spacing=24, expand=True)

        return ft.Column([
            title_row, sep,
            make_section_header("PİYASA HAVA DURUMU (MAKRO)", GOLD),
            macro_cards,
            make_section_header("KÜRESEL ENDEKSLER", BLUE),
            idx_cards,
            ft.Container(height=28),
            stock_section,
        ], spacing=0, expand=True, scroll="always")

    def _build_placeholder(self, idx):
        """Diğer sekmeler için placeholder."""
        titles = {
            1: ("Piyasa Tarama", "Teknik gösterge taraması, formasyonlar, hacim anomalileri"),
            2: ("Hisse Analizi", "Teknik, temel ve sentiment analiz — tek ekranda"),
            3: ("Yapay Zeka (ML)", "XGBoost / LightGBM / CatBoost model eğitimi"),
            4: ("YZ Karnesi", "Model performans metrikleri ve karşılaştırmalı analiz"),
            5: ("Backtest (Test)", "Strateji geriye dönük test simülasyonu"),
            6: ("Portföy Takibi", "Portföy yönetimi ve performans takibi"),
            7: ("Piyasa Haberleri", "Küresel haber akışı, çeviri ve sentiment analizi"),
            8: ("Yardım & Referans", "Kullanım kılavuzu, gösterge referansı ve SSS"),
        }
        title, subtitle = titles.get(idx, ("Modül", ""))

        features = {
            1: ["• Teknik gösterge taraması\n• Formasyon taraması\n• Hacim anomalileri\n• RSI/MACD filtreleri"],
            2: ["• Fiyat grafiği\n• Teknik göstergeler (RSI, MACD, MA)\n• Şirket bilgileri\n• Analist tahminleri"],
            3: ["• XGBoost / LightGBM / CatBoost\n• Optuna hiperparametre optimizasyonu\n• SHAP model açıklanabilirliği\n• Backtest entegrasyonu"],
            4: ["• Doğruluk, F1, Sharpe oranı\n• Karışıklık matrisi\n• Model karşılaştırma tablosu\n• Özellik önem sıralaması"],
            5: ["• Strateji seçimi\n• Dönem aralığı\n• Performans metrikleri\n• Portföy değer grafiği"],
            6: ["• Portföy ekleme/çıkarma\n• Anlık değer takibi\n• Kar/zarar hesaplama\n• Performans grafikleri"],
            7: ["• Haber tarama (Yahoo, Bloomberg)\n• Türkçe çeviri\n• Sentiment analizi\n• Dashboard entegrasyonu"],
            8: ["• Kullanım kılavuzu\n• Gösterge referansları\n• ML eğitim rehberi\n• Veri kaynağı bilgisi"],
        }

        return ft.Column([
            ft.Text(title, font_family=FONT_SORA, size=28, weight="w800", color=TXT1, letter_spacing=-1),
            ft.Text(subtitle, font_family=FONT_SORA, size=13, color=TXT2, opacity=0.85),
            ft.Container(height=1,
                gradient=ft.LinearGradient(colors=[GOLD_D, f"{GOLD_D}33", "transparent"]),
                margin=ft.margin.symmetric(vertical=14)),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"⚙️ {self.TAB_NAMES[idx]} MODÜLÜ",
                           font_family=FONT_MONO, size=9, weight="w600", color=GOLD, letter_spacing=2),
                    ft.Text(f"Orijinal Streamlit modülü Flet bileşenleriyle yeniden yazılıyor...\n\n{features.get(idx, [''])[0]}",
                           font_family=FONT_SORA, size=12, color=TXT2, opacity=0.9),
                ], spacing=8),
                bgcolor=f"{BG2}99", border_radius=8, padding=ft.padding.all(24),
            ),
        ], spacing=0, expand=True, scroll="always")

    def _build_analiz(self):
        """ANALİZ sekmesi: Görsel yükleme + Yapay Zeka yorumu + Canlı takip."""
        # ── Başlık ────────────────────────────────────────────────────
        title_row = ft.Row([
            ft.Column([
                ft.Row([
                    ft.Text("Grafik ", size=32, weight="w800", color=TXT1, letter_spacing=-2),
                    ft.Text("Analizi", size=32, weight="w800", color=GOLD, letter_spacing=-2),
                ], spacing=4),
                ft.Text("Mum grafiği ekran görüntüsü yükleyin — YZ yorumlasın · Seviyeler · Kademeler · Stop-loss",
                       font_family=FONT_SORA, size=12, color=TXT2, opacity=0.8),
            ], spacing=2),
            ft.Text(datetime.now().strftime("%d.%m.%Y %H:%M"), font_family=FONT_MONO, size=10, color=TXT3, letter_spacing=2),
        ], alignment="spaceBetween", vertical_alignment="start")

        sep = ft.Container(height=1,
            gradient=ft.LinearGradient(colors=[f"{BLUE}80", f"{BLUE}14", "transparent"]),
            margin=ft.margin.symmetric(vertical=18), opacity=0.5)

        # ── TradingView Widget Butonu (GERÇEK TradingView) ──────────
        self.analiz_tv_btn = ft.FilledButton(
            content=ft.Text("📊 TRADINGVIEW GRAFİĞİNİ AÇ", font_family=FONT_MONO, size=12, weight="w700"),
            style=ft.ButtonStyle(
                color=BG0, bgcolor=GREEN,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.all(18),
            ),
            on_click=self._analiz_tv_ac,
        )

        self.analiz_hisse_input = ft.TextField(
            hint_text="Örn: THYAO.IS, AAPL, GARAN.IS",
            border_color=f"{BORDER}88",
            border_radius=8,
            text_style=ft.TextStyle(font_family=FONT_MONO, size=14, color=TXT1),
            width=300,
            on_change=lambda e: setattr(self, 'analiz_hisse_kodu', e.control.value.upper()),
        )
        
        self.analiz_tv_durum = ft.Text("", font_family=FONT_MONO, size=11, color=TXT3)
        
        self.analiz_file_path = ft.Text(
            "Henüz görsel seçilmedi",
            font_family=FONT_MONO, size=11, color=TXT3,
        )
        
        self.analiz_btn = ft.FilledButton(
            content=ft.Text("🔍 GÖRSELİ ANALİZ ET", font_family=FONT_MONO, size=11, weight="w700"),
            style=ft.ButtonStyle(
                color=BG0, bgcolor=GOLD,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.all(18),
            ),
            on_click=self._analiz_baslat,
        )
        
        analiz_input_panel = ft.Container(
            content=ft.Column([
                ft.Text("📊 TRADINGVIEW TARZI GRAFİK", font_family=FONT_SORA, size=14, weight="w700", color=GREEN),
                ft.Text("Hisse kodunu girip butona tıklayın — Mum, hacim, MACD, RSI, formasyonlar, Fibonacci hepsi bir arada.", font_family=FONT_SORA, size=11, color=TXT2),
                ft.Container(height=6),
                ft.Row([
                    self.analiz_hisse_input,
                    self.analiz_tv_btn,
                ], spacing=12, vertical_alignment="center"),
                self.analiz_tv_durum,
                ft.Container(height=20, border=ft.border.only(bottom=ft.BorderSide(1, f"{BORDER}44"))),
                ft.Container(height=12),
                ft.Text("🤖 YAPAY ZEKA GÖRSEL ANALİZİ", font_family=FONT_SORA, size=14, weight="w700", color=GOLD),
                ft.Text("TradingView'dan aldığınız grafik PNG'sini yükleyin — Gemini AI yorumlasın:", font_family=FONT_SORA, size=11, color=TXT2),
                ft.Container(height=6),
                ft.Row([
                    self.analiz_file_path,
                    ft.Container(
                        content=ft.Text("📂 SEÇ", font_family=FONT_MONO, size=10, weight="w600", color=GOLD),
                        on_click=self._analiz_dosya_sec,
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                        border=ft.border.all(1, GOLD),
                        border_radius=8,
                    ),
                ]),
                ft.Container(height=8),
                ft.Row([
                    self.analiz_btn,
                ]),
            ], spacing=8),
            bgcolor=f"{BG2}99", border_radius=12,
            border=ft.border.all(1, f"{BORDER}44"),
            padding=ft.padding.all(24),
            width=420,
        )

        # ── Sağ panel: Sonuçlar ──────────────────────────────────────
        self.analiz_sonuc_container = ft.Container(
            content=ft.Column([
                ft.Text("⏳ Hisse kodu girip grafiği açın veya görsel analiz yapın",
                       font_family=FONT_SORA, size=13, color=TXT3, italic=True),
            ]),
            bgcolor=f"{BG2}99", border_radius=12,
            border=ft.border.all(1, f"{BORDER}44"),
            padding=ft.padding.all(24),
            expand=True,
        )

        # ── Ana düzen ────────────────────────────────────────────────
        return ft.Column([
            title_row, sep,
            ft.Row([
                analiz_input_panel,
                self.analiz_sonuc_container,
            ], spacing=24, expand=True, vertical_alignment="start"),
        ], spacing=0, expand=True, scroll="always")


    def _analiz_tv_ac(self, e):
        """GERÇEK TradingView Widget HTML grafiği oluştur ve tarayıcıda aç."""
        sembol = self.analiz_hisse_kodu.strip().upper()
        if not sembol:
            self.analiz_tv_durum.value = "⚠️ Lütfen bir hisse kodu girin!"
            self.analiz_tv_durum.color = RED
            self.analiz_tv_durum.update()
            return
        
        # Borsa belirleme
        exchange = "BIST"
        if ".IS" in sembol:
            exchange = "BIST"
        elif "NASDAQ" in sembol.upper() or sembol.upper() in ["AAPL","NVDA","MSFT","AMZN","GOOGL","META","TSLA"]:
            exchange = "NASDAQ"
        elif "USDT" in sembol.upper() or "BTC" in sembol.upper() or "ETH" in sembol.upper():
            exchange = "BITSTAMP"
        
        self.analiz_tv_durum.value = f"⏳ {sembol} için GERÇEK TradingView grafiği oluşturuluyor..."
        self.analiz_tv_durum.color = GOLD
        self.analiz_tv_durum.update()
        
        def _tv_thread():
            try:
                dosya = tradingview_veri_cek_ve_kaydet(
                    sembol=sembol,
                    exchange=exchange,
                    period="6mo",
                    interval="1d",
                    otomatik_ac=True,
                )
                self.analiz_tv_durum.value = f"✅ Gerçek TradingView açıldı: {os.path.basename(dosya)}"
                self.analiz_tv_durum.color = GREEN
                self.analiz_tv_durum.update()
                
                # Formasyon özetini de analiz sonucuna ekle
                try:
                    ticker = yf.Ticker(sembol)
                    data = ticker.history(period="6mo", interval="1d")
                    if not data.empty:
                        data = _teknik_gostergeleri_hesapla(data)
                        formasyonlar = formasyon_ozeti_al(data)
                        if formasyonlar:
                            items = [ft.Container(height=6)]
                            items.append(ft.Text(f"📊 {sembol.replace('.IS','')} — Tespit Edilen Formasyonlar",
                                       font_family=FONT_MONO, size=11, weight="w700", color=GOLD))
                            items.append(ft.Container(height=8))
                            for f in formasyonlar:
                                items.append(ft.Row([
                                    ft.Container(width=8, height=8, bgcolor=f['renk'], border_radius=4),
                                    ft.Text(f['isim'], font_family=FONT_SORA, size=13, color=TXT1),
                                ], spacing=8))
                            items.append(ft.Container(height=16))
                            items.append(ft.Text("💡 Grafik tarayıcıda açıldı. Formasyonlar yan panelde.",
                                       font_family=FONT_SORA, size=11, color=TXT3, italic=True))
                            # Gemini AI kısa yorum ekle
                            items.append(ft.Container(height=8))
                            items.append(ft.Text("🤖 Analiz için 'Görseli Analiz Et' butonunu kullanın",
                                       font_family=FONT_SORA, size=11, color=BLUE, italic=True))
                            self.analiz_sonuc_container.content = ft.Column(items, spacing=4)
                            self.analiz_sonuc_container.update()
                except:
                    pass
                    
            except Exception as ex:
                self.analiz_tv_durum.value = f"❌ Hata: {ex}"
                self.analiz_tv_durum.color = RED
                self.analiz_tv_durum.update()
        
        threading.Thread(target=_tv_thread, daemon=True).start()


    def _analiz_plotly_ac(self, e):
        """Plotly HTML grafiği oluştur (alternatif)."""
        sembol = self.analiz_hisse_kodu.strip().upper()
        if not sembol:
            return
        
        def _thread():
            try:
                dosya = veri_cek_ve_grafik_olustur(
                    sembol=sembol, period="6mo", interval="1d",
                    gosterge_alt="MACD", gosterge_alt2="RSI",
                    overlay_list=["MA20", "MA50", "BB"],
                    otomatik_ac=True,
                )
                self.analiz_tv_durum.value = f"✅ Plotly grafik açıldı: {os.path.basename(dosya)}"
                self.analiz_tv_durum.color = GREEN
                self.analiz_tv_durum.update()
            except Exception as ex:
                self.analiz_tv_durum.value = f"❌ Hata: {ex}"
                self.analiz_tv_durum.color = RED
                self.analiz_tv_durum.update()
        
        threading.Thread(target=_thread, daemon=True).start()



    def _analiz_dosya_sec(self, e):
        """Dosya yolu girme penceresi (Flet file picker basitleştirmesi)."""
        # Flet'in file_picker'ı container içinde tetiklenemiyor, 
        # bu yüzden basit text input kullanıyoruz
        def on_dialog_result(e):
            if e.control.value:
                self.analiz_gorsel_yolu = e.control.value
                self.analiz_file_path.value = f"📎 {os.path.basename(e.control.value)}"
                self.analiz_file_path.update()
        
        # TextField dialog
        dialog = ft.AlertDialog(
            title=ft.Text("Görsel Dosya Yolu", font_family=FONT_SORA, color=TXT1),
            content=ft.TextField(
                hint_text="C:\\Users\\...\\grafik.png",
                border_color=f"{BORDER}88",
                border_radius=8,
                text_style=ft.TextStyle(font_family=FONT_MONO, size=13, color=TXT1),
                width=400,
            ),
            actions=[
                ft.TextButton("İptal", on_click=lambda e: self._close_dialog(e)),
                ft.TextButton("Onayla", on_click=lambda e: self._analiz_dosya_onay(e)),
            ],
        )
        self.content_area.page.dialog = dialog
        dialog.open = True
        self.content_area.page.update()


    def _close_dialog(self, e):
        e.control.parent.parent.open = False
        self.content_area.page.update()


    def _analiz_dosya_onay(self, e):
        """Dosya yolunu onayla."""
        dialog = e.control.parent.parent
        text_field = dialog.content
        yol = text_field.value.strip()
        if yol and os.path.exists(yol):
            self.analiz_gorsel_yolu = yol
            self.analiz_file_path.value = f"📎 {os.path.basename(yol)}"
            self.analiz_file_path.color = GREEN
        else:
            self.analiz_file_path.value = "❌ Dosya bulunamadı!"
            self.analiz_file_path.color = RED
        dialog.open = False
        self.content_area.page.update()


    def _analiz_baslat(self, e):
        """Analizi başlat."""
        if not self.analiz_hisse_kodu:
            self._analiz_hata_goster("⚠️ Lütfen bir hisse kodu girin!")
            return
        if not self.analiz_gorsel_yolu or not os.path.exists(self.analiz_gorsel_yolu):
            self._analiz_hata_goster("⚠️ Lütfen geçerli bir görsel dosyası seçin!")
            return

        # Loading durumu
        self.analiz_calisiyor = True
        self.analiz_sonuc_container.content = ft.Column([
            ft.Row([
                ft.ProgressRing(width=24, height=24, color=GOLD, stroke_width=3),
                ft.Text(" Gemini Vision ile grafik analiz ediliyor...", font_family=FONT_SORA, size=13, color=TXT2),
            ], spacing=12),
            ft.Text("Bu işlem 10-20 saniye sürebilir", font_family=FONT_MONO, size=9, color=TXT3, italic=True),
        ], spacing=8)
        self.analiz_sonuc_container.update()

        # Arka planda çalıştır
        thread = threading.Thread(target=self._analiz_thread, daemon=True)
        thread.start()


    def _analiz_hata_goster(self, mesaj: str):
        """Hata mesajı göster."""
        self.analiz_sonuc_container.content = ft.Column([
            ft.Text(mesaj, font_family=FONT_SORA, size=14, color=RED),
        ])
        try:
            self.analiz_sonuc_container.update()
        except:
            pass


    def _analiz_thread(self):
        """Analizi arka planda çalıştır."""
        try:
            sonuc = grafik_gorsel_analiz(self.analiz_gorsel_yolu, self.analiz_hisse_kodu)
            self.analiz_sonuc = sonuc

            if sonuc.get("basarili"):
                self.analiz_sonuc_container.content = self._analiz_sonuc_karti(sonuc)
            else:
                self.analiz_sonuc_container.content = ft.Column([
                    ft.Text(f"❌ {sonuc.get('mesaj', 'Analiz başarısız')}",
                           font_family=FONT_SORA, size=14, color=RED),
                ])

            self.analiz_calisiyor = False
            if self.content_area.page:
                self.analiz_sonuc_container.update()

            # Canlı takibi başlat
            self._analiz_canli_takip_baslat()

        except Exception as ex:
            self._analiz_hata_goster(f"❌ Hata: {str(ex)}")
            self.analiz_calisiyor = False


    def _analiz_sonuc_karti(self, sonuc) -> ft.Column:
        if sonuc is None:
            return ft.Column([ft.Text("Henüz analiz yapılmadı", color=TXT3)])

        """Analiz sonuçlarını görsel kartlara dönüştür."""
        items = []

        # Başlık
        items.append(ft.Row([
            ft.Text("📊 ANALİZ RAPORU", font_family=FONT_MONO, size=9, weight="w700", color=GOLD, letter_spacing=2),
            ft.Text(f"{sonuc.get('hisse_kodu', '')} · {sonuc.get('analiz_zamani', '')}",
                   font_family=FONT_MONO, size=9, color=TXT3),
        ], alignment="spaceBetween"))

        items.append(ft.Container(height=16))

        # ── CANLI FİYAT KARTI ──────────
        canli = sonuc.get("canli_veri", {})
        if canli and "hata" not in canli:
            fiyat_renk = GREEN if canli.get("degisim_yuzde", 0) >= 0 else RED
            boga_renk = GREEN if canli.get("guclu_mu") == "Boga" else RED
            items.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"💰 {canli.get('fiyat', 0):.2f}",
                               font_family=FONT_MONO, size=28, weight="w800", color=fiyat_renk),
                        ft.Container(
                            content=ft.Text(f"{'▲' if canli.get('degisim_yuzde', 0) >= 0 else '▼'} {abs(canli.get('degisim_yuzde', 0)):.2f}%",
                                           font_family=FONT_MONO, size=12, weight="w700", color=fiyat_renk),
                            bgcolor=f"{fiyat_renk}1a", border_radius=14,
                            padding=ft.padding.symmetric(horizontal=12, vertical=4),
                        ),
                    ], spacing=12, vertical_alignment="center"),
                    ft.Row([
                        ft.Text(f"Açılış: {canli.get('acilis', 0):.2f}", font_family=FONT_MONO, size=10, color=TXT3),
                        ft.Text(f"Y: {canli.get('yuksek', 0):.2f}", font_family=FONT_MONO, size=10, color=GREEN),
                        ft.Text(f"D: {canli.get('dusuk', 0):.2f}", font_family=FONT_MONO, size=10, color=RED),
                        ft.Text(f"Hacim: {int(canli.get('hacim', 0)):,}", font_family=FONT_MONO, size=10, color=TXT3),
                    ], spacing=16),
                    ft.Row([
                        ft.Container(
                            content=ft.Text(f"🐂 Boğa: {canli.get('boga_gucu', 0):+.2f}",
                                           font_family=FONT_MONO, size=10, weight="w600", color=GREEN if canli.get('boga_gucu', 0) > 0 else TXT3),
                            bgcolor=f"{GREEN}12", border_radius=6, padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        ft.Container(
                            content=ft.Text(f"🐻 Ayı: {canli.get('ayi_gucu', 0):+.2f}",
                                           font_family=FONT_MONO, size=10, weight="w600", color=RED if canli.get('ayi_gucu', 0) < 0 else TXT3),
                            bgcolor=f"{RED}12", border_radius=6, padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                        ft.Container(
                            content=ft.Text(f"⚡ Denge: {canli.get('guclu_mu', '')}",
                                           font_family=FONT_MONO, size=10, weight="w700", color=boga_renk),
                            bgcolor=f"{boga_renk}18", border_radius=6, padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        ),
                    ], spacing=8),
                ], spacing=8),
                bgcolor=f"{BG1}cc", border_radius=10,
                border=ft.border.all(1, f"{fiyat_renk}44"),
                padding=ft.padding.all(18),
            ))
            items.append(ft.Container(height=12))

        # ── KADEME TAHMİNLERİ ──────────
        kademe = sonuc.get("kademe_tahminleri", {})
        if kademe:
            yukari = kademe.get("yukari_senaryo", {})
            asagi = kademe.get("asagi_senaryo", {})
            stop_loss = kademe.get("stop_loss", {})

            # Yukarı senaryo
            items.append(ft.Container(
                content=ft.Column([
                    ft.Text("📈 YUKARI KIRILIM SENARYOSU", font_family=FONT_MONO, size=9, weight="w700", color=GREEN, letter_spacing=1),
                    ft.Container(height=6),
                    ft.Text(f"🔑 Kırılması gereken: {yukari.get('kirilmasi_gereken', 0):.2f}",
                           font_family=FONT_MONO, size=13, weight="w600", color=TXT1),
                    ft.Row([
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"🎯 Hedef 1", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"{yukari.get('hedef_1', 0):.2f}", font_family=FONT_MONO, size=16, weight="w800", color=GREEN),
                                ft.Text(f"%{yukari.get('hedef_1_getiri', 0):+.2f}", font_family=FONT_MONO, size=10, color=GREEN_L),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{GREEN}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"🎯 Hedef 2", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"{yukari.get('hedef_2', 0):.2f}", font_family=FONT_MONO, size=16, weight="w800", color=GREEN),
                                ft.Text(f"%{yukari.get('hedef_2_getiri', 0):+.2f}", font_family=FONT_MONO, size=10, color=GREEN_L),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{GREEN}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"🎯 Hedef 3", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"{yukari.get('hedef_3', 0):.2f}", font_family=FONT_MONO, size=16, weight="w800", color=GREEN),
                                ft.Text(f"%{yukari.get('hedef_3_getiri', 0):+.2f}", font_family=FONT_MONO, size=10, color=GREEN_L),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{GREEN}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                    ], spacing=8),
                ]),
                bgcolor=f"{BG2}99", border_radius=10,
                border=ft.border.all(1, f"{GREEN}33"),
                padding=ft.padding.all(18),
            ))
            items.append(ft.Container(height=10))

            # Aşağı senaryo
            items.append(ft.Container(
                content=ft.Column([
                    ft.Text("📉 AŞAĞI KIRILIM SENARYOSU", font_family=FONT_MONO, size=9, weight="w700", color=RED, letter_spacing=1),
                    ft.Container(height=6),
                    ft.Text(f"🔑 Kırılması gereken: {asagi.get('kirilmasi_gereken', 0):.2f}",
                           font_family=FONT_MONO, size=13, weight="w600", color=TXT1),
                    ft.Row([
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"🎯 Hedef 1", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"{asagi.get('hedef_1', 0):.2f}", font_family=FONT_MONO, size=16, weight="w800", color=RED),
                                ft.Text(f"%{asagi.get('hedef_1_getiri', 0):+.2f}", font_family=FONT_MONO, size=10, color=RED_L),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{RED}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"🎯 Hedef 2", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"{asagi.get('hedef_2', 0):.2f}", font_family=FONT_MONO, size=16, weight="w800", color=RED),
                                ft.Text(f"%{asagi.get('hedef_2_getiri', 0):+.2f}", font_family=FONT_MONO, size=10, color=RED_L),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{RED}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                    ], spacing=8),
                ]),
                bgcolor=f"{BG2}99", border_radius=10,
                border=ft.border.all(1, f"{RED}33"),
                padding=ft.padding.all(18),
            ))
            items.append(ft.Container(height=10))

            # Stop loss
            items.append(ft.Container(
                content=ft.Column([
                    ft.Text("🛑 STOP LOSS SEVİYELERİ", font_family=FONT_MONO, size=9, weight="w700", color=RED_L, letter_spacing=1),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Container(
                            content=ft.Column([
                                ft.Text("UZUN (LONG)", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"{stop_loss.get('uzun_icin', 0):.2f}", font_family=FONT_MONO, size=20, weight="w800", color=RED),
                                ft.Text(f"%{stop_loss.get('uzun_kayip_yuzde', 0):+.2f} kayıp", font_family=FONT_MONO, size=10, color=RED_L),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{RED}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("KISA (SHORT)", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"{stop_loss.get('kisa_icin', 0):.2f}", font_family=FONT_MONO, size=20, weight="w800", color=RED),
                                ft.Text(f"%{stop_loss.get('kisa_kayip_yuzde', 0):+.2f} kayıp", font_family=FONT_MONO, size=10, color=RED_L),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{RED}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("RİSK/ÖDÜL", font_family=FONT_MONO, size=8, color=TXT3),
                                ft.Text(f"1 : {kademe.get('risk_odul', 1):.1f}", font_family=FONT_MONO, size=20, weight="w800", color=GOLD),
                                ft.Text(f"{kademe.get('detay', '')[:20]}", font_family=FONT_MONO, size=9, color=TXT2),
                            ], spacing=2, horizontal_alignment="center"),
                            bgcolor=f"{GOLD}12", border_radius=8,
                            padding=ft.padding.all(14), expand=True,
                        ),
                    ], spacing=8),
                ]),
                bgcolor=f"{BG2}99", border_radius=10,
                border=ft.border.all(1, f"{RED_L}33"),
                padding=ft.padding.all(18),
            ))
            items.append(ft.Container(height=10))

        # ── GEMINI YORUMU ──────────
        gemini = sonuc.get("gemini_yorumu", {})
        if gemini and "hata" not in gemini:
            ozet = gemini.get("ozet", "")
            trend = gemini.get("grafik_yorumu", {}).get("trend", "belirsiz")
            trend_gucu = gemini.get("grafik_yorumu", {}).get("trend_gucu", "orta")
            trend_renk = {"yukari": GREEN, "asagi": RED, "yatay": GOLD}.get(trend, TXT3)

            items.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("🤖 GEMINI AI YORUMU", font_family=FONT_MONO, size=9, weight="w700", color=BLUE, letter_spacing=1),
                        ft.Container(
                            content=ft.Text(f"Trend: {trend.upper()} · Güç: {trend_gucu.upper()}",
                                           font_family=FONT_MONO, size=9, weight="w600", color=trend_renk),
                            bgcolor=f"{trend_renk}15", border_radius=6,
                            padding=ft.padding.symmetric(horizontal=10, vertical=3),
                        ),
                    ], spacing=12),
                    ft.Container(height=4),
                    ft.Text(ozet if ozet else "Yapay zeka grafiği analiz etti. Detaylı yorum yukarıdaki kademe tahminlerinde.",
                           font_family=FONT_SORA, size=12, color=TXT2),
                ]),
                bgcolor=f"{BG2}99", border_radius=10,
                border=ft.border.all(1, f"{BLUE}33"),
                padding=ft.padding.all(18),
            ))
            items.append(ft.Container(height=10))

        # ── TEKNİK SEVİYELER ──────────
        teknik = sonuc.get("teknik_veri", {})
        if teknik:
            direnc = teknik.get("direnc_seviyeleri", {})
            destek = teknik.get("destek_seviyeleri", {})
            fib = teknik.get("fibonacci", {})
            items.append(ft.Container(
                content=ft.Column([
                    ft.Text("📐 TEKNİK SEVİYELER (Pivot + Fibonacci)", font_family=FONT_MONO, size=9, weight="w700", color=TXT3, letter_spacing=1),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Column([
                            ft.Text("🔥 DİRENÇLER", font_family=FONT_MONO, size=8, color=RED, weight="w600"),
                            ft.Text(f"R3: {direnc.get('r3', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                            ft.Text(f"R2: {direnc.get('r2', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                            ft.Text(f"R1: {direnc.get('r1', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                        ], spacing=2, expand=True),
                        ft.Column([
                            ft.Text("🛡️ DESTEKLER", font_family=FONT_MONO, size=8, color=GREEN, weight="w600"),
                            ft.Text(f"S1: {destek.get('s1', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                            ft.Text(f"S2: {destek.get('s2', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                            ft.Text(f"S3: {destek.get('s3', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                        ], spacing=2, expand=True),
                        ft.Column([
                            ft.Text("📊 FIBONACCI", font_family=FONT_MONO, size=8, color=BLUE, weight="w600"),
                            ft.Text(f"0.382: {fib.get('0_382', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                            ft.Text(f"0.500: {fib.get('0_500', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                            ft.Text(f"0.618: {fib.get('0_618', 0):.2f}", font_family=FONT_MONO, size=11, color=TXT2),
                        ], spacing=2, expand=True),
                        ft.Column([
                            ft.Text(f"📈 En Yüksek", font_family=FONT_MONO, size=8, color=TXT3, weight="w600"),
                            ft.Text(f"{teknik.get('en_yuksek_seviye', 0):.2f}", font_family=FONT_MONO, size=13, weight="w700", color=TXT1),
                            ft.Text(f"Pivot: {teknik.get('pivot', 0):.2f}", font_family=FONT_MONO, size=10, color=TXT3),
                        ], spacing=2, expand=True),
                    ], spacing=8),
                ]),
                bgcolor=f"{BG1}cc", border_radius=10,
                border=ft.border.all(1, f"{BORDER}44"),
                padding=ft.padding.all(18),
            ))

        # ── Yenile butonu ──────────
        items.append(ft.Container(height=12))
        items.append(ft.FilledButton(
            content=ft.Text("🔄 Canlı Veriyi Güncelle", font_family=FONT_MONO, size=10, weight="w600"),
            style=ft.ButtonStyle(
                color=BG0, bgcolor=BLUE,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self._analiz_canli_guncelle,
        ))

        return ft.Column(items, spacing=0, scroll="always")


    def _analiz_canli_takip_baslat(self):
        """Canlı veri takibini başlat (30 saniyede bir güncelleme)."""
        if self.analiz_canli_timer:
            return  # Zaten çalışıyor

        def guncelle():
            while self.analiz_calisiyor or True:
                try:
                    if self.analiz_hisse_kodu:
                        canli = canli_veriyi_guncelle(self.analiz_hisse_kodu)
                        if self.analiz_sonuc:
                            self.analiz_sonuc["canli_veri"] = canli
                            self.analiz_sonuc_container.content = self._analiz_sonuc_karti(self.analiz_sonuc)
                            if self.content_area.page:
                                self.analiz_sonuc_container.update()
                except:
                    pass
                time.sleep(30)  # 30 saniye bekle

        self.analiz_canli_timer = threading.Thread(target=guncelle, daemon=True)
        self.analiz_canli_timer.start()


    def _analiz_canli_guncelle(self, e):
        """Canlı veriyi manuel güncelle."""
        if self.analiz_hisse_kodu:
            try:
                canli = canli_veriyi_guncelle(self.analiz_hisse_kodu)
                if self.analiz_sonuc:
                    self.analiz_sonuc["canli_veri"] = canli
                self.analiz_sonuc_container.content = self._analiz_sonuc_karti(self.analiz_sonuc)
                self.analiz_sonuc_container.update()
            except Exception as ex:
                self._analiz_hata_goster(f"Güncelleme hatası: {ex}")


    def _background_data_load(self):
        """Arka planda verileri yükle."""
        try:
            idx = fetch_indices()
            macro = fetch_macro()
            bist = get_price_list(["THYAO.IS","GARAN.IS","ASELS.IS","KCHOL.IS","TUPRS.IS"])
            us = get_price_list(["AAPL","NVDA","TSLA","MSFT","AMZN"])
            bist.sort(key=lambda x: abs(x["degisim"]), reverse=True)
            us.sort(key=lambda x: abs(x["degisim"]), reverse=True)

            self.indices_data = idx
            self.macro_data = macro
            self.bist_data = bist
            self.us_data = us
            self.loading = False

            # UI'yi güncelle
            if self.content_area.page:
                self.switch_tab(self.active_tab)
        except Exception as e:
            print(f"Veri yükleme hatası: {e}")
            self.loading = False


# ══════════════════════════════════════════════════════════════════════
#  BAŞLAT
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        app = BorsaSinyalApp()
        ft.app(
            target=app.main,
            name="BorsaSinyal Pro",
            view=ft.AppView.FLET_APP,
        )
    except Exception as e:
        # Fallback: düz web sunucusu
        print(f"Flet GUI başlatılamadı: {e}")
        print("Web tarayıcıda başlatılıyor...")
        app = BorsaSinyalApp()
        ft.app(
            target=app.main,
            view=ft.AppView.WEB_BROWSER,
            port=8573,
        )