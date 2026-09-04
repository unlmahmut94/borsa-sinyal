# ══════════════════════════════════════════════════════════════════════
#  mod_veri_kaynagi.py — Çok Kaynaklı Veri Çekme Motoru v1.1
#  Kaynaklar: yfinance → pandas_datareader (Stooq/Yahoo) → ccxt (Binance)
#  Her kaynak denenir, ilk başarılı olandan veri alınır.
#  v1.1: Ölü/delisted hisse filtresi ve otomatik temizleme mekanizması
# ══════════════════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
import time
import warnings
import logging
import json
import os
import random
import threading
from datetime import datetime, timedelta
from functools import wraps
from collections import deque

warnings.filterwarnings('ignore')

# ── yfinance gürültüsünü bastır ─────────────────────────────────────
# yfinance'in kendi logger'ını sustur (delisted uyarıları console'u kirletmesin)
yf_logger = logging.getLogger("yfinance")
yf_logger.setLevel(logging.CRITICAL)
yf_shared_logger = logging.getLogger("peewee")
yf_shared_logger.setLevel(logging.CRITICAL)
# yfinance'in print'lediği "possibly delisted" mesajlarını da engellemek için
# thread tabanlı internal logger'ları sustur
for _name in ["urllib3", "requests", "multitasking"]:
    logging.getLogger(_name).setLevel(logging.CRITICAL)

# ── Kütüphane varlık kontrolleri ─────────────────────────────────────
try:
    import yfinance as yf
    YF_AKTIF = True
except ImportError:
    YF_AKTIF = False

try:
    import pandas_datareader.data as web
    PD_AKTIF = True
except ImportError:
    PD_AKTIF = False

try:
    import ccxt
    CCXT_AKTIF = True
except ImportError:
    CCXT_AKTIF = False

try:
    import requests
    REQUESTS_AKTIF = True
except ImportError:
    REQUESTS_AKTIF = False

# ── Logger ───────────────────────────────────────────────────────────
_veri_logger = logging.getLogger("VeriKaynagi")
_veri_logger.setLevel(logging.DEBUG)
if not _veri_logger.handlers:
    h = logging.StreamHandler()
    h.setLevel(logging.WARNING)
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    _veri_logger.addHandler(h)

# ══════════════════════════════════════════════════════════════════════
#  IP KORUMA: RATE LİMİTER + RETRY + BATCH YÖNETİMİ 🛡️
# ══════════════════════════════════════════════════════════════════════

# ── Config'ten rate limiting ayarlarını yükle ─────────────────────────
CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")

def _config_yukle() -> dict:
    """strateji_config.json'u yükler, eksik anahtarları varsayılanlarla tamamlar."""
    VARSAYILANLAR = {
        "stop_loss_yuzde": 0.03, "take_profit_yuzde": 0.08, "rsi_al_esigi": 30,
        "min_win_rate_hedef": 45, "max_risk_per_trade": 0.02, "kelly_fraksiyon": 0.25,
        "komisyon_orani": 0.002, "slippage_yuzde": 0.001, "max_paralel_islem": 5,
        "min_islem_hacmi": 100000, "atr_stop_carpani": 1.5, "bb_std_carpan": 2.0,
        "macd_hizli": 12, "macd_yavas": 26, "macd_sinyal": 9, "rsi_periyot": 14,
        "stoch_k_periyot": 14, "stoch_d_periyot": 3, "adx_esik": 25,
        "cci_alt_esik": -100, "cci_ust_esik": 100, "mfi_alt_esik": 20, "mfi_ust_esik": 80,
        "williams_alt_esik": -80, "williams_ust_esik": -20,
        "haber_agirlik": 0.15, "piyasa_havasi_agirlik": 0.1,
        "backtest_varsayilan_sermaye": 10000, "backtest_varsayilan_gun": 365,
        "backtest_monte_carlo_simulasyon": 1000,
        "tarama_batch_boyutu": 35, "tarama_batch_arasi_sn": 150, "tarama_max_workers": 4,
        "egitim_dongu_aralik_dk": 60, "derin_optuna_aralik_gun": 2,
        "guvenlik_sinir_saat": 7,
        "circuit_breaker_gunluk_yuzde": 0.05, "circuit_breaker_anlik_yuzde": 0.05,
        "circuit_breaker_toparlanma_dk": 30,
        "sinyal_kalite_min_ornek": 10, "sinyal_kalite_ogrenme_orani": 0.1,
        "teyit_zaman_dilimleri": ["5dk", "1sa", "1gun"],
        "korelasyon_esik": 0.7, "korelasyon_max_sektor_agirlik": 0.25,
        "websocket_aktif": False, "websocket_sembol_limiti": 20,
        "paper_slippage_yuzde": 0.002, "paper_kismi_dolum_orani": 0.85,
        "rate_limit_aktif": True, "rate_limit_saniye_basina_istek": 2,
        "rate_limit_min_bekleme_sn": 0.5, "rate_limit_max_bekleme_sn": 3.0,
        "rate_limit_jitter_sn": 0.3, "retry_max_deneme": 3,
        "retry_base_bekleme_sn": 2.0, "retry_backoff_carpani": 2.0,
        "retry_max_bekleme_sn": 60.0, "rate_limit_basina_dusen_gunluk_limit": 50000
    }
    try:
        if os.path.exists(CONFIG_YOLU):
            with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
                yuklu = json.load(f)
            # Eksik anahtarları varsayılanlarla tamamla
            for anahtar, varsayilan in VARSAYILANLAR.items():
                if anahtar not in yuklu:
                    yuklu[anahtar] = varsayilan
            return yuklu
    except (json.JSONDecodeError, IOError):
        pass
    return dict(VARSAYILANLAR)

def _config_kaydet(cfg: dict):
    try:
        with open(CONFIG_YOLU, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except IOError:
        pass

# Varsayılan rate limit ayarları
def _rate_limit_varsayilan() -> dict:
    return {
        "rate_limit_aktif": True,
        "rate_limit_saniye_basina_istek": 2,       # Yahoo: saniyede max 2 istek
        "rate_limit_min_bekleme_sn": 0.5,          # İstekler arası minimum bekleme
        "rate_limit_max_bekleme_sn": 3.0,          # Ban riskinde max bekleme
        "rate_limit_jitter_sn": 0.3,               # Rastgele gecikme (anti-bot koruması)
        "tarama_batch_boyutu": 25,                 # Her batch'te kaç hisse
        "tarama_batch_arasi_sn": 45,               # Batch'ler arası bekleme
        "tarama_max_workers": 3,                   # Paralel worker sayısı (düşürüldü)
        "retry_max_deneme": 3,                     # Max yeniden deneme
        "retry_base_bekleme_sn": 2.0,              # İlk retry bekleme
        "retry_backoff_carpani": 2.0,              # Her denemede 2x bekle
        "retry_max_bekleme_sn": 60.0,              # Max retry bekleme
        "rate_limit_basina_dusen_gunluk_limit": 50000,  # 7/24 tarama için limit artırıldı
    }

def rate_limit_ayarlari_al() -> dict:
    """Config'ten rate limit ayarlarını okur, yoksa varsayılan döndürür."""
    cfg = _config_yukle()
    varsayilan = _rate_limit_varsayilan()
    # Config'teki değerleri varsayılanlarla birleştir
    for k, v in varsayilan.items():
        if k not in cfg:
            cfg[k] = v
    return {k: cfg.get(k, v) for k, v in varsayilan.items()}

class RateLimiter:
    """
    Thread-safe token bucket rate limiter v2.0.
    Yahoo Finance ve diğer API'ler için gelişmiş IP ban koruması.
    
    YENİ ÖZELLİKLER:
    - Ban geçmişi ve akıllı bekleme (saat bazlı pattern tanıma)
    - Borsa türüne göre akıllı throttle (BIST: hızlı, US: orta, Kripto: yavaş)
    - Gerçek zamanlı risk seviyesi göstergesi
    - Adaptif hız ayarı (ban yedikçe yavaşla, sorunsuzsa hızlan)
    """
    
    # ── Borsa türüne göre varsayılan throttle çarpanları ──────────────
    THROTTLE_CARPANLARI = {
        'bist': 1.0,      # BIST hisseleri en hızlı (Stooq toleranslı)
        'us': 0.6,        # US hisseleri orta hız (Yahoo Finance hassas)
        'kripto': 0.4,    # Kripto en yavaş (Binance rate limit'li)
        'forex': 0.8,
        'bilinmiyor': 0.5
    }
    
    # Risk seviyeleri
    RISK_DUSUK = "dusuk"
    RISK_ORTA = "orta"
    RISK_YUKSEK = "yuksek"
    RISK_KRITIK = "kritik"
    
    BAN_GECMISI_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ban_gecmisi.json")
    
    def __init__(self, saniye_basina_istek: float = 2.0, 
                 min_bekleme: float = 0.5, max_bekleme: float = 3.0,
                 jitter: float = 0.3, gunluk_limit: int = 2000,
                 adaptif_ogrenme: bool = True):
        self.base_rate = saniye_basina_istek  # Temel hız (hiç ban yokken)
        self.rate = saniye_basina_istek       # Anlık hız (ban yedikçe düşer)
        self.min_bekleme = min_bekleme
        self.max_bekleme = max_bekleme
        self.jitter = jitter
        self.gunluk_limit = gunluk_limit
        self.adaptif_ogrenme = adaptif_ogrenme
        
        self._token = 1.0
        self._son_yenileme = time.monotonic()
        self._kilit = threading.Lock()
        
        # Günlük sayaç
        self._gunluk_sayac_tarih = datetime.now().date()
        self._gunluk_istek_sayisi = 0
        
        # Son istek zamanları (son 60 sn'lik pencere)
        self._son_istek_zamanlari: deque = deque(maxlen=200)
        
        # ── BAN GEÇMİŞİ VE AKILLI BEKLEME ──────────────────────────
        self._ban_sayisi_bugun = 0
        self._son_ban_zamani = None
        self._ban_saatleri = {}  # {saat: ban_sayisi}
        self._ban_gecmisi = self._ban_gecmisi_yukle()
        self._basari_orani_son_100 = deque(maxlen=100)  # True=başarılı, False=ban
        self._mevcut_risk = self.RISK_DUSUK
        self._throttle_carpani = 1.0
        self._adaptif_rate = saniye_basina_istek
        
        # ── İSTATİSTİKLER ─────────────────────────────────────────
        self._toplam_basarili = 0
        self._toplam_basarisiz = 0
        self._son_uyari_zamani = 0
        
        _veri_logger.info(f"🛡️ RateLimiter v2.0 başlatıldı: {saniye_basina_istek} istek/sn, "
                         f"günlük limit: {gunluk_limit}, adaptif: {adaptif_ogrenme}")
    
    # ══════════════════════════════════════════════════════════════════
    #  BAN GEÇMİŞİ YÖNETİMİ
    # ══════════════════════════════════════════════════════════════════
    
    def _ban_gecmisi_yukle(self) -> dict:
        try:
            if os.path.exists(self.BAN_GECMISI_DOSYASI):
                with open(self.BAN_GECMISI_DOSYASI, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {"ban_saatleri": {}, "toplam_ban": 0, "son_ban_tarih": None}
    
    def _ban_gecmisi_kaydet(self):
        try:
            with open(self.BAN_GECMISI_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self._ban_gecmisi, f, indent=2, ensure_ascii=False)
        except IOError:
            pass
    
    def ban_kaydet(self, sebep: str = ""):
        """Bir ban olayını kaydeder ve akıllı bekleme stratejisini günceller."""
        simdi = datetime.now()
        saat = simdi.hour
        
        with self._kilit:
            self._ban_sayisi_bugun += 1
            self._son_ban_zamani = simdi
            self._toplam_basarisiz += 1
            self._basari_orani_son_100.append(False)
            
            # Saat bazlı kayıt
            saat_str = str(saat)
            if saat_str not in self._ban_saatleri:
                self._ban_saatleri[saat_str] = 0
            self._ban_saatleri[saat_str] += 1
            
            # Kalıcı geçmişi güncelle
            if saat_str not in self._ban_gecmisi["ban_saatleri"]:
                self._ban_gecmisi["ban_saatleri"][saat_str] = 0
            self._ban_gecmisi["ban_saatleri"][saat_str] += 1
            self._ban_gecmisi["toplam_ban"] += 1
            self._ban_gecmisi["son_ban_tarih"] = simdi.strftime("%Y-%m-%d %H:%M:%S")
            self._ban_gecmisi_kaydet()
            
            # Adaptif hız ayarı: ban yedikçe %30 yavaşla
            if self.adaptif_ogrenme:
                self._adaptif_rate = max(0.3, self._adaptif_rate * 0.7)
                self.rate = self._adaptif_rate * self._throttle_carpani
                _veri_logger.warning(f"  ⚠ Ban TESPİT! Adaptif hız düşürüldü: {self.rate:.2f} istek/sn ({sebep})")
    
    def basari_kaydet(self):
        """Başarılı bir API isteğini kaydeder."""
        with self._kilit:
            self._toplam_basarili += 1
            self._basari_orani_son_100.append(True)
            
            # Başarı oranı yüksekse yavaşça hızı artır (ama base_rate'i geçme)
            if self.adaptif_ogrenme and len(self._basari_orani_son_100) >= 20:
                son_basari = sum(self._basari_orani_son_100) / len(self._basari_orani_son_100)
                if son_basari > 0.95:  # Son 100 isteğin %95'i başarılı → hızlan
                    self._adaptif_rate = min(self.base_rate, self._adaptif_rate * 1.05)
                    self.rate = self._adaptif_rate * self._throttle_carpani
    
    def saat_risk_kontrol(self) -> float:
        """Şu anki saate göre ekstra bekleme çarpanı döndürür (0-1 arası)."""
        simdi = datetime.now()
        saat_str = str(simdi.hour)
        
        # Bu saatte daha önce ban yediysek
        saat_banlari = self._ban_gecmisi.get("ban_saatleri", {}).get(saat_str, 0)
        
        if saat_banlari >= 5:
            return 0.3  # %70 yavaşla - bu saat çok riskli
        elif saat_banlari >= 2:
            return 0.5  # %50 yavaşla
        elif saat_banlari >= 1:
            return 0.7  # %30 yavaşla
        return 1.0
    
    # ══════════════════════════════════════════════════════════════════
    #  AKILLI THROTTLE (BORSA TÜRÜNE GÖRE)
    # ══════════════════════════════════════════════════════════════════
    
    def throttle_ayarla(self, borsa_turu: str = 'bilinmiyor'):
        """
        Borsa türüne göre throttle seviyesini ayarlar.
        Her istekte çağrılabilir, sadece değişiklik olduğunda log basar.
        """
        carpan = self.THROTTLE_CARPANLARI.get(borsa_turu, 0.5)
        with self._kilit:
            eski_carpan = self._throttle_carpani
            self._throttle_carpani = carpan
            self.rate = self._adaptif_rate * carpan
            
            if abs(eski_carpan - carpan) > 0.01:
                _veri_logger.debug(f"  🎚 Throttle: {borsa_turu} → {carpan}x (rate: {self.rate:.2f}/sn)")
    
    # ══════════════════════════════════════════════════════════════════
    #  RİSK SEVİYESİ
    # ══════════════════════════════════════════════════════════════════
    
    def risk_seviyesi_hesapla(self) -> str:
        """Anlık risk seviyesini hesaplar."""
        with self._kilit:
            kullanim_orani = self._gunluk_istek_sayisi / max(1, self.gunluk_limit)
            son_60sn = len([t for t in self._son_istek_zamanlari if time.monotonic() - t < 60])
            basari_orani = sum(self._basari_orani_son_100) / max(1, len(self._basari_orani_son_100)) if self._basari_orani_son_100 else 1.0
            
            if kullanim_orani > 0.9 or self._ban_sayisi_bugun >= 3:
                self._mevcut_risk = self.RISK_KRITIK
            elif kullanim_orani > 0.7 or self._ban_sayisi_bugun >= 1 or basari_orani < 0.7:
                self._mevcut_risk = self.RISK_YUKSEK
            elif kullanim_orani > 0.4 or son_60sn > 10:
                self._mevcut_risk = self.RISK_ORTA
            else:
                self._mevcut_risk = self.RISK_DUSUK
            
            return self._mevcut_risk
    
    # ══════════════════════════════════════════════════════════════════
    #  TEMEL FONKSİYONLAR
    # ══════════════════════════════════════════════════════════════════
    
    def _gunluk_kontrol(self):
        """Günlük limit aşıldı mı kontrol et."""
        bugun = datetime.now().date()
        if bugun != self._gunluk_sayac_tarih:
            self._gunluk_sayac_tarih = bugun
            self._gunluk_istek_sayisi = 0
            self._ban_sayisi_bugun = 0
            # Yeni günde adaptif rate'i sıfırla
            if self.adaptif_ogrenme:
                self._adaptif_rate = self.base_rate
                self.rate = self._adaptif_rate * self._throttle_carpani
        
        if self._gunluk_istek_sayisi >= self.gunluk_limit:
            raise RuntimeError(
                f"⛔ Günlük istek limiti aşıldı! ({self.gunluk_limit} istek/gün). "
                f"Yarın {bugun} 00:00'da sıfırlanacak."
            )
    
    def _token_bekle(self) -> float:
        """Token bucket'tan bir token alana kadar bekler (saat riski + adaptif)."""
        with self._kilit:
            simdi = time.monotonic()
            gecen = simdi - self._son_yenileme
            
            # Token yenile
            self._token = min(1.0, self._token + gecen * self.rate)
            self._son_yenileme = simdi
            
            if self._token >= 1.0:
                self._token -= 1.0
                bekleme = self.min_bekleme
            else:
                bekleme = (1.0 - self._token) / max(0.1, self.rate)
                bekleme = max(self.min_bekleme, min(bekleme, self.max_bekleme))
                self._token = 0.0
            
            # Saat riski çarpanı (tarihsel ban verisine göre)
            saat_carpani = self.saat_risk_kontrol()
            if saat_carpani < 1.0:
                bekleme = bekleme / saat_carpani  # Beklemeyi artır
            
            # Jitter ekle
            jitter_ek = random.uniform(-self.jitter, self.jitter)
            bekleme = max(0.1, bekleme + jitter_ek)
            
            return bekleme
    
    def bekle_ve_ilerle(self, kaynak: str = "bilinmiyor", borsa_turu: str = None):
        """
        Rate limit beklemesi yapar ve ilerler.
        Her API isteğinden ÖNCE çağrılır.
        
        Parametreler:
            kaynak: API kaynağı (örn: 'yfinance:AAPL')
            borsa_turu: 'bist', 'us', 'kripto', 'forex' (throttle için)
        """
        self._gunluk_kontrol()
        
        # Akıllı throttle
        if borsa_turu:
            self.throttle_ayarla(borsa_turu)
        
        bekleme = self._token_bekle()
        
        # Son istek kaydını tut
        with self._kilit:
            self._son_istek_zamanlari.append(time.monotonic())
            self._gunluk_istek_sayisi += 1
        
        if bekleme > 0.5:
            _veri_logger.debug(f"  ⏳ Rate limit bekleme: {bekleme:.2f}sn (kaynak: {kaynak})")
        
        time.sleep(bekleme)
    
    def durum_raporu(self) -> dict:
        """Kapsamlı durum raporu döndürür (sidebar paneli için optimize)."""
        with self._kilit:
            kullanim_orani = self._gunluk_istek_sayisi / max(1, self.gunluk_limit) * 100
            basari_orani = (sum(self._basari_orani_son_100) / max(1, len(self._basari_orani_son_100)) * 100) if self._basari_orani_son_100 else 100
            son_ban = self._son_ban_zamani.strftime("%H:%M:%S") if self._son_ban_zamani else "Yok"
            
            return {
                "gunluk_istek": self._gunluk_istek_sayisi,
                "gunluk_limit": self.gunluk_limit,
                "gunluk_kalan": max(0, self.gunluk_limit - self._gunluk_istek_sayisi),
                "kullanim_yuzde": round(kullanim_orani, 1),
                "son_60sn_istek": len([t for t in self._son_istek_zamanlari 
                                       if time.monotonic() - t < 60]),
                "mevcut_token": round(self._token, 2),
                "oran_saniye": round(self.rate, 2),
                "base_rate": self.base_rate,
                "adaptif_rate": round(self._adaptif_rate, 2),
                "throttle_carpani": round(self._throttle_carpani, 2),
                "ban_sayisi_bugun": self._ban_sayisi_bugun,
                "son_ban_zamani": son_ban,
                "risk_seviyesi": self.risk_seviyesi_hesapla(),
                "basari_orani": round(basari_orani, 1),
                "toplam_basarili": self._toplam_basarili,
                "toplam_basarisiz": self._toplam_basarisiz,
                "tarihsel_ban_sayisi": self._ban_gecmisi.get("toplam_ban", 0),
                "saat_uyari": self.saat_risk_kontrol() < 1.0
            }
    
    def uyari_mesaji(self) -> str:
        """Kullanıcıya gösterilecek uyarı mesajı (sidebar için)."""
        rapor = self.durum_raporu()
        risk = rapor["risk_seviyesi"]
        
        if risk == self.RISK_KRITIK:
            return "🔴 KRİTİK: Günlük limit neredeyse doldu! Ban yeme riski çok yüksek. Tarama yapmayı yarına erteleyin."
        elif risk == self.RISK_YUKSEK:
            return f"🟠 YÜKSEK RİSK: {rapor['ban_sayisi_bugun']} ban yediniz. Yavaş tarama önerilir."
        elif risk == self.RISK_ORTA:
            return f"🟡 ORTA: Kullanım %{rapor['kullanim_yuzde']:.0f}. Dikkatli olun."
        else:
            return f"🟢 GÜVENLİ: %{rapor['kullanim_yuzde']:.0f} kullanım. Sorunsuz tarama yapabilirsiniz."

# ── Global RateLimiter singleton ─────────────────────────────────────
_rate_limiter = None
_rate_limiter_kilit = threading.Lock()

def _rate_limiter_al() -> RateLimiter:
    """Global rate limiter singleton'ını döndürür (lazy init)."""
    global _rate_limiter
    with _rate_limiter_kilit:
        if _rate_limiter is None:
            ayarlar = rate_limit_ayarlari_al()
            if ayarlar.get("rate_limit_aktif", True):
                _rate_limiter = RateLimiter(
                    saniye_basina_istek=ayarlar.get("rate_limit_saniye_basina_istek", 2.0),
                    min_bekleme=ayarlar.get("rate_limit_min_bekleme_sn", 0.5),
                    max_bekleme=ayarlar.get("rate_limit_max_bekleme_sn", 3.0),
                    jitter=ayarlar.get("rate_limit_jitter_sn", 0.3),
                    gunluk_limit=ayarlar.get("rate_limit_basina_dusen_gunluk_limit", 2000)
                )
            else:
                _rate_limiter = None
    return _rate_limiter

def retry_with_backoff(max_deneme: int = None, base_bekleme: float = None,
                       backoff_carpani: float = None, max_bekleme: float = None):
    """
    Decorator: Başarısız API çağrılarını exponential backoff ile tekrar dener.
    
    Kullanım:
        @retry_with_backoff(max_deneme=3)
        def api_cagrisi(...):
            ...
    """
    ayarlar = rate_limit_ayarlari_al()
    _max_deneme = max_deneme or ayarlar.get("retry_max_deneme", 3)
    _base_bekleme = base_bekleme or ayarlar.get("retry_base_bekleme_sn", 2.0)
    _backoff = backoff_carpani or ayarlar.get("retry_backoff_carpani", 2.0)
    _max_bekleme = max_bekleme or ayarlar.get("retry_max_bekleme_sn", 60.0)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            son_hata = None
            for deneme in range(1, _max_deneme + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    son_hata = e
                    hata_str = str(e).lower()
                    
                    # Rate limit / ban / timeout hataları
                    geri_cekilme_gereken = any(kw in hata_str for kw in [
                        "rate limit", "too many requests", "429",
                        "timeout", "connection", "forbidden", "403",
                        "service unavailable", "503", "temporarily",
                        "jsondecodeerror", "no data found"
                    ])
                    
                    if deneme < _max_deneme and geri_cekilme_gereken:
                        bekleme = min(_base_bekleme * (_backoff ** (deneme - 1)), _max_bekleme)
                        jitter = random.uniform(0, bekleme * 0.25)
                        toplam_bekleme = bekleme + jitter
                        
                        _veri_logger.warning(
                            f"  🔄 Retry {deneme}/{_max_deneme}: {toplam_bekleme:.1f}sn bekleniyor... "
                            f"Hata: {str(e)[:80]}"
                        )
                        time.sleep(toplam_bekleme)
                    else:
                        raise
            raise son_hata
        return wrapper
    return decorator

def batch_bol(sembol_listesi: list, batch_boyutu: int = None) -> list:
    """
    Büyük hisse listesini batch'lere böler.
    Her batch'in kripto mu, BIST mi yoksa US hisse mi olduğunu belirler.
    """
    if batch_boyutu is None:
        ayarlar = rate_limit_ayarlari_al()
        batch_boyutu = ayarlar.get("tarama_batch_boyutu", 25)
    
    batches = []
    for i in range(0, len(sembol_listesi), batch_boyutu):
        batch = sembol_listesi[i:i + batch_boyutu]
        
        # Batch türünü belirle (ilk sembolden)
        tur = hisse_turu_belirle(batch[0]) if batch else 'bilinmiyor'
        
        batches.append({
            "indeks": len(batches),
            "semboller": batch,
            "tur": tur,
            "boyut": len(batch)
        })
    
    return batches

def batch_arasi_bekle(batch_indeksi: int = 0):
    """
    İki batch arasında bekleme yapar.
    İlk batch'te bekleme yapılmaz (indeks 0).
    """
    if batch_indeksi == 0:
        return
    
    ayarlar = rate_limit_ayarlari_al()
    bekleme_sn = ayarlar.get("tarama_batch_arasi_sn", 45)
    
    # Batch indeksine göre artan bekleme (her 5 batch'te +10sn)
    ek_bekleme = (batch_indeksi // 5) * 10
    toplam_bekleme = bekleme_sn + ek_bekleme
    
    _veri_logger.info(f"  ⏸ Batch #{batch_indeksi} tamamlandı. "
                      f"IP koruması için {toplam_bekleme}sn bekleniyor...")
    time.sleep(toplam_bekleme)

def rate_limit_baslat():
    """Rate limiter'ı başlatır (gerekirse config'i günceller)."""
    cfg = _config_yukle()
    varsayilan = _rate_limit_varsayilan()
    
    degisti = False
    for k, v in varsayilan.items():
        if k not in cfg:
            cfg[k] = v
            degisti = True
    
    if degisti:
        _config_kaydet(cfg)
        _veri_logger.info("📝 Rate limit ayarları config'e eklendi.")
    
    rl = _rate_limiter_al()
    if rl:
        durum = rl.durum_raporu()
        _veri_logger.info(f"🛡️ IP Koruma aktif: {durum['oran_saniye']} istek/sn, "
                         f"günlük limit: {durum['gunluk_limit']}")
        return True
    else:
        _veri_logger.warning("⚠️ Rate limit DEVRE DIŞI! (rate_limit_aktif=False)")
        return False

# ══════════════════════════════════════════════════════════════════════
#  ÖLÜ HAVUZ (DEAD POOL) — Delisted / Kote Dışı Hisse Yönetimi
# ══════════════════════════════════════════════════════════════════════

DEAD_SEMBOL_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dead_semboller.json")

# yfinance "delisted" hata mesajı anahtar kelimeleri
# ⚠️ DİKKAT: Bu liste bilinçli olarak DARALTILDI (v1.2).
# Önceden "404", "not found", "no timezone found", "jsondecodeerror", "yahoo error"
# gibi geniş anahtar kelimeler rate-limit (429) ve geçici ağ hatalarını da
# "delisted" sanıp canlı hisseleri ölü havuza atıyordu. Bu yüzden kaldırıldı.
# Artık SADECE gerçekten "delisted" olduğunu belirten net ifadeler eşleşir.
_DELISTED_ANAHTAR_KELIMELER = [
    "possibly delisted",
    "no data found, symbol may be delisted",
    "symbol may be delisted",
    "delisted",
    "no price data found",
]


def dead_liste_yukle() -> set:
    """
    Ölü (delisted/kote dışı) sembollerin set'ini JSON dosyasından yükler.
    Dosya yoksa boş set döner.
    """
    if not os.path.exists(DEAD_SEMBOL_DOSYASI):
        return set()
    try:
        with open(DEAD_SEMBOL_DOSYASI, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("dead_semboller", []))
    except (json.JSONDecodeError, IOError):
        return set()


def dead_listeye_ekle(kod: str, sebep: str = "bilinmiyor") -> bool:
    """
    Bir sembolü ölü havuza ekler.
    Zaten varsa tekrar eklemez.
    Dönüş: True (yeni eklendi), False (zaten vardı)
    """
    dead_set = dead_liste_yukle()
    kod_ust = kod.upper()
    if kod_ust in dead_set:
        return False

    dead_set.add(kod_ust)
    # Kaydet
    try:
        with open(DEAD_SEMBOL_DOSYASI, "w", encoding="utf-8") as f:
            json.dump({
                "dead_semboller": sorted(list(dead_set)),
                "son_guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "toplam_olu": len(dead_set),
                "not": "Bu semboller delisted/kote dışı olduğu için tarama listelerinden otomatik çıkarılmıştır."
            }, f, indent=2, ensure_ascii=False)
        _veri_logger.info(f"  💀 Ölü havuza eklendi: {kod_ust} ({sebep})")
        return True
    except IOError as e:
        _veri_logger.error(f"  ✗ Ölü havuz dosyası yazılamadı: {e}")
        return False


def dead_listeden_sil(kod: str) -> bool:
    """Bir sembolü ölü havuzdan çıkarır (yeniden aktif hale geldiyse)."""
    dead_set = dead_liste_yukle()
    kod_ust = kod.upper()
    if kod_ust not in dead_set:
        return False
    dead_set.discard(kod_ust)
    try:
        with open(DEAD_SEMBOL_DOSYASI, "w", encoding="utf-8") as f:
            json.dump({
                "dead_semboller": sorted(list(dead_set)),
                "son_guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "toplam_olu": len(dead_set)
            }, f, indent=2, ensure_ascii=False)
        _veri_logger.info(f"  ♻ Ölü havuzdan çıkarıldı: {kod_ust}")
        return True
    except IOError:
        return False


def dead_listeyi_temizle(liste: list) -> list:
    """
    Bir hisse listesindeki ölü sembolleri temizler.
    Temizlenmiş yeni bir liste döndürür.
    """
    dead_set = dead_liste_yukle()
    if not dead_set:
        return list(liste)
    
    orijinal_sayi = len(liste)
    temiz_liste = [s for s in liste if s.upper() not in dead_set]
    silinen = orijinal_sayi - len(temiz_liste)
    
    if silinen > 0:
        _veri_logger.info(f"  🧹 {silinen} ölü hisse listeden filtrelendi (toplam {len(temiz_liste)} canlı)")
    
    return temiz_liste


def delisted_mi(hata_mesaji: str) -> bool:
    """
    Bir hata mesajının 'delisted' (kote dışı) hatası olup olmadığını kontrol eder.
    """
    if not hata_mesaji:
        return False
    hata_lower = hata_mesaji.lower()
    return any(kw in hata_lower for kw in _DELISTED_ANAHTAR_KELIMELER)


def _yfinance_rapor_dene(kod: str) -> bool:
    """
    yfinance Ticker.info üzerinden hissenin hala aktif olup olmadığını kontrol eder.
    Aktif hisselerde quoteType, regularMarketPrice gibi alanlar dolu olur.
    Dönüş: True (aktif/erişilebilir), False (delisted olabilir)
    """
    try:
        tk = yf.Ticker(kod)
        info = tk.info
        if not info or len(info) < 3:
            # DÜZELTME (Ölü Havuz Tuzağı): Boş info rate-limit/geçici ağ
            # hatası olabilir. Emin olunamadığında aktif kabul et.
            return True
        # Bazı temel alanlar kontrolü
        quote_type = info.get("quoteType", "")
        if quote_type and quote_type.upper() == "MUTUALFUND":
            # Mutual fund, hisse değil
            return True
        # Eğer hiçbir fiyat verisi yoksa delisted olabilir
        fiyat = info.get("regularMarketPrice") or info.get("previousClose")
        if fiyat is None:
            # Bazı durumlarda info boş dönebilir ama hisse aktiftir
            # Daha detaylı kontrol: marketState veya tradeable
            if info.get("tradeable") is False:
                return False
        return True
    except Exception:
        return True  # Emin olamayız, aktif kabul et


def hisse_turu_belirle(kod: str) -> str:
    """
    Hisse kodundan türünü belirler.
    
    Dönüş: 'bist', 'kripto', 'nasdaq', 'sp500', 'forex', 'bilinmiyor'
    """
    kod_ust = kod.upper()
    
    # Kripto (Binance formatı: BTCUSDT, ETHUSDT vb.)
    if kod_ust.endswith('USDT') or kod_ust.endswith('USD') and not kod.endswith('.IS'):
        return 'kripto'
    
    # BIST
    if kod_ust.endswith('.IS'):
        return 'bist'
    
    # Forex
    if len(kod_ust) <= 7 and ('USD' in kod_ust or 'EUR' in kod_ust or 'TRY' in kod_ust) and '-' not in kod_ust and '.' not in kod_ust:
        return 'forex'
    
    # US hisseleri (NASDAQ/SP500)
    return 'us'


def _yfinance_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """yfinance ile veri çeker. Başarısız olursa None döner."""
    if not YF_AKTIF:
        return None
    
    try:
        tk = yf.Ticker(kod)
        df = tk.history(period=period)
        
        if df is None or df.empty or len(df) < 10:
            # Veri boş geldi — delisted kontrolü yap
            # ⚠️ DÜZELTME (Ölü Havuz Tuzağı): Sadece NET `tradeable=False`
            # onayı ölü havuza eklenebilir. Boş/eksik info; rate limit (429),
            # geçici ağ kesintisi veya Yahoo bakımı yüzünden olabilir — bu
            # durumlarda THYAO/AAPL gibi canlı hisseler yanlışlıkla "kote dışı"
            # sanılıp kalıcı olarak tarama listelerinden çıkarılıyordu.
            if df is not None and df.empty:
                try:
                    import time as _t
                    _t.sleep(0.3)  # rate-limit'i biraz bekleyip tekrar dene
                    tk2 = yf.Ticker(kod)
                    df2 = tk2.history(period=period)
                    if df2 is not None and not df2.empty and len(df2) >= 10:
                        return df2.dropna(subset=["Close"])
                except Exception:
                    pass
                try:
                    info = tk.info
                    if info and info.get("tradeable") is False:
                        dead_listeye_ekle(kod, "tradeable=False (kote dışı)")
                    else:
                        # Boş info rate-limit/ağ hatası olabilir — ölü havuza EKLEME
                        _veri_logger.debug(f"{kod}: boş veri - ölü havuza eklenmedi (muhtemel rate limit / geçici ağ sorunu)")
                except Exception:
                    _veri_logger.debug(f"{kod}: info alınamadı - ölü havuza eklenmedi (geçici hata)")
            return None
        
        # MultiIndex sütunları düzelt
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Gerekli sütunları kontrol et
        gerekli = ['Open', 'High', 'Low', 'Close', 'Volume']
        eksik = [c for c in gerekli if c not in df.columns]
        if len(eksik) >= 3:
            return None
        
        df = df.dropna(subset=['Close'])
        if len(df) < 10:
            return None
        
        _veri_logger.info(f"  ✓ yfinance: {kod} ({len(df)} satır)")
        return df
        
    except Exception as e:
        hata_str = str(e)
        _veri_logger.debug(f"  ✗ yfinance ({kod}): {hata_str[:120]}")
        # Delisted hatası kontrolü (rate-limit/geçici hatalar ölü havuza EKLENMEZ)
        hata_lower = hata_str.lower()
        rate_limit_belirtisi = any(kw in hata_lower for kw in [
            "rate limit", "too many requests", "429", "403", "forbidden",
            "timeout", "connection", "jsondecodeerror", "no timezone found"
        ])
        if delisted_mi(hata_str) and not rate_limit_belirtisi:
            dead_listeye_ekle(kod, f"yfinance hatası: {hata_str[:80]}")
        return None


def _stooq_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """Stooq (pandas_datareader) ile veri çeker. Özellikle BIST için iyi."""
    if not PD_AKTIF:
        return None
    
    # Stooq sembol formatına çevir
    if kod.endswith('.IS'):
        stooq_kod = kod.replace('.IS', '.E')
    else:
        # US hisseleri için Stooq'da .US eki gerekir, ama direkt deneyelim
        stooq_kod = kod
    
    try:
        # Tarih aralığını period'dan hesapla
        period_map = {
            '1mo': 30, '3mo': 90, '6mo': 180,
            '1y': 365, '2y': 730, '3y': 1095, '5y': 1825, '10y': 3650
        }
        gun = period_map.get(period, 1825)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=gun)
        
        df = web.DataReader(stooq_kod, 'stooq', start=start_date, end=end_date)
        
        if df is None or df.empty or len(df) < 10:
            return None
        
        # Stooq sütunları: Open, High, Low, Close, Volume (zaten doğru formatta)
        # Stooq veriyi ters sırada verir (yeni -> eski), düzeltelim
        df = df.sort_index()
        
        df = df.dropna(subset=['Close'])
        if len(df) < 10:
            return None
        
        _veri_logger.info(f"  ✓ Stooq: {kod} ({len(df)} satır)")
        return df
        
    except Exception as e:
        hata_str = str(e)
        _veri_logger.debug(f"  ✗ Stooq ({kod}): {hata_str[:120]}")
        return None


def _yahoo_pdr_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """pandas_datareader üzerinden Yahoo Finance (alternatif yol)."""
    if not PD_AKTIF:
        return None
    
    try:
        period_map = {
            '1mo': 30, '3mo': 90, '6mo': 180,
            '1y': 365, '2y': 730, '3y': 1095, '5y': 1825, '10y': 3650
        }
        gun = period_map.get(period, 1825)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=gun)
        
        df = web.DataReader(kod, 'yahoo', start=start_date, end=end_date)
        
        if df is None or df.empty or len(df) < 10:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df = df.dropna(subset=['Close'])
        if len(df) < 10:
            return None
        
        _veri_logger.info(f"  ✓ Yahoo-PDR: {kod} ({len(df)} satır)")
        return df
        
    except Exception as e:
        hata_str = str(e)
        _veri_logger.debug(f"  ✗ Yahoo-PDR ({kod}): {hata_str[:120]}")
        hata_lower = hata_str.lower()
        rate_limit_belirtisi = any(kw in hata_lower for kw in [
            "rate limit", "too many requests", "429", "403", "forbidden",
            "timeout", "connection", "jsondecodeerror", "no timezone found"
        ])
        if delisted_mi(hata_str) and not rate_limit_belirtisi:
            dead_listeye_ekle(kod, f"Yahoo-PDR hatası: {hata_str[:80]}")
        return None


def _ccxt_ile_cek(kod: str, period: str = "5y", exchange_name: str = "binance") -> pd.DataFrame:
    """ccxt ile belirtilen borsadan kripto verisi çeker."""
    if not CCXT_AKTIF:
        return None
    
    # Sadece kripto sembolleri için çalışır
    if not kod.upper().endswith('USDT') and not kod.upper().endswith('USD'):
        return None
    
    try:
        exchange_class = getattr(ccxt, exchange_name, None)
        if exchange_class is None:
            return None
        
        exchange = exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        # Period -> timeframe dönüşümü
        period_gun = {
            '1mo': 30, '3mo': 90, '6mo': 180,
            '1y': 365, '2y': 730, '3y': 1095, '5y': 1825, '10y': 3650
        }
        
        gun = period_gun.get(period, 730)
        
        since = exchange.parse8601((datetime.now() - timedelta(days=gun)).strftime('%Y-%m-%dT00:00:00Z'))
        
        ohlcv = exchange.fetch_ohlcv(kod.upper(), '1d', since=since, limit=1000)
        
        if not ohlcv or len(ohlcv) < 10:
            return None
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('Date')
        df = df.drop('timestamp', axis=1)
        
        if len(df) < 10:
            return None
        
        _veri_logger.info(f"  ✓ {exchange_name.title()}: {kod} ({len(df)} satır)")
        return df
        
    except Exception as e:
        _veri_logger.debug(f"  ✗ {exchange_name.title()} ({kod}): {str(e)[:100]}")
        return None


def _ccxt_binance_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """ccxt (Binance) ile kripto verisi çeker. (geriye dönük uyumluluk)"""
    return _ccxt_ile_cek(kod, period, "binance")


def _ccxt_kraken_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """ccxt (Kraken) ile kripto verisi çeker."""
    # Kraken'de USDT yerine USD kullanılır, sembol formatını düzelt
    kod_temiz = kod.upper()
    if kod_temiz.endswith('USDT'):
        kod_temiz = kod_temiz.replace('USDT', 'USD')
    return _ccxt_ile_cek(kod_temiz, period, "kraken")


def _ccxt_kucoin_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """ccxt (KuCoin) ile kripto verisi çeker."""
    return _ccxt_ile_cek(kod, period, "kucoin")


def _ccxt_okx_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """ccxt (OKX) ile kripto verisi çeker."""
    return _ccxt_ile_cek(kod, period, "okx")


def _ccxt_bybit_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """ccxt (Bybit) ile kripto verisi çeker."""
    return _ccxt_ile_cek(kod, period, "bybit")


def _coingecko_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """
    CoinGecko ücretsiz API'si ile kripto verisi çeker.
    Rate limit: 10-30 istek/dakika (ücretsiz API).
    """
    if not REQUESTS_AKTIF:
        return None
    
    # Sadece kripto sembolleri
    kod_ust = kod.upper()
    if not (kod_ust.endswith('USDT') or kod_ust.endswith('USD')):
        return None
    
    try:
        coin_id = kod_ust.replace('USDT', '').replace('USD', '').lower()
        
        period_gun = {
            '1mo': 30, '3mo': 90, '6mo': 180,
            '1y': 365, '2y': 730, '3y': 1095, '5y': 1825, '10y': 3650
        }
        gun = period_gun.get(period, 365)
        
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': str(min(gun, 365)),
            'interval': 'daily'
        }
        
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        prices = data.get('prices', [])
        volumes = data.get('total_volumes', [])
        
        if len(prices) < 10:
            return None
        
        df = pd.DataFrame(prices, columns=['timestamp', 'Close'])
        df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('Date')
        df = df.drop('timestamp', axis=1)
        
        if volumes:
            vol_df = pd.DataFrame(volumes, columns=['timestamp', 'Volume'])
            vol_df['Date'] = pd.to_datetime(vol_df['timestamp'], unit='ms')
            vol_df = vol_df.set_index('Date')
            vol_df = vol_df.drop('timestamp', axis=1)
            df['Volume'] = vol_df['Volume']
        else:
            df['Volume'] = 0
        
        # OHLC tahmini (CoinGecko sadece fiyat verir, OHLC'yi fiyattan türet)
        df['Open'] = df['Close'].shift(1)
        df['High'] = df['Close'] * 1.02
        df['Low'] = df['Close'] * 0.98
        df = df.dropna(subset=['Open'])
        
        if len(df) < 10:
            return None
        
        _veri_logger.info(f"  ✓ CoinGecko: {kod} ({len(df)} satır)")
        return df
        
    except Exception as e:
        _veri_logger.debug(f"  ✗ CoinGecko ({kod}): {str(e)[:100]}")
        return None


def _yfinance_csv_ile_cek(kod: str, period: str = "5y") -> pd.DataFrame:
    """Yahoo Finance CSV API'si ile direkt HTTP isteği (son çare)."""
    if not REQUESTS_AKTIF:
        return None
    
    try:
        # Yahoo Finance CSV download URL
        period_map = {
            '1mo': '1mo', '3mo': '3mo', '6mo': '6mo',
            '1y': '1y', '2y': '2y', '3y': '5y', '5y': '5y', '10y': '10y'
        }
        interval_map = {
            '1mo': '1d', '3mo': '1d', '6mo': '1d',
            '1y': '1d', '2y': '1d', '3y': '1d', '5y': '1d', '10y': '1wk'
        }
        
        p = period_map.get(period, '5y')
        i = interval_map.get(period, '1d')
        
        # YEREL VERİTABANI İLE HIZLI İNDİRME
        try:
            from mod_yerel_veri import yerel_veriyi_getir_ve_guncelle
            df = yerel_veriyi_getir_ve_guncelle(kod, limit_gun=90)
        except Exception:
            # Yerel veritabanında hata olursa normal şekilde indir
            df = yf.download(kod, period=p, interval=i, progress=False, auto_adjust=True)
        
        if df is None or df.empty or len(df) < 10:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df = df.dropna(subset=['Close'])
        if len(df) < 10:
            return None
        
        _veri_logger.info(f"  ✓ Yahoo-CSV: {kod} ({len(df)} satır)")
        return df
        
    except Exception as e:
        hata_str = str(e)
        _veri_logger.debug(f"  ✗ Yahoo-CSV ({kod}): {hata_str[:120]}")
        hata_lower = hata_str.lower()
        rate_limit_belirtisi = any(kw in hata_lower for kw in [
            "rate limit", "too many requests", "429", "403", "forbidden",
            "timeout", "connection", "jsondecodeerror", "no timezone found"
        ])
        if delisted_mi(hata_str) and not rate_limit_belirtisi:
            dead_listeye_ekle(kod, f"Yahoo-CSV hatası: {hata_str[:80]}")
        return None

def veri_cek(kod: str, period: str = "5y", kaynak_sirasi: list = None, start_date: str = None) -> pd.DataFrame:
    """
    Birden fazla kaynaktan veri çekmeyi dener.
    Her kaynak sırayla denenir, ilk başarılı sonuç döndürülür.
    Tüm kaynaklar başarısızsa ve delisted tespit edilirse ölü havuza ekler.
    
    Parametreler:
        kod: Hisse kodu (örn: THYAO.IS, BTCUSDT, AAPL)
        period: Veri periyodu (1mo, 3mo, 6mo, 1y, 2y, 5y)
        kaynak_sirasi: Denenecek kaynak fonksiyonlarının listesi (None = otomatik)
        start_date: Başlangıç tarihi (str, 'YYYY-MM-DD'). Verilirse period yerine bu tarihten itibaren çekilir.
                    Modelin son eğitim tarihinden bugüne incremental veri çekmek için kullanılır.
    
    Dönüş: OHLCV DataFrame veya None
    """
    # Önce ölü havuz kontrolü — zaten ölüyse direkt None dön
    dead_set = dead_liste_yukle()
    if kod.upper() in dead_set:
        _veri_logger.debug(f"  ⏭ Atlanıyor (ölü havuzda): {kod}")
        return None
    
    tur = hisse_turu_belirle(kod)
    
    # ── start_date verilmişse period'u dinamik hesapla ──
    if start_date:
        try:
            from datetime import datetime
            bas_tarih = datetime.strptime(start_date, '%Y-%m-%d')
            bugun = datetime.now()
            gun_farki = (bugun - bas_tarih).days
            # En az 90 gün (indikatörler için minimum veri), en fazla 5y
            gun_farki = max(90, min(gun_farki + 30, 1825))  # +30 buffer indikatörler için
            # Uygun period'u seç
            if gun_farki <= 90:
                period = '6mo'
            elif gun_farki <= 365:
                period = '1y'
            elif gun_farki <= 730:
                period = '2y'
            elif gun_farki <= 1095:
                period = '3y'
            else:
                period = '5y'
            _veri_logger.debug(f"  📅 Incremental veri: {start_date} → bugün ({gun_farki}gün) → period={period}")
        except:
            pass  # start_date geçersizse period'u olduğu gibi kullan
    
    # Otomatik kaynak sıralaması (çoklu borsa + API)
    if kaynak_sirasi is None:
        if tur == 'kripto':
            kaynak_sirasi = [
                _ccxt_binance_ile_cek,    # Binance (en büyük likidite)
                _ccxt_kucoin_ile_cek,     # KuCoin (geniş altcoin)
                _ccxt_kraken_ile_cek,     # Kraken (USD pariteleri)
                _ccxt_bybit_ile_cek,      # Bybit (yeni token'lar)
                _ccxt_okx_ile_cek,        # OKX
                _yfinance_ile_cek,         # Yahoo (BTC-USD, ETH-USD)
                _coingecko_ile_cek,        # CoinGecko API (son çare)
                _yfinance_csv_ile_cek,
            ]
        elif tur == 'bist':
            kaynak_sirasi = [_stooq_ile_cek, _yfinance_ile_cek, _yahoo_pdr_ile_cek, _yfinance_csv_ile_cek]
        else:
            kaynak_sirasi = [_yfinance_ile_cek, _stooq_ile_cek, _yahoo_pdr_ile_cek, _yfinance_csv_ile_cek]
    
    tum_hata_mesajlari = []
    
    for idx, kaynak_fn in enumerate(kaynak_sirasi):
        try:
            df = kaynak_fn(kod, period)
            if df is not None and not df.empty and len(df) >= 10:
                return df
        except Exception as e:
            hata_str = str(e)
            tum_hata_mesajlari.append(hata_str)
            _veri_logger.debug(f"  Kaynak #{idx+1} hatası ({kod}): {hata_str[:120]}")
            continue
    
    # Tüm kaynaklar başarısız — delisted kontrolü
    # DÜZELTME (Ölü Havuz Tuzağı): Rate-limit (429) ve geçici ağ hataları
    # tüm kaynaklarda aynı anda görülebilir. Bu durumlarda canlı hisseler
    # yanlışlıkla "kote dışı" sanılıp kalıcı olarak taramadan çıkarılıyordu.
    # Ölü havuza ekleme SADECE net `tradeable=False` onayıyla yapılır.
    birlestirilmis_hata = " | ".join(tum_hata_mesajlari)
    rate_limit_belirtisi = any(kw in birlestirilmis_hata.lower() for kw in [
        "rate limit", "too many requests", "429", "403",
        "forbidden", "timeout", "connection", "jsondecodeerror",
        "no timezone found", "404"
    ])
    if delisted_mi(birlestirilmis_hata) and not rate_limit_belirtisi:
        dead_listeye_ekle(kod, f"Tüm kaynaklar başarısız + delisted: {birlestirilmis_hata[:100]}")
    elif len(tum_hata_mesajlari) > 0 and not rate_limit_belirtisi:
        # Sadece NET tradeable=False onayı ölü havuza ekleyebilir
        try:
            tk = yf.Ticker(kod)
            info = tk.info
            if info and info.get("tradeable") is False:
                dead_listeye_ekle(kod, "Tüm kaynaklar başarısız + tradeable=False (kote dışı)")
            else:
                _veri_logger.debug(f"{kod}: tüm kaynaklar başarısız ama kote dışı doğrulanamadı - ölü havuza eklenmedi")
        except Exception:
            _veri_logger.debug(f"{kod}: info alınamadı - ölü havuza eklenmedi (geçici hata)")
    
    _veri_logger.warning(f"  ⚠ Tüm kaynaklar başarısız: {kod}")
    return None


def canli_fiyat_cek(kod: str) -> dict:
    """
    Tek bir hisse için canlı fiyat bilgisini çeker.
    Birden fazla kaynak dener.
    Ölü havuzdaki hisseleri atlar.
    
    Dönüş: {
        'sembol': str,
        'fiyat': float,
        'acan': float,
        'yuksek': float,
        'dusuk': float,
        'hacim': float,
        'degisim': float
    } veya None
    """
    # Ölü havuz kontrolü
    dead_set = dead_liste_yukle()
    if kod.upper() in dead_set:
        return None
    
    # Önce yfinance ile dene
    if YF_AKTIF:
        try:
            h = yf.Ticker(kod).history(period="5d")
            h = h.dropna(subset=["Close"])
            
            if len(h) >= 2:
                son = float(h["Close"].iloc[-1])
                acan = float(h["Open"].iloc[-1])
                yuk = float(h["High"].iloc[-1])
                dus = float(h["Low"].iloc[-1])
                hacim = float(h["Volume"].iloc[-1])
                deg = ((son - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100
                
                return {
                    "sembol": kod,
                    "fiyat": son,
                    "acan": acan,
                    "yuksek": yuk,
                    "dusuk": dus,
                    "hacim": hacim,
                    "degisim": round(deg, 2)
                }
        except Exception as e:
            hata_str = str(e)
            # DÜZELTME (Ölü Havuz Tuzağı): Rate-limit/geçici ağ hatalarında
            # canlı hisseleri ölü havuza EKLEME. Sadece gerçek delisted
            # ifadesi ve tradeable=False doğrulamasıyla ekleme yapılır.
            hata_lower = hata_str.lower()
            rate_limit_belirtisi = any(kw in hata_lower for kw in [
                "rate limit", "too many requests", "429", "403",
                "forbidden", "timeout", "connection", "jsondecodeerror"
            ])
            if delisted_mi(hata_str) and not rate_limit_belirtisi:
                dead_listeye_ekle(kod, f"canli_fiyat yfinance: {hata_str[:80]}")
                return None
    
    # ccxt ile dene (kripto için)
    tur = hisse_turu_belirle(kod)
    if tur == 'kripto' and CCXT_AKTIF:
        try:
            exchange = ccxt.binance({'enableRateLimit': True})
            ticker = exchange.fetch_ticker(kod.upper())
            if ticker and 'last' in ticker:
                son = float(ticker['last'])
                acan = float(ticker.get('open', son))
                yuk = float(ticker.get('high', son))
                dus = float(ticker.get('low', son))
                hacim = float(ticker.get('quoteVolume', 0))
                deg = float(ticker.get('percentage', 0))
                
                return {
                    "sembol": kod,
                    "fiyat": son,
                    "acan": acan,
                    "yuksek": yuk,
                    "dusuk": dus,
                    "hacim": hacim,
                    "degisim": round(deg, 2)
                }
        except:
            pass
    
    return None


def toplu_fiyat_cek(semboller: list) -> list:
    """
    Birden fazla hisse için canlı fiyat çeker.
    Tüm kaynakları dener.
    Ölü havuzdaki hisseleri otomatik filtreler.
    
    Dönüş: [{sembol, fiyat, acan, yuksek, dusuk, hacim, degisim}, ...]
    """
    sonuc = []
    temiz_semboller = dead_listeyi_temizle(semboller)
    
    for sym in temiz_semboller:
        fiyat = canli_fiyat_cek(sym)
        if fiyat:
            sonuc.append(fiyat)
    
    return sonuc


# ── TEST ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  ÇOK KAYNAKLI VERİ MOTORU TEST")
    print("=" * 60)
    
    # Ölü havuz durumu
    dead = dead_liste_yukle()
    print(f"\n  💀 Ölü Havuz: {len(dead)} sembol")
    if dead:
        print(f"     {sorted(list(dead))[:10]}...")
    
    test_hisseleri = [
        ("THYAO.IS", "BIST"),
        ("GARAN.IS", "BIST"),
        ("BTC-USD", "Kripto (Yahoo)"),
        ("BTCUSDT", "Kripto (Binance)"),
        ("AAPL", "NASDAQ"),
        ("NVDA", "NASDAQ"),
    ]
    
    for kod, tur in test_hisseleri:
        print(f"\n  [{tur}] {kod} deneniyor...")
        df = veri_cek(kod, period="6mo")
        if df is not None and not df.empty:
            print(f"    ✓ Başarılı! {len(df)} satır, Son fiyat: {df['Close'].iloc[-1]:.2f}")
        else:
            print(f"    ✗ Tüm kaynaklar başarısız!")
    
    print(f"\n  💀 Güncel Ölü Havuz: {len(dead_liste_yukle())} sembol")