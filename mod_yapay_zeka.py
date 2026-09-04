# ══════════════════════════════════════════════════════════════════════
#  mod_yapay_zeka.py — ML Yön ve Fiyat Tahmin Motoru (XGBoost v2.0)
#  Yeni: 50+ özellik, piyasa rejimi, walk-forward validation, 
#        Kelly pozisyon, geri bildirim döngüsü
# ══════════════════════════════════════════════════════════════════════

from mod_ml_egitim import (
    AnaMLMotor, PiyasaRejimi, FeatureEngineer, MLModel, 
    WalkForwardValidator, get_motor, ml_tahmin_et, ml_hata_analizi_yap
)
import pandas as pd
import numpy as np
from datetime import datetime

def yapay_zeka_tahmin_et(hisse_kodu: str, hedef_gun: int = 5, guncel_haber_puani: float = 0):
    """
    Yeni ML motoru ile hisse tahmini yapar.
    Eski arayüz ile tam uyumlu.
    
    Parametreler:
        hisse_kodu: THYAO.IS, AAPL vb.
        hedef_gun: 5, 10, 20 (varsayılan: 5)
        guncel_haber_puani: 0-100 haber skoru (opsiyonel)
    
    Dönüş: (dict, str) — (sonuç, mesaj)
        - Başarılı: ({
            'Olasilik': float,
            'Karar': str,
            'Gecmis_Basari': float,
            'Etkenler': DataFrame,
            'Guncel_Fiyat': float,
            'Tahmini_Fiyat': float,
            'Fiyat_Alt_Bant': float,
            'Fiyat_Ust_Bant': float
        }, "Başarılı")
        - Başarısız: (None, "hata mesajı")
    """
    try:
        motor = get_motor()
        sonuc = motor.olasilik_tahmin_et(hisse_kodu, hedef_gun)
        
        if sonuc.get('regime') == 'FALLBACK':
            # Eğer ML modeli henüz eğitilmemişse, eski RandomForest yöntemini dene
            return _eski_yontem_ile_tahmin(hisse_kodu, hedef_gun)
        
        # Yeni ML motoru sonucunu eski arayüze çevir
        from sklearn.metrics import accuracy_score
        
        # Etkenler DataFrame'i oluştur
        if sonuc.get('feature_importance'):
            onem_dict = sonuc['feature_importance']
            keys = list(onem_dict.keys())[:4]
            etken_df = pd.DataFrame({
                "Faktör": [k.replace('_', ' ').title() for k in keys],
                "Önem": [onem_dict[k] * 100 for k in keys]
            })
        else:
            etken_df = pd.DataFrame({
                "Faktör": ["ML Model (XGBoost)", "Piyasa Rejimi", "Volatilite", "Momentum"],
                "Önem": [40, 30, 20, 10]
            })
        
        # Geçmiş başarı oranı
        model_metrik = sonuc.get('model_metrikleri', {})
        gecmis_basari = 50.0
        if 'validasyon' in model_metrik:
            gecmis_basari = model_metrik['validasyon'].get('accuracy', 0.5) * 100
        elif 'egitim' in model_metrik:
            gecmis_basari = model_metrik['egitim'].get('accuracy', 0.5) * 100
        
        # Haber puanını entegre et
        if guncel_haber_puani > 0:
            olasilik = sonuc['olasilik']
            haber_agirlik = 0.15  # Haberlerin %15 ağırlığı
            olasilik = olasilik * (1 - haber_agirlik) + guncel_haber_puani * haber_agirlik
            sonuc['olasilik'] = min(99.0, max(1.0, olasilik))
        
        geri_don = {
            "Olasilik": sonuc['olasilik'],
            "Karar": sonuc['karar'],
            "Gecmis_Basari": round(gecmis_basari, 1),
            "Etkenler": etken_df,
            "Guncel_Fiyat": sonuc['guncel_fiyat'],
            "Tahmini_Fiyat": sonuc['tahmini_fiyat'],
            "Fiyat_Alt_Bant": sonuc['alt_bant'],
            "Fiyat_Ust_Bant": sonuc['ust_bant'],
            "Kelly_Pozisyon": sonuc.get('kelly_pozisyon', 0),
            "Piyasa_Rejimi": sonuc.get('regime', 'NORMAL'),
            "Guven_Seviyesi": "YÜKSEK" if gecmis_basari > 65 else "ORTA" if gecmis_basari > 50 else "DÜŞÜK"
        }
        
        return geri_don, "Başarılı"
        
    except Exception as e:
        # Hata durumunda fallback
        return _eski_yontem_ile_tahmin(hisse_kodu, hedef_gun)


