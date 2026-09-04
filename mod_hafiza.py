import sqlite3
import datetime
import os
import numpy as np
import pandas as pd
import yfinance as yf

# Telegram modulunu guvenli cagir
try:
    from mod_telegram import telegram_mesaj_gonder
except ImportError:
    def telegram_mesaj_gonder(mesaj): pass

# Binance/ccxt icin (kripto sinyalleri kontrol etmek icin gerekli)
try:
    import ccxt
    CCXT_AKTIF = True
except ImportError:
    CCXT_AKTIF = False

# Veritabani yolunu mutlak yol olarak belirle
DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")

# ══════════════════════════════════════════════════════════════════════
#  STANDART DURUM SABITLERI (Tum modullerde tutarli olmasi icin)
# ══════════════════════════════════════════════════════════════════════
DURUM_BASARILI = "🎯 BAŞARILI"
DURUM_BASARISIZ = "⛔ BAŞARISIZ"
DURUM_BEKLIYOR = "BEKLIYOR"
DURUM_ZAMAN_ASIMI = "⏰ ZAMAN AŞIMI"

# Max bekleme sureleri (gun)
MAX_BEKLEME_KRIPTO = 9
MAX_BEKLEME_HISSE = 30

# ══════════════════════════════════════════════════════════════════════
#  DURUM NORMALIZASYONU — Eski formattaki durumlari yeniye cevirir
# ══════════════════════════════════════════════════════════════════════
def _durum_normalize(durum_str: str) -> str:
    """Eski/usulsuz durum degerlerini standart formata cevirir."""
    if not durum_str or not isinstance(durum_str, str):
        return durum_str
    d = durum_str.strip().upper()
    # BASARILI varyantlari
    if any(k in d for k in ['BASARILI', 'BAŞARILI', 'KAR', 'HEDEF']):
        return DURUM_BASARILI
    # BASARISIZ varyantlari
    if any(k in d for k in ['BASARISIZ', 'BAŞARISIZ', 'STOP', 'ZARAR']):
        return DURUM_BASARISIZ
    # ZAMAN ASIMI varyantlari
    if any(k in d for k in ['ZAMAN', 'ASIMI', 'AŞIMI']):
        return DURUM_ZAMAN_ASIMI
    # ZAYIF KAPATMA -> BASARISIZ say
    if 'ZAYIF' in d or 'KAPATMA' in d:
        return DURUM_BASARISIZ
    # GUNCELLENDI -> yok say, BEKLIYOR olarak kalsin (tekrar sinyal kaydi yapilir)
    if 'GUNCELLENDI' in d:
        return DURUM_BEKLIYOR
    return durum_str


def _durum_basarili_mi(durum_str: str) -> bool:
    """Bir durum degerinin basarili olup olmadigini kontrol eder."""
    if not durum_str or not isinstance(durum_str, str):
        return False
    d = durum_str.strip().upper()
    return any(k in d for k in ['BASARILI', 'BAŞARILI', 'KAR', 'HEDEF']) and 'BASARISIZ' not in d and 'BAŞARISIZ' not in d and 'STOP' not in d


def _durum_basarisiz_mi(durum_str: str) -> bool:
    """Bir durum degerinin basarisiz/stop olup olmadigini kontrol eder."""
    if not durum_str or not isinstance(durum_str, str):
        return False
    d = durum_str.strip().upper()
    return any(k in d for k in ['BASARISIZ', 'BAŞARISIZ', 'STOP', 'ZAYIF', 'ZARAR'])


def _durum_bekliyor_mu(durum_str: str) -> bool:
    """Bir durum degerinin bekliyor olup olmadigini kontrol eder."""
    if not durum_str or not isinstance(durum_str, str):
        return False
    d = durum_str.strip().upper()
    return 'BEK' in d and 'IYOR' in d


def _durum_zaman_asimi_mi(durum_str: str) -> bool:
    """Bir durum degerinin zaman asimi olup olmadigini kontrol eder."""
    if not durum_str or not isinstance(durum_str, str):
        return False
    d = durum_str.strip().upper()
    return 'ZAMAN' in d or 'ASIMI' in d or 'AŞIMI' in d


# ══════════════════════════════════════════════════════════════════════
#  KRIPTO SEMBOL KONTROLU
# ══════════════════════════════════════════════════════════════════════
def _is_kripto_sembol(kod: str) -> bool:
    """Bir sembolun kripto olup olmadigini kontrol eder."""
    if not kod or not isinstance(kod, str):
        return False
    ust = kod.upper().strip()
    return ('USDT' in ust or 'USD' in ust or 'BTC' in ust) and '.IS' not in ust

# ══════════════════════════════════════════════════════════════════════
#  CCXT BINANCE ILE KRIPTO VERI CEKME
# ══════════════════════════════════════════════════════════════════════
def _kripto_binance_fiyat_cek(kod: str, gun_sayisi: int = 30) -> pd.DataFrame:
    """
    ccxt Binance ile kripto OHLCV verisi ceker.
    yfinance'in desteklemedigi USDT ciftleri icin kullanilir.
    """
    if not CCXT_AKTIF:
        return pd.DataFrame()
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        sembol = kod.upper().strip().replace('-', '/').replace('_', '/')
        if '/' not in sembol and sembol.endswith('USDT'):
            sembol = sembol[:-4] + '/USDT'
        elif '/' not in sembol and sembol.endswith('USD') and not sembol.endswith('USDT'):
            sembol = sembol[:-3] + '/USD'
        
        # Son N gunu kapsayacak sekilde veri cek
        since = exchange.parse8601(
            (datetime.datetime.now() - datetime.timedelta(days=gun_sayisi + 1)).strftime("%Y-%m-%dT00:00:00Z")
        )
        ohlcv = exchange.fetch_ohlcv(sembol, '1d', since=since, limit=gun_sayisi + 5)
        
        if not ohlcv:
            return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        print(f"[BINANCE] {kod} veri cekilemedi: {str(e)[:80]}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════
#  GUCLU VERI CEKME: yfinance + gerekirse Binance fallback
# ══════════════════════════════════════════════════════════════════════
def _guvenli_fiyat_cek(hisse: str, gun_sayisi: int = 30) -> tuple:
    """
    Hisse/kripto icin guvenli fiyat verisi ceker.
    Kripto ise once Binance/ccxt, basarisiz olursa yfinance dener.
    Hisse ise yfinance dener.
    
    Donus: (df: pd.DataFrame, son_fiyat: float veya None, hata: str veya None)
    """
    df = pd.DataFrame()
    hata = None
    is_kripto = _is_kripto_sembol(hisse)
    
    if is_kripto and CCXT_AKTIF:
        df = _kripto_binance_fiyat_cek(hisse, gun_sayisi)
        if not df.empty:
            son_fiyat = float(df['Close'].iloc[-1])
            return df, son_fiyat, None
    
    # Fallback: yfinance
    try:
        # Kripto icin sembol donusumu dene
        sorgu_kodu = hisse
        if is_kripto and 'USDT' in hisse.upper():
            sorgu_kodu = hisse.upper().replace('USDT', '-USD')
        
        tk = yf.Ticker(sorgu_kodu)
        period_str = f"{max(5, gun_sayisi)}d"
        df = tk.history(period=period_str)
        
        # Eger USDT formatinda veri gelmezse orijinal kodu dene
        if df.empty and sorgu_kodu != hisse:
            tk = yf.Ticker(hisse)
            df = tk.history(period=period_str)
        
        if df.empty:
            return df, None, f"yfinance'ten veri alinamadi ({hisse})"
        
        son_fiyat = float(df['Close'].iloc[-1])
        return df, son_fiyat, None
    except Exception as e:
        return df, None, str(e)[:100]


# ══════════════════════════════════════════════════════════════════════
#  SINYAL KAYDET
# ══════════════════════════════════════════════════════════════════════
def sinyal_kaydet(hisse, sinyal_tipi, giris_fiyat, hedef_fiyat, stop_fiyat):
    try:
        conn = sqlite3.connect(DB_YOLU, timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS ai_sinyaller
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      tarih TEXT,
                      hisse TEXT,
                      sinyal_tipi TEXT,
                      giris_fiyati REAL,
                      hedef_fiyat REAL,
                      stop_fiyat REAL,
                      durum TEXT,
                      kapanis_fiyati REAL)''')
        
        # Performans indeksleri (sorgu hizini 10x artirir)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sinyaller_hisse ON ai_sinyaller(hisse)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sinyaller_tarih ON ai_sinyaller(tarih)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sinyaller_durum ON ai_sinyaller(durum)")
        
        # Sinyal tipini normalize et (GUCLU AL, GÜÇLÜ AL farkını ortadan kaldır)
        sinyal_tipi_normalized = _sinyal_tipi_normalize(sinyal_tipi)
        
        # --- CIFT ISLEM KORUMASI (DÜZELTİLDİ v2): Ayni hisse icin bekleyen varsa guncelle ---
        c.execute("SELECT id, giris_fiyati, durum, tarih FROM ai_sinyaller WHERE hisse=? AND durum LIKE 'BEK%IYOR' ORDER BY tarih DESC", (hisse,))
        mevcut_liste = c.fetchall()
        atlanan_sinyal = False
        
        # Birden fazla BEKLIYOR kaydi varsa en yenisini tut, eskilerini temizle
        if len(mevcut_liste) > 1:
            en_yeni = mevcut_liste[0]
            for eski_kayit in mevcut_liste[1:]:
                c.execute("UPDATE ai_sinyaller SET durum=?, kapanis_fiyati=? WHERE id=?", 
                          ('GUNCELLENDI', float(giris_fiyat), eski_kayit[0]))
            print(f"[TEMIZLIK] {hisse}: {len(mevcut_liste)-1} eski BEKLIYOR kaydi GUNCELLENDI yapildi")
            mevcut_liste = [en_yeni]
        
        if mevcut_liste:
            eski_id, eski_giris, eski_durum, eski_tarih = mevcut_liste[0]
            fark_yuzde = abs(float(giris_fiyat) - float(eski_giris)) / float(eski_giris) * 100 if float(eski_giris) > 0 else 100
            
            # Son 1 saat icinde ayni hisse kaydedilmisse spam engeli (gercek kisa vadeli spam)
            # HAFTASONU DUZELTMESI: Hafta sonlari fiyatlar sabit kaldigi icin fark %1'in
            # altinda olur ve bu kural tum sinyalleri eziyordu. Artik fiyat farki %1'in
            # altinda olsa bile sinyal KAYDEDILIR; asiri spam sadece Telegram bildirimini
            # engelleyerek sinirlandirilir (GUNCELLENDI mekanizmasi ayni hissedeki eski
            # BEKLIYOR kayitlarini yine temizler, tablo siismez).
            try:
                from datetime import datetime, timedelta
                eski_dt = datetime.strptime(eski_tarih, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - eski_dt).total_seconds() < 3600 and fark_yuzde < 1.0:
                    print(f"[BILGI] {hisse} son 1 saatte zaten BEKLIYOR (fark %{fark_yuzde:.1f}) - yine de kaydediliyor (hafta sonu sabit fiyat)")
            except:
                pass
            
            # Fiyat farkina bakmaksizin eski pozisyonu GUNCELLENDI yap, yeni sinyali kaydet
            c.execute("UPDATE ai_sinyaller SET durum=?, kapanis_fiyati=? WHERE id=?", 
                      ('GUNCELLENDI', float(giris_fiyat), eski_id))
            print(f"[GUNCELLE] {hisse}: Eski BEKLIYOR pozisyon (giris: {eski_giris:.2f}, fark %{fark_yuzde:.1f}) -> yeni pozisyon (giris: {giris_fiyat:.2f}) ile guncellendi")
        
        tarih = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute('''INSERT INTO ai_sinyaller 
                     (tarih, hisse, sinyal_tipi, giris_fiyati, hedef_fiyat, stop_fiyat, durum, kapanis_fiyati) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (tarih, hisse, sinyal_tipi_normalized, float(giris_fiyat), float(hedef_fiyat), float(stop_fiyat), DURUM_BEKLIYOR, 0.0))
        
        conn.commit()
        conn.close()
        print(f"[YENI] Firsat Yakalandi: {hisse} hafizaya yazildi.")
        
        # ⭐ DUZELTME: Sadece atlanan sinyal degilse Telegram bildirimi gonder
        if not atlanan_sinyal:
            _telegram_bildirim_gonder(hisse, sinyal_tipi_normalized, giris_fiyat, hedef_fiyat, stop_fiyat)
        
    except Exception as e:
        print(f"HATA: {hisse} kaydedilemedi! Sebep: {e}")


def _sinyal_tipi_normalize(sinyal_tipi: str) -> str:
    """Sinyal tipini standart ASCII formata cevirir (GUCLU AL, KRIPTO SCALP)."""
    if not sinyal_tipi:
        return "GUCLU AL"
    ust = sinyal_tipi.upper()
    # Türkçe karakterleri ASCII'ye çevir
    ust = ust.replace('Ü', 'U').replace('Ğ', 'G').replace('İ', 'I').replace('Ş', 'S').replace('Ö', 'O').replace('Ç', 'C')
    if 'GUCLU AL' in ust:
        return 'GUCLU AL'
    if 'GUCLU SAT' in ust:
        return 'GUCLU SAT'
    if 'KRIPTO SCALP' in ust:
        return 'KRIPTO SCALP'
    if 'AL' in ust:
        return 'AL'
    if 'SAT' in ust:
        return 'SAT'
    return sinyal_tipi


def _telegram_bildirim_gonder(hisse, sinyal_tipi, giris_fiyat, hedef_fiyat, stop_fiyat):
    """
    Telegram'a GUCLU AL bildirimi gonderir.
    Son 24 saatte ayni hisseye ayni tipte bildirim gidip gitmedigini kontrol eder.
    """
    son_24_saat = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        kontrol_conn = sqlite3.connect(DB_YOLU)
        kc = kontrol_conn.cursor()
        # ⭐ DUZELTME: Hem GUCLU AL hem GÜÇLÜ AL formatlarini kontrol et
        # Türkçe karakter sorununu asmak için her iki formati da ara
        kc.execute(
            "SELECT id FROM ai_sinyaller WHERE hisse=? AND "
            "(sinyal_tipi LIKE '%GUCLU%AL%' OR sinyal_tipi LIKE '%GÜÇLÜ%AL%') "
            "AND tarih >= ? AND id < (SELECT MAX(id) FROM ai_sinyaller)",
            (hisse, son_24_saat)
        )
        son_mesaj_var = kc.fetchone()
        kontrol_conn.close()
        
        if son_mesaj_var:
            print(f"[TELEGRAM] {hisse} icin son 24 saatte zaten GUCLU AL mesaji gonderilmis - Telegram mesaji atlaniyor")
            return
        
        mesaj = (
            f"<b>YENI FIRSAT YAKALANDI!</b>\n\n"
            f"Sembol: <b>{hisse}</b>\n"
            f"Sinyal: <b>{sinyal_tipi}</b>\n"
            f"Giris: {giris_fiyat:.2f}\n"
            f"Hedef: {hedef_fiyat:.2f}\n"
            f"Stop: {stop_fiyat:.2f}"
        )
        telegram_mesaj_gonder(mesaj)
        print(f"[TELEGRAM] {hisse} GUCLU AL mesaji gonderildi")
        
    except Exception as e:
        print(f"[TELEGRAM] Kontrol hatasi: {e} - yine de mesaj gonderiliyor")
        mesaj = (
            f"<b>YENI FIRSAT YAKALANDI!</b>\n\n"
            f"Sembol: <b>{hisse}</b>\n"
            f"Sinyal: <b>{sinyal_tipi}</b>\n"
            f"Giris: {giris_fiyat:.2f}\n"
            f"Hedef: {hedef_fiyat:.2f}\n"
            f"Stop: {stop_fiyat:.2f}"
        )
        telegram_mesaj_gonder(mesaj)


# ══════════════════════════════════════════════════════════════════════
#  BEKLEYENLERI KONTROL ET (ANA FONKSIYON — DUZELTILDI)
# ══════════════════════════════════════════════════════════════════════
def bekleyenleri_kontrol_et():
    """
    Bekleyen tum pozisyonlari kontrol eder.
    
    DUZELTMELER (v1.1):
    - Kripto semboller icin ccxt Binance kullanilir (yfinance desteklemez)
    - Durum degerleri standart formatta yazilir (🎯 BAŞARILI / ⛔ BAŞARISIZ)
    - Veri cekilemeyen semboller atlanir (hata verilmez)
    """
    try:
        conn = sqlite3.connect(DB_YOLU, timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'")
        if not c.fetchone():
            conn.close()
            return 0

        c.execute("SELECT id, hisse, hedef_fiyat, stop_fiyat, giris_fiyati, tarih FROM ai_sinyaller WHERE durum LIKE 'BEK%IYOR'")
        bekleyenler = c.fetchall()

        if not bekleyenler:
            conn.close()
            return 0

        simdi = datetime.datetime.now()
        kapanan = 0

        for islem in bekleyenler:
            islem_id, hisse, hedef, stop, giris_fiyat, sinyal_tarihi = islem
            
            try:
                try:
                    sinyal_dt = datetime.datetime.strptime(sinyal_tarihi, "%Y-%m-%d %H:%M:%S")
                except:
                    sinyal_dt = datetime.datetime.strptime(sinyal_tarihi, "%Y-%m-%d")
                
                gun_farki = (simdi - sinyal_dt).days
                
                # Zaman asimi kontrolu: kripto 7 gun, hisse 30 gun
                is_kripto = _is_kripto_sembol(hisse)
                max_bekleme = MAX_BEKLEME_KRIPTO if is_kripto else MAX_BEKLEME_HISSE
                if gun_farki > max_bekleme:
                    df, son_fiyat, hata = _guvenli_fiyat_cek(hisse, gun_sayisi=5)
                    if son_fiyat is None:
                        son_fiyat = giris_fiyat
                    
                    c.execute('''UPDATE ai_sinyaller
                                 SET durum = ?, kapanis_fiyati = ?
                                 WHERE id = ?''', (DURUM_ZAMAN_ASIMI, son_fiyat, islem_id))
                    tur_str = "KRIPTO 7" if is_kripto else "HISSE 30"
                    print(f"ZAMAN ASIMI ({tur_str}gun): {hisse} -> {gun_farki} gun gecti (Kapanis: {son_fiyat:.2f})")
                    kapanan += 1
                    continue
                
                # Piyasa verisini cek
                period_gun = max(5, min(gun_farki + 1, 30))
                df, son_fiyat, hata = _guvenli_fiyat_cek(hisse, gun_sayisi=period_gun)
                
                if df.empty or son_fiyat is None:
                    if hata:
                        print(f"[ATLANDI] {hisse}: {hata}")
                    continue
                
                yeni_durum = None
                kapanis_fiyat = None
                
                max_fiyat = float(df['High'].max())
                min_fiyat = float(df['Low'].min())
                guncel_fiyat = float(df['Close'].iloc[-1])
                
                # Hedefe ulasti mi?
                if max_fiyat >= hedef:
                    yeni_durum = DURUM_BASARILI
                    hedef_gunleri = df[df['High'] >= hedef]
                    if len(hedef_gunleri) > 0:
                        kapanis_fiyat = float(hedef_gunleri['Close'].iloc[0])
                    else:
                        kapanis_fiyat = hedef
                
                # Stop oldu mu?
                elif min_fiyat <= stop:
                    yeni_durum = DURUM_BASARISIZ
                    stop_gunleri = df[df['Low'] <= stop]
                    if len(stop_gunleri) > 0:
                        kapanis_fiyat = float(stop_gunleri['Close'].iloc[0])
                    else:
                        kapanis_fiyat = stop
                
                # Guncel fiyat kontrolleri
                elif guncel_fiyat >= hedef:
                    yeni_durum = DURUM_BASARILI
                    kapanis_fiyat = guncel_fiyat
                elif guncel_fiyat <= stop:
                    yeni_durum = DURUM_BASARISIZ
                    kapanis_fiyat = guncel_fiyat

                # ═══ TEKNIK GECERLILIK KONTROLU (7+ gun bekleyenler icin) ═══
                if not yeni_durum and gun_farki >= 7:
                    try:
                        close = df['Close'].squeeze()
                        # RSI hesapla
                        delta = close.diff()
                        gain = delta.where(delta > 0, 0.0)
                        loss = (-delta).where(delta < 0, 0.0)
                        avg_gain = gain.rolling(14).mean()
                        avg_loss = loss.rolling(14).mean()
                        rs = avg_gain / avg_loss.replace(0, np.nan) if hasattr(np, 'nan') else avg_gain / avg_loss.replace(0, 0.001)
                        rsi_vals = 100 - (100 / (1 + rs))
                        guncel_rsi = float(rsi_vals.iloc[-1]) if not pd.isna(rsi_vals.iloc[-1]) else 50.0
                        
                        # MACD kontrolu
                        ema12 = close.ewm(span=12, adjust=False).mean()
                        ema26 = close.ewm(span=26, adjust=False).mean()
                        macd_line = ema12 - ema26
                        signal_line = macd_line.ewm(span=9, adjust=False).mean()
                        macd_sat_sinyali = macd_line.iloc[-1] < signal_line.iloc[-1]
                        
                        # Trend yonu degismis mi? (MA20 vs MA50)
                        ma20 = float(close.rolling(20).mean().iloc[-1])
                        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else ma20
                        trend_dusus = guncel_fiyat < ma20 and ma20 < ma50
                        
                        # Eger sinyal AL/sat trendi tersine donmusse kapat
                        if guncel_rsi > 65 and macd_sat_sinyali and trend_dusus:
                            yeni_durum = DURUM_BASARISIZ
                            kapanis_fiyat = guncel_fiyat
                            print(f"TEKNIK IPTAL (7+g): {hisse} -> RSI={guncel_rsi:.0f} MACD=SAT Trend=DUSUS -> pozisyon kapatiliyor")
                        elif guncel_rsi > 60 and macd_sat_sinyali and gun_farki >= 14:
                            # 14+ gun bekleyen ve teknik bozulan
                            yeni_durum = DURUM_BASARISIZ
                            kapanis_fiyat = guncel_fiyat
                            print(f"TEKNIK IPTAL (14+g): {hisse} -> RSI={guncel_rsi:.0f} MACD=SAT -> pozisyon kapatiliyor")
                    except Exception as te:
                        print(f"Teknik kontrol hatasi ({hisse}): {te}")

                if yeni_durum:
                    c.execute('''UPDATE ai_sinyaller
                                 SET durum = ?, kapanis_fiyati = ?
                                 WHERE id = ?''', (yeni_durum, kapanis_fiyat, islem_id))
                    print(f"POZISYON KAPANDI: {hisse} -> {yeni_durum} (Kapanis: {kapanis_fiyat:.2f})")
                    kapanan += 1
                    
                    kapanis_mesaji = f"<b>ISLEM KAPANDI!</b>\n\nSembol: <b>{hisse}</b>\nDurum: <b>{yeni_durum}</b>\nKapanis Fiyati: {kapanis_fiyat:.2f}"
                    telegram_mesaj_gonder(kapanis_mesaji)

            except Exception as e:
                print(f"Kontrol hatasi ({hisse}): {e}")
                continue
        
        conn.commit()
        if kapanan > 0:
            print(f"[KONTROL] {kapanan} pozisyon sonuclandi.")
        
        conn.close()
        return kapanan
        
    except Exception as e:
        print(f"Kontrolcu hatasi: {e}")
        return 0


# ══════════════════════════════════════════════════════════════════════
#  ESKI DURUM DEGERLERINI GUNCELLE (BIR KERELIK TEMIZLIK)
# ══════════════════════════════════════════════════════════════════════
def eski_durumlari_normallestir():
    """
    Veritabanindaki eski/usulsuz durum degerlerini standart formata cevirir.
    Bu fonksiyon bekleyenleri_kontrol_et() oncesinde bir kere calistirilmalidir.
    """
    try:
        conn = sqlite3.connect(DB_YOLU)
        c = conn.cursor()
        
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'")
        if not c.fetchone():
            conn.close()
            return 0
        
        # Tum BEKLIYOR olmayan kayitlari cek
        c.execute("SELECT id, durum FROM ai_sinyaller WHERE durum NOT LIKE 'BEK%IYOR' AND durum != 'GUNCELLENDI'")
        rows = c.fetchall()
        
        degisen = 0
        for row_id, eski_durum in rows:
            yeni_durum = _durum_normalize(eski_durum)
            if yeni_durum and yeni_durum != eski_durum:
                c.execute("UPDATE ai_sinyaller SET durum = ? WHERE id = ?", (yeni_durum, row_id))
                print(f"[NORMALIZE] id={row_id}: '{eski_durum}' -> '{yeni_durum}'")
                degisen += 1
        
        conn.commit()
        conn.close()
        if degisen > 0:
            print(f"[NORMALIZE] {degisen} durum degeri standartlastirildi.")
        return degisen
    except Exception as e:
        print(f"[NORMALIZE] Hata: {e}")
        return 0


