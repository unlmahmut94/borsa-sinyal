# Yapılacaklar Listesi

## 1. ❗ KRİTİK: mod_ml_feature_engineer.py → mod_ml_egitim.py entegrasyonu
Durum: `mod_ml_feature_engineer.py` 130+ özellik çıkaran bağımsız bir modül olarak ayrılmış,
ancak `mod_ml_egitim.py`'de hala aynı `FeatureEngineer` sınıfının eski kopyası duruyor.
`mod_yapay_zeka.py` ve diğerleri eski kopyayı kullanıyor.

## 2. 🔶 ORTA: mod_piyasa_takvimi.py → otomatik_tarayici.py entegrasyonu
Durum: Piyasa saat/tatil kontrol motoru yazılmış ama hiçbir yerde kullanılmıyor.
API kotasından %30-40 tasarruf sağlayabilir.

## 3. 🔶 ORTA: mod_korelasyon.py → mod_portfoy.py entegrasyonu
Durum: Korelasyon matrisi ve sektörel risk analizi yapılmış ama kullanılmıyor.

## 4. 🔶 ORTA: mod_sinyal_kalite.py → mod_yz_karnesi.py entegrasyonu
Durum: Sinyal kalite takip motoru yazılmış ama kullanılmıyor.

## 5. ℹ️ DÜŞÜK: Diğer yalıtılmış modüller
- mod_arama.py, mod_hisse_analiz.py, mod_bekleyen_takip.py, mod_paper_trading.py
- mod_pozisyon_yonetimi.py, mod_websocket.py, mod_sinyaller.py