def _eski_yontem_ile_tahmin(hisse_kodu, hedef_gun=5):
    """Eski RandomForest yöntemi (fallback) - Çok kaynaklı veri ile."""
    try:
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.metrics import accuracy_score
    except ImportError:
        return None, "Makine öğrenmesi kütüphanesi eksik."
    
    try:
        # ═══ Çok kaynaklı veri çek ═══
        from mod_veri_kaynagi import veri_cek as coklu_veri_cek
        df = coklu_veri_cek(hisse_kodu, period="3y")
        
        if df is None or df.empty or len(df) < 50:
            return None, "Yeterli veri yok."
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df['Getiri'] = df['Close'].pct_change()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Fiyat_MA20_Fark'] = (df['Close'] - df['MA20']) / df['MA20']
        df['Volatilite'] = df['Getiri'].rolling(window=10).std()
        
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        df.dropna(subset=['Getiri', 'Fiyat_MA20_Fark', 'Volatilite', 'RSI'], inplace=True)
        
        if len(df) < 100:
            return None, "Yeterli temiz veri kalmadı."
        
        X_guncel = df[['Getiri', 'Fiyat_MA20_Fark', 'Volatilite', 'RSI']]
        son_veri = X_guncel.iloc[-1:].copy()
        guncel_fiyat = float(df['Close'].iloc[-1])
        son_volatilite = float(df['Volatilite'].iloc[-1])
        
        df['Gelecek_Fiyat'] = df['Close'].shift(-hedef_gun)
        df['Gelecek_Getiri'] = (df['Gelecek_Fiyat'] - df['Close']) / df['Close']
        df['Hedef_Yon'] = (df['Gelecek_Fiyat'] > df['Close']).astype(int)
        df_train = df.dropna(subset=['Gelecek_Fiyat', 'Gelecek_Getiri'])
        
        X_full = df_train[['Getiri', 'Fiyat_MA20_Fark', 'Volatilite', 'RSI']]
        y_yon = df_train['Hedef_Yon']
        y_getiri = df_train['Gelecek_Getiri']
        
        split = int(len(df_train) * 0.8)
        X_tr, X_te = X_full.iloc[:split], X_full.iloc[split:]
        y_t, y_v = y_yon.iloc[:split], y_yon.iloc[split:]
        
        clf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
        clf.fit(X_tr, y_t)
        reg = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=5)
        reg.fit(X_tr, y_getiri.iloc[:split])
        
        acc = accuracy_score(y_v, clf.predict(X_te)) * 100
        proba = clf.predict_proba(son_veri)[0]
        yukselis = proba[1] * 100
        tahmini_getiri = float(reg.predict(son_veri)[0])
        
        if (yukselis >= 50 and tahmini_getiri < 0) or (yukselis < 50 and tahmini_getiri > 0):
            yon = 1 if yukselis >= 50 else -1
            tahmini_getiri = yon * abs(son_volatilite * np.sqrt(hedef_gun) * 0.5)
        
        tahmini_f = guncel_fiyat * (1 + tahmini_getiri)
        sapma = guncel_fiyat * son_volatilite * np.sqrt(hedef_gun)
        
        karar = "GÜÇLÜ YÜKSELİŞ" if yukselis >= 65 else \
                "YÜKSELİŞ" if yukselis >= 50 else \
                "DÜŞÜŞ" if yukselis >= 35 else "GÜÇLÜ DÜŞÜŞ"
        
        etkenler = pd.DataFrame({
            "Faktör": ["Fiyat İvmesi", "Trend Sapması", "Volatilite", "RSI"],
            "Önem": clf.feature_importances_ * 100
        })
        
        return {
            "Olasilik": yukselis,
            "Karar": karar,
            "Gecmis_Basari": round(acc, 1),
            "Etkenler": etkenler,
            "Guncel_Fiyat": guncel_fiyat,
            "Tahmini_Fiyat": tahmini_f,
            "Fiyat_Alt_Bant": tahmini_f - sapma,
            "Fiyat_Ust_Bant": tahmini_f + sapma
        }, "Başarılı (Fallback)"
    
    except Exception as e:
        return None, f"Veri işleme hatası: {str(e)}"


def hata_analizi_raporu() -> str:
    """
    Kapanan işlemleri analiz eder ve rapor döndürür.
    mod_yz_karnesi.py tarafından kullanılır.
    """
    try:
        rapor = ml_hata_analizi_yap()
        if 'hata' in rapor:
            return f"⚠️ {rapor['hata']}"
        
        ozet = f"""📊 **ML ÖĞRENME RAPORU**
━━━━━━━━━━━━━━━━━━━━━━━
📈 Toplam İşlem: {rapor.get('toplam_islem', 0)}
✅ Başarılı: {rapor.get('basarili', 0)}
❌ Başarısız: {rapor.get('basarisiz', 0)}
📊 Win Rate: %{rapor.get('win_rate', 0)}
📉 Son 20 İşlem: %{rapor.get('son_20_win_rate', 0)}
🔄 Trend: {rapor.get('trend', 'STABİL')}
🛠️ Model: {rapor.get('model_guncelleme', 'Gerek yok')}"""
        return ozet
    except Exception as e:
        return f"⚠️ Rapor alınamadı: {str(e)}"


def modeli_egit(hisse_kodu: str = "THYAO.IS") -> dict:
    """
    Yeni ML modelini eğitir.
    Doğrudan Python'dan çağrılabilir.
    """
    motor = get_motor()
    sonuc = motor.rejime_gore_egit(hisse_kodu, force_retrain=True)
    return sonuc


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  XGBoost ML Tahmin Motoru Test")
    print("=" * 60)
    
    sonuc, mesaj = yapay_zeka_tahmin_et("THYAO.IS", hedef_gun=5)
    if sonuc:
        print(f"✓ Hisse: THYAO.IS")
        print(f"✓ Olasılık: %{sonuc['Olasilik']:.1f}")
        print(f"✓ Karar: {sonuc['Karar']}")
        print(f"✓ Güncel Fiyat: {sonuc['Guncel_Fiyat']:.2f} TL")
        print(f"✓ Tahmini Fiyat: {sonuc['Tahmini_Fiyat']:.2f} TL")
        print(f"✓ Geçmiş Başarı: %{sonuc['Gecmis_Basari']:.1f}")
        if 'Kelly_Pozisyon' in sonuc:
            print(f"✓ Kelly Pozisyon: %{sonuc['Kelly_Pozisyon']:.1f}")
        if 'Piyasa_Rejimi' in sonuc:
            print(f"✓ Piyasa Rejimi: {sonuc['Piyasa_Rejimi']}")
    else:
        print(f"✗ Hata: {mesaj}")
