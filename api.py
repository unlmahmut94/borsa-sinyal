# ══════════════════════════════════════════════════════════════════════
#  api.py — REST API Gateway — FastAPI (Tavsiye #9)
# ══════════════════════════════════════════════════════════════════════
#
#  ALGORİTMA:
#  ┌───────────────────────────────────────────────────────────────────┐
#  │ TEMEL PRENSİP: CLI komutlarını HTTP endpoint olarak sunarak      │
#  │ harici sistemlerle (Telegram, TradingView, Google Sheets)         │
#  │ entegrasyonu mümkün kılmak.                                       │
#  │                                                                    │
#  │ ENDPOINT'LER:                                                     │
#  │   GET  /                        → API durumu                      │
#  │   GET  /tahmin/{sembol}        → ML tahmini                       │
#  │   GET  /sinyaller              → Son sinyalleri listele           │
#  │   GET  /tarama/{borsa}         → Toplu tarama başlat              │
#  │   GET  /backtest/{sembol}      → Strateji testi                   │
#  │   GET  /rapor/korelasyon       → Korelasyon raporu                │
#  │   GET  /rapor/sinyal-kalite    → Sinyal kalite raporu             │
#  │   GET  /rapor/log              → Log analiz raporu                │
#  │   GET  /durum/circuit-breaker  → Circuit breaker durumu           │
#  │   GET  /durum/websocket        → WebSocket durumu                 │
#  │   POST /webhook/tradingview    → TradingView webhook alıcı        │
#  └───────────────────────────────────────────────────────────────────┘
#
#  KULLANIM:
#    uvicorn api:app --host 0.0.0.0 --port 8000
#    curl http://localhost:8000/tahmin/THYAO.IS?gun=5
#

from fastapi import FastAPI, Query, Path, HTTPException, Request, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
import os
import sys
import json
import pandas as pd
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

# Proje kök dizinini ekle
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from mod_logger import yapilandirilmis_logger, guvenli_blok
from mod_config import config_al

_api_logger = yapilandirilmis_logger("API")

# ── Rate Limiting State ──
_rate_limit_store: Dict[str, Tuple[int, float]] = {}
_rate_limit_lock = __import__('threading').Lock()

# ── API Key yapılandırması ──
API_KEY_GEREKLI = config_al("api.api_anahtari_gerekli", False)
API_ANAHTARI = os.environ.get("BORSASINYAL_API_KEY", "")
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# ══════════════════════════════════════════════════════════════════════
#  YARDIMCI: Rate Limiting Middleware
# ══════════════════════════════════════════════════════════════════════

def rate_limit_kontrol(client_ip: str, limit: int = 30, window: int = 60) -> bool:
    """
    Dakikada `limit` istek sınırı kontrolü.
    Sınır aşılırsa False döner.
    """
    simdi = time.time()
    with _rate_limit_lock:
        if client_ip in _rate_limit_store:
            count, start_time = _rate_limit_store[client_ip]
            if simdi - start_time > window:
                # Pencere sıfırlandı
                _rate_limit_store[client_ip] = (1, simdi)
                return True
            elif count >= limit:
                return False
            else:
                _rate_limit_store[client_ip] = (count + 1, start_time)
                return True
        else:
            _rate_limit_store[client_ip] = (1, simdi)
            return True


