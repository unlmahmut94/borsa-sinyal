# ══════════════════════════════════════════════════════════════════════
#  mod_logger.py — Yapılandırılmış JSON Loglama Sistemi (Tavsiye #4)
# ══════════════════════════════════════════════════════════════════════
#
#  ALGORİTMA:
#  ┌───────────────────────────────────────────────────────────────────┐
#  │ TEMEL PRENSİP: Düz metin logları JSON formatında kategorize      │
#  │ ederek hatayı bulma süresini 10 kat azaltmak.                     │
#  │                                                                    │
#  │ ADIM 1: Her log kaydı şu alanları içerir:                         │
#  │         timestamp, level, module, function, hisse,                │
#  │         mesaj, hata_tipi, traceback (varsa)                       │
#  │ ADIM 2: Log seviyesine göre rotalama:                             │
#  │         - INFO/DEBUG  → logs/sistem.log                           │
#  │         - WARNING     → logs/uyari.log                            │
#  │         - ERROR/CRITICAL → logs/hata.log                          │
#  │         - TÜMÜ        → logs/tumu.log (JSON Lines formatı)       │
#  │ ADIM 3: Log rotasyonu: Dosya 10MB'ı geçerse otomatik arşivle     │
#  │         (max 5 yedek dosya)                                       │
#  │ ADIM 4: Otomatik analiz fonksiyonu:                               │
#  │         - Son 24 saatte en sık hata veren modül                  │
#  │         - En sık karşılaşılan hata tipi                          │
#  │         - Hata frekans grafiği (ops.)                             │
#  │ ADIM 5: Kritik hatalarda Telegram bildirimi                       │
#  └───────────────────────────────────────────────────────────────────┘
#
#  KULLANIM:
#    from mod_logger import yapilandirilmis_logger
#    logger = yapilandirilmis_logger("ModulAdi")
#    logger.info("İşlem başarılı", hisse="THYAO.IS")
#    logger.error("Bağlantı hatası", hisse="AAPL", hata_tipi="ConnectionError")
#

import logging
import json
import os
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

# ── Log dizini ──
LOG_DIZINI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIZINI, exist_ok=True)

# JSON Lines formatında özel formatter
class JSONFormatter(logging.Formatter):
    """Her log kaydını JSON formatına çevirir."""
    
    def format(self, record):
        log_verisi = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "module": getattr(record, 'modul_adi', record.name),
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "hisse": getattr(record, 'hisse', None),
            "hata_tipi": getattr(record, 'hata_tipi', None),
        }
        
        # Exception bilgisi varsa ekle
        if record.exc_info and record.exc_info[0]:
            log_verisi["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exc()
            }
        elif record.exc_text:
            log_verisi["exception"] = {"traceback": record.exc_text}
        
        return json.dumps(log_verisi, ensure_ascii=False)


class YapilandirilmisLogger:
    """
    Her modül için yapılandırılmış JSON logger oluşturur.
    
    Özellikler:
    - JSON formatında loglama
    - Seviye bazlı dosya rotalama
    - Otomatik rotasyon (10MB / 5 yedek)
    - Hata analizi fonksiyonları
    """
    
    def __init__(self, modul_adi: str, log_seviyesi: int = logging.DEBUG):
        self.modul_adi = modul_adi
        self._logger = logging.getLogger(f"yapilandirilmis.{modul_adi}")
        self._logger.setLevel(log_seviyesi)
        self._logger.propagate = False
        
        if self._logger.handlers:
            return  # Zaten yapılandırılmış
        
        json_formatter = JSONFormatter()
        
        # ── Tüm loglar (JSON Lines) ──
        tumu_dosya = os.path.join(LOG_DIZINI, "tumu.jsonl")
        tumu_handler = RotatingFileHandler(
            tumu_dosya, maxBytes=10 * 1024 * 1024, backupCount=5,
            encoding="utf-8"
        )
        tumu_handler.setLevel(logging.DEBUG)
        tumu_handler.setFormatter(json_formatter)
        self._logger.addHandler(tumu_handler)
        
        # ── Hata logları (ERROR+) ──
        hata_dosya = os.path.join(LOG_DIZINI, "hata.jsonl")
        hata_handler = RotatingFileHandler(
            hata_dosya, maxBytes=10 * 1024 * 1024, backupCount=5,
            encoding="utf-8"
        )
        hata_handler.setLevel(logging.ERROR)
        hata_handler.setFormatter(json_formatter)
        self._logger.addHandler(hata_handler)
        
        # ── Konsol çıktısı (DEBUG seviyesinde) ──
        if os.environ.get("DEBUG_LOG", "").lower() == "true":
            konsol_handler = logging.StreamHandler(sys.stdout)
            konsol_handler.setLevel(logging.DEBUG)
            konsol_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-7s | %(module)-15s | %(message)s",
                    datefmt="%H:%M:%S"
                )
            )
            self._logger.addHandler(konsol_handler)
    
    def _ek_bilgi(self, hisse: str = None, hata_tipi: str = None, **kwargs) -> dict:
        """Log kaydına eklenecek ekstra bilgileri hazırlar."""
        extra = {"modul_adi": self.modul_adi}
        if hisse:
            extra["hisse"] = hisse.upper()
        if hata_tipi:
            extra["hata_tipi"] = hata_tipi
        extra.update(kwargs)
        return extra
    
    def debug(self, mesaj: str, hisse: str = None, **kwargs):
        self._logger.debug(mesaj, extra=self._ek_bilgi(hisse=hisse, **kwargs))
    
    def info(self, mesaj: str, hisse: str = None, **kwargs):
        self._logger.info(mesaj, extra=self._ek_bilgi(hisse=hisse, **kwargs))
    
    def warning(self, mesaj: str, hisse: str = None, hata_tipi: str = None, **kwargs):
        self._logger.warning(mesaj, extra=self._ek_bilgi(hisse=hisse, hata_tipi=hata_tipi, **kwargs))
    
    def error(self, mesaj: str, hisse: str = None, hata_tipi: str = None, exc_info: bool = False, **kwargs):
        self._logger.error(mesaj, extra=self._ek_bilgi(hisse=hisse, hata_tipi=hata_tipi, **kwargs), exc_info=exc_info)
    
    def critical(self, mesaj: str, hisse: str = None, hata_tipi: str = None, **kwargs):
        self._logger.critical(mesaj, extra=self._ek_bilgi(hisse=hisse, hata_tipi=hata_tipi, **kwargs))
        # Kritik hatalarda Telegram bildirimi
        try:
            from mod_telegram import telegram_mesaj_gonder
            telegram_mesaj_gonder(f"🚨 KRİTİK HATA [{self.modul_adi}]\n{mesaj}\nZaman: {datetime.now()}")
        except ImportError:
            pass


# ── Kolay erişim için module-level fonksiyon ──
_logger_kayit = {}

def yapilandirilmis_logger(modul_adi: str) -> YapilandirilmisLogger:
    """
    Belirtilen modül için yapılandırılmış logger döner.
    Aynı modül için tekrar çağrılırsa cache'lenmiş logger'ı döner.
    
    Kullanım:
        from mod_logger import yapilandirilmis_logger
        logger = yapilandirilmis_logger("PozisyonYonetimi")
        logger.info("Pozisyon hesaplandı", hisse="THYAO.IS")
    """
    if modul_adi not in _logger_kayit:
        _logger_kayit[modul_adi] = YapilandirilmisLogger(modul_adi)
    return _logger_kayit[modul_adi]


# ══════════════════════════════════════════════════════════════════════
#  GÜVENLİ FONKSİYON DEKORATÖRÜ (sessiz hata yutmayı önler)
# ══════════════════════════════════════════════════════════════════════
import functools
import threading

_sessiz_logger = yapilandirilmis_logger("GuvenliCalistirici")


def guvenli_calistir(
    varsayilan_donus=None,
    hata_mesaji: str = "",
    modul_adi: str = "",
    bildirim_gonder: bool = False,
    yeniden_yukselt: bool = False,
    log_seviyesi: str = "error"
):
    """
    Fonksiyonları güvenli şekilde çalıştıran dekoratör.
    
    Sessiz `except:` veya `except Exception:` yerine KESİNLİKLE bunu kullanın.
    Bu dekoratör:
    1. Hatayı yapılandırılmış log'a kaydeder
    2. İsteğe bağlı Telegram bildirimi gönderir
    3. Varsayılan bir değer döndürür (None, boş liste, 0, vb.)
    4. İsteğe bağlı olarak hatayı yeniden yükseltir
    
    Kullanım:
        @guvenli_calistir(varsayilan_donus=[], modul_adi="Tarayici", hata_mesaji="Tarama başarısız")
        def hisseleri_tara():
            ...
        
        # VEYA doğrudan çağırarak:
        sonuc = guvenli_calistir(varsayilan_donus=0.0)(lambda: riskli_fonksiyon())
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _modul = modul_adi or func.__module__.split('.')[-1]
            _logger = yapilandirilmis_logger(_modul) if modul_adi else _sessiz_logger
            
            try:
                return func(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                hata_tipi = type(e).__name__
                mesaj = hata_mesaji or f"{func.__name__} başarısız: {e}"
                
                if log_seviyesi == "warning":
                    _logger.warning(mesaj, hata_tipi=hata_tipi)
                elif log_seviyesi == "critical":
                    _logger.critical(mesaj, hata_tipi=hata_tipi)
                else:
                    _logger.error(mesaj, hata_tipi=hata_tipi, exc_info=True)
                
                if bildirim_gonder:
                    try:
                        from mod_telegram import telegram_mesaj_gonder
                        telegram_mesaj_gonder(f"⚠️ [{_modul}] {mesaj}\nHata: {hata_tipi}: {e}")
                    except Exception:
                        pass
                
                if yeniden_yukselt:
                    raise
                
                # İterable varsayılan değerleri klonla
                if isinstance(varsayilan_donus, (list, dict, set)):
                    return varsayilan_donus.copy() if hasattr(varsayilan_donus, 'copy') else type(varsayilan_donus)()
                return varsayilan_donus
        
        return wrapper
    
    # Hem @guvenli_calistir hem de @guvenli_calistir() kullanımına izin ver
    if callable(varsayilan_donus) and not hata_mesaji and not modul_adi:
        func = varsayilan_donus
        varsayilan_donus = None
        return decorator(func)
    
    return decorator


def guvenli_blok(
    func,
    varsayilan_donus=None,
    hata_mesaji: str = "",
    modul_adi: str = "",
    log_seviyesi: str = "error"
):
    """
    Tek seferlik güvenli çalıştırma. Lambda/closure ile çağrılır.
    
    Kullanım:
        veri = guvenli_blok(lambda: riskli_veri_cek("AAPL"), varsayilan_donus={})
    """
    try:
        return func()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        _modul = modul_adi or "GuvenliBlok"
        _logger = yapilandirilmis_logger(_modul)
        hata_tipi = type(e).__name__
        mesaj = hata_mesaji or f"İşlem başarısız: {e}"
        
        if log_seviyesi == "warning":
            _logger.warning(mesaj, hata_tipi=hata_tipi)
        elif log_seviyesi == "critical":
            _logger.critical(mesaj, hata_tipi=hata_tipi)
        else:
            _logger.error(mesaj, hata_tipi=hata_tipi)
        
        if isinstance(varsayilan_donus, (list, dict, set)):
            return varsayilan_donus.copy() if hasattr(varsayilan_donus, 'copy') else type(varsayilan_donus)()
        return varsayilan_donus


# ══════════════════════════════════════════════════════════════════════
#  PERFORMANS İZLEME
# ══════════════════════════════════════════════════════════════════════
_performans_kayitlari = {}
_performans_lock = threading.Lock()


def performans_izle(func_adi: str = ""):
    """
    Fonksiyon çalışma süresini ölçen dekoratör.
    
    Kullanım:
        @performans_izle("veri_cek")
        def agir_fonksiyon():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            _ad = func_adi or func.__name__
            basla = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                sure = time.time() - basla
                with _performans_lock:
                    if _ad not in _performans_kayitlari:
                        _performans_kayitlari[_ad] = []
                    _performans_kayitlari[_ad].append(sure)
                    
                    # Sadece son 100 ölçümü tut
                    if len(_performans_kayitlari[_ad]) > 100:
                        _performans_kayitlari[_ad] = _performans_kayitlari[_ad][-100:]
                
                if sure > 5.0:  # 5 saniyeden uzun süren işlemleri uyar
                    _sessiz_logger.warning(
                        f"YAVAŞ İŞLEM: {_ad} {sure:.2f}s sürdü",
                        hata_tipi="PerformansUyarisi"
                    )
        return wrapper
    return decorator


def performans_raporu() -> dict:
    """Son ölçümlerin performans özetini döndürür."""
    with _performans_lock:
        rapor = {}
        for ad, sureler in _performans_kayitlari.items():
            if sureler:
                rapor[ad] = {
                    'cagri_sayisi': len(sureler),
                    'ortalama': round(sum(sureler) / len(sureler), 3),
                    'minimum': round(min(sureler), 3),
                    'maksimum': round(max(sureler), 3),
                    'son': round(sureler[-1], 3)
                }
        return rapor


def log_analiz_et(son_saat: int = 24) -> dict:
    """
    Son N saatteki logları analiz eder.
    
    Algoritma:
    1. tumu.jsonl dosyasını satır satır oku
    2. Son N saatteki kayıtları filtrele
    3. Modül bazında hata sayısını hesapla
    4. En sık hata tipini bul
    5. Özet rapor üret
    
    Parametreler:
        son_saat: Kaç saatlik log analiz edilecek
    
    Dönüş: {
        'toplam_kayit': int,
        'hata_sayisi': int,
        'modul_bazinda': dict,
        'en_sik_hata': str,
        'hata_listesi': list
    }
    """
    tumu_dosya = os.path.join(LOG_DIZINI, "tumu.jsonl")
    
    if not os.path.exists(tumu_dosya):
        return {
            'toplam_kayit': 0,
            'hata_sayisi': 0,
            'modul_bazinda': {},
            'en_sik_hata': '',
            'hata_listesi': []
        }
    
    simdi = datetime.now()
    hata_sayaci = {}
    modul_sayaci = {}
    hata_listesi = []
    toplam = 0
    
    try:
        with open(tumu_dosya, "r", encoding="utf-8") as f:
            for satir in f:
                satir = satir.strip()
                if not satir:
                    continue
                
                try:
                    kayit = json.loads(satir)
                    
                    # Zaman filtresi
                    try:
                        kayit_zamani = datetime.strptime(kayit['timestamp'][:19], "%Y-%m-%d %H:%M:%S")
                        saat_farki = (simdi - kayit_zamani).total_seconds() / 3600
                        if saat_farki > son_saat:
                            continue
                    except:
                        pass
                    
                    toplam += 1
                    
                    # Seviye kontrolü
                    seviye = kayit.get('level', 'INFO')
                    if seviye in ('ERROR', 'CRITICAL'):
                        modul = kayit.get('module', 'Bilinmeyen')
                        modul_sayaci[modul] = modul_sayaci.get(modul, 0) + 1
                        
                        hata_tipi = kayit.get('hata_tipi', 'Genel')
                        hata_sayaci[hata_tipi] = hata_sayaci.get(hata_tipi, 0) + 1
                        
                        hata_listesi.append({
                            'zaman': kayit.get('timestamp'),
                            'modul': modul,
                            'mesaj': kayit.get('message', ''),
                            'hata_tipi': hata_tipi
                        })
                        
                except json.JSONDecodeError:
                    continue
    
    except IOError:
        pass
    
    en_sik_hata = max(hata_sayaci, key=hata_sayaci.get) if hata_sayaci else ''
    
    return {
        'toplam_kayit': toplam,
        'hata_sayisi': len(hata_listesi),
        'modul_bazinda': modul_sayaci,
        'en_sik_hata': en_sik_hata,
        'hata_listesi': hata_listesi[-20:]  # Son 20 hata
    }


def log_raporu() -> str:
    """
    İnsan okunur log analiz raporu üretir.
    
    Dönüş: Formatlanmış rapor metni
    """
    analiz = log_analiz_et(son_saat=24)
    
    rapor = []
    rapor.append("=" * 60)
    rapor.append("  LOG ANALİZ RAPORU (Son 24 Saat)")
    rapor.append("=" * 60)
    rapor.append(f"  Toplam Kayıt  : {analiz['toplam_kayit']}")
    rapor.append(f"  Hata Sayısı   : {analiz['hata_sayisi']}")
    rapor.append(f"  En Sık Hata   : {analiz['en_sik_hata'] or 'Yok'}")
    rapor.append(f"  {'─' * 50}")
    
    if analiz['modul_bazinda']:
        rapor.append(f"  {'Modül':<25s} {'Hata':>6s}")
        rapor.append(f"  {'─' * 50}")
        for modul, sayi in sorted(analiz['modul_bazinda'].items(), key=lambda x: -x[1]):
            rapor.append(f"  {modul:<25s} {sayi:>6d}")
    
    if analiz['hata_listesi']:
        rapor.append(f"\n  Son Hatalar:")
        for h in analiz['hata_listesi'][-10:]:
            rapor.append(f"    [{h['zaman'][:19]}] {h['modul']}: {h['mesaj'][:80]}")
    
    rapor.append("=" * 60)
    
    return "\n".join(rapor)


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("JSON Yapılandırılmış Loglama Testi")
    print("=" * 40)
    
    # Test logger'ı
    test_log = yapilandirilmis_logger("TestModul")
    test_log.info("Sistem başlatıldı")
    test_log.warning("Düşük bakiye uyarısı", hisse="THYAO.IS", hata_tipi="BakiyeUyarisi")
    test_log.error("Bağlantı zaman aşımı", hisse="AAPL", hata_tipi="TimeoutError")
    
    # Analiz testi
    print("\nLog analizi:")
    analiz = log_analiz_et(son_saat=1)
    print(f"  Son 1 saatte {analiz['hata_sayisi']} hata tespit edildi.")
    
    # Rapor testi
    print("\n" + log_raporu())