# BorsaSinyal Pro Terminal v3.1

Çok piyasalı (BIST, NASDAQ, S&P 500, Kripto) teknik ve ML tabanlı sinyal üretim sistemi.

## Özellikler

- **15+ Teknik İndikatör**: RSI, MACD, Bollinger, ADX, CCI, MFI, Williams %R, Stochastic, OBV, ATR, EMA, Ichimoku
- **ML Tahmin Motoru**: XGBoost/LightGBM/CatBoost Ensemble + Walk-Forward Validation + Optuna
- **Otomatik Tarama**: BIST + NASDAQ + S&P 500 + Kripto toplu sinyal taraması
- **Backtest Motoru**: Sharpe, Sortino, Calmar, VaR %95, Monte Carlo, Benchmark karşılaştırması
- **YZ Karnesi**: İşlem geçmişi analizi, Win Rate takibi, Otomatik strateji optimizasyonu
- **Otomatik Eğitim**: Zamanlanmış (22:00) ve sürekli akıllı ML eğitimi
- **Gerçek Zamanlı Fiyat**: Çok kaynaklı (yfinance, Stooq, Binance) veri çekme
- **Ölü Havuz (Dead Pool)**: Delisted hisseleri otomatik filtreleme

## Kurulum

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Streamlit uygulamasını başlat
streamlit run app.py
```

## CLI Kullanımı

```bash
# İnteraktif menü
python main.py

# Tek hisse analizi
python main.py --symbol THYAO.IS --hedef 5

# Toplu tarama
python main.py --auto --borsa BIST

# Backtest
python main.py --backtest THYAO.IS --gun 180

# Son sinyalleri listele
python main.py --sinyaller --adet 20

# Sürekli tarama motoru
python main.py --surekli

# ML eğitim motoru başlat
python main.py --egitim-baslat --tip akilli
```

## Proje Yapısı

```
borsa-sinyal/
├── app.py                    # Streamlit ana uygulama
├── main.py                   # CLI giriş noktası
├── analiz.py                 # Teknik indikatör ve sinyal hesaplama
├── backtest.py               # Gelişmiş strateji test motoru
├── otomatik_tarayici.py      # Sürekli tarama motoru
├── strateji_config.json      # Merkezi yapılandırma (37 parametre)
├── requirements.txt          # Python bağımlılıkları
├── hisseler_bist.py          # BIST hisse listesi
├── hisseler_sp500.py         # S&P 500 hisse listesi
├── hisseler_nasdaq.py        # NASDAQ hisse listesi
├── hisseler_kripto.py        # Kripto coin listesi
├── hisse_isimleri.py         # Hisse isim eşleştirme
├── grafik.py                 # Plotly grafik fonksiyonları
├── modeller/                 # Eğitilmiş ML modelleri (.pkl)
├── logs/                     # Eğitim log dosyaları
├── mod_ml_egitim.py          # ML motoru (XGBoost/LightGBM/CatBoost)
├── mod_yapay_zeka.py         # ML tahmin arayüzü
├── mod_yapay_zeka_karar.py   # YZ strateji analiz + otomatik güncelleme
├── mod_veri_kaynagi.py       # Çok kaynaklı veri çekme
├── mod_veri_servisi.py       # Önbellekli veri servisi
├── mod_hafiza.py             # Sinyal veritabanı (SQLite)
├── mod_guvenlik.py           # Session & rate limit
├── mod_egitim_kontrol.py     # Eğitim kontrol paneli
├── mod_dashboard.py          # Dashboard sekmesi
├── mod_tarama_sekmesi.py     # Piyasa tarama sekmesi
├── mod_yz_arayuz.py          # Yapay Zeka sekmesi
├── mod_yz_karnesi.py         # YZ İşlem Karnesi sekmesi
├── mod_bt_arayuz.py          # Strateji Testi sekmesi
├── mod_detay_paneli.py       # Hisse analiz paneli
├── mod_haberler.py           # Haber çekme ve analiz
├── mod_gorsel.py             # Tema ve CSS
├── mod_animasyon.py          # Geçiş efektleri
├── mod_portfoy.py            # Portföy takibi
├── mod_formasyon.py          # Formasyon tespiti
├── mod_tahminler.py          # Analist tahminleri
├── mod_sirket.py             # Şirket bilgileri
├── mod_gostergeler.py        # Gösterge rehberi
├── mod_yardim.py             # Yardım sekmesi
└── ...
```

## Yapılandırma

Tüm strateji parametreleri `strateji_config.json` içinde:

```json
{
    "stop_loss_yuzde": 0.03,
    "take_profit_yuzde": 0.08,
    "rsi_al_esigi": 30,
    "komisyon_orani": 0.002,
    "slippage_yuzde": 0.001,
    "backtest_varsayilan_sermaye": 10000,
    "backtest_varsayilan_gun": 365
}
```

## ML Eğitim Motoru

2 modda çalışır:

1. **Eski Sistem (22:00)**: Her gece saat 22:00'de günlük hızlı eğitim, 2 günde bir derin Optuna optimizasyonu
2. **Sürekli Akıllı Eğitim**: Güçlü AL sinyalleri → YZ Karnesi → Tüm hisseler öncelik sırasıyla

```bash
# Eski sistemi başlat
python mod_egitim_kontrol.py eski

# Sürekli akıllı eğitimi başlat
python mod_egitim_kontrol.py simdi
```

## Veri Kaynakları

- **BIST/NASDAQ/SP500**: yfinance (öncelikli) → Stooq → Yahoo PDR → Yahoo CSV
- **Kripto**: Binance (ccxt) → yfinance
- **Ölü Havuz**: Delisted hisseler `dead_semboller.json`'a kaydedilir, taramalardan otomatik filtrelenir

## Sinyal Sistemi

15 göstergeli puanlama sistemi:
- Market Yapısı (SMC) - Ağırlık: 3
- Order Block - Ağırlık: 4
- RSI - Ağırlık: 3
- Hareketli Ortalama - Ağırlık: 2
- MACD - Ağırlık: 3
- Bollinger Bantları - Ağırlık: 3
- Stochastic - Ağırlık: 2
- CCI - Ağırlık: 2
- Williams %R - Ağırlık: 2
- MFI - Ağırlık: 2
- ADX - Ağırlık: 2
- OBV - Ağırlık: 2
- ATR - Ağırlık: 1
- Temel Analiz (F/K, PD/DD) - Ağırlık: 1
- NLP Haber Duyarlılığı - Ağırlık: 3

Toplam skor ≥ 10 → GÜÇLÜ AL, 4-9 → AL, -3 ile 3 → NÖTR, -9 ile -4 → SAT, ≤ -10 → GÜÇLÜ SAT

## Gereksinimler

- Python 3.9+
- Streamlit 1.55+
- yfinance 1.4+
- scikit-learn 1.8+, XGBoost 3.2+, LightGBM 4.6+
- pandas-ta (teknik indikatörler)
- Optuna 4.9+ (hiperparametre optimizasyonu)
- Plotly 6.6+ (grafikler)

## Lisans

MIT