def api_anahtari_dogrula(api_key: Optional[str] = Security(API_KEY_HEADER)) -> bool:
    """API anahtarı doğrulaması. Devre dışıysa her zaman True."""
    if not API_KEY_GEREKLI:
        return True
    if not API_ANAHTARI:
        return True  # Anahtar tanımlanmamışsa izin ver
    if api_key and hmac.compare_digest(api_key, API_ANAHTARI):
        return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç/kapanış olayları."""
    _api_logger.info("API Gateway başlatıldı")
    yield
    _api_logger.info("API Gateway kapatıldı")


app = FastAPI(
    title="BorsaSinyal Pro API",
    description="ML Destekli Çok Piyasalı Sinyal Sistemi - Güvenli Gateway",
    version="3.2.0",
    lifespan=lifespan
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting Middleware ──
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Her isteği rate limit kontrolünden geçirir."""
    if config_al("api.rate_limit_aktif", True):
        client_ip = request.client.host if request.client else "bilinmeyen"
        limit = config_al("api.rate_limit_dakika_basina", 30)
        
        if not rate_limit_kontrol(client_ip, limit=limit):
            _api_logger.warning(f"Rate limit aşıldı: {client_ip}", hata_tipi="RateLimit")
            return JSONResponse(
                status_code=429,
                content={"error": True, "message": "Rate limit aşıldı. Lütfen bekleyin.", "retry_after": 60}
            )
    
    response = await call_next(request)
    return response


# ── İstek Loglama Middleware ──
@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    """Her isteği loglar."""
    basla = time.time()
    response = await call_next(request)
    sure = time.time() - basla
    
    if sure > 3.0:  # 3 saniyeden uzun istekleri uyar
        _api_logger.warning(
            f"Yavaş istek: {request.method} {request.url.path} ({sure:.2f}s)",
            hata_tipi="YavasIstek"
        )
    
    return response


# ══════════════════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════════

def _guncel_fiyat(symbol: str) -> float:
    """Güvenli güncel fiyat çekme - loglanmış hata yönetimi ile."""
    sonuc = guvenli_blok(
        lambda: __import__('mod_veri_kaynagi', fromlist=['canli_fiyat_cek']).canli_fiyat_cek(symbol),
        varsayilan_donus=None, modul_adi="API", hata_mesaji=f"Fiyat çekilemedi: {symbol}"
    )
    if sonuc and sonuc.get('fiyat'):
        return float(sonuc['fiyat'])
    
    fiyat = guvenli_blok(
        lambda: float(__import__('yfinance').Ticker(symbol).history(period="2d").get("Close", pd.Series([0])).iloc[-1]),
        varsayilan_donus=0.0, modul_adi="API", hata_mesaji=f"yfinance fiyat çekilemedi: {symbol}"
    )
    return fiyat if fiyat else 0.0


async def _api_anahtari_kontrol(api_key: Optional[str] = Security(API_KEY_HEADER)):
    """API anahtarı doğrulama bağımlılığı."""
    if not api_anahtari_dogrula(api_key):
        _api_logger.warning("Geçersiz API anahtarı", hata_tipi="YetkisizErisim")
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")
    return True


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT'LER
# ══════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "api": "BorsaSinyal Pro",
        "version": "3.1.0",
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs"
    }


