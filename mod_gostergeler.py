# ══════════════════════════════════════════════════════════════════════
#  mod_gostergeler.py — Gösterge rehberi ve açıklamaları · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════

import streamlit as st


def gosterge_referansi():
    """Gösterge rehberi — tüm teknik indikatörlerin açıklamaları."""
    st.markdown('<span class="section-label">Gösterge Rehberi</span>', unsafe_allow_html=True)
    gostergeler = [
        ("RSI — Göreceli Güç Endeksi",
         "0–100 arası osilatör. <b style='color:#0fdb7a'>30 altı</b> aşırı satım (AL fırsatı), "
         "<b style='color:#ff3b5c'>70 üstü</b> aşırı alım (SAT sinyali). 14 günlük periyot."),
        ("MACD — Hareketli Ort. Yakınsama/Iraksama",
         "MACD sinyal çizgisini <b style='color:#0fdb7a'>yukarı keserse güçlü AL</b>, "
         "<b style='color:#ff3b5c'>aşağı keserse SAT</b> sinyali. 12/26/9 EMA."),
        ("Bollinger Bantları",
         "20 günlük MA ± 2σ. Fiyat <b style='color:#0fdb7a'>alt banda</b> değerse AL, "
         "<b style='color:#ff3b5c'>üst banda</b> değerse SAT sinyali. Bant daralması kırılımı işaret eder."),
        ("ADX / DI+/DI- — Yönlü Hareket",
         "<b style='color:#d4a843'>ADX>25</b> → güçlü trend mevcut. "
         "DI+>DI- → yükseliş trendi. DI->DI+ → düşüş trendi."),
        ("Stochastic Osilatör %K/%D",
         "Kapanışı son N günün aralığına göre konumlandırır. "
         "<b style='color:#0fdb7a'>20 altı AS</b>, <b style='color:#ff3b5c'>80 üstü AA</b>."),
        ("CCI — Emtia Kanal Endeksi",
         "Fiyatın istatistiksel ortalamasından sapması. "
         "<b style='color:#0fdb7a'>-100 altı</b> aşırı satım, <b style='color:#ff3b5c'>+100 üstü</b> aşırı alım."),
        ("Williams %R",
         "-100 ile 0 arası. <b style='color:#0fdb7a'>-80 altı</b> aşırı satım, "
         "<b style='color:#ff3b5c'>-20 üstü</b> aşırı alım."),
        ("MFI — Para Akışı Endeksi (Hacim RSI)",
         "Hacim ağırlıklı RSI. <b style='color:#0fdb7a'>20 altı</b> aşırı satım, "
         "<b style='color:#ff3b5c'>80 üstü</b> aşırı alım."),
        ("Boğa/Ayı Gücü (Elder Ray)",
         "<b style='color:#0fdb7a'>Boğa Gücü</b> = Yüksek - EMA13. Pozitifse alıcılar güçlü. "
         "<b style='color:#ff3b5c'>Ayı Gücü</b> = Düşük - EMA13. Negatifse satıcılar güçlü."),
        ("OBV — Denkleme Göre Hacim",
         "Fiyat artışında hacim eklenir, düşüşte çıkarılır. "
         "OBV artarken fiyat duruyorsa yükseliş sinyali. Diverjans önemlidir."),
        ("ATR — Gerçek Aralık Ortalaması",
         "Volatilite ölçüsü. Büyük ATR → yüksek volatilite. "
         "Stop-loss ve pozisyon boyutlandırmada kullanılır."),
        ("Parabolic SAR",
         "Fiyatın altında nokta → yükseliş trendi. Üstünde nokta → düşüş trendi. "
         "Trend dönüşlerini yakalamak için kullanılır."),
        ("Ichimoku Bulutu",
         "Tenkan > Kijun → yükseliş. Fiyat bulutun üzerinde → güçlü yükseliş trendi. "
         "Chikou açıkta → trend devam. 5 elemanlı kapsamlı sistem."),
        ("ROC — Değişim Hızı",
         "N gün öncesine göre yüzde değişim. 0 üzeri ivme kazanılıyor, altı ivme kaybediliyor."),
        ("VWAP — Hacim Ağırlıklı Ort. Fiyat",
         "Gün içi işlemlerde kurumsal yatırımcıların referans fiyatı. "
         "Fiyat VWAP üstündeyse güçlü, altındaysa zayıf konumda."),
        ("EMA — Üstel Hareketli Ortalama",
         "Son fiyatlara daha fazla ağırlık verir. EMA9/21 kesişimi kısa vadeli dönüşleri gösterir. "
         "MA'ya göre daha hızlı tepki verir."),
        ("MA — Basit Hareketli Ortalama",
         "Seçilen periyottaki kapanışların ortalaması. MA20/50/200 temel destek/direnç seviyeleridir. "
         "Golden Cross (MA50>MA200) güçlü yükseliş sinyalidir."),
        ("Momentum",
         "N gün öncesine göre fiyat değişimi. 0 üzeri yükseliş momentumu, altı düşüş momentumu. "
         "Sıfır çizgisi kesişimi sinyal üretir."),
    ]
    c1, c2 = st.columns(2)
    for i, (baslik, icerik) in enumerate(gostergeler):
        with (c1 if i % 2 == 0 else c2):
            st.markdown(
                f'<div class="help-card" style="margin:4px 0;">'
                f'<div class="help-title" style="font-size:12px;">{baslik}</div>'
                f'<div class="help-text" style="font-size:11px;">{icerik}</div></div>',
                unsafe_allow_html=True
            )


def sinyal_aciklamalari():
    """Sinyal sistemi renk ve skor açıklamaları."""
    st.markdown('<span class="section-label">Sinyal Sistemi</span>', unsafe_allow_html=True)
    for renk, bg, sinyal, aciklama in [
        ("#0fdb7a", "rgba(11,121,61,0.15)", "GÜÇLÜ AL", "Skor >= +5, Tüm indikatörler pozitif hizalanmış"),
        ("#f5cc6a", "rgba(160,120,30,0.12)", "AL",        "Skor +2 ile +4, Çoğunluk olumlu sinyal veriyor"),
        ("#8a9bb5", "rgba(100,120,150,0.10)", "NÖTR",     "Skor -1/+1, Karışık sinyaller, bekle"),
        ("#ff8c42", "rgba(180,90,30,0.12)", "SAT",        "Skor -2 ile -4, Çoğunluk olumsuz sinyal"),
        ("#ff3b5c", "rgba(155,31,53,0.15)", "GÜÇLÜ SAT", "Skor <= -5, Tüm indikatörler negatif hizalanmış"),
    ]:
        st.markdown(
            f'<div class="fade-in" style="background:{bg};border:1px solid {renk}33;border-radius:8px;'
            f'padding:12px 18px;margin:6px 0;display:flex;align-items:center;gap:14px;'
            f'backdrop-filter:blur(8px);">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:13px;'
            f'font-weight:700;color:{renk};min-width:120px;">{sinyal}</span>'
            f'<span style="font-family:Sora,sans-serif;font-size:11px;'
            f'font-weight:300;color:{renk}cc;line-height:1.5;">{aciklama}</span></div>',
            unsafe_allow_html=True
        )