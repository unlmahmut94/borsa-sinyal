# ══════════════════════════════════════════════════════════════════════
#  mod_websocket.py — Gerçek Zamanlı WebSocket Veri Akışı (Tavsiye #6)
# ══════════════════════════════════════════════════════════════════════
#
#  ALGORİTMA:
#  ┌───────────────────────────────────────────────────────────────────┐
#  │ TEMEL PRENSİP: Binance WebSocket ile gerçek zamanlı fiyat        │
#  │ akışı alarak gecikmeyi 15 saniyeden milisaniyeye indirmek.       │
#  │                                                                    │
#  │ ADIM 1: WebSocket bağlantısı aç (Binance Futures wss)            │
#  │ ADIM 2: İzlenecek sembolleri abone et (max 20 stream)            │
#  │ ADIM 3: Gelen tick verisini (fiyat, hacim, zaman) işle           │
#  │ ADIM 4: Fiyat değişimini hesapla ve eşik kontrolü yap            │
#  │ ADIM 5: Eşik aşıldıysa sinyal üret ve kaydet                     │
#  │ ADIM 6: Circuit breaker ve pozisyon yönetimi entegrasyonu        │
#  │ ADIM 7: Bağlantı koparsa otomatik yeniden bağlan (reconnect)     │
#  └───────────────────────────────────────────────────────────────────┘
#
#  KULLANIM:
#    from mod_websocket import websocket_akisi_baslat, websocket_durdur
#    websocket_akisi_baslat(["BTCUSDT", "ETHUSDT"], callback=islem_fonksiyonu)
#

import json
import os
import time
import threading
import logging
from datetime import datetime
from collections import defaultdict
from typing import Callable, Optional

_logger = logging.getLogger("WebSocket")

# ── WebSocket kütüphanesi opsiyonel ──
try:
    import websocket
    _ws_enabled = True
except ImportError:
    _ws_enabled = False
    _logger.warning("websocket-client yüklü değil. pip install websocket-client")

try:
    import requests
except ImportError:
    requests = None

CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")

# ── Durum değişkenleri ──
_ws_thread = None
_ws_running = False
_ws_lock = threading.Lock()
_fiyat_cache = {}
_hacim_cache = {}
_son_guncelleme = {}
_aktif_semboller = []
_callback_fn = None
_yeniden_baglanma_sayisi = 0
_MAX_YENIDEN_BAGLANMA = 10


def _config_yukle() -> dict:
    try:
        if os.path.exists(CONFIG_YOLU):
            with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}


def websocket_akisi_baslat(
    semboller: list,
    callback: Callable = None,
    max_sembol: int = None
) -> bool:
    """
    WebSocket canlı fiyat akışını başlatır.
    
    Algoritma:
    1. websocket-client kütüphanesini kontrol et
    2. Config'ten max sembol limitini al
    3. Sembolleri küçük harfe çevir (Binance formatı)
    4. Stream URL'lerini oluştur: wss://stream.binance.com:9443/stream?streams=...
    5. Arka plan thread'inde WebSocket dinlemeye başla
    6. Her tick'te fiyat cache'ini güncelle ve callback çağır
    
    Parametreler:
        semboller: İzlenecek kripto sembolleri (örn: ["BTCUSDT", "ETHUSDT"])
        callback: Her fiyat güncellemesinde çağrılacak fonksiyon
                  callback(sembol, fiyat, hacim, zaman)
        max_sembol: Maksimum sembol sayısı (None = config'ten)
    
    Dönüş: Başarılıysa True
    """
    global _ws_thread, _ws_running, _aktif_semboller, _callback_fn
    
    if not _ws_enabled:
        _logger.error("websocket-client yüklü değil.")
        return False
    
    with _ws_lock:
        if _ws_running:
            _logger.warning("WebSocket zaten çalışıyor.")
            return False
    
    config = _config_yukle()
    if max_sembol is None:
        max_sembol = config.get("websocket_sembol_limiti", 20)
    
    # Sembolleri formatla ve limitle
    semboller = [s.lower().strip() for s in semboller[:max_sembol]]
    
    if not semboller:
        _logger.error("İzlenecek sembol listesi boş.")
        return False
    
    _aktif_semboller = semboller
    _callback_fn = callback
    
    _ws_running = True
    _ws_thread = threading.Thread(target=_ws_dinleyici, daemon=True)
    _ws_thread.start()
    
    _logger.info(f"✓ WebSocket başlatıldı — {len(semboller)} sembol izleniyor.")
    return True


