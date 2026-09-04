import time
import threading
import os
import json
import traceback
import sys
from analiz import tum_hisseleri_tara
from hisseler_bist import BIST
from hisseler_nasdaq import NASDAQ
from hisseler_sp500 import SP500
from hisseler_kripto import KRIPTO_LISTESI
from mod_hafiza import sinyal_kaydet, bekleyenleri_kontrol_et
from supabase_baglanti import supabase
from collections import deque
import time

# Kripto fiyat geçmişini bellekte tutacak hafıza (Son 5 dakika)
_kripto_bellek = {} 

def kripto_canli_akis_dinleyicisi(sembol, fiyat, hacim, zaman_ms):
    """WebSocket'ten saniyede bir akan veriyi dinler ve anında analiz eder."""
    simdi = time.time()
    
    if sembol not in _kripto_bellek:
        _kripto_bellek[sembol] = deque()
        
    # Belleğe yeni fiyatı ekle: (zaman_sn, fiyat, hacim)
    _kripto_bellek[sembol].append((simdi, fiyat, hacim))
    
    # 5 dakikadan (300 saniye) eski verileri bellekten at
    while _kripto_bellek[sembol] and simdi - _kripto_bellek[sembol][0][0] > 300:
        _kripto_bellek[sembol].popleft()
        
    # Yeterli veri biriktiyse anlık patlama (Scalp) kontrolü yap
    if len(_kripto_bellek[sembol]) > 10:
        ilk_fiyat = _kripto_bellek[sembol][0][1]
        degisim_yuzde = ((fiyat - ilk_fiyat) / ilk_fiyat) * 100
        
        # Eğer son 5 dakika içinde %1.5'ten fazla anlık zıplama varsa!
        if degisim_yuzde >= 1.5:
            # Hemen kâr al ve stop seviyelerini belirle
            hedef = round(fiyat * 1.04, 4) # %4 kâr
            stop = round(fiyat * 0.98, 4)  # %2 stop
            
            # Belleği temizle ki aynı sinyali saniyede 10 kere atmasın
            _kripto_bellek[sembol].clear() 
            
            # Veritabanına anında yaz ve Telegram'a gönder
            try:
                from mod_hafiza import sinyal_kaydet
                from mod_telegram import telegram_mesaj_gonder
                sinyal_kaydet(sembol, "KRIPTO SCALP (CANLI)", fiyat, hedef, stop)
                telegram_mesaj_gonder(f"🚀 <b>ANLIK PATLAMA!</b>\n{sembol}: ${fiyat}\nSon 5dk Değişim: %{degisim_yuzde:.2f}")
                print(f"[{time.ctime()}] 🚀 CANLI KRİPTO YAKALANDI: {sembol} | Fiyat: {fiyat}")
            except Exception as e:
                print(f"Kripto kayıt hatası: {e}")
# ── Piyasa takvimi entegrasyonu (Tavsiye #2) ───────────────────────
try:
    from mod_piyasa_takvimi import tarama_yapilabilir_mi, seansa_kalan_sure, borsa_acik_mi
    PIYASA_TAKVIMI_AKTIF = True
except ImportError:
    PIYASA_TAKVIMI_AKTIF = False
    def _piyasa_yedek():
        return True, "Piyasa takvimi modülü bulunamadı"

# ── Ölü havuz entegrasyonu ──────────────────────────────────────────
try:
    from mod_veri_kaynagi import dead_liste_yukle, dead_listeyi_temizle, dead_listeye_ekle
    OLI_HAVUZ_AKTIF = True
except ImportError:
    OLI_HAVUZ_AKTIF = False

# ═══════════════════════════════════════════════════════════════════
#  SÜREKLİ TARAMA MOTORU YAPILANDIRMASI
# ═══════════════════════════════════════════════════════════════════
BATCH_SIZE = 50           # Her turda taranacak hisse sayısı (35→50: daha az batch = daha hızlı tur)
BATCH_ARASI = 90          # Batch'ler arası bekleme (saniye) = 1.5 dakika (150→90)
TAM_TUR_ARASI = 60        # Tam tur bittikten sonra dinlenme (saniye) (90→60)
MAX_WORKERS = 6           # Paralel indirme işçi sayısı (4→6: daha hızlı batch)
CRASH_BEKLEME = 30        # Hata sonrası yeniden başlama beklemesi (saniye)

class DummyUI:
    def progress(self, val): pass
    def text(self, msg): pass
    def success(self, msg): pass
    def error(self, msg): pass

_tarama_devam_ediyor = False
_tarama_lock = threading.Lock()

def piyasa_tipine_gore_esikler(hisse):
    """Piyasa tipine göre hedef yüzdesi ve piyasa tipini döndürür. (ESNETILDI)"""
    if ".IS" in hisse:
        return 0.015, "bist"          # BIST: %1.5 hedef (eskiden %3)
    elif any(x in hisse.upper() for x in ["BTC", "ETH", "XRP", "ADA", "SOL", "DOGE", "DOT", "AVAX", "LINK", "MATIC", "UNI"]):
        return 0.02, "kripto"          # Kripto: %2 hedef (eskiden %7)
    elif any(x in hisse.upper() for x in ["QQQ", "TQQQ", "SOXL", "NVDA", "AMD", "TSLA", "AMZN", "AAPL", "MSFT", "GOOGL", "META", "NFLX"]):
        return 0.02, "nasdaq"          # NASDAQ: %2 hedef (eskiden %5)
    else:
        return 0.015, "sp500"          # SP500/Diger: %1.5 hedef (eskiden %3)

def _sinyal_norm(sinyal_str: str) -> str:
    """Türkçe karakterleri İngilizce'ye normalize eder."""
    return sinyal_str.upper().replace("Ü", "U").replace("Ğ", "G").replace("İ", "I").replace("Ş", "S").replace("Ö", "O").replace("Ç", "C")

def firsat_kaydet(row):
    """Bir tarama sonucunu GUCLU AL ise veritabanına kaydeder."""
    sinyal = str(row.get('Sinyal', ''))
    sinyal_norm = _sinyal_norm(sinyal)
    if "GUCLU AL" not in sinyal_norm:
        return False
    
    hisse = row['Hisse']
    fiyat = row['Son Fiyat']
    hedef_yuzde, piyasa_tipi = piyasa_tipine_gore_esikler(hisse)
    
    hedef_fiyat = round(fiyat * (1 + hedef_yuzde), 2)
    
    # 🔥 ATR TABANLI DİNAMİK STOP-LOSS
    # Yapılandırmadan min/max % ve ATR çarpanını oku
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json"), "r") as f:
            config = json.load(f)
    except:
        config = {}
    atr_carpani = config.get("atr_stop_carpani", 1.5)
    stop_min_pct = config.get("stop_loss_min_yuzde", 2.0) / 100.0
    stop_max_pct = (config.get("stop_loss_max_yuzde_bist", 5.0) if piyasa_tipi == "bist"
                    else config.get("stop_loss_max_yuzde_diger", 6.5)) / 100.0
    
    # ATR hesapla
    try:
        import yfinance as yf
        tk = yf.Ticker(hisse)
        df = tk.history(period="1mo")
        if not df.empty and len(df) > 5:
            atr_val = float((df['High'] - df['Low']).tail(14).mean())
            atr_yuzde = atr_val / fiyat if fiyat > 0 else 0
            # Stop = ATR × Çarpan, ama min/max sınırları içinde
            stop_yuzde = min(stop_max_pct, max(stop_min_pct, atr_yuzde * atr_carpani))
        else:
            stop_yuzde = stop_min_pct  # Veri yoksa minimum stop
    except:
        stop_yuzde = stop_min_pct  # Hata durumunda minimum stop
    
    stop_fiyat = round(fiyat * (1 - stop_yuzde), 2)
    
 # Bulut Supabase tablosuna anında yazıyoruz
    try:
        yeni_kayit = {
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hisse": hisse,
            "sinyal_tipi": "GUCLU AL",
            "giris_fiyati": float(fiyat),
            "hedef_fiyat": float(hedef_fiyat),
            "stop_fiyat": float(stop_fiyat),
            "durum": "BEKLIYOR"
        }
        supabase.table("ai_sinyaller").insert(yeni_kayit).execute()
    except Exception as sb_err:
        print(f"  ⚠ Supabase bulut kayıt hatası: {sb_err}")   
    print(f"  🔥 FIRSAT: {hisse} | Giriş: {fiyat:.2f} | Hedef: {hedef_fiyat:.2f} (%{hedef_yuzde*100:.1f}) | Stop: {stop_fiyat:.2f} (%{stop_yuzde*100:.1f} · ATR×{atr_carpani})")
    return True

def tek_batch_tara(batch_liste, batch_no, toplam_batch, bas_idx, son_idx):
    """Tek bir batch'i tarar, fırsatları kaydeder."""
    global _tarama_devam_ediyor
    
    with _tarama_lock:
        if _tarama_devam_ediyor:
            print(f"[{time.ctime()}] ⚠️ Önceki tarama hala devam ediyor, bu batch atlanıyor...")
            return 0
        _tarama_devam_ediyor = True
    
    try:
        print(f"[{time.ctime()}] 📊 Batch {batch_no}/{toplam_batch} taranıyor ({bas_idx+1}-{son_idx} / ...)")
        dummy = DummyUI()
        sonuclar = tum_hisseleri_tara(batch_liste, "1mo", dummy, dummy, max_workers=MAX_WORKERS)
        kaydedilen = 0
        
        if sonuclar:
            for row in sonuclar:
                try:
                    if firsat_kaydet(row):
                        kaydedilen += 1
                except Exception as fe:
                    print(f"  ⚠ Fırsat kaydetme hatası ({row.get('Hisse','?')}): {fe}")
        
        print(f"[{time.ctime()}] ✅ Batch {batch_no} bitti → {kaydedilen} yeni fırsat")
        return kaydedilen
        
    except Exception as e:
        print(f"[{time.ctime()}] ❌ Batch {batch_no} HATA: {e}")
        traceback.print_exc()
        return 0
    finally:
        with _tarama_lock:
            _tarama_devam_ediyor = False
def surekli_tarama_dongusu():
    # 1. Kriptoları ana listeden AYIR
    from hisseler_kripto import KRIPTO_LISTESI
    kripto_semboller = [k.replace("USDT", "").lower() + "usdt" for k in KRIPTO_LISTESI]
    
    # 2. WebSocket'i Arka Planda Başlat (Kriptolar artık kendi kendine çalışacak)
    from mod_websocket import websocket_akisi_baslat
    print(f"[{time.ctime()}] ⚡ Kripto WebSocket Motoru Başlatılıyor...")
    websocket_akisi_baslat(kripto_semboller, callback=kripto_canli_akis_dinleyicisi, max_sembol=50)

    # 3. Yavaş tarama döngüsüne SADECE hisseleri (BIST, NASDAQ, SP500) ver
    ham_liste = list(set(BIST + NASDAQ + SP500))

def surekli_tarama_dongusu():
    """Ana sürekli tarama döngüsü - batch'ler halinde durmadan tarar."""
    # TÜM hisseler + kriptolar (tekrarsız)
    kripto_yf = [k.replace("USDT", "-USD") for k in KRIPTO_LISTESI]
    ham_liste = list(set(BIST + NASDAQ + SP500 + kripto_yf))
    
    # ── Ölü havuz filtresi: başlangıçta temizle ─────────────────────
    if OLI_HAVUZ_AKTIF:
        tum_liste = dead_listeyi_temizle(ham_liste)
        dead_set = dead_liste_yukle()
        if dead_set:
            print(f"  💀 {len(dead_set)} ölü/delisted hisse listeden filtrelendi")
    else:
        tum_liste = ham_liste
    
    toplam = len(tum_liste)
    toplam_batch = (toplam + BATCH_SIZE - 1) // BATCH_SIZE
    tahmini_tur_suresi = toplam_batch * (BATCH_ARASI // 60) + (TAM_TUR_ARASI // 60)
    
    print("="*60)
    print("  ◈ SÜREKLİ TARAMA MOTORU AKTİF ◈")
    print(f"  Toplam Hisse : {toplam}")
    print(f"  Batch Boyutu : {BATCH_SIZE} hisse/batch")
    print(f"  Toplam Batch : {toplam_batch}")
    print(f"  Batch Arası  : {BATCH_ARASI}s (~{BATCH_ARASI//60}dk)")
    print(f"  İşçi Sayısı  : {MAX_WORKERS}")
    print(f"  Tahmini Tur  : ~{tahmini_tur_suresi}dk")
    if PIYASA_TAKVIMI_AKTIF:
        durum = borsa_acik_mi()
        acik_piyasalar = [k for k, v in durum.items() if v and k != 'neden']
        print(f"  🕐 Piyasa Durumu: {', '.join(acik_piyasalar) if acik_piyasalar else '🔴 TÜM PİYASALAR KAPALI'}")
        if durum.get('neden'):
            print(f"  📌 {durum['neden']}")
    print("="*60)
    
    batch_no = 0
    tur_sayisi = 0
    toplam_firsat = 0
    piyasa_kapali_uyari = False
    
    while True:
        try:
            # ── Piyasa takvimi kontrolü (Tavsiye #2) ────────────────
            if PIYASA_TAKVIMI_AKTIF:
                yapilabilir, mesaj = tarama_yapilabilir_mi()
                if not yapilabilir:
                    if not piyasa_kapali_uyari:
                        print(f"[{time.ctime()}] 🔴 {mesaj}")
                        print(f"[{time.ctime()}] ⏳ Piyasalar açılana kadar beklemede...")
                        piyasa_kapali_uyari = True
                    
                    # Piyasa açılana kadar bekle (5 dk'da bir kontrol)
                    time.sleep(300)
                    continue
                else:
                    if piyasa_kapali_uyari:
                        print(f"[{time.ctime()}] ✅ {mesaj} → Tarama başlıyor!")
                        piyasa_kapali_uyari = False
            
            # Her yeni tur başında bekleyen pozisyonları kontrol et
            if batch_no == 0:
                tur_sayisi += 1
                print(f"\n{'─'*55}")
                print(f"[{time.ctime()}] 🔄 TUR {tur_sayisi} BAŞLADI")
                if PIYASA_TAKVIMI_AKTIF:
                    durum = borsa_acik_mi()
                    acik_str = " | ".join([f"{k}: {'🟢' if v else '🔴'}" for k, v in durum.items() if k != 'neden'])
                    print(f"[{time.ctime()}] 🕐 {acik_str}")
                print(f"{'─'*55}")
                try:
                    bekleyenleri_kontrol_et()
                except Exception as be:
                    print(f"[{time.ctime()}] ⚠ Bekleyen kontrol hatası: {be}")
            
            # Batch aralığını hesapla
            bas = batch_no * BATCH_SIZE
            son = min(bas + BATCH_SIZE, toplam)
            batch_liste = tum_liste[bas:son]
            
            # Batch'i tara
            kaydedilen = tek_batch_tara(batch_liste, batch_no + 1, toplam_batch, bas, son)
            toplam_firsat += kaydedilen
            
            # Sonraki batch'e geç
            batch_no += 1
            
            # Tur bitti mi?
            if batch_no >= toplam_batch:
                batch_no = 0
                print(f"[{time.ctime()}] 🏁 TUR {tur_sayisi} TAMAMLANDI → Toplam {toplam_firsat} fırsat (bu oturum)")
                bekleme = TAM_TUR_ARASI
                print(f"[{time.ctime()}] ⏳ Yeni tur öncesi {bekleme}s dinlenme...")
            else:
                bekleme = BATCH_ARASI
                print(f"[{time.ctime()}] ⏳ Sonraki batch için {bekleme}s ({bekleme//60}dk)...")
            
        except KeyboardInterrupt:
            print(f"\n[{time.ctime()}] 🛑 Tarama kullanıcı tarafından durduruldu.")
            print(f"  📊 Bu oturum: {tur_sayisi} tur, {toplam_firsat} fırsat")
            sys.exit(0)
        except Exception as crash:
            print(f"\n[{time.ctime()}] 💥 ANA DÖNGÜ ÇÖKTÜ: {crash}")
            traceback.print_exc()
            print(f"[{time.ctime()}] 🔄 {CRASH_BEKLEME}s sonra yeniden başlıyor...")
            time.sleep(CRASH_BEKLEME)
            # Sayaçları sıfırlama, kaldığı yerden devam et
            bekleme = 5
            if batch_no >= toplam_batch:
                batch_no = 0
        
        time.sleep(bekleme)

if __name__ == "__main__":
    surekli_tarama_dongusu()
