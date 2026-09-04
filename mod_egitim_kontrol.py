# ══════════════════════════════════════════════════════════════════════
#  mod_egitim_kontrol.py — Tek Tıkla Eğitim Kontrol Paneli v3.0
#  
#  Mevcut mod_ml_egitim.py KODLARINA DOKUNMADAN:
#    • Seçenek 1: standart → Tek tur standart eğitim (Optuna KAPALI)
#    • Seçenek 2: optuna   → Tek tur derin Optuna eğitimi (AĞIR)
#    • Seçenek 3: zamanli  → Her gün 22:00 + 2 günde bir derin Optuna
#
#  Kullanım (komut satırı):
#    python mod_egitim_kontrol.py standart  → Şimdi standart eğitim
#    python mod_egitim_kontrol.py optuna    → Şimdi derin Optuna eğitimi
#    python mod_egitim_kontrol.py zamanli   → 22:00 zamanlanmış eğitim
# ══════════════════════════════════════════════════════════════════════

import sys
import os
import time
import json
import sqlite3
import subprocess
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import OrderedDict

# Proje kök dizini (bu dosyanın bulunduğu dizin)
_ANA_DIZIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ANA_DIZIN)

from mod_ml_egitim import (
    ZamanlanmisEgitimMotoru,
    VARSAYILAN_EGITIM_HISSELERI,
    _egitim_log_baslik,
    _egitim_log_yaz,
    _ml_logger,
    EGITIM_LOG_DOSYASI,
    get_motor,
    MODEL_DIZINI
)

# Tüm hisse listelerini import et
from hisseler_bist import BIST
from hisseler_kripto import KRIPTO_LISTESI
from hisseler_nasdaq import NASDAQ
from hisseler_sp500 import SP500

# Binance için
try:
    import ccxt
    CCXT_AKTIF = True
except ImportError:
    CCXT_AKTIF = False

# Veritabanı yolu
DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")

# PID takip dosyası
PID_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".egitim_durum.txt")

# Checkpoint dosyası — eğitimin kaldığı yeri takip eder
CHECKPOINT_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".egitim_checkpoint.json")
CHECKPOINT_GECERLILIK_SAAT = 2  # Bu saatten eski checkpoint sıfırlanır (yeni veri gelmiş olabilir)

# ══════════════════════════════════════════════════════════════════════
#  CHECKPOINT (KALINAN YER) TAKİP SİSTEMİ
# ══════════════════════════════════════════════════════════════════════

def checkpoint_yukle() -> dict:
    """
    .egitim_checkpoint.json dosyasını okur.
    Dönüş: {'tarih': str, 'egitilenler': list, 'tum_liste': list, 'basarili': int, 'basarisiz': int}
    Dosya yoksa veya süresi geçmişse boş checkpoint döner.
    """
    try:
        if not os.path.exists(CHECKPOINT_DOSYASI):
            return _bos_checkpoint()
        
        with open(CHECKPOINT_DOSYASI, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Süre kontrolü: son checkpoint'ten bu yana CHECKPOINT_GECERLILIK_SAAT geçti mi?
        son_tarih_str = data.get('tarih', '')
        if son_tarih_str:
            try:
                son_tarih = datetime.strptime(son_tarih_str, '%Y-%m-%d %H:%M:%S')
                gecen_saat = (datetime.now() - son_tarih).total_seconds() / 3600
                if gecen_saat > CHECKPOINT_GECERLILIK_SAAT:
                    # Checkpoint eski — tüm listeyi yeniden eğit
                    _ml_logger.info(f"  ⏰ Checkpoint {gecen_saat:.1f} saat eski, sıfırlanıyor (yeni veri eklenecek)")
                    checkpoint_sil()
                    return _bos_checkpoint()
            except:
                pass
        
        return {
            'tarih': data.get('tarih', ''),
            'egitilenler': data.get('egitilenler', []),
            'tum_liste': data.get('tum_liste', []),
            'basarili': data.get('basarili', 0),
            'basarisiz': data.get('basarisiz', 0),
            'toplam_egitilen': data.get('toplam_egitilen', 0),
            'basarisiz_liste': data.get('basarisiz_liste', [])  # v3.1
        }
    except:
        return _bos_checkpoint()

def _bos_checkpoint() -> dict:
    return {
        'tarih': '',
        'egitilenler': [],
        'tum_liste': [],
        'basarili': 0,
        'basarisiz': 0,
        'toplam_egitilen': 0,
        'basarisiz_liste': []  # v3.1: başarısızlar ayrı listede, tekrar denenmek üzere
    }

def checkpoint_kaydet(ck: dict):
    """Checkpoint'i JSON dosyasına yazar."""
    try:
        ck['tarih'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(CHECKPOINT_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ck, f, ensure_ascii=False, indent=2)
    except:
        pass

def checkpoint_sil():
    """Checkpoint dosyasını siler (sıfırlar)."""
    try:
        if os.path.exists(CHECKPOINT_DOSYASI):
            os.remove(CHECKPOINT_DOSYASI)
    except:
        pass

def checkpointten_kalanlari_getir(tum_liste: list, egitilenler: list) -> list:
    """Tüm listeden zaten eğitilmiş olanları çıkarır, kalanları döner."""
    egitilen_set = set(egitilenler)
    kalanlar = [h for h in tum_liste if h not in egitilen_set]
    return kalanlar

# ══════════════════════════════════════════════════════════════════════
#  EĞİTİM DURUM TAKİP SİSTEMİ
# ══════════════════════════════════════════════════════════════════════

def _pid_yaz(tip: str):
    """Çalışan eğitimin PID ve tipini dosyaya yazar."""
    try:
        with open(PID_DOSYASI, "w") as f:
            f.write(f"{os.getpid()}|{tip}|{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except:
        pass

def _pid_sil():
    """PID dosyasını temizler."""
    try:
        if os.path.exists(PID_DOSYASI):
            os.remove(PID_DOSYASI)
    except:
        pass

def egitim_durumu_oku() -> dict:
    """
    Şu anda çalışan bir eğitim olup olmadığını kontrol eder.
    Dönüş: {'calisiyor': bool, 'tip': str, 'pid': int, 'baslangic': str}
    """
    try:
        if not os.path.exists(PID_DOSYASI):
            return {'calisiyor': False, 'tip': '', 'pid': 0, 'baslangic': ''}
        
        with open(PID_DOSYASI, "r") as f:
            icerik = f.read().strip()
        
        if not icerik:
            return {'calisiyor': False, 'tip': '', 'pid': 0, 'baslangic': ''}
        
        parcalar = icerik.split("|")
        if len(parcalar) < 3:
            return {'calisiyor': False, 'tip': '', 'pid': 0, 'baslangic': ''}
        
        pid = int(parcalar[0])
        tip = parcalar[1]
        baslangic = parcalar[2]
        
        # PID hala çalışıyor mu kontrol et
        import ctypes
        try:
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return {'calisiyor': True, 'tip': tip, 'pid': pid, 'baslangic': baslangic}
            else:
                _pid_sil()
                return {'calisiyor': False, 'tip': '', 'pid': 0, 'baslangic': ''}
        except:
            return {'calisiyor': True, 'tip': tip, 'pid': pid, 'baslangic': baslangic}
            
    except:
        return {'calisiyor': False, 'tip': '', 'pid': 0, 'baslangic': ''}

def egitim_durdur() -> bool:
    """Çalışan eğitimi PID üzerinden durdurur."""
    import signal
    durum = egitim_durumu_oku()
    if not durum['calisiyor']:
        return False
    
    try:
        pid = durum['pid']
        if os.name == 'nt':
            import subprocess
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        _pid_sil()
        return True
    except:
        return False


# ══════════════════════════════════════════════════════════════════════
#  BINANCE 5 DAKİKA CANLI VERİ ÇEKİCİ
# ══════════════════════════════════════════════════════════════════════

class Binance5dkVeriCekici:
    
    def __init__(self):
        self.exchange = None
        self._exchange_olustur()
        self.son_istek_zamani = 0
        self.min_bekleme = 10
        
    def _exchange_olustur(self):
        if not CCXT_AKTIF:
            return False
        try:
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
                'rateLimit': 200,
                'options': {'defaultType': 'spot', 'adjustForTimeDifference': True, 'recvWindow': 60000},
                'timeout': 15000,
            })
            self.exchange.load_markets()
            return True
        except Exception as e:
            _ml_logger.warning(f"  ⚠ Binance bağlantısı kurulamadı: {e}")
            self.exchange = None
            return False
    
    def _rate_limit_bekle(self):
        simdi = time.time()
        fark = simdi - self.son_istek_zamani
        if fark < self.min_bekleme:
            time.sleep(self.min_bekleme - fark + np.random.uniform(0.5, 2.0))
        self.son_istek_zamani = time.time()
    
    def tek_sembol_cek(self, sembol: str, limit: int = 500):
        if self.exchange is None:
            if not self._exchange_olustur():
                return None
        self._rate_limit_bekle()
        try:
            ohlcv = self.exchange.fetch_ohlcv(sembol, timeframe='5m', limit=limit)
            if not ohlcv or len(ohlcv) < 20:
                return None
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('Date').drop('timestamp', axis=1)
            return df
        except ccxt.RateLimitExceeded:
            bekle = 30 + np.random.uniform(5, 15)
            _ml_logger.debug(f"  ⏳ Rate-limit aşıldı, {bekle:.0f}s bekleniyor...")
            time.sleep(bekle)
            return None
        except ccxt.NetworkError:
            _ml_logger.debug("  🌐 Ağ hatası (Binance), 15s bekleniyor...")
            time.sleep(15)
            return None
        except Exception as e:
            _ml_logger.debug(f"  ⚠ Binance 5dk veri hatası ({sembol}): {str(e)[:80]}")
            self.exchange = None
            return None


# ══════════════════════════════════════════════════════════════════════
#  HİSSE LİSTESİ OLUŞTURUCU
# ══════════════════════════════════════════════════════════════════════

def _guclu_al_sinyalleri_getir() -> list:
    try:
        conn = sqlite3.connect(DB_YOLU)
        query = """SELECT hisse, sinyal_tipi FROM ai_sinyaller 
                   WHERE sinyal_tipi LIKE '%GÜÇLÜ%AL%' OR sinyal_tipi = 'GÜÇLÜ AL'
                   ORDER BY id DESC LIMIT 100"""
        try:
            df = pd.read_sql_query(query, conn)
        except:
            conn.close()
            return []
        conn.close()
        if df.empty:
            return []
        goruldu = set()
        guclu_al = []
        for _, row in df.iterrows():
            hisse = str(row['hisse']).strip().upper()
            if hisse not in goruldu and hisse:
                goruldu.add(hisse)
                guclu_al.append(hisse)
        return guclu_al
    except Exception:
        return []


def _yz_karnesi_hisseleri_getir() -> list:
    try:
        conn = sqlite3.connect(DB_YOLU)
        query = "SELECT DISTINCT hisse FROM ai_sinyaller ORDER BY id DESC LIMIT 500"
        try:
            df = pd.read_sql_query(query, conn)
        except:
            conn.close()
            return []
        conn.close()
        if df.empty:
            return []
        return [str(x).strip().upper() for x in df['hisse'].tolist() if x]
    except Exception:
        return []


def _tum_hisseleri_getir() -> list:
    """BIST + NASDAQ + SP500 + Kripto — tüm sistem hisseleri."""
    tum = []
    for h in BIST:
        tum.append(h)
    for h in NASDAQ:
        tum.append(h)
    for h in SP500:
        tum.append(h)
    for k in KRIPTO_LISTESI:
        formatted = k.replace('USDT', '/USDT') if k.endswith('USDT') else k
        tum.append(formatted)
    return list(dict.fromkeys(tum))


def oncelikli_egitim_listesi_olustur() -> list:
    """1.GüçlüAL Hisse → 2.GüçlüAL Coin → 3.YZ Karnesi → 4.Tümü"""
    goruldu = set()
    sonuc = []
    
    guclu_al = _guclu_al_sinyalleri_getir()
    
    hisse_guclu = [h for h in guclu_al if '.IS' in h.upper() or (
        not any(kw in h.upper() for kw in ['USD', 'USDT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE'])
    )]
    for h in hisse_guclu:
        if h not in goruldu:
            goruldu.add(h)
            sonuc.append(h)
    
    coin_guclu = [h for h in guclu_al if h not in goruldu]
    for h in coin_guclu:
        if h not in goruldu:
            goruldu.add(h)
            sonuc.append(h)
    
    yz_kayitli = _yz_karnesi_hisseleri_getir()
    for h in yz_kayitli:
        if h not in goruldu:
            goruldu.add(h)
            sonuc.append(h)
    
    tum = _tum_hisseleri_getir()
    for h in tum:
        if h not in goruldu:
            goruldu.add(h)
            sonuc.append(h)
    
    return sonuc


# ══════════════════════════════════════════════════════════════════════
#  TEK TUR EĞİTİM MOTORU (STANDART & OPTUNA)
# ══════════════════════════════════════════════════════════════════════

class TekTurEgitimMotoru:
    """
    Tek tur eğitim yapar ve biter.
    use_optuna=False → Standart hızlı eğitim (varsayılan parametreler)
    use_optuna=True  → Derin Optuna optimizasyonlu eğitim (30 trial, ~8-10x yavaş)
    
    Checkpoint sistemi ile kaldığı yerden devam eder.
    Son eğitimden 2+ saat geçtiyse sıfırdan başlar (yeni veri eklenmiş olabilir).
    """
    
    def __init__(self, use_optuna: bool = False):
        self.motor = get_motor()
        self.binance_cekici = Binance5dkVeriCekici()
        self.use_optuna = use_optuna
        self.toplam_egitilen = 0
        self.basarili_egitim = 0
        self.basarisiz_egitim = 0
        self.baslangic_zamani = None
        self.egitim_listesi = []
        self.checkpoint = _bos_checkpoint()
        
    def _kripto_mu(self, kod: str) -> bool:
        ust = kod.upper()
        kripto_kelimeler = ['USD', 'USDT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 
                           'ADA', 'DOGE', 'DOT', 'LINK', 'MATIC', 'SHIB', 
                           'LTC', 'TRX', 'UNI', 'ATOM', 'ETC', 'XLM', 'ALGO',
                           'NEAR', 'VET', 'FIL', 'ICP', 'EGLD', 'SAND', 'THETA',
                           'AXS', 'MANA', 'AAVE', 'FTM', 'PEPE', 'WIF', 'FLOKI',
                           'BONK', 'RENDER', 'INJ', 'RNDR', 'SUI', 'APT', 'ARB']
        if '/USDT' in ust or ust.endswith('USDT'):
            return True
        for kw in kripto_kelimeler:
            if ust == kw or ust.startswith(kw) or f'{kw}/' in ust:
                return True
        return False
    
    def _binance_sembolune_cevir(self, kod: str) -> str:
        ust = kod.upper().replace('-', '/')
        if '/' not in ust:
            ust = ust.replace('USDT', '/USDT') if ust.endswith('USDT') else f"{ust}/USDT"
        return ust
    
    def _tek_hisse_egit(self, kod: str) -> dict:
        try:
            if self._kripto_mu(kod):
                kod = self._binance_sembolune_cevir(kod)
            return self.motor.rejime_gore_egit(kod, force_retrain=True, use_optuna=self.use_optuna)
        except Exception as e:
            return {'hata': str(e)}
    
    def _egitim_turu_yap(self, tur_adi: str, hisse_listesi: list):
        if self.use_optuna:
            _ml_logger.info(f"\n{'─'*70}")
            _ml_logger.info(f"  🔬 DERİN OPTUNA EĞİTİMİ: {tur_adi} ({len(hisse_listesi)} sembol)")
            _ml_logger.info(f"  📊 Optuna n_trials=30 | Hisse başı ~30-90sn")
            _ml_logger.info(f"{'─'*70}")
        else:
            _ml_logger.info(f"\n{'─'*70}")
            _ml_logger.info(f"  📚 STANDART EĞİTİM: {tur_adi} ({len(hisse_listesi)} sembol)")
            _ml_logger.info(f"{'─'*70}")
        
        _egitim_log_yaz(f"  📚 {tur_adi} — {len(hisse_listesi)} sembol eğitiliyor "
                       f"(Optuna: {'AÇIK' if self.use_optuna else 'KAPALI'})")
        
        for idx, hisse in enumerate(hisse_listesi, 1):
            try:
                sonuc = self._tek_hisse_egit(hisse)
                if 'hata' in sonuc:
                    self.basarisiz_egitim += 1
                    _ml_logger.warning(f"  ⚠ [{idx}/{len(hisse_listesi)}] {hisse}: {sonuc['hata']}")
                else:
                    self.basarili_egitim += 1
                    self.toplam_egitilen += 1
                    regime = sonuc.get('regime', '?')
                    metrikler = sonuc.get('metrikler', {})
                    acc = metrikler.get('validasyon', {}).get('accuracy', 0) * 100 if 'validasyon' in metrikler else 0
                    _ml_logger.info(f"  ✓ [{idx}/{len(hisse_listesi)}] {hisse:15s} | Rejim: {regime:8s} | Acc: %{acc:.1f}")
                
                # ✅ Her sembolden sonra checkpoint'i güncelle (anlık kayıt)
                self.checkpoint['basarili'] = self.basarili_egitim
                self.checkpoint['basarisiz'] = self.basarisiz_egitim
                self.checkpoint['toplam_egitilen'] = self.toplam_egitilen
                # v3.1: başarılı sembolü egitilenler'e ekle, başarısız listesinden çıkar
                if hisse not in self.checkpoint['egitilenler']:
                    self.checkpoint['egitilenler'].append(hisse)
                if hisse in self.checkpoint['basarisiz_liste']:
                    self.checkpoint['basarisiz_liste'].remove(hisse)
                checkpoint_kaydet(self.checkpoint)
                
            except Exception as e:
                self.basarisiz_egitim += 1
                _ml_logger.error(f"  ✗ [{idx}/{len(hisse_listesi)}] {hisse}: {str(e)[:80]}")
                # v3.1: başarısızı ayrı listeye ekle (tekrar denemek için)
                self.checkpoint['basarisiz'] = self.basarisiz_egitim
                if hisse not in self.checkpoint['basarisiz_liste']:
                    self.checkpoint['basarisiz_liste'].append(hisse)
                checkpoint_kaydet(self.checkpoint)
                
            if self._kripto_mu(hisse):
                time.sleep(np.random.uniform(0.5, 1.5))
    
    def tek_tur_egitimi_baslat(self):
        """
        Tek tur eğitim yapar ve biter.  v3.1: Başarısızları önce dener
        - Checkpoint varsa kaldığı yerden devam eder
        - Checkpoint 2+ saat eskiyse sıfırdan başlar
        - Başarısızlar bitmeden checkpoint silinmez (tekrar denemeye devam eder)
        """
        self.baslangic_zamani = datetime.now()
        _pid_yaz("optuna" if self.use_optuna else "standart")
        
        # ── Checkpoint'i yükle ──
        self.checkpoint = checkpoint_yukle()
        
        # ── Tam listeyi oluştur ──
        tam_liste = oncelikli_egitim_listesi_olustur()
        if not tam_liste:
            tam_liste = list(VARSAYILAN_EGITIM_HISSELERI)
        
        # Önceki istatistikleri devral
        self.basarili_egitim = self.checkpoint.get('basarili', 0)
        self.basarisiz_egitim = 0  # v3.1: başarısız sayacı sıfırlanır (tekrar denenecek)
        self.toplam_egitilen = self.checkpoint.get('toplam_egitilen', 0)
        onceki_basarili = self.checkpoint.get('egitilenler', [])
        onceki_basarisiz = self.checkpoint.get('basarisiz_liste', [])
        
        # ── v3.3: Öncelik: Başarısızlar → Güçlü AL başarılılar → Diğer başarılılar → Yeniler ──
        basarisiz_set = set(onceki_basarisiz)
        basarili_set = set(onceki_basarili)
        
        # GÜÇLÜ AL sinyali olan sembolleri belirle (öncelikli güncelleme)
        guclu_al_set = set(_guclu_al_sinyalleri_getir())
        
        # 1) Başarısızlar (tekrar dene)
        kalanlar = onceki_basarisiz.copy()
        
        # 2) GÜÇLÜ AL olan başarılılar (öncelikli güncelleme)
        basarili_guclu_al = [h for h in tam_liste if h in basarili_set and h not in basarisiz_set and h in guclu_al_set]
        kalanlar.extend(basarili_guclu_al)
        
        # 3) Diğer başarılılar (normal güncelleme)
        basarili_diger = [h for h in tam_liste if h in basarili_set and h not in basarisiz_set and h not in guclu_al_set]
        kalanlar.extend(basarili_diger)
        
        # 4) Hiç denenmemiş yeniler
        for h in tam_liste:
            if h not in basarisiz_set and h not in basarili_set:
                kalanlar.append(h)
        
        yeni_sayisi = sum(1 for h in tam_liste if h not in basarisiz_set and h not in basarili_set)
        
        if onceki_basarisiz or onceki_basarili:
            _ml_logger.info("\n" + "═"*70)
            _ml_logger.info(f"  ◈ {('DERİN OPTUNA' if self.use_optuna else 'STANDART')} EĞİTİM (KALINAN YERDEN DEVAM) ◈")
            if onceki_basarisiz:
                _ml_logger.info(f"  🔄 1) BAŞARISIZLAR (tekrar): {len(onceki_basarisiz)} sembol")
            if basarili_guclu_al:
                _ml_logger.info(f"  ⚡ 2) GÜÇLÜ AL başarılılar (güncelleme): {len(basarili_guclu_al)} sembol")
            if basarili_diger:
                _ml_logger.info(f"  📡 3) Diğer başarılılar (güncelleme): {len(basarili_diger)} sembol")
            if yeni_sayisi > 0:
                _ml_logger.info(f"  🆕 4) YENİ: {yeni_sayisi} sembol")
            _ml_logger.info(f"  📊 Toplam eğitilecek: {len(kalanlar)} sembol")
            _ml_logger.info("═"*70)
        else:
            # Sıfırdan başlangıç
            kalanlar = tam_liste.copy()
        
        # Checkpoint'e tam listeyi kaydet
        self.checkpoint['tum_liste'] = tam_liste
        # v3.1: başarısız_liste'yi koru ama sayaçları sıfırla (tekrar denenecek)
        self.checkpoint['basarisiz'] = 0
        
        # ── Başlangıç mesajı ──
        egitim_tipi = "DERİN OPTUNA" if self.use_optuna else "STANDART"
        _egitim_log_baslik(f"◈ {egitim_tipi} EĞİTİM BAŞLATILDI ◈")
        
        if not onceki_basarisiz and not onceki_basarili:
            _ml_logger.info("\n" + "═"*70 + f"\n  ◈ {egitim_tipi} EĞİTİM BAŞLATILDI ◈\n" + "═"*70)
        _ml_logger.info(f"  📊 Eğitilecek: {len(kalanlar)} sembol")
        if self.use_optuna:
            _ml_logger.info(f"  🔬 Optuna: AÇIK (n_trials=30)")
            _ml_logger.info(f"  ⏰ Tahmini süre: {len(kalanlar) * 45 / 3600:.1f} saat (hisse başı ~45sn)")
        else:
            _ml_logger.info(f"  ⚡ Optuna: KAPALI (standart hızlı eğitim)")
            _ml_logger.info(f"  ⏰ Tahmini süre: {len(kalanlar) * 5 / 60:.0f} dakika (hisse başı ~5sn)")
        
        self.egitim_listesi = kalanlar
        
        # ── Tek tur eğitimi yap ──
        try:
            tur_baslangic = datetime.now()
            _ml_logger.info(f"\n{'█'*70}\n  🔄 EĞİTİM — {tur_baslangic.strftime('%Y-%m-%d %H:%M:%S')}\n{'█'*70}")
            
            self._egitim_turu_yap("Tek Tur", self.egitim_listesi)
            
            tur_sure = (datetime.now() - tur_baslangic).total_seconds()
            _ml_logger.info(f"\n  📊 EĞİTİM TAMAMLANDI | {tur_sure/60:.1f}dk | Başarılı: {self.basarili_egitim} | Başarısız: {self.basarisiz_egitim}")
            _egitim_log_yaz(f"  ✅ Tek tur eğitim tamamlandı ({tur_sure/60:.1f} dk) — Başarılı: {self.basarili_egitim}")
            
            # v3.1: Başarısız kaldıysa checkpoint'i silme, tekrar denenecek
            kalan_basarisiz = self.checkpoint.get('basarisiz_liste', [])
            if kalan_basarisiz:
                _ml_logger.info(f"  ⚠️ {len(kalan_basarisiz)} sembol başarısız oldu — bir sonraki başlatmada tekrar denenecek")
                _ml_logger.info(f"  💾 Checkpoint korundu (başarısızlar: {len(kalan_basarisiz)})")
            elif len(self.checkpoint.get('egitilenler', [])) >= len(tam_liste):
                _ml_logger.info("  🎉 TÜM SEMBOLLER BAŞARIYLA EĞİTİLDİ! Checkpoint sıfırlanıyor.")
                _egitim_log_yaz("  🎉 Tüm semboller başarıyla eğitildi! Checkpoint sıfırlandı.")
                checkpoint_sil()
            else:
                _ml_logger.info(f"  📊 İlerleme: {len(self.checkpoint.get('egitilenler', []))}/{len(tam_liste)} tamamlandı")
                
        except KeyboardInterrupt:
            _ml_logger.info(f"\n{'═'*70}\n  ◈ DURDURULDU | Eğitilen: {self.toplam_egitilen} | Checkpoint kaydedildi ◈\n{'═'*70}")
            _egitim_log_baslik("◈ EĞİTİM DURDURULDU (checkpoint kaydedildi) ◈")
        except Exception as e:
            _ml_logger.error(f"  ❌ Kritik hata: {e} | Checkpoint kaydedildi")
        finally:
            _pid_sil()
            # Checkpoint'i son kez kaydet (zaten her adımda kaydediliyor, garanti olsun)
            checkpoint_kaydet(self.checkpoint)
            _ml_logger.info("  💾 Checkpoint kaydedildi. Tekrar başlatıldığında kaldığı yerden devam eder.")
            _ml_logger.info("  ⏰ 2 saat sonra otomatik sıfırlanır (yeni veri eklenmiş olabilir).")


# ══════════════════════════════════════════════════════════════════════
#  ZAMANLI EĞİTİM MOTORU (22:00) — TÜM HİSSELERİ EĞİTİR
# ══════════════════════════════════════════════════════════════════════

class ZamanliEgitimMotoru(ZamanlanmisEgitimMotoru):
    """
    Saat 22:00 zamanlanmış eğitim.
    Her gün hızlı eğitim + 2 günde bir derin Optuna.
    FARK: Varsayılan 19 hisse değil, TÜM hisseleri (BIST+NQ+SP500+Kripto) eğitir.
    """
    EGITIM_BASLANGIC_SAAT = 22
    
    def __init__(self, hisse_listesi: list = None):
        if hisse_listesi is None:
            hisse_listesi = _tum_hisseleri_getir()
        super().__init__(hisse_listesi=hisse_listesi)


# ══════════════════════════════════════════════════════════════════════
#  ARKA PLAN BAŞLATMA FONKSİYONLARI (Streamlit butonları için)
# ══════════════════════════════════════════════════════════════════════

def standart_egitimi_arka_planda_baslat():
    """Standart (hızlı) eğitimi yeni terminalde başlatır."""
    try:
        durum = egitim_durumu_oku()
        durduruldu = False
        if durum['calisiyor']:
            durduruldu = egitim_durdur()
            if durduruldu:
                time.sleep(1)
        script_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mod_egitim_kontrol.py")
        if os.name == 'nt':
            subprocess.Popen([sys.executable, script_yolu, "standart"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([sys.executable, script_yolu, "standart"], start_new_session=True)
        ek = f"\n⚠️ Önceki {durum['tip']} eğitimi otomatik durduruldu." if durduruldu else ""
        return True, f"✅ Standart Eğitim başlatıldı! (Kaldığı yerden devam eder){ek}"
    except Exception as e:
        return False, f"❌ Başlatılamadı: {str(e)}"


def optuna_egitimi_arka_planda_baslat():
    """Derin Optuna eğitimini yeni terminalde başlatır."""
    try:
        durum = egitim_durumu_oku()
        durduruldu = False
        if durum['calisiyor']:
            durduruldu = egitim_durdur()
            if durduruldu:
                time.sleep(1)
        script_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mod_egitim_kontrol.py")
        if os.name == 'nt':
            subprocess.Popen([sys.executable, script_yolu, "optuna"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([sys.executable, script_yolu, "optuna"], start_new_session=True)
        ek = f"\n⚠️ Önceki {durum['tip']} eğitimi otomatik durduruldu." if durduruldu else ""
        return True, f"✅ Derin Optuna Eğitimi başlatıldı! (Kaldığı yerden devam eder){ek}"
    except Exception as e:
        return False, f"❌ Başlatılamadı: {str(e)}"


def zamanli_egitimi_arka_planda_baslat():
    """Zamanlı (22:00) eğitimi yeni terminalde başlatır."""
    try:
        durum = egitim_durumu_oku()
        durduruldu = False
        if durum['calisiyor']:
            durduruldu = egitim_durdur()
            if durduruldu:
                time.sleep(1)
        script_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mod_egitim_kontrol.py")
        if os.name == 'nt':
            subprocess.Popen([sys.executable, script_yolu, "zamanli"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([sys.executable, script_yolu, "zamanli"], start_new_session=True)
        ek = f"\n⚠️ Önceki {durum['tip']} eğitimi otomatik durduruldu." if durduruldu else ""
        return True, f"✅ Zamanlı Eğitim (22:00) başlatıldı!{ek}"
    except Exception as e:
        return False, f"❌ Başlatılamadı: {str(e)}"


# ══════════════════════════════════════════════════════════════════════
#  ESKİ FONKSİYON İSİMLERİ (geriye dönük uyumluluk)
# ══════════════════════════════════════════════════════════════════════

def eski_sistemi_arka_planda_baslat():
    """Geriye dönük uyumluluk: zamanli_egitimi_arka_planda_baslat() çağırır."""
    return zamanli_egitimi_arka_planda_baslat()

def agir_egitimi_arka_planda_baslat():
    """Geriye dönük uyumluluk: standart_egitimi_arka_planda_baslat() çağırır."""
    return standart_egitimi_arka_planda_baslat()


# ══════════════════════════════════════════════════════════════════════
#  KOMUT SATIRI
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ("zamanli", "eski"):
            print("=" * 60)
            print("  ◈ ZAMANLI EĞİTİM MOTORU (22:00) ◈")
            print("  ⏰ Her gün 22:00'de standart eğitim")
            print("  🔬 2 günde bir 22:00'de derin Optuna")
            print("  🛑 Güvenlik sınırı: 07:00 (ertesi gün)")
            print("  📦 TÜM hisseler (BIST+NQ+SP500+Kripto)")
            print("  📊 Rapor: logs/egitim_log.txt")
            print("=" * 60)
            
            _egitim_log_baslik("◈ ZAMANLI EĞİTİM (22:00) — TÜM HİSSELER ◈")
            motor = ZamanliEgitimMotoru()
            motor.zamanlanmis_donguyu_baslat()
        
        elif arg in ("standart", "simdi"):
            print("=" * 60)
            print("  ◈ STANDART EĞİTİM MOTORU ◈")
            print("  🎯 Tek tur eğitir ve durur")
            print("  ⚡ Optuna KAPALI — Hızlı eğitim")
            print("  📦 TÜM hisseler (BIST+NQ+SP500+Kripto)")
            print("  📊 Öncelik: Güçlü AL → YZ Karnesi → Tümü")
            print("  🔄 Kaldığı yerden devam eder (checkpoint)")
            print("  ⏰ 2 saat sonra checkpoint sıfırlanır")
            print("  💡 Durdurmak için Ctrl+C (ilerleme kaydedilir)")
            print("=" * 60)
            
            motor = TekTurEgitimMotoru(use_optuna=False)
            motor.tek_tur_egitimi_baslat()
        
        elif arg == "optuna":
            print("=" * 60)
            print("  ◈ DERİN OPTUNA EĞİTİM MOTORU ◈")
            print("  🎯 Tek tur eğitir ve durur")
            print("  🔬 Optuna AÇIK — n_trials=30")
            print("  ⚠️ UYARI: Hisse başı ~30-90 saniye sürer!")
            print("  ⏰ 1722 sembol için ~20-40 saat sürebilir")
            print("  📦 TÜM hisseler (BIST+NQ+SP500+Kripto)")
            print("  📊 Öncelik: Güçlü AL → YZ Karnesi → Tümü")
            print("  🔄 Kaldığı yerden devam eder (checkpoint)")
            print("  ⏰ 2 saat sonra checkpoint sıfırlanır")
            print("  💡 Durdurmak için Ctrl+C (ilerleme kaydedilir)")
            print("=" * 60)
            
            motor = TekTurEgitimMotoru(use_optuna=True)
            motor.tek_tur_egitimi_baslat()
        
        elif arg == "listele":
            liste = oncelikli_egitim_listesi_olustur()
            print(f"Toplam: {len(liste)} sembol")
            for i, h in enumerate(liste[:30], 1):
                print(f"  {i:3d}. {h}")
            if len(liste) > 30:
                print(f"  ... ve {len(liste)-30} tane daha")
        
        else:
            print(f"Kullanım: python mod_egitim_kontrol.py [standart|optuna|zamanli|listele]")
    else:
        print("EĞİTİM KONTROL PANELİ v3.0")
        print("  standart → Tek tur standart eğitim (Optuna KAPALI, hızlı)")
        print("  optuna   → Tek tur derin Optuna eğitimi (AĞIR, 30 trial)")
        print("  zamanli  → 22:00 zamanlanmış eğitim (günlük + 2 günde bir Optuna)")
        print("  listele  → Eğitim listesini göster")