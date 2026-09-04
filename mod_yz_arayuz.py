# ══════════════════════════════════════════════════════════════════════
#  mod_yz_arayuz.py — Yapay Zeka (ML) · v3.1 ✨
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
from mod_animasyon import bolum_baslik
from hisse_isimleri import HISSE_ISIMLERI


def render_yz_arayuz():
    bolum_baslik(
        "Yapay Zeka (ML) Yön Tahmin Motoru",
        "Makine öğrenmesi algoritmaları ile farklı periyotlar için olasılık analizi",
        bg_url="https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=1200&auto=format&fit=crop"
    )
    c_yz1, c_yz2 = st.columns([1, 3])
    with c_yz1:
        hisse_secenekleri = [f"{sembol} - {isim}" for sembol, isim in HISSE_ISIMLERI.items()]
        populerler = [
            "THYAO.IS - Türk Hava Yolları", "AAPL - Apple Inc.",
            "GARAN.IS - Garanti BBVA Bankası", "NVDA - NVIDIA Corporation",
            "KCHOL.IS - Koç Holding"
        ]
        kalanlar = [h for h in hisse_secenekleri if h not in populerler]
        arama_listesi = populerler + ["--- DİĞER TÜM HİSSELER ---"] + kalanlar

        yz_secim = st.selectbox(
            "Hisse Ara veya Seç:", options=arama_listesi,
            index=None, placeholder="🔍 Aramak için tıklayın...", key="yz_hisse_smart"
        )
        yz_hisse = yz_secim.split(" - ")[0] if yz_secim and "---" not in yz_secim else None

        periyot_secenekleri = {
            "1 Saat (Gün İçi)": 1, "3 Saat (Gün İçi)": 3,
            "1 Gün": 1, "1 Hafta": 5, "2 Hafta": 10,
            "1 Ay": 21, "3 Ay": 63, "6 Ay": 126,
            "1 Yıl": 252, "3 Yıl": 756, "5 Yıl": 1260
        }
        yz_periyot_etiket = st.selectbox("Tahmin Periyodu (Vade):", list(periyot_secenekleri.keys()))
        hedef_gun = periyot_secenekleri[yz_periyot_etiket]

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        yz_baslat = st.button("🤖 MODELİ EĞİT VE TAHMİN ET", use_container_width=True, type="primary")

    with c_yz2:
        if yz_baslat:
            if not yz_hisse:
                st.warning("⚠️ Lütfen tahmine başlamadan önce sol taraftan geçerli bir hisse seçin!")
            else:
                with st.spinner(f"{yz_hisse} için {yz_periyot_etiket} verileri işleniyor... (Bu işlem biraz sürebilir)"):
                    try:
                        from mod_yapay_zeka import yapay_zeka_tahmin_et
                        ml_sonuc, mesaj = yapay_zeka_tahmin_et(
                            yz_hisse, hedef_gun=hedef_gun, guncel_haber_puani=0
                        )

                        if ml_sonuc:
                            olasilik = ml_sonuc['Olasilik']
                            renk = "#0fdb7a" if olasilik >= 50 else "#ff3b5c"
                            yon_metni = "YÜKSELİŞ" if olasilik >= 50 else "DÜŞÜŞ"
                            gosterilen_oran = olasilik if olasilik >= 50 else (100 - olasilik)

                            guncel = ml_sonuc.get("Guncel_Fiyat", 0)
                            hedef_fiyat = ml_sonuc.get("Tahmini_Fiyat", 0)
                            alt_bant = ml_sonuc.get("Fiyat_Alt_Bant", 0)
                            ust_bant = ml_sonuc.get("Fiyat_Ust_Bant", 0)

                            getiri_yuzde = ((hedef_fiyat - guncel) / guncel) * 100 if guncel > 0 else 0
                            getiri_renk = "#0fdb7a" if getiri_yuzde >= 0 else "#ff3b5c"
                            getiri_ok = "▲" if getiri_yuzde >= 0 else "▼"

                            st.markdown(f"""
                            <div class="fade-in glass-card" style="padding:24px;border:1px solid rgba(255,255,255,0.06);">
                                <div style="font-family:'Sora',sans-serif;font-size:18px;font-weight:700;
                                            color:var(--txt1);margin-bottom:20px;">
                                  📊 Tahmin Özeti: {yz_hisse} ({yz_periyot_etiket})
                                </div>
                                <div style="display:flex;gap:16px;flex-wrap:wrap;">
                                  <div style="flex:1;min-width:220px;background:rgba(0,0,0,0.15);
                                              padding:18px;border-radius:10px;border-left:4px solid {renk};">
                                    <div style="font-size:10px;color:var(--txt3);letter-spacing:.1em;
                                                font-family:'JetBrains Mono',monospace;">
                                      MODELİN BEKLEDİĞİ YÖN</div>
                                    <div style="font-size:26px;font-weight:800;color:{renk};
                                                letter-spacing:-.02em;margin-top:6px;">
                                      {yon_metni} İHTİMALİ: %{gosterilen_oran:.1f}</div>
                                    <div style="font-size:10px;color:var(--txt2);margin-top:6px;opacity:.8;">
                                      Belirlediğiniz vade sonunda fiyatın bugünden daha yüksek/düşük olma ihtimali.</div>
                                  </div>
                                  <div style="flex:1;min-width:220px;background:rgba(0,0,0,0.15);
                                              padding:18px;border-radius:10px;border-left:4px solid var(--gold);">
                                    <div style="font-size:10px;color:var(--txt3);letter-spacing:.1em;
                                                font-family:'JetBrains Mono',monospace;">
                                      YAPAY ZEKA KARARI</div>
                                    <div style="font-size:22px;font-weight:800;color:var(--gold);
                                                letter-spacing:-.02em;margin-top:6px;">
                                      {ml_sonuc['Karar']}</div>
                                    <div style="font-size:10px;color:var(--txt3);margin-top:8px;">
                                      Geçmiş Test Doğruluğu: <b style="color:#eef2f7;">%{ml_sonuc['Gecmis_Basari']}</b></div>
                                  </div>
                                </div>
                                <div style="display:flex;gap:16px;margin-top:16px;flex-wrap:wrap;">
                                  <div style="flex:1;min-width:220px;background:rgba(0,0,0,0.15);
                                              padding:18px;border-radius:10px;border-left:4px solid {getiri_renk};">
                                    <div style="font-size:10px;color:var(--txt3);letter-spacing:.1em;
                                                font-family:'JetBrains Mono',monospace;">
                                      HEDEF FİYAT TAHMİNİ (Regresyon)</div>
                                    <div style="font-size:26px;font-weight:800;color:{getiri_renk};
                                                letter-spacing:-.02em;margin-top:6px;">
                                      {hedef_fiyat:,.2f}
                                      <span style="font-size:14px;opacity:.8;">
                                        ({getiri_ok} %{abs(getiri_yuzde):.2f})</span></div>
                                    <div style="font-size:10px;color:var(--txt2);margin-top:6px;opacity:.8;">
                                      Güncel Fiyat: <b style="color:#eef2f7;">{guncel:,.2f}</b></div>
                                  </div>
                                  <div style="flex:1;min-width:220px;background:rgba(0,0,0,0.15);
                                              padding:18px;border-radius:10px;border-left:4px solid var(--blue);">
                                    <div style="font-size:10px;color:var(--txt3);letter-spacing:.1em;
                                                font-family:'JetBrains Mono',monospace;">
                                      TAHMİNİ FİYAT ARALIĞI (Güven Bandı)</div>
                                    <div style="font-size:22px;font-weight:800;color:var(--txt1);
                                                letter-spacing:-.02em;margin-top:6px;">
                                      {alt_bant:,.2f}
                                      <span style="color:var(--txt3);font-size:14px;font-weight:400;">ile</span>
                                      {ust_bant:,.2f}</div>
                                    <div style="font-size:10px;color:var(--txt2);margin-top:8px;opacity:.8;">
                                      Geçmiş oynaklık verilerine göre modelin hesapladığı olası dalgalanma aralığı.</div>
                                  </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
                            st.markdown(
                                '<span class="section-label">Kararı Etkileyen En Önemli Parametreler (Etki Oranları)</span>',
                                unsafe_allow_html=True
                            )

                            etken_df = ml_sonuc["Etkenler"].sort_values(by="Önem", ascending=False)
                            e_cols = st.columns(len(etken_df))
                            for i, (idx, row) in enumerate(etken_df.iterrows()):
                                with e_cols[i]:
                                    st.markdown(f"""
                                    <div class="fade-in" style="background:linear-gradient(160deg,rgba(10,18,36,0.9),rgba(6,12,26,0.8));
                                                border:1px solid rgba(77,184,255,0.15);border-top:3px solid #4db8ff;
                                                border-radius:10px;padding:18px;height:130px;
                                                display:flex;flex-direction:column;justify-content:space-between;">
                                      <div style="font-family:'Sora',sans-serif;font-size:12px;color:var(--txt2);
                                                  line-height:1.4;">
                                        {row['Faktör']}
                                      </div>
                                      <div style="font-family:'JetBrains Mono',monospace;font-size:28px;
                                                  color:var(--txt1);font-weight:800;letter-spacing:-.02em;">
                                        %{row['Önem']:.1f}
                                      </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.error(mesaj)
                    except Exception as e:
                        st.error(f"Yapay zeka modülü çalıştırılamadı: {e}")