@app.get("/tahmin/{sembol}")
async def tahmin(
    sembol: str,
    gun: int = Query(5, ge=1, le=30, description="Tahmin günü"),
    _auth: bool = Depends(_api_anahtari_kontrol) if API_KEY_GEREKLI else True,
):
    """ML ile hisse fiyat ve yön tahmini."""
    try:
        from mod_yapay_zeka import yapay_zeka_tahmin_et
        sonuc, mesaj = yapay_zeka_tahmin_et(sembol.upper(), hedef_gun=gun)
        
        if sonuc is None:
            _api_logger.warning(f"Tahmin başarısız: {sembol.upper()}", hisse=sembol.upper(), hata_tipi="TahminHatasi")
            return JSONResponse(
                status_code=404,
                content={"error": True, "message": mesaj, "sembol": sembol.upper()}
            )
        
        _api_logger.info(f"Tahmin başarılı: {sembol.upper()} ({gun}gün)", hisse=sembol.upper())
        return {
            "sembol": sembol.upper(),
            "gun": gun,
            "sonuc": sonuc,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        _api_logger.error(f"Tahmin kritik hata: {sembol.upper()}", hisse=sembol.upper(), hata_tipi=type(e).__name__, exc_info=True)
        raise HTTPException(status_code=500, detail=f"İşlem hatası: {type(e).__name__}")


@app.get("/sinyaller")
async def sinyaller(
    adet: int = Query(10, ge=1, le=100),
    sembol: Optional[str] = Query(None),
):
    """Son sinyalleri listeler."""
    try:
        import sqlite3
        db_yolu = os.path.join(ROOT, "ai_hafiza.db")
        conn = sqlite3.connect(db_yolu)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'")
        if not cursor.fetchone():
            conn.close()
            return {"sinyaller": [], "adet": 0}
        
        if sembol:
            cursor.execute(
                "SELECT * FROM ai_sinyaller WHERE hisse=? ORDER BY id DESC LIMIT ?",
                (sembol.upper(), adet)
            )
        else:
            cursor.execute("SELECT * FROM ai_sinyaller ORDER BY id DESC LIMIT ?", (adet,))
        
        rows = cursor.fetchall()
        conn.close()
        
        sinyaller_list = []
        for row in rows:
            sinyaller_list.append({
                "id": row[0],
                "tarih": row[1],
                "hisse": row[2],
                "sinyal_tipi": row[3],
                "giris_fiyati": row[4],
                "hedef_fiyat": row[5],
                "stop_fiyat": row[6],
                "durum": row[7],
                "kapanis_fiyati": row[8]
            })
        
        return {"sinyaller": sinyaller_list, "adet": len(sinyaller_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tarama/{borsa}")
async def tarama(
    borsa: str = Path(..., description="BIST, SP500, NASDAQ, KRIPTO"),
):
    """Toplu piyasa taraması başlatır."""
    try:
        from main import toplu_tarama_baslat
        from hisseler_bist import BIST
        from hisseler_sp500 import SP500
        from hisseler_nasdaq import NASDAQ
        from hisseler_kripto import KRIPTO_LISTESI as KRIPTO
        from analiz import tum_hisseleri_tara
        
        borsa_map = {
            "BIST": BIST,
            "SP500": SP500,
            "NASDAQ": NASDAQ,
            "KRIPTO": KRIPTO,
        }
        
        borsa = borsa.upper()
        if borsa not in borsa_map:
            raise HTTPException(status_code=400, detail=f"Geçersiz borsa: {borsa}")
        
        semboller = borsa_map[borsa]
        
        # Dead pool filtreleme
        try:
            from mod_veri_kaynagi import dead_listeyi_temizle, dead_liste_yukle
            dead_set = dead_liste_yukle()
            semboller = dead_listeyi_temizle(semboller)
        except:
            pass
        
        # Dummy progress/durum nesneleri (API modunda UI yok)
        class _DummyUI:
            def progress(self, val): pass
            def text(self, msg): pass
        
        dummy_ui = _DummyUI()
        from fastapi.concurrency import run_in_threadpool
        sonuclar = await run_in_threadpool(tum_hisseleri_tara, semboller, "1mo", dummy_ui, dummy_ui)        
        guclu_al = [r for r in sonuclar if "GUCLU AL" in str(r.get('Sinyal', ''))]
        
        return {
            "borsa": borsa,
            "taranan": len(sonuclar),
            "guclu_al_sayisi": len(guclu_al),
            "guclu_al": [{
                "hisse": r['Hisse'],
                "fiyat": r.get('Son Fiyat', 0),
                "sinyal": r.get('Sinyal', ''),
                "skor": r.get('Skor', 0)
            } for r in guclu_al[:20]],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/backtest/{sembol}")
async def backtest(
    sembol: str,
    gun: int = Query(365, ge=30, le=1825),
):
    """Seçilen hisse için strateji backtest'i yapar."""
    try:
        from backtest import backtest_calistir as bt_run
        sonuc = bt_run(sembol.upper(), periyot_gun=gun)
        
        if sonuc is None:
            return JSONResponse(status_code=404, content={"error": True, "message": "Yetersiz veri."})
        
        return {
            "sembol": sembol.upper(),
            "gun": gun,
            "baslangic": sonuc.get('Baslangic', 0),
            "final": sonuc.get('Final', 0),
            "getiri_yuzde": sonuc.get('Getiri %', 0),
            "win_rate": sonuc.get('Win Rate %', 0),
            "max_drawdown": sonuc.get('Max Drawdown %', 0),
            "kelly": sonuc.get('Kelly Kriteri %', 0),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rapor/korelasyon")
async def rapor_korelasyon(
    semboller: str = Query("GARAN.IS,AKBNK.IS,THYAO.IS,ASELS.IS,EREGL.IS"),
):
    """Portföy korelasyon ve diversifikasyon raporu."""
    try:
        from mod_korelasyon import korelasyon_raporu, portfoy_optimize_et
        sembol_list = [s.strip().upper() for s in semboller.split(",")]
        rapor = korelasyon_raporu(sembol_list)
        
        return {
            "diversifikasyon_skoru": rapor['diversifikasyon_skoru'],
            "yuksek_korelasyonlu": rapor['yuksek_korelasyonlu'][:10],
            "sektor_dagilimi": rapor['sektor_analizi']['sektor_dagilimi'],
            "tavsiyeler": rapor['tavsiyeler'],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rapor/sinyal-kalite")
async def rapor_sinyal_kalite():
    """Sinyal kalite geri bildirim raporu."""
    try:
        from mod_hafiza import sinyal_kalite_analiz_et
        analiz = sinyal_kalite_analiz_et()
        return {
            "ornek_sayisi": analiz['ornek_sayisi'],
            "genel_basari": analiz['genel_basari'],
            "agirliklar": analiz['agirliklar'],
            "tavsiyeler": analiz['tavsiyeler'],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rapor/log")
async def rapor_log(saat: int = Query(24, ge=1, le=168)):
    """Son N saatlik log analiz raporu."""
    try:
        from mod_logger import log_analiz_et
        analiz = log_analiz_et(son_saat=saat)
        return {
            "son_saat": saat,
            "toplam_kayit": analiz['toplam_kayit'],
            "hata_sayisi": analiz['hata_sayisi'],
            "modul_bazinda": analiz['modul_bazinda'],
            "en_sik_hata": analiz['en_sik_hata'],
            "son_hatalar": analiz['hata_listesi'][-10:],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/durum/circuit-breaker")
async def durum_circuit_breaker():
    """Circuit breaker anlık durumu."""
    try:
        from mod_pozisyon_yonetimi import circuit_breaker_durum
        return {
            **circuit_breaker_durum(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/durum/websocket")
async def durum_websocket():
    """WebSocket bağlantı durumu."""
    try:
        from mod_websocket import websocket_durum
        return {
            **websocket_durum(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/tradingview")
async def webhook_tradingview(data: dict):
    """
    TradingView strateji webhook alıcısı.
    
    Beklenen JSON:
    {
        "symbol": "THYAO.IS",
        "signal": "BUY",
        "price": 123.45,
        "interval": "1d",
        "strategy": "BorsaSinyal"
    }
    """
    try:
        sembol = data.get('symbol', 'BILINMEYEN')
        sinyal = data.get('signal', 'NEUTRAL')
        fiyat = data.get('price', 0)
        
        from mod_hafiza import sinyal_kaydet
        
        if sinyal.upper() in ("BUY", "STRONG_BUY"):
            hedef = fiyat * 1.08
            stop = fiyat * 0.97
            sinyal_kaydet(sembol, f"TV GUCLU AL", fiyat, hedef, stop)
        elif sinyal.upper() in ("SELL", "STRONG_SELL"):
            hedef = fiyat * 1.08
            stop = fiyat * 0.97
            sinyal_kaydet(sembol, f"TV SAT", fiyat, hedef, stop)
        
        return {
            "status": "ok",
            "symbol": sembol,
            "signal": sinyal,
            "price": fiyat,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  BorsaSinyal Pro API")
    print("  http://localhost:8000")
    print("  http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")