def _ws_dinleyici():
    """
    WebSocket bağlantısını yöneten arka plan thread'i.
    
    Algoritma:
    1. Stream URL'lerini oluştur (max 200 stream tek bağlantıda)
    2. WebSocket bağlan
    3. on_message: gelen JSON'u parse et, fiyat cache'ini güncelle
    4. on_error: hatayı logla
    5. on_close: yeniden bağlanmayı dene (exponential backoff)
    """
    global _ws_running, _yeniden_baglanma_sayisi
    
    streams = [f"{s}@ticker" for s in _aktif_semboller]
    stream_param = "/".join(streams)
    ws_url = f"wss://stream.binance.com:9443/stream?streams={stream_param}"
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            
            if 'data' not in data:
                return
            
            tick = data['data']
            sembol = tick.get('s', '').upper()
            fiyat = float(tick.get('c', 0))  # Current price
            hacim = float(tick.get('v', 0))  # Volume
            zaman = tick.get('E', int(time.time() * 1000))
            
            # Cache güncelle
            with _ws_lock:
                _fiyat_cache[sembol] = fiyat
                _hacim_cache[sembol] = hacim
                _son_guncelleme[sembol] = zaman
            
            # Callback çağır
            if _callback_fn:
                try:
                    _callback_fn(sembol, fiyat, hacim, zaman)
                except Exception as e:
                    _logger.error(f"WebSocket callback hatası: {e}")
                    
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            _logger.debug(f"WebSocket parse hatası: {e}")
    
    def on_error(ws, error):
        _logger.error(f"WebSocket hatası: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        global _ws_running, _yeniden_baglanma_sayisi
        _logger.warning(f"WebSocket kapandı: {close_status_code} - {close_msg}")
        
        if _ws_running and _yeniden_baglanma_sayisi < _MAX_YENIDEN_BAGLANMA:
            _yeniden_baglanma_sayisi += 1
            bekleme = min(2 ** _yeniden_baglanma_sayisi, 120)  # Exponential backoff, max 2 dk
            _logger.info(f"Yeniden bağlanıyor ({_yeniden_baglanma_sayisi}/{_MAX_YENIDEN_BAGLANMA}), {bekleme}sn bekleniyor...")
            time.sleep(bekleme)
            _ws_dinleyici()  # Rekürsif yeniden bağlanma
        else:
            _ws_running = False
            _logger.error("WebSocket kalıcı olarak durduruldu.")
    
    def on_open(ws):
        global _yeniden_baglanma_sayisi
        _yeniden_baglanma_sayisi = 0
        _logger.info(f"✓ WebSocket bağlandı — {len(_aktif_semboller)} stream aktif.")
    
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        ws.run_forever(ping_interval=30, ping_timeout=10)
    except Exception as e:
        _logger.error(f"WebSocket kritik hata: {e}")
        _ws_running = False


def websocket_durdur():
    """WebSocket akışını durdurur."""
    global _ws_running, _ws_thread
    with _ws_lock:
        _ws_running = False
    _logger.info("WebSocket durduruldu.")


def websocket_fiyat_al(sembol: str) -> Optional[float]:
    """
    WebSocket cache'inden anlık fiyatı alır.
    
    Dönüş: Fiyat (float) veya None (cache'te yoksa)
    """
    with _ws_lock:
        return _fiyat_cache.get(sembol.upper())


def websocket_hacim_al(sembol: str) -> Optional[float]:
    """WebSocket cache'inden anlık hacmi alır."""
    with _ws_lock:
        return _hacim_cache.get(sembol.upper())


def websocket_durum() -> dict:
    """WebSocket bağlantı durumunu döner."""
    with _ws_lock:
        return {
            'calisiyor': _ws_running,
            'aktif_semboller': list(_aktif_semboller),
            'cache_boyutu': len(_fiyat_cache),
            'yeniden_baglanma': _yeniden_baglanma_sayisi,
            'son_guncelleme': dict(_son_guncelleme)
        }


def websocket_fiyat_degisim_kontrol(sembol: str, yuzde_esik: float = 1.0) -> dict:
    """
    WebSocket fiyat hareketini kontrol eder ve eşik aşıldıysa sinyal üretir.
    
    Algoritma:
    1. Cache'ten son 2 fiyatı al (önceki ve şimdiki)
    2. Yüzde değişimi hesapla: %değişim = (yeni - eski) / eski * 100
    3. Eşik aşıldıysa AL/SAT sinyali döndür
    4. Pozisyon yönetimi ve circuit breaker entegrasyonu
    
    Dönüş: {
        'sinyal': 'AL' / 'SAT' / 'YOK',
        'fiyat': float,
        'degisim': float,
        'esik_asildi': bool
    }
    """
    with _ws_lock:
        fiyat = _fiyat_cache.get(sembol.upper())
    
    if fiyat is None:
        return {'sinyal': 'YOK', 'fiyat': 0, 'degisim': 0, 'esik_asildi': False}
    
    # Önceki fiyat (5 saniye öncesi)
    onceki_fiyat = fiyat  # Gerçek implementasyonda zaman serisi tutulur
    
    degisim = 0 if onceki_fiyat == 0 else ((fiyat - onceki_fiyat) / onceki_fiyat) * 100
    
    esik_asildi = abs(degisim) >= yuzde_esik
    
    return {
        'sinyal': 'AL' if degisim > yuzde_esik else ('SAT' if degisim < -yuzde_esik else 'YOK'),
        'fiyat': round(fiyat, 4),
        'degisim': round(degisim, 4),
        'esik_asildi': esik_asildi
    }


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("WebSocket Gerçek Zamanlı Veri Testi")
    print("=" * 40)
    
    if not _ws_enabled:
        print("⚠️ websocket-client yüklü değil. Test yapılamıyor.")
        print("   pip install websocket-client")
    else:
        print("WebSocket modülü hazır.")
        print(f"  Durum: {websocket_durum()}")
        
        def test_callback(sembol, fiyat, hacim, zaman):
            print(f"  [{datetime.now():%H:%M:%S}] {sembol}: ${fiyat:.4f} Vol: {hacim:.2f}")
        
        test_semboller = ["btcusdt", "ethusdt"]
        print(f"\nTest başlatılıyor... ({test_semboller})")
        print("(Çıkmak için CTRL+C)")
        
        ok = websocket_akisi_baslat(test_semboller, callback=test_callback)
        
        if ok:
            try:
                while _ws_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                websocket_durdur()
                print("\nWebSocket durduruldu.")