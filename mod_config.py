# ══════════════════════════════════════════════════════════════════════
#  mod_config.py — Merkezi Konfigürasyon Yükleyici
#  app_config.json + strateji_config.json'u birleştirir.
# ══════════════════════════════════════════════════════════════════════

import json
import os
from typing import Any, Dict, Optional

from mod_logger import yapilandirilmis_logger, guvenli_blok

_config_logger = yapilandirilmis_logger("Config")

# ── Dosya yolları ──
ROOT = os.path.dirname(os.path.abspath(__file__))
APP_CONFIG_YOLU = os.path.join(ROOT, "app_config.json")
STRATEJI_CONFIG_YOLU = os.path.join(ROOT, "strateji_config.json")

# ── Cache ──
_config_cache: Optional[Dict] = None


def _dosya_yukle(dosya_yolu: str) -> Dict:
    """Tek bir JSON dosyasını güvenli şekilde yükler."""
    try:
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        _config_logger.warning(
            f"Konfigürasyon yüklenemedi: {dosya_yolu}",
            hata_tipi="ConfigYukleme"
        )
        return {}


def tum_config_yukle(force_reload: bool = False) -> Dict:
    """
    Tüm konfigürasyonu birleştirip döndürür.
    app_config.json temel, strateji_config.json onun üstüne yazılır.
    
    Sonuç cache'lenir, force_reload=True ile yeniden yüklenebilir.
    """
    global _config_cache
    
    if _config_cache is not None and not force_reload:
        return _config_cache
    
    config = _dosya_yukle(APP_CONFIG_YOLU)
    strateji = _dosya_yukle(STRATEJI_CONFIG_YOLU)
    
    # Strateji konfigürasyonunu merge et (strateji değerleri öncelikli)
    if strateji:
        if "strateji" not in config:
            config["strateji"] = {}
        config["strateji"].update(strateji)
    
    _config_cache = config
    return config


def config_al(anahtar_yolu: str, varsayilan: Any = None) -> Any:
    """
    Nokta ile ayrılmış anahtar yolundan değer okur.
    
    Örnekler:
        config_al("uygulama.isim") → "BorsaSinyal Pro"
        config_al("tarayici.batch_boyutu") → 50
        config_al("bulunmayan.anahtar", 42) → 42
    """
    config = tum_config_yukle()
    parcalar = anahtar_yolu.split(".")
    
    current = config
    for parca in parcalar:
        if isinstance(current, dict) and parca in current:
            current = current[parca]
        else:
            return varsayilan
    
    return current


def config_guncelle(anahtar_yolu: str, deger: Any):
    """Bellekteki konfigürasyonu günceller (disk'e yazmaz)."""
    config = tum_config_yukle()
    parcalar = anahtar_yolu.split(".")
    
    current = config
    for parca in parcalar[:-1]:
        if parca not in current:
            current[parca] = {}
        current = current[parca]
    
    current[parcalar[-1]] = deger


from filelock import FileLock

def config_dosyaya_kaydet():
    """Bellekteki konfigürasyonu app_config.json'a kaydeder."""
    config = tum_config_yukle()
    try:
        strateji = config.pop("strateji", {})
        
        lock1 = FileLock(APP_CONFIG_YOLU + ".lock", timeout=5)
        with lock1:
            with open(APP_CONFIG_YOLU, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        
        if strateji:
            lock2 = FileLock(STRATEJI_CONFIG_YOLU + ".lock", timeout=5)
            with lock2:
                with open(STRATEJI_CONFIG_YOLU, "w", encoding="utf-8") as f:
                    json.dump(strateji, f, ensure_ascii=False, indent=4)
        
        config["strateji"] = strateji
        _config_logger.info("Konfigürasyon diske kaydedildi")
        return True
    except IOError as e:
        _config_logger.error(f"Konfigürasyon kaydedilemedi: {e}", hata_tipi="IOError")
        return False

# ── Kısayol fonksiyonları ──

def takip_havuzu() -> list:
    """Dashboard takip havuzunu döndürür."""
    return config_al("dashboard.takip_havuzu", [])


def populer_hisseler() -> list:
    """Popüler hisse listesini döndürür."""
    return config_al("dashboard.populer_hisseler", [])


def populer_haber_sembolleri() -> list:
    """Popüler haber sembollerini döndürür."""
    return config_al("dashboard.populer_haber_sembolleri", [])


def tarayici_ayar(anahtar: str, varsayilan: Any = None) -> Any:
    """Tarayıcı konfigürasyonundan değer okur."""
    return config_al(f"tarayici.{anahtar}", varsayilan)


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Merkezi Konfigürasyon Testi")
    print("=" * 50)
    
    # Uygulama ayarları
    print(f"Uygulama: {config_al('uygulama.isim')} v{config_al('uygulama.versiyon')}")
    print(f"Debug: {config_al('uygulama.debug_modu')}")
    
    # Tarayıcı ayarları
    print(f"Batch: {config_al('tarayici.batch_boyutu')}, Workers: {config_al('tarayici.max_workers')}")
    
    # Strateji ayarları
    print(f"Stop Loss Min: %{config_al('strateji.stop_loss_min_yuzde', 2.0)}")
    print(f"RSI Eşik: {config_al('strateji.rsi_al_esigi', 20)}")
    
    # Takip havuzu
    havuz = takip_havuzu()
    print(f"Takip Havuzu: {len(havuz)} hisse")
    
    # Olmayan anahtar
    print(f"Olmayan: {config_al('olmayan.anahtar', 'YOK')}")