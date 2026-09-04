# 🔬 HİSSEYE ÖZEL UZMANLAR (Per-Stock Model Architecture)

## 📋 Yapılacak Değişiklikler Listesi

1. `mod_ml_egitim.py` içinde `AnaMLMotor` sınıfını yeniden yapılandır
2. Her hisse için ayrı model kaydetme sistemi kur
3. `olasilik_tahmin_et` metodunu hisseye özel model yükleyecek şekilde değiştir
4. `rejime_gore_egit` metodunu hisseye özel model kaydedecek şekilde değiştir
5. Incremental learning döngüsünü hisseye özel modellerle uyumlu hale getir
6. Tüm sinyal/indikatör/grafik materyali için ayrı öğrenme sağla

## 📐 Mimari Değişiklik

### ESKİ SİSTEM (Genel Uzman - Şu anki)
```
active_models = {
    "TREND": model_trend.pkl,    # TÜM hisseler için aynı!
    "YATAY": model_yatay.pkl,    # TÜM hisseler için aynı!
    "VOLATIL": model_volatil.pkl # TÜM hisseler için aynı!
}
```

### YENİ SİSTEM (Hisseye Özel Uzman)
```
stock_models = {
    "THYAO.IS": {
        "TREND": thyao_trend_model,
        "YATAY": thyao_yatay_model,
        "VOLATIL": thyao_volatil_model
    },
    "GARAN.IS": {
        "TREND": garan_trend_model,
        "YATAY": garan_yatay_model,
        "VOLATIL": garan_volatil_model
    },
    ...
}
```

### Kaydedilen Model Dosyaları
```
modeller/
├── THYAO.IS_TREND.pkl
├── THYAO.IS_YATAY.pkl
├── THYAO.IS_VOLATIL.pkl
├── GARAN.IS_TREND.pkl
├── GARAN.IS_YATAY.pkl
├── GARAN.IS_VOLATIL.pkl
├── AAPL_TREND.pkl
...
```
