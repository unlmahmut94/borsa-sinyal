# ══════════════════════════════════════════════════════════════════════
#  mod_yardim.py — Yardım sekmesi, SSS, kullanım kılavuzu · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
from datetime import datetime
from mod_gostergeler import gosterge_referansi, sinyal_aciklamalari


def yardim_paneli():
    st.markdown("""
    <div class="fade-in" style="padding:28px 0 4px 0;">
      <span style="font-family:'Sora','Outfit',sans-serif;font-size:28px;font-weight:800;
                   color:var(--txt1);letter-spacing:-.03em;">
        Yardım <span style="color:var(--gold);">& Destek</span>
      </span>
      <div style="height:1px;background:linear-gradient(90deg,var(--gold-d),rgba(184,136,42,0.2),transparent);
                  margin:14px 0 22px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    y1, y2 = st.columns(2)

    with y1:
        st.markdown('<span class="section-label">Kullanım Kılavuzu</span>', unsafe_allow_html=True)
        for baslik, icerik in [
            ("Piyasa Taraması",
             "Sol paneldeki Tarama Parametreleri bölümünü açın. "
             "Borsa, periyot ve filtreler seçtikten sonra TARA butonuna basın."),
            ("Hisse Analizi",
             "Dashboard'daki herhangi bir hisse satırına tıklayın ya da "
             "Hisse Analizi sekmesinde arama yapın. GRAFİK/TEKNİK/HABERLER sekmeleri açılır."),
            ("Mum Aralığı Seçimi",
             "Grafik panelinde Mum Aralığı açılır menüsünden "
             "1 dakikadan aylığa kadar 9 farklı zaman dilimi seçebilirsiniz."),
            ("Portföy",
             "Portföy sekmesinde hisse, adet, alış fiyatı ve tarih girerek "
             "pozisyonlarınızı takip edin. Kar/zarar otomatik hesaplanır."),
            ("Gösterge Ekleme",
             "Grafik sekmesindeki sol panelden istediğiniz göstergeleri seçin. "
             "Maksimum 4 alt panel aynı anda gösterilebilir."),
            ("Çizim Araçları",
             "Grafik üzerinde trend çizgisi, Fibonacci, dikdörtgen gibi araçlar "
             "sol araç çubuğundan seçilebilir."),
        ]:
            st.markdown(
                f'<div class="help-card"><div class="help-title">{baslik}</div>'
                f'<div class="help-text">{icerik}</div></div>',
                unsafe_allow_html=True
            )

    with y2:
        sinyal_aciklamalari()

        st.markdown('<span class="section-label">SSS</span>', unsafe_allow_html=True)
        for soru, cevap in [
            ("BIST için neden .IS ekliyorum?",
             "Yahoo Finance TR sembollerini .IS uzantısıyla tanır: THYAO.IS, GARAN.IS gibi."),
            ("Tarama ne kadar sürer?",
             "BIST 2-4 dk, S&P 500 3-5 dk, Hepsi 8-15 dk sürebilir."),
            ("Sinyaller güvenilir mi?",
             "Teknik indikatörlere dayalı matematiksel hesaplamalardır. Finansal tavsiye değildir."),
            ("Portföy nerede saklanır?",
             "Yerel portfoy.json dosyasına kaydedilir. Buluta gönderilmez."),
            ("Haberler neden İngilizce geliyor?",
             "Yahoo Finance haberleri İngilizce sağlar. deep-translator kuruluysa otomatik çevrilir."),
        ]:
            with st.expander(soru):
                st.markdown(
                    f"<div style='font-family:Sora,sans-serif;font-size:12px;font-weight:300;"
                    f"color:var(--txt2);line-height:1.7;padding:8px 0;'>{cevap}</div>",
                    unsafe_allow_html=True
                )

    # ── FOTOĞRAF / GÖRSEL DESTEK YÜKLEME ──
    st.markdown("""
    <div class="fade-in" style="padding:28px 0 4px 0;">
      <span style="font-family:'Sora','Outfit',sans-serif;font-size:28px;font-weight:800;
                   color:var(--txt1);letter-spacing:-.03em;">
        📷 Görsel <span style="color:var(--gold);">Destek</span>
      </span>
      <div style="font-size:12px;color:var(--txt3);margin-top:6px;">
        Sorun giderme, hata raporu veya önerileriniz için ekran görüntüsü yükleyin
      </div>
      <div style="height:1px;background:linear-gradient(90deg,var(--gold-d),rgba(184,136,42,0.2),transparent);
                  margin:14px 0 22px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    g1, g2 = st.columns([2, 3])

    with g1:
        uploaded_file = st.file_uploader(
            "Ekran görüntüsü veya görsel seçin",
            type=["png", "jpg", "jpeg", "gif", "webp"],
            accept_multiple_files=False,
            key="yardim_resim_yukle",
            help="Destek almak istediğiniz konuyla ilgili bir görsel yükleyin (PNG, JPG, GIF)"
        )

        if uploaded_file is not None:
            # Dosya bilgilerini göster
            file_size_kb = len(uploaded_file.getvalue()) / 1024
            st.markdown(f"""
            <div style="background:rgba(10,18,36,0.6);border:1px solid rgba(77,184,255,0.15);
                        border-radius:8px;padding:12px;margin-top:8px;">
              <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--gold);">
                📎 {uploaded_file.name}
              </div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--txt3);margin-top:4px;">
                {file_size_kb:.1f} KB · {uploaded_file.type or "bilinmiyor"}
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Açıklama alanı
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            foto_aciklama = st.text_area(
                "Açıklama (isteğe bağlı)",
                placeholder="Görselle ilgili kısa bir açıklama yazın...",
                key="yardim_resim_aciklama",
                label_visibility="collapsed",
                max_chars=500,
                height=80
            )

            # Gönder butonu
            if st.button("📤 GÖNDER", key="yardim_resim_gonder", use_container_width=True):
                st.success("✅ Görseliniz başarıyla alındı! En kısa sürede değerlendirilecektir.")
                st.balloons()

    with g2:
        st.markdown('<span class="section-label">Ne tür görseller yükleyebilirsiniz?</span>', unsafe_allow_html=True)
        for ornek_baslik, ornek_icerik in [
            ("🐞 Hatalar & Çökmeler",
             "Uygulamada karşılaştığınız hata mesajlarının ekran görüntüsü"),
            ("📊 Grafik Sorunları",
             "Yanlış görünen grafik, eksik veri veya garip indikatör davranışları"),
            ("⚙️ Kurulum & Konfigürasyon",
             "Config dosyaları, bat dosyası hataları veya Python kurulum sorunları"),
            ("💡 Öneriler",
             "Yeni özellik fikirleri, tasarım iyileştirmeleri veya UX önerileri"),
        ]:
            st.markdown(
                f'<div class="help-card"><div class="help-title">{ornek_baslik}</div>'
                f'<div class="help-text">{ornek_icerik}</div></div>',
                unsafe_allow_html=True
            )

        st.markdown("""
        <div style="background:rgba(240,192,64,0.05);border:1px solid rgba(240,192,64,0.15);
                    border-radius:8px;padding:14px;margin-top:10px;">
          <div style="font-family:'Sora',sans-serif;font-size:11px;color:var(--txt2);line-height:1.6;">
            ⚠️ Yüklediğiniz görseller yerel tarayıcınızda saklanır, 
            sunucuya gönderilmez. Görsel önizlemesi sadece sizin tarafınızdan görülebilir.
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    gosterge_referansi()

    st.markdown(f"""
    <div style="text-align:center;padding:28px 0 10px 0;">
      <div style="font-family:'Sora',sans-serif;font-size:10px;font-weight:300;color:var(--txt3);">
        BorsaSinyal Pro Terminal · v3.1 · {datetime.now().year}
      </div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--txt3);
                  letter-spacing:.16em;margin-top:4px;text-transform:uppercase;">
        Veri: Yahoo Finance · Bu uygulama finansal tavsiye vermez
      </div>
    </div>
    """, unsafe_allow_html=True)