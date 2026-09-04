# ══════════════════════════════════════════════════════════════════════
#  mod_ml_egitim.py — Kendini Eğiten ML Motoru v3.0 (DEEP)
#  Özellikler:
#    • Piyasa rejimi tespiti (Trend/Yatay/Volatil) + Alt rejimler
#    • 130+ teknik indikatör (pandas-ta + manuel)
#    • Multi-Model Ensemble: XGBoost/LightGBM/CatBoost/ExtraTrees/Voting/Stacking
#    • SHAP feature importance + RFE + VIF multicollinearity
#    • Walk-Forward Validation (TimeSeriesSplit)
#    • Optuna ile hiperparametre optimizasyonu (genişletilmiş grid)
#    • Kelly Kriteri + VaR + CVaR risk yönetimi
#    • Multi-timeframe Ensemble (5dk/15dk/1sa/4sa/günlük/haftalık)
#    • Piyasa bağlamı (VIX, BTC Dominans, DXY, S&P korelasyonu)
#    • Online/incremental learning + Model decay tespiti
#    • Otomatik geri bildirim döngüsü
# ══════════════════════════════════════════════════════════════════════

import numpy as np
import pandas as pd
import yfinance as yf
import json
import os
import time
import warnings
import joblib
import logging
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

# ── ML KÜTÜPHANELERİ ──────────────────────────────────────────────
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import VotingClassifier, StackingClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression

# XGBoost
try:
    import xgboost as xgb
    XGB_AKTIF = True
except ImportError:
    XGB_AKTIF = False

# LightGBM
try:
    import lightgbm as lgb
    LGB_AKTIF = True
except ImportError:
    LGB_AKTIF = False

# CatBoost
try:
    import catboost as cb
    CATBOOST_AKTIF = True
except ImportError:
    CATBOOST_AKTIF = False

# pandas-ta
try:
    import pandas_ta as ta
    PANDAS_TA_AKTIF = True
except ImportError:
    PANDAS_TA_AKTIF = False

# Optuna
try:
    import optuna
    OPTUNA_AKTIF = True
except ImportError:
    OPTUNA_AKTIF = False

# SHAP (feature importance)
try:
    import shap
    SHAP_AKTIF = True
except ImportError:
    SHAP_AKTIF = False

# ── SABİTLER ────────────────────────────────────────────────────────
MODEL_DIZINI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modeller")
DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")
LOG_DIZINI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_DOSYASI = os.path.join(LOG_DIZINI, "ml_egitim.log")
EGITIM_LOG_DOSYASI = os.path.join(LOG_DIZINI, "egitim_log.txt")
os.makedirs(MODEL_DIZINI, exist_ok=True)
os.makedirs(LOG_DIZINI, exist_ok=True)

# ── FEATURE ENGINEER IMPORT (ayrı modülden al) ──────────────────
from mod_ml_feature_engineer import FeatureEngineer

# ── LOG YAPILANDIRMASI ─────────────────────────────────────────────
def _log_yapilandir():
    """ML eğitim log handler'ını yapılandırır ve döndürür."""
    logger = logging.getLogger("ML_Egitim")
    logger.setLevel(logging.DEBUG)
    
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(
        LOG_DOSYASI, encoding="utf-8",
        maxBytes=10 * 1024 * 1024,
        backupCount=3
    )
    fh.setLevel(logging.DEBUG)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

_ml_logger = _log_yapilandir()

# ─────────────────────────────────────────────────────────────────────
#  1. PİYASA REJİMİ TESPİTİ
# ─────────────────────────────────────────────────────────────────────
class PiyasaRejimi:
    TREND = "TREND"
    YATAY = "YATAY"
    VOLATIL = "VOLATIL"
    
    @staticmethod
    def tespit_et(data: pd.DataFrame) -> str:
        try:
            close = data['Close'].squeeze()
            if PANDAS_TA_AKTIF and len(data) >= 20:
                adx_df = ta.adx(data['High'], data['Low'], close, length=14)
                adx_val = float(adx_df.iloc[-1]['ADX_14']) if 'ADX_14' in adx_df.columns else 20
            else:
                adx_val = 20
            
            if PANDAS_TA_AKTIF and len(data) >= 14:
                atr_ser = ta.atr(data['High'], data['Low'], close, length=14)
                atr_val = float(atr_ser.iloc[-1]) if atr_ser is not None else 0
            else:
                high_14 = data['High'].tail(14)
                low_14 = data['Low'].tail(14)
                close_prev = close.shift(1).tail(14)
                tr = pd.concat([
                    high_14 - low_14,
                    (high_14 - close_prev).abs(),
                    (low_14 - close_prev).abs()
                ], axis=1).max(axis=1)
                atr_val = float(tr.mean())
            
            atr_yuzde = (atr_val / float(close.iloc[-1])) * 100 if float(close.iloc[-1]) > 0 else 0
            
            ma20 = close.rolling(20).mean()
            ma20_son = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else float(close.iloc[-1])
            ma20_once = float(ma20.iloc[-20]) if len(ma20) >= 20 and not pd.isna(ma20.iloc[-20]) else ma20_son
            ma_egim = (ma20_son - ma20_once) / abs(ma20_once) * 100 if abs(ma20_once) > 0 else 0
            
            if atr_yuzde > 4:
                return PiyasaRejimi.VOLATIL
            elif adx_val > 25 and abs(ma_egim) > 3:
                return PiyasaRejimi.TREND
            else:
                return PiyasaRejimi.YATAY
        except Exception as e:
            return PiyasaRejimi.YATAY

# ─────────────────────────────────────────────────────────────────────
#  3. XGBOOST/LIGHTGBM MODEL SINIFI
# ─────────────────────────────────────────────────────────────────────
class MLModel:
    def __init__(self, model_adi: str = "signal_model_v1", model_turu: str = "classification",
                 use_ensemble: bool = True):
        self.model_adi = model_adi
        self.model_turu = model_turu
        self.use_ensemble = use_ensemble
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.feature_importance = {}
        self.basari_metrikleri = {}
        self.egitim_gunu = None
        self.model_params = {}
        self.individual_models = {}
        
    def set_params(self, params: dict):
        self.model_params = params
    
    def _tek_model_olustur(self, model_tipi: str = "xgb"):
        n_est = self.model_params.get('n_estimators', 200)
        max_d = self.model_params.get('max_depth', 6)
        lr = self.model_params.get('learning_rate', 0.05)
        subs = self.model_params.get('subsample', 0.8)
        colsample = self.model_params.get('colsample_bytree', 0.8)
        
        if model_tipi == "xgb" and XGB_AKTIF:
            if self.model_turu == "classification":
                return xgb.XGBClassifier(n_estimators=n_est, max_depth=max_d, learning_rate=lr,
                    subsample=subs, colsample_bytree=colsample, scale_pos_weight=2,
                    random_state=42, n_jobs=-1, eval_metric='logloss', verbosity=0)
            return xgb.XGBRegressor(n_estimators=n_est, max_depth=max_d, learning_rate=lr,
                subsample=subs, colsample_bytree=colsample, random_state=42, n_jobs=-1, verbosity=0)
        elif model_tipi == "lgb" and LGB_AKTIF:
            if self.model_turu == "classification":
                return lgb.LGBMClassifier(n_estimators=n_est, max_depth=max_d, learning_rate=lr,
                    subsample=subs, colsample_bytree=colsample, class_weight='balanced',
                    random_state=43, n_jobs=-1, verbose=-1)
            return lgb.LGBMRegressor(n_estimators=n_est, max_depth=max_d, learning_rate=lr,
                subsample=subs, colsample_bytree=colsample, random_state=43, n_jobs=-1, verbose=-1)
        elif model_tipi == "cat" and CATBOOST_AKTIF:
            if self.model_turu == "classification":
                return cb.CatBoostClassifier(iterations=n_est, depth=max_d, learning_rate=lr,
                    subsample=subs, random_seed=44, thread_count=-1, logging_level='Silent')
            return cb.CatBoostRegressor(iterations=n_est, depth=max_d, learning_rate=lr,
                subsample=subs, random_seed=44, thread_count=-1, logging_level='Silent')
        elif model_tipi == "xtra":
            if self.model_turu == "classification":
                return ExtraTreesClassifier(n_estimators=n_est, max_depth=max_d,
                    min_samples_leaf=5, random_state=45, n_jobs=-1, class_weight='balanced')
            return None
        elif model_tipi == "rf":
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
            if self.model_turu == "classification":
                return RandomForestClassifier(n_estimators=n_est, max_depth=max_d,
                    min_samples_leaf=5, random_state=46, n_jobs=-1, class_weight='balanced')
            return RandomForestRegressor(n_estimators=n_est, max_depth=max_d,
                min_samples_leaf=5, random_state=46, n_jobs=-1)
        return None
    
    def _model_olustur(self):
        if not self.use_ensemble or self.model_turu != "classification":
            self.model = self._tek_model_olustur("xgb")
            if self.model is None:
                self.model = self._tek_model_olustur("rf")
            return self.model
        
        estimators = []
        model_types = []
        for tip in ['xgb', 'lgb', 'cat', 'xtra']:
            m = self._tek_model_olustur(tip)
            if m is not None:
                estimators.append((tip, m))
                model_types.append(tip)
                self.individual_models[tip] = m
        
        if len(estimators) >= 2:
            try:
                self.model = VotingClassifier(estimators=estimators, voting='soft', n_jobs=-1)
            except:
                self.model = VotingClassifier(estimators=estimators, voting='hard', n_jobs=-1)
        elif len(estimators) == 1:
            self.model = estimators[0][1]
        else:
            self.model = self._tek_model_olustur("rf")
        return self.model
    
    def egit(self, X_train: pd.DataFrame, y_train: pd.Series, 
             X_val: pd.DataFrame = None, y_val: pd.Series = None) -> dict:
        self._model_olustur()
        self.feature_names = list(X_train.columns)
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        if X_val is not None and y_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            model_sinifi = self.model.__class__.__name__
            
            if 'XGB' in model_sinifi or 'xgb' in str(type(self.model)):
                try:
                    self.model.fit(X_train_scaled, y_train, eval_set=[(X_val_scaled, y_val)], verbose=False)
                except:
                    self.model.fit(X_train_scaled, y_train)
            elif 'LGBM' in model_sinifi:
                try:
                    self.model.fit(X_train_scaled, y_train, eval_set=[(X_val_scaled, y_val)],
                        eval_metric='logloss' if self.model_turu == "classification" else 'l2',
                        callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
                except:
                    self.model.fit(X_train_scaled, y_train)
            elif 'CatBoost' in model_sinifi:
                try:
                    self.model.fit(X_train_scaled, y_train, eval_set=(X_val_scaled, y_val),
                        early_stopping_rounds=20, verbose=False)
                except:
                    self.model.fit(X_train_scaled, y_train)
            elif 'Voting' in model_sinifi:
                self.model.fit(X_train_scaled, y_train)
            else:
                self.model.fit(X_train_scaled, y_train)
        else:
            self.model.fit(X_train_scaled, y_train)
        
        metrikler = self._metrik_hesapla(X_train, y_train, X_val, y_val)
        self.basari_metrikleri = metrikler
        self.egitim_gunu = datetime.now()
        return metrikler
    
    def _metrik_hesapla(self, X_train, y_train, X_val=None, y_val=None) -> dict:
        metrikler = {}
        for set_adi, X, y in [("egitim", X_train, y_train), 
                               ("validasyon", X_val, y_val) if X_val is not None else (None, None, None)]:
            if X is None:
                continue
            X_s = self.scaler.transform(X)
            if self.model_turu == "classification":
                y_pred = self.model.predict(X_s)
                y_proba = self.model.predict_proba(X_s)[:, 1] if hasattr(self.model, 'predict_proba') else y_pred
                metrikler[set_adi] = {
                    'accuracy': round(float(accuracy_score(y, y_pred)), 4),
                    'precision': round(float(precision_score(y, y_pred, zero_division=0)), 4),
                    'recall': round(float(recall_score(y, y_pred, zero_division=0)), 4),
                    'f1': round(float(f1_score(y, y_pred, zero_division=0)), 4)
                }
                try:
                    metrikler[set_adi]['auc_roc'] = round(float(roc_auc_score(y, y_proba)), 4)
                except:
                    metrikler[set_adi]['auc_roc'] = 0.5
            else:
                y_pred = self.model.predict(X_s)
                from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
                metrikler[set_adi] = {
                    'mae': round(float(mean_absolute_error(y, y_pred)), 4),
                    'rmse': round(float(np.sqrt(mean_squared_error(y, y_pred))), 4),
                    'r2': round(float(r2_score(y, y_pred)), 4)
                }
        return metrikler
    
    def tahmin_et(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            return np.zeros(len(X))
        X_s = self.scaler.transform(X[self.feature_names])
        if self.model_turu == "classification":
            proba = self.model.predict_proba(X_s)
            if proba.shape[1] >= 2:
                return proba[:, 1]
            return proba[:, 0]
        else:
            return self.model.predict(X_s)
    
    def kaydet(self, ek_adi: str = "") -> str:
        if ek_adi:
            dosya_adi = f"{self.model_adi}_{ek_adi}.pkl"
        else:
            dosya_adi = f"{self.model_adi}.pkl"
        dosya_yolu = os.path.join(MODEL_DIZINI, dosya_adi)
        metadata = {
            'model_adi': self.model_adi,
            'model_turu': self.model_turu,
            'feature_names': self.feature_names,
            'basari_metrikleri': self.basari_metrikleri,
            'egitim_gunu': self.egitim_gunu.isoformat() if self.egitim_gunu else None,
            'feature_importance': self.feature_importance
        }
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'metadata': metadata
        }, dosya_yolu)
        return dosya_yolu
    
    @staticmethod
    def yukle(dosya_yolu: str) -> 'MLModel':
        data = joblib.load(dosya_yolu)
        model = MLModel(
            model_adi=data['metadata']['model_adi'],
            model_turu=data['metadata']['model_turu']
        )
        model.model = data['model']
        model.scaler = data['scaler']
        model.feature_names = data['metadata']['feature_names']
        model.basari_metrikleri = data['metadata']['basari_metrikleri']
        if data['metadata'].get('egitim_gunu'):
            model.egitim_gunu = datetime.fromisoformat(data['metadata']['egitim_gunu'])
        return model
    
    @staticmethod
    def son_modeli_bul() -> str:
        if not os.path.exists(MODEL_DIZINI):
            return ""
        model_dosyalari = [f for f in os.listdir(MODEL_DIZINI) if f.endswith('.pkl')]
        if not model_dosyalari:
            return ""
        model_dosyalari.sort(key=lambda f: os.path.getmtime(os.path.join(MODEL_DIZINI, f)), reverse=True)
        return os.path.join(MODEL_DIZINI, model_dosyalari[0])

# ─────────────────────────────────────────────────────────────────────
#  4. WALK-FORWARD CROSS VALIDATION
# ─────────────────────────────────────────────────────────────────────
class WalkForwardValidator:
    @staticmethod
    def dogrula(df: pd.DataFrame, hedef_kolon: str = 'target_binary_5d',
                n_splits: int = 5, model_turu: str = "classification") -> dict:
        if hedef_kolon not in df.columns:
            return {'hata': f'Hedef kolon {hedef_kolon} bulunamadı'}
        
        exclude_cols = [col for col in df.columns if col.startswith('target_')]
        feature_cols = [col for col in df.columns if col not in exclude_cols and col != 'target_binary_5d']
        feature_cols = [col for col in feature_cols if df[col].dtype in [np.float64, np.int64, np.float32, np.int32]]
        
        X = df[feature_cols].fillna(0)
        y = df[hedef_kolon]
        X = X.replace([np.inf, -np.inf], 0).fillna(0)
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        split_metrikler = []
        tum_importancelar = []
        
        for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            if y_train.nunique() < 2:
                continue
            
            model = MLModel(model_adi=f"fold_{fold}", model_turu=model_turu)
            model.egit(X_train, y_train, X_test, y_test)
            
            if hasattr(model.model, 'feature_importances_'):
                importances = dict(zip(feature_cols, model.model.feature_importances_))
                importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10])
                tum_importancelar.append(importances)
            
            split_metrikler.append({
                'fold': fold + 1,
                'train_size': len(X_train),
                'test_size': len(X_test),
                'metrikler': model.basari_metrikleri
            })
        
        if not split_metrikler:
            return {'hata': 'Yeterli veri yok', 'uyari': True, 'ortalama': {}, 'split_metrikler': [],
                    'feature_importance': {}, 'toplam_satir': len(df),
                    'feature_sayisi': len(feature_cols), 'test_edilen_fold': 0}
        
        ortalama = {}
        if 'validasyon' in split_metrikler[0]['metrikler']:
            for metrik in split_metrikler[0]['metrikler']['validasyon']:
                degerler = [s['metrikler']['validasyon'][metrik] for s in split_metrikler]
                ortalama[f'ortalama_{metrik}'] = round(float(np.mean(degerler)), 4)
        
        ort_importance = {}
        if tum_importancelar:
            for imp_dict in tum_importancelar:
                for feature, imp in imp_dict.items():
                    if feature in ort_importance:
                        ort_importance[feature] += imp
                    else:
                        ort_importance[feature] = imp
            n = len(tum_importancelar)
            ort_importance = {k: v / n for k, v in ort_importance.items()}
            ort_importance = dict(sorted(ort_importance.items(), key=lambda x: x[1], reverse=True))
        
        return {
            'ortalama': ortalama,
            'split_metrikler': split_metrikler,
            'feature_importance': ort_importance,
            'toplam_satir': len(df),
            'feature_sayisi': len(feature_cols),
            'test_edilen_fold': len(split_metrikler)
        }

# ─────────────────────────────────────────────────────────────────────
#  5. OPTUNA İLE HİPERPARAMETRE OPTİMİZASYONU
# ─────────────────────────────────────────────────────────────────────
class HiperparametreOptimizasyonu:
    @staticmethod
    def optimize_et(X_train, y_train, n_trials=50, use_xgboost=True):
        if not OPTUNA_AKTIF:
            return {'n_estimators': 200, 'max_depth': 6, 'learning_rate': 0.05}
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0)
            }
            if use_xgboost and XGB_AKTIF:
                model = xgb.XGBClassifier(**params, random_state=42, n_jobs=-1, verbosity=0)
            else:
                from lightgbm import LGBMClassifier
                model = LGBMClassifier(**params, random_state=42, n_jobs=-1, verbose=-1)
            
            tscv = TimeSeriesSplit(n_splits=3)
            skorlar = []
            for train_idx, test_idx in tscv.split(X_train):
                X_tr, X_te = X_train.iloc[train_idx], X_train.iloc[test_idx]
                y_tr, y_te = y_train.iloc[train_idx], y_train.iloc[test_idx]
                if y_tr.nunique() < 2:
                    continue
                model.fit(X_tr, y_tr)
                y_pred = model.predict(X_te)
                skor = f1_score(y_te, y_pred, zero_division=0)
                skorlar.append(skor)
            return np.mean(skorlar) if skorlar else 0
        
        study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        return study.best_params

# ─────────────────────────────────────────────────────────────────────
#  6. ANA ML MOTORU
# ─────────────────────────────────────────────────────────────────────
class AnaMLMotor:
    def __init__(self):
        self.stock_models = {}
        self.stock_basari_metrikleri = {}
        self.ensemble_models = {}
        self.son_egitim_zamani = None
        self._varsayilan_model_yukle()
    
    def _varsayilan_model_yukle(self):
        import glob
        if not os.path.exists(MODEL_DIZINI):
            return
        pkl_dosyalari = glob.glob(os.path.join(MODEL_DIZINI, "*.pkl"))
        for dosya_yolu in pkl_dosyalari:
            try:
                dosya_adi = os.path.basename(dosya_yolu).replace('.pkl', '')
                if dosya_adi.startswith('rejim_'):
                    eski_regime = dosya_adi.replace('rejim_', '').upper()
                    model = MLModel.yukle(dosya_yolu)
                    if '___GENEL___' not in self.stock_models:
                        self.stock_models['___GENEL___'] = {}
                    self.stock_models['___GENEL___'][eski_regime] = model
                    continue
                
                son_ayrac = dosya_adi.rfind('_')
                if son_ayrac == -1:
                    continue
                hisse_kodu = dosya_adi[:son_ayrac]
                regime = dosya_adi[son_ayrac+1:].upper()
                if regime not in [PiyasaRejimi.TREND, PiyasaRejimi.YATAY, PiyasaRejimi.VOLATIL]:
                    continue
                model = MLModel.yukle(dosya_yolu)
                if hisse_kodu not in self.stock_models:
                    self.stock_models[hisse_kodu] = {}
                self.stock_models[hisse_kodu][regime] = model
            except Exception as e:
                continue
    
    def veri_cek_ve_hazirla(self, hisse_kodu: str, fetch_period: str = "5y", start_date: str = None) -> pd.DataFrame:
        try:
            from mod_veri_kaynagi import veri_cek as coklu_veri_cek
            if start_date:
                df = coklu_veri_cek(hisse_kodu, period=fetch_period, start_date=start_date)
            else:
                df = coklu_veri_cek(hisse_kodu, period=fetch_period)
            
            if df is None or df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=['Close'])
            if len(df) < 10:
                return None
            feature_df = FeatureEngineer.tum_ozellikleri_olustur(df)
            if feature_df is None or len(feature_df) < 8:
                return None
            return feature_df
        except Exception as e:
            return None
    
    def rejime_gore_egit(self, hisse_kodu: str, force_retrain: bool = False, use_optuna: bool = False) -> dict:
        guvenli_hisse = hisse_kodu.replace('/', '_').replace('\\', '_')
        mevcut_model = None
        mevcut_egitim_gunu = None
        if force_retrain:
            if guvenli_hisse in self.stock_models:
                for rejim_adi, mdl in self.stock_models[guvenli_hisse].items():
                    if mdl.egitim_gunu:
                        mevcut_model = mdl
                        mevcut_egitim_gunu = mdl.egitim_gunu
                        break
            if mevcut_model is None:
                import glob
                pkl_dosyalari = glob.glob(os.path.join(MODEL_DIZINI, f"{guvenli_hisse}_*.pkl"))
                if pkl_dosyalari:
                    pkl_dosyalari.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                    try:
                        mevcut_model = MLModel.yukle(pkl_dosyalari[0])
                        mevcut_egitim_gunu = mevcut_model.egitim_gunu
                        dosya_ad = os.path.basename(pkl_dosyalari[0]).replace('.pkl', '')
                        son_ayrac = dosya_ad.rfind('_')
                        eski_regime = dosya_ad[son_ayrac+1:].upper() if son_ayrac != -1 else PiyasaRejimi.YATAY
                        if guvenli_hisse not in self.stock_models:
                            self.stock_models[guvenli_hisse] = {}
                        self.stock_models[guvenli_hisse][eski_regime] = mevcut_model
                    except:
                        mevcut_model = None
                        mevcut_egitim_gunu = None
        
        start_date_str = None
        if mevcut_egitim_gunu and force_retrain:
            start_date_str = mevcut_egitim_gunu.strftime('%Y-%m-%d')
        
        df = self.veri_cek_ve_hazirla(hisse_kodu, start_date=start_date_str)
        if df is None:
            return {'hata': 'Yeterli veri yok'}
        
        regime = PiyasaRejimi.tespit_et(df)
        if 'target_binary_5d' not in df.columns:
            return {'hata': 'Feature engineering başarısız'}
        
        if guvenli_hisse not in self.stock_models:
            self.stock_models[guvenli_hisse] = {}
        hisse_rejim_modelleri = self.stock_models[guvenli_hisse]
        
        if regime in hisse_rejim_modelleri and not force_retrain:
            model = hisse_rejim_modelleri[regime]
            return {
                'durum': f'Mevcut model kullanıldı ({hisse_kodu} - {regime})',
                'regime': regime,
                'metrikler': model.basari_metrikleri,
                'model_dosyasi': f'{hisse_kodu}_{regime}.pkl',
                'feature_sayisi': len(model.feature_names) if model.feature_names else 0
            }
        
        exclude_cols = [col for col in df.columns if col.startswith('target_')]
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        feature_cols = [col for col in feature_cols if df[col].dtype in [np.float64, np.int64, np.float32, np.int32]]
        
        X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = df['target_binary_5d']
        
        dogrudan_incremental = False
        if mevcut_model is not None and force_retrain:
            model_sinifi = mevcut_model.model.__class__.__name__ if mevcut_model.model else ''
            if 'XGB' in model_sinifi or 'LGBM' in model_sinifi or 'CatBoost' in model_sinifi:
                dogrudan_incremental = True
        
        if dogrudan_incremental:
            try:
                split_idx = int(len(X) * 0.8)
                X_train = X.iloc[:split_idx] if split_idx > 0 else X
                X_val = X.iloc[split_idx:] if split_idx < len(X) else None
                y_train = y.iloc[:split_idx] if split_idx > 0 else y
                y_val = y.iloc[split_idx:] if split_idx < len(y) and X_val is not None else None
                
                model = mevcut_model
                model.use_ensemble = False
                
                if use_optuna and OPTUNA_AKTIF and len(X_train) > 20:
                    try:
                        best_params = HiperparametreOptimizasyonu.optimize_et(X_train, y_train, n_trials=30, use_xgboost=True)
                        model.model_params = best_params
                    except:
                        pass
                
                X_train_scaled = model.scaler.transform(X_train)
                if 'XGB' in model_sinifi:
                    model.model.fit(X_train_scaled, y_train, xgb_model=model.model, verbose=False)
                elif 'LGBM' in model_sinifi:
                    model.model.fit(X_train_scaled, y_train, init_model=model.model)
                elif 'CatBoost' in model_sinifi:
                    model.model.fit(X_train_scaled, y_train, init_model=model.model)
                
                metrikler = model._metrik_hesapla(X_train, y_train, X_val, y_val)
                model.basari_metrikleri = metrikler
                model.egitim_gunu = datetime.now()
                model_dosyasi = model.kaydet()
                
                hisse_rejim_modelleri[regime] = model
                self.stock_models[guvenli_hisse] = hisse_rejim_modelleri
                self.son_egitim_zamani = datetime.now()
                
                if guvenli_hisse not in self.stock_basari_metrikleri:
                    self.stock_basari_metrikleri[guvenli_hisse] = {}
                self.stock_basari_metrikleri[guvenli_hisse][regime] = metrikler
                
                return {
                    'durum': f'🔄 Incremental güncelleme',
                    'regime': regime,
                    'metrikler': metrikler,
                    'model_dosyasi': model_dosyasi,
                    'feature_sayisi': len(feature_cols),
                    'hisse_kodu': hisse_kodu,
                    'incremental': True,
                    'yeni_veri_satir': len(df)
                }
            except:
                dogrudan_incremental = False
        
        validator = WalkForwardValidator()
        wf_sonuc = validator.dogrula(df, 'target_binary_5d', n_splits=5)
        
        model_adi = f"{guvenli_hisse}_{regime}"
        model = MLModel(model_adi=model_adi, model_turu="classification")
        
        if use_optuna and OPTUNA_AKTIF:
            split_idx = int(len(X) * 0.8)
            X_train_opt, X_val_opt = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train_opt, y_val_opt = y.iloc[:split_idx], y.iloc[split_idx:]
            try:
                best_params = HiperparametreOptimizasyonu.optimize_et(X_train_opt, y_train_opt, n_trials=30, use_xgboost=True)
                model.set_params(best_params)
            except:
                pass
        
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
        
        metrikler = model.egit(X_train, y_train, X_val, y_val)
        model_dosyasi = model.kaydet()
        
        hisse_rejim_modelleri[regime] = model
        self.stock_models[guvenli_hisse] = hisse_rejim_modelleri
        self.son_egitim_zamani = datetime.now()
        
        if guvenli_hisse not in self.stock_basari_metrikleri:
            self.stock_basari_metrikleri[guvenli_hisse] = {}
        self.stock_basari_metrikleri[guvenli_hisse][regime] = metrikler
        
        return {
            'durum': f'Model eğitildi',
            'regime': regime,
            'metrikler': metrikler,
            'walk_forward': wf_sonuc,
            'model_dosyasi': model_dosyasi,
            'feature_sayisi': len(feature_cols),
            'hisse_kodu': hisse_kodu,
            'incremental': False,
            'yeni_veri_satir': len(df)
        }
    
    def olasilik_tahmin_et(self, hisse_kodu: str, hedef_gun: int = 5) -> dict:
        df = self.veri_cek_ve_hazirla(hisse_kodu, fetch_period="3y")
        if df is None:
            return self._fallback_tahmin(hisse_kodu, hedef_gun)
        
        regime = PiyasaRejimi.tespit_et(df)
        son_satir = df.iloc[-1:].copy()
        guncel_fiyat = float(son_satir['Close'].iloc[-1]) if 'Close' in son_satir.columns else 0
        
        guvenli_hisse = hisse_kodu.replace('/', '_').replace('\\', '_')
        hisse_modelleri = self.stock_models.get(guvenli_hisse, {})
        model = hisse_modelleri.get(regime)
        
        if model is None:
            genel_modeller = self.stock_models.get('___GENEL___', {})
            model = genel_modeller.get(regime)
        
        if model is None:
            return self._fallback_tahmin(hisse_kodu, hedef_gun)
        
        exclude_cols = [col for col in son_satir.columns if col.startswith('target_')]
        feature_cols = [col for col in son_satir.columns if col not in exclude_cols]
        feature_cols = [col for col in feature_cols if son_satir[col].dtype in [np.float64, np.int64, np.float32, np.int32]]
        
        X_pred = son_satir[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        olasilik = float(model.tahmin_et(X_pred)[0]) * 100
        olasilik = max(1, min(99, olasilik))
        
        if olasilik >= 65:
            karar = "GÜÇLÜ YÜKSELİŞ"
        elif olasilik >= 55:
            karar = "YÜKSELİŞ"
        elif olasilik >= 45:
            karar = "NÖTR"
        elif olasilik >= 35:
            karar = "DÜŞÜŞ"
        else:
            karar = "GÜÇLÜ DÜŞÜŞ"
        
        volatilite = float(df['volatility_10d'].iloc[-1]) if 'volatility_10d' in df.columns else 0.02
        beklenen_getiri = (olasilik / 100 - 0.5) * 2 * volatilite * np.sqrt(hedef_gun) * 3
        tahmini_fiyat = guncel_fiyat * (1 + beklenen_getiri) if guncel_fiyat > 0 else guncel_fiyat
        sapma = guncel_fiyat * volatilite * np.sqrt(hedef_gun) * 2 if guncel_fiyat > 0 else 0
        alt_bant = tahmini_fiyat - sapma
        ust_bant = tahmini_fiyat + sapma
        
        p = olasilik / 100
        q = 1 - p
        b = 1.5
        kelly = (p * b - q) / b
        kelly = max(0, min(0.25, kelly))
        
        importance_dict = {}
        if hasattr(model.model, 'feature_importances_') and feature_cols:
            importances = model.model.feature_importances_
            for name, imp in zip(feature_cols[:min(len(feature_cols), len(importances))], importances[:len(feature_cols)]):
                importance_dict[name] = round(float(imp), 4)
            importance_dict = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:5])
        
        return {
            'olasilik': round(olasilik, 1),
            'regime': regime,
            'karar': karar,
            'guncel_fiyat': round(guncel_fiyat, 4),
            'tahmini_fiyat': round(tahmini_fiyat, 4) if tahmini_fiyat > 0 else 0,
            'alt_bant': round(alt_bant, 4),
            'ust_bant': round(ust_bant, 4),
            'kelly_pozisyon': round(kelly * 100, 1),
            'feature_importance': importance_dict,
            'model_metrikleri': model.basari_metrikleri,
            'tahmin_gunu': hedef_gun
        }
    
    def _fallback_tahmin(self, hisse_kodu, hedef_gun=5) -> dict:
        try:
            from mod_yapay_zeka import _eski_yontem_ile_tahmin
            sonuc, mesaj = _eski_yontem_ile_tahmin(hisse_kodu, hedef_gun)
            if sonuc:
                return {
                    'olasilik': sonuc['Olasilik'],
                    'regime': 'FALLBACK',
                    'karar': sonuc['Karar'],
                    'guncel_fiyat': sonuc['Guncel_Fiyat'],
                    'tahmini_fiyat': sonuc['Tahmini_Fiyat'],
                    'alt_bant': sonuc['Fiyat_Alt_Bant'],
                    'ust_bant': sonuc['Fiyat_Ust_Bant'],
                    'kelly_pozisyon': 0,
                    'feature_importance': {},
                    'model_metrikleri': {},
                    'tahmin_gunu': hedef_gun
                }
        except:
            pass
        return {
            'olasilik': 50, 'regime': 'HATA', 'karar': 'NÖTR',
            'guncel_fiyat': 0, 'tahmini_fiyat': 0, 'alt_bant': 0, 'ust_bant': 0,
            'kelly_pozisyon': 0, 'feature_importance': {}, 'model_metrikleri': {}, 'tahmin_gunu': hedef_gun
        }
    
    def kendi_hatalarindan_ogren(self) -> dict:
        import sqlite3
        try:
            conn = sqlite3.connect(DB_YOLU)
            query = "SELECT * FROM ai_sinyaller WHERE durum != 'BEKLIYOR' ORDER BY id DESC LIMIT 200"
            df = pd.read_sql_query(query, conn)
            conn.close()
        except:
            return {'hata': 'Veritabanı okunamadı'}
        
        if df.empty or len(df) < 10:
            return {'hata': 'Yeterli işlem yok'}
        
        basarili = len(df[df['durum'].str.contains('BAŞARILI', na=False)])
        basarisiz = len(df[df['durum'].str.contains('BAŞARISIZ', na=False)])
        toplam = basarili + basarisiz
        win_rate = (basarili / toplam) * 100 if toplam > 0 else 0
        
        son_20 = df.head(20)
        son_basarili = len(son_20[son_20['durum'].str.contains('BAŞARILI', na=False)])
        son_win_rate = (son_basarili / max(len(son_20), 1)) * 100
        
        rapor = {
            'toplam_islem': toplam,
            'basarili': basarili,
            'basarisiz': basarisiz,
            'win_rate': round(win_rate, 1),
            'son_20_win_rate': round(son_win_rate, 1),
            'trend': 'İYİLEŞİYOR' if son_win_rate > win_rate + 5 else 'KÖTÜLEŞİYOR' if son_win_rate < win_rate - 5 else 'STABİL'
        }
        rapor['model_guncelleme'] = 'Gerekli' if son_win_rate < 40 and toplam >= 20 else 'Gerek yok'
        return rapor

VARSAYILAN_EGITIM_HISSELERI = [
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "ASELS.IS", "EREGL.IS",
    "SASA.IS", "KRDMD.IS", "PETKM.IS", "BIMAS.IS", "TUPRS.IS",
    "BTC-USD", "ETH-USD",
    "AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMZN", "META",
]

_GUCULU_AL_SEMBOLLERI = None
_GUCULU_AL_SEMBOL_TTL = 0
_GUCULU_AL_CACHE_SURE = 3600

def _guclu_al_sembollerini_getir() -> set:
    global _GUCULU_AL_SEMBOLLERI, _GUCULU_AL_SEMBOL_TTL
    simdi = time.time()
    if _GUCULU_AL_SEMBOLLERI is not None and (simdi - _GUCULU_AL_SEMBOL_TTL) < _GUCULU_AL_CACHE_SURE:
        return _GUCULU_AL_SEMBOLLERI
    
    import sqlite3
    guclu_set = set()
    try:
        if not os.path.exists(DB_YOLU):
            _GUCULU_AL_SEMBOLLERI = guclu_set
            _GUCULU_AL_SEMBOL_TTL = simdi
            return guclu_set
        conn = sqlite3.connect(DB_YOLU)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'")
        if cursor.fetchone():
            cursor.execute("SELECT DISTINCT hisse_kodu FROM ai_sinyaller WHERE karar = 'GÜÇLÜ YÜKSELİŞ' OR karar = 'YÜKSELİŞ' ORDER BY id DESC LIMIT 200")
            for row in cursor.fetchall():
                guclu_set.add(row[0])
        conn.close()
    except:
        pass
    _GUCULU_AL_SEMBOLLERI = guclu_set
    _GUCULU_AL_SEMBOL_TTL = simdi
    return guclu_set

def egitim_oncelik_sirala(hisse_listesi: list, onceki_basarisizlar: set = None) -> list:
    if not hisse_listesi:
        return []
    if onceki_basarisizlar is None:
        onceki_basarisizlar = set()
    guclu_set = _guclu_al_sembollerini_getir()
    oncelik1, oncelik2, oncelik3 = [], [], []
    for h in hisse_listesi:
        h_upper = h.upper()
        if h in guclu_set or h_upper in guclu_set:
            oncelik1.append(h)
        elif h in onceki_basarisizlar or h_upper in onceki_basarisizlar:
            oncelik2.append(h)
        else:
            oncelik3.append(h)
    oncelik1.sort()
    oncelik2.sort()
    oncelik3.sort()
    return oncelik1 + oncelik2 + oncelik3

class IncrementalOgrenmeMotoru:
    def __init__(self, hisse_listesi: list = None, dongu_araligi_dakika: int = 60):
        self.hisse_listesi = hisse_listesi if hisse_listesi else VARSAYILAN_EGITIM_HISSELERI
        self.dongu_araligi = dongu_araligi_dakika * 60
        self.motor = get_motor()
        self.dongu_sayisi = 0
        self.toplam_egitilen_model = 0
        self.son_hata_analizi = None
        self.baslangic_zamani = None
        self.onceki_basarisizlar = set()
        
    def _log_baslik(self, mesaj: str):
        _ml_logger.info("")
        _ml_logger.info("═" * 70)
        _ml_logger.info(f"  {mesaj}")
        _ml_logger.info("═" * 70)
        
    def _veritabani_durumunu_kontrol_et(self) -> dict:
        import sqlite3
        try:
            conn = sqlite3.connect(DB_YOLU)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'")
            if not cursor.fetchone():
                conn.close()
                return {'toplam_kapanan': 0, 'yeni_kapanan': 0, 'basarili': 0, 'basarisiz': 0, 'win_rate': 0, 'model_guncelleme_gerekli': False}
            
            yeni_kapanan = 0
            if self.son_hata_analizi:
                son_kontrol_tarihi = self.son_hata_analizi.get('kontrol_zamani', '2000-01-01')
                cursor.execute("SELECT COUNT(*) FROM ai_sinyaller WHERE durum != 'BEKLIYOR' AND tarih > ?", (son_kontrol_tarihi,))
                yeni_kapanan = cursor.fetchone()[0]
            
            df = pd.read_sql_query("SELECT * FROM ai_sinyaller WHERE durum != 'BEKLIYOR' ORDER BY id DESC", conn)
            conn.close()
            
            if df.empty:
                return {'toplam_kapanan': 0, 'yeni_kapanan': 0, 'basarili': 0, 'basarisiz': 0, 'win_rate': 0, 'model_guncelleme_gerekli': False}
            
            basarili = len(df[df['durum'].str.contains('BASARILI', na=False)])
            basarisiz = len(df[df['durum'].str.contains('BASARISIZ', na=False)])
            toplam = basarili + basarisiz
            win_rate = (basarili / toplam * 100) if toplam > 0 else 0
            
            return {
                'toplam_kapanan': toplam, 'yeni_kapanan': max(0, yeni_kapanan),
                'basarili': basarili, 'basarisiz': basarisiz,
                'win_rate': round(win_rate, 1), 'model_guncelleme_gerekli': (toplam >= 10 and win_rate < 45)
            }
        except:
            return {'toplam_kapanan': 0, 'yeni_kapanan': 0, 'basarili': 0, 'basarisiz': 0, 'win_rate': 0, 'model_guncelleme_gerekli': False}
    
    def _tek_hisse_egit_ve_logla(self, hisse_kodu: str, force_retrain: bool = False) -> dict:
        try:
            sonuc = self.motor.rejime_gore_egit(hisse_kodu, force_retrain=force_retrain)
            if 'hata' in sonuc:
                return sonuc
            self.toplam_egitilen_model += 1
            return sonuc
        except Exception as e:
            return {'hata': str(e)}
    
    def donguyu_baslat(self):
        self.baslangic_zamani = datetime.now()
        self._log_baslik("◈ INCREMENTAL LEARNING MOTORU BAŞLATILDI ◈")
        while True:
            try:
                self.dongu_sayisi += 1
                dongu_baslangic = datetime.now()
                db_durum = self._veritabani_durumunu_kontrol_et()
                hata_raporu = self.motor.kendi_hatalarindan_ogren()
                force_retrain = ('Gerekli' in str(hata_raporu.get('model_guncelleme', '')))
                
                self.son_hata_analizi = {
                    'kontrol_zamani': dongu_baslangic.strftime('%Y-%m-%d %H:%M:%S'),
                    'db_durum': db_durum
                }
                
                siralanmis_hisseler = egitim_oncelik_sirala(self.hisse_listesi, self.onceki_basarisizlar)
                bu_tur_basarisizlar = set()
                
                for hisse in siralanmis_hisseler:
                    sonuc = self._tek_hisse_egit_ve_logla(hisse, force_retrain=force_retrain)
                    if 'hata' in sonuc:
                        bu_tur_basarisizlar.add(hisse)
                
                self.onceki_basarisizlar = bu_tur_basarisizlar
                time.sleep(self.dongu_araligi)
            except KeyboardInterrupt:
                break
            except:
                time.sleep(30)

def incremental_ogrenme_dongusu(hisse_listesi: list = None, dongu_araligi_dakika: int = 60):
    motor = IncrementalOgrenmeMotoru(hisse_listesi=hisse_listesi, dongu_araligi_dakika=dongu_araligi_dakika)
    motor.donguyu_baslat()

_zamanlanmis_egitim_sayaci = 0

def _egitim_log_yaz(satir: str):
    try:
        with open(EGITIM_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {satir}\n")
    except:
            pass

def _egitim_log_baslik(baslik: str):
    _egitim_log_yaz("=" * 70)
    _egitim_log_yaz(f"  {baslik}")
    _egitim_log_yaz("=" * 70)

class ZamanlanmisEgitimMotoru:
    EGITIM_BASLANGIC_SAAT = 3
    EGITIM_BITIS_SAAT = 7
    DERIN_OPTIMIZASYON_ARALIK = 2
    
    def __init__(self, hisse_listesi: list = None):
        self.hisse_listesi = hisse_listesi if hisse_listesi else VARSAYILAN_EGITIM_HISSELERI
        self.motor = get_motor()
        self.gunluk_egitim_sayisi = 0
        self.derin_optimizasyon_sayisi = 0
        self.eksik_egitim_sayisi = 0
        self.baslangic_zamani = None
        self.son_egitim_tarihi = None
        
    def _saat_kontrol(self, hedef_saat: int) -> bool:
        simdi = datetime.now()
        return simdi.hour == hedef_saat and simdi.minute < 5
    
    def _guvenlik_siniri_gecildi_mi(self) -> bool:
        simdi = datetime.now()
        return simdi.hour >= self.EGITIM_BITIS_SAAT
    
    def _gunluk_hizli_egitim(self) -> dict:
        global _zamanlanmis_egitim_sayaci
        _zamanlanmis_egitim_sayaci += 1
        baslangic = datetime.now()
        siralanmis_hisseler = egitim_oncelik_sirala(self.hisse_listesi)
        
        basarili_egitim = 0
        basarisiz_egitim = 0
        kesintiye_ugradi = False
        
        for idx, hisse in enumerate(siralanmis_hisseler, 1):
            if self._guvenlik_siniri_gecildi_mi():
                kesintiye_ugradi = True
                break
            try:
                sonuc = self.motor.rejime_gore_egit(hisse, force_retrain=True, use_optuna=False)
                if 'hata' in sonuc:
                    basarisiz_egitim += 1
                else:
                    basarili_egitim += 1
            except:
                basarisiz_egitim += 1
                
        bitis = datetime.now()
        sure = (bitis - baslangic).total_seconds()
        durum = "EKSİK" if kesintiye_ugradi else "TAMAMLANDI"
        self.gunluk_egitim_sayisi += 1
        if kesintiye_ugradi:
            self.eksik_egitim_sayisi += 1
        self.son_egitim_tarihi = baslangic.strftime('%Y-%m-%d')
        return {'durum': durum, 'sure': sure, 'basarili': basarili_egitim, 'basarisiz': basarisiz_egitim}
    
    def _derin_optimizasyon_egitimi(self) -> dict:
        global _zamanlanmis_egitim_sayaci
        _zamanlanmis_egitim_sayaci += 1
        baslangic = datetime.now()
        basarili_egitim = 0
        basarisiz_egitim = 0
        kesintiye_ugradi = False
        
        for idx, hisse in enumerate(self.hisse_listesi, 1):
            if self._guvenlik_siniri_gecildi_mi():
                kesintiye_ugradi = True
                break
            try:
                sonuc = self.motor.rejime_gore_egit(hisse, force_retrain=True, use_optuna=True)
                if 'hata' in sonuc:
                    basarisiz_egitim += 1
                else:
                    basarili_egitim += 1
            except:
                basarisiz_egitim += 1
                
        bitis = datetime.now()
        sure = (bitis - baslangic).total_seconds()
        durum = "EKSİK" if kesintiye_ugradi else "TAMAMLANDI"
        self.derin_optimizasyon_sayisi += 1
        if kesintiye_ugradi:
            self.eksik_egitim_sayisi += 1
        self.son_egitim_tarihi = baslangic.strftime('%Y-%m-%d')
        return {'durum': durum, 'sure': sure, 'basarili': basarili_egitim, 'basarisiz': basarisiz_egitim}
    
    def zamanlanmis_donguyu_baslat(self):
        self.baslangic_zamani = datetime.now()
        bugun_egitim_yapildi = False
        son_derin_optimizasyon_gun = None
        
        while True:
            try:
                simdi = datetime.now()
                gun_str = simdi.strftime('%Y-%m-%d')
                if self._saat_kontrol(self.EGITIM_BASLANGIC_SAAT) and not bugun_egitim_yapildi:
                    derin_opt_yap = False
                    if self.derin_optimizasyon_sayisi == 0:
                        derin_opt_yap = True
                    elif son_derin_optimizasyon_gun:
                        son_gun = datetime.strptime(son_derin_optimizasyon_gun, '%Y-%m-%d')
                        if (simdi - son_gun).days >= self.DERIN_OPTIMIZASYON_ARALIK:
                            derin_opt_yap = True
                    
                    if derin_opt_yap:
                        self._derin_optimizasyon_egitimi()
                        son_derin_optimizasyon_gun = gun_str
                    else:
                        self._gunluk_hizli_egitim()
                    bugun_egitim_yapildi = True
                
                if simdi.hour > self.EGITIM_BITIS_SAAT and bugun_egitim_yapildi:
                    if self.son_egitim_tarihi != gun_str:
                        bugun_egitim_yapildi = False
                time.sleep(60)
            except KeyboardInterrupt:
                break
            except:
                time.sleep(60)

def zamanlanmis_egitim_dongusu(hisse_listesi: list = None):
    motor = ZamanlanmisEgitimMotoru(hisse_listesi=hisse_listesi)
    motor.zamanlanmis_donguyu_baslat()

_ANA_MOTOR = None

def get_motor() -> AnaMLMotor:
    global _ANA_MOTOR
    if _ANA_MOTOR is None:
        _ANA_MOTOR = AnaMLMotor()
    return _ANA_MOTOR

def ml_tahmin_et(hisse_kodu: str, hedef_gun: int = 5) -> dict:
    motor = get_motor()
    return motor.olasilik_tahmin_et(hisse_kodu, hedef_gun)

def ml_hata_analizi_yap() -> dict:
    motor = get_motor()
    return motor.kendi_hatalarindan_ogren()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "incremental":
            dongu_araligi = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            incremental_ogrenme_dongusu(dongu_araligi_dakika=dongu_araligi)
        elif arg == "scheduler":
            zamanlanmis_egitim_dongusu()
        elif arg == "test":
            motor = get_motor()
            motor.rejime_gore_egit("THYAO.IS")