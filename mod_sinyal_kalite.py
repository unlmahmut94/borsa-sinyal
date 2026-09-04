# ══════════════════════════════════════════════════════════════════════
#  mod_sinyal_kalite.py — Sinyal Kalite Takip Motoru v1.0
#  
#  AMAÇ: 15 indikatörün her birinin gerçek piyasa performansını ölçmek.
#         Düşük performanslı indikatörleri otomatik devre dışı bırakmak.
#         Win Rate'i indikatör bazında artırmak.
#
#  ALGORİTMA:
#  ┌─────────────────────────────────────────────────────────────────┐
#  │ ADIM 1: Veritabanından kapanan işlemleri çek                    │
#  │ ADIM 2: Her işlem için sinyal_detay'ı parse et                 │
#  │         "✅ RSI 28: Aşırı Satım" → RSI AL sinyali              │
#  │ ADIM 3: İndikatör bazında başarı/başarısız say                  │
#  │ ADIM 4: Her indikatör için Win Rate hesapla                     │
#  │ ADIM 5: Win Rate < %40 olanları "ZAYIF" işaretle               │
#  │ ADIM 6: 2 ardışık raporda ZAYIF çıkanları otomatik devre dışı   │
#  │ ADIM 7: Raporu JSON'a kaydet, Streamlit'te göster              │
#  └─────────────────────────────────────────────────────────────────┘
#
#  KULLANIM:
#    from mod_sinyal_kalite import kalite_raporu_olustur
#    rapor = kalite_raporu_olustur()
#    print(rapor['ozet'])
# ══════════════════════════════════════════════════════════════════════

import sqlite3
import os
import json
import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np

_logger = logging.getLogger("SinyalKalite")
_logger.setLevel(logging.DEBUG)
if not _logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(h)

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")
KALITE_DOSYASI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sinyal_kalite_raporu.json")

# ══════════════════════════════════════════════════════════════════════
#  İNDİKATÖR TANIMLARI VE PARSE KURALLARI
# ══════════════════════════════════════════════════════════════════════

INDIKATOR_PARSER = {
    # (regex pattern, indikatör adı, ne zaman AL sinyali sayılır)
    "rsi": (
        r"RSI\s*[\d.]+.*?(Aşırı Satım|Dip Fırsatı|Satış Bölgesine Yakın)",
        "RSI (Göreceli Güç)",
        "RSI aşırı satımda AL sinyali verir"
    ),
    "macd": (
        r"MACD.*?(Yukarı Kesişim|AL Sinyali|Yükseliş Bölgesinde|Güçleniyor)",
        "MACD (Momentum)",
        "MACD yukarı kesişim AL sinyalidir"
    ),
    "bollinger": (
        r"BB.*?(Alt Bant|Aşırı Satım|Daralması)",
        "Bollinger Bantları",
        "BB alt bant kırılımı AL sinyalidir"
    ),
    "market_yapisi": (
        r"Market Yapısı.*?(Yükseliş|BOS)",
        "Market Yapısı (SMC)",
        "BOS yapısı yükseliş sinyalidir"
    ),
    "order_block": (
        r"Order Block.*?(Kurumsal Alım)",
        "Order Block",
        "Kurumsal alım bölgesi AL sinyalidir"
    ),
    "ma": (
        r"(Fiyat MA50 Üzerinde|EMA9 > EMA21|MA20 > MA50|Boğa Trendi)",
        "Hareketli Ortalama",
        "Fiyat MA üzerinde boğa piyasası"
    ),
    "stochastic": (
        r"Stoch.*?(Aşırı Satım|Yukarı Kesişim)",
        "Stochastic Osilatör",
        "Stochastic aşırı satım AL sinyalidir"
    ),
    "cci": (
        r"CCI.*?(Aşırı Satım|Derin Aşırı Satım)",
        "CCI (Commodity Channel)",
        "CCI aşırı satım AL sinyalidir"
    ),
    "williams": (
        r"Williams.*?(Dip Bölgesi)",
        "Williams %R",
        "Williams dip bölgesi AL sinyalidir"
    ),
    "mfi": (
        r"MFI.*?(Para Girişi|Gizli Alım)",
        "MFI (Money Flow)",
        "MFI para girişi AL sinyalidir"
    ),
    "adx": (
        r"ADX.*?(Güçlü Yükseliş|Yükseliş Eğilimi)",
        "ADX (Trend Gücü)",
        "ADX yükseliş trendi AL sinyalidir"
    ),
    "obv": (
        r"OBV.*?(Hacim Artışı|Alıcılar Güçlü)",
        "OBV (Hacim Trendi)",
        "OBV hacim artışı AL sinyalidir"
    ),
    "atr": (
        r"ATR.*?(Düşük.*?Sıkışma|Patlama Öncesi)",
        "ATR (Volatilite)",
        "ATR düşük volatilite sıkışma sinyalidir"
    ),
    "temel": (
        r"(F/K|PD/DD).*?(Çok Ucuz|Cazip|Defter Değeri Altı)",
        "Temel Analiz (F/K PD/DD)",
        "Düşük F/K ve PD/DD AL sinyalidir"
    ),
    "nlp": (
        r"NLP.*?(Çok Pozitif|Pozitif Haber)",
        "Haber Duyarlılığı (NLP)",
        "Pozitif haber akışı AL sinyalidir"
    ),
}


def _sinyal_detayini_parse_et(detay_metni: str) -> list:
    """
    Sinyal detay metnini indikatörlere ayırır.
    
    Algoritma:
    1. Detay metni " | " ile ayrılmış indikatör sinyalleridir
    2. Her parça regex ile hangi indikatöre ait olduğu belirlenir
    3. ✅ = AL sinyali, ❌ = SAT sinyali, ⚠️ = Uyarı, ⚡ = Nötr
    4. Dönüş: [{"indikator": "RSI", "sinyal": "AL"}, ...]
    
    Örnek Girdi:
    "✅ Market Yapısı: Yükseliş (BOS) | ✅ RSI 28: Aşırı Satım | ❌ MACD: Aşağı Kesişim"
    
    Örnek Çıktı:
    [{"indikator": "rsi", "sinyal": "AL"}, {"indikator": "macd", "sinyal": "SAT"}]
    """
    if not detay_metni or not isinstance(detay_metni, str):
        return []
    
    # Parçalara ayır
    parcalar = detay_metni.split(" | ")
    
    sonuc = []
    for parca in parcalar:
        parca = parca.strip()
        if not parca:
            continue
        
        # Emoji bazlı sinyal yönü tespiti
        if parca.startswith("✅"):
            sinyal_yonu = "AL"
        elif parca.startswith("❌"):
            sinyal_yonu = "SAT"
        elif parca.startswith("⚠️"):
            sinyal_yonu = "UYARI"
        elif parca.startswith("⚡"):
            sinyal_yonu = "NOTR"
        elif parca.startswith("📊"):
            sinyal_yonu = "NOTR"
        else:
            sinyal_yonu = "NOTR"
        
        # Hangi indikatöre ait?
        for indikator_key, (pattern, isim, aciklama) in INDIKATOR_PARSER.items():
            if re.search(pattern, parca, re.IGNORECASE):
                sonuc.append({
                    "indikator": indikator_key,
                    "indikator_isim": isim,
                    "sinyal": sinyal_yonu,
                    "ham_metin": parca[:120]
                })
                break
    
    return sonuc


def _veritabanindan_kapanan_islemleri_cek(son_gun: int = 90) -> pd.DataFrame:
    """
    Son N günde kapanan işlemleri veritabanından çeker.
    
    Algoritma:
    1. ai_sinyaller tablosuna bağlan
    2. durum 'BEKLIYOR' olmayanları filtrele
    3. Son N güne ait olanları al
    4. DataFrame olarak döndür
    
    Dönüş kolonları: id, tarih, hisse, sinyal_tipi, giris_fiyati, 
                      hedef_fiyat, stop_fiyat, durum, kapanis_fiyati
    """
    try:
        conn = sqlite3.connect(DB_YOLU)
        
        # Tablo var mı?
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'"
        )
        if not cursor.fetchone():
            conn.close()
            return pd.DataFrame()
        
        # Kapanan işlemleri çek
        son_tarih = (datetime.now() - timedelta(days=son_gun)).strftime("%Y-%m-%d")
        
        query = """
            SELECT * FROM ai_sinyaller 
            WHERE durum != 'BEKLIYOR' 
              AND tarih >= ?
            ORDER BY id DESC
        """
        df = pd.read_sql_query(query, conn, params=(son_tarih,))
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # Tarih kolonunu datetime'a çevir
        df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
        
        return df
        
    except Exception as e:
        _logger.warning(f"Veritabanı okunamadı: {e}")
        return pd.DataFrame()


def _sinyal_detaylarini_al(islem_id: int) -> str:
    """
    Belirli bir işlemin sinyal detay metnini veritabanından alır.
    
    NOT: Şu anki tablo yapısında sinyal_detay kolonu yok.
    Bu nedenle aynı hisse + yakın tarihteki tarama sonuçlarından 
    sinyal detayını yeniden oluşturmayı dener.
    
    Fallback: Eğer detay bulunamazsa None döner.
    """
    try:
        conn = sqlite3.connect(DB_YOLU)
        cursor = conn.cursor()
        
        # Önce direkt sinyal_detay kolonu var mı kontrol et
        cursor.execute("PRAGMA table_info(ai_sinyaller)")
        kolonlar = [row[1] for row in cursor.fetchall()]
        
        if 'sinyal_detay' in kolonlar:
            cursor.execute(
                "SELECT sinyal_detay FROM ai_sinyaller WHERE id = ?", 
                (islem_id,)
            )
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return str(row[0])
        
        conn.close()
        return None
        
    except Exception:
        return None


def _sinyal_detayi_yeniden_olustur(hisse_kodu: str, tarih: datetime) -> str:
    """
    Verilen hisse ve tarih için sinyal detayını yeniden hesaplar.
    Bu, eski işlemlerin detay metni olmadığında kullanılır.
    
    Algoritma:
    1. hisse için o tarihteki fiyat verisini çek
    2. analiz.sinyal_hesapla ile sinyal detayını oluştur
    3. detay metnini döndür
    """
    try:
        from analiz import sinyal_hesapla, rsi_serisi
        import yfinance as yf
        
        # O tarihten önceki 1 yıllık veriyi çek
        end_date = tarih + timedelta(days=1)
        start_date = end_date - timedelta(days=365)
        
        tk = yf.Ticker(hisse_kodu)
        df = tk.history(start=start_date.strftime('%Y-%m-%d'), 
                       end=end_date.strftime('%Y-%m-%d'))
        
        if df.empty or len(df) < 50:
            return None
        
        close = df['Close'].squeeze()
        son_fiyat = float(close.iloc[-1])
        rsi_val = round(float(rsi_serisi(close).iloc[-1]), 2)
        ma50_val = float(close.rolling(50).mean().iloc[-1])
        
        _, _, detay, _ = sinyal_hesapla(df, rsi_val, son_fiyat, ma50_val)
        return detay
        
    except Exception:
        return None


def kalite_raporu_olustur(son_gun: int = 90, min_islem: int = 5) -> dict:
    """
    SONUÇ: Her indikatörün AL sinyali verme sıklığı ve 
    bu sinyallerin başarı oranını hesaplayan ana fonksiyon.
    
    Algoritma Adımları:
    ┌──────────────────────────────────────────────────────────────┐
    │ 1. Son N günde kapanan tüm işlemleri DB'den çek            │
    │ 2. Her işlem için:                                         │
    │    a. Başarılı mı (BAŞARILI) yoksa başarısız mı?          │
    │    b. Sinyal detay metnini parse et                        │
    │    c. Hangi indikatörler AL sinyali vermiş?                │
    │ 3. İndikatör bazında istatistik hesapla:                   │
    │    - Toplam AL sinyali sayısı                              │
    │    - Başarılı işlemlerde bu indikatör kaç kez AL demiş?    │
    │    - Başarısız işlemlerde bu indikatör kaç kez AL demiş?   │
    │    - Win Rate = Başarılı / (Başarılı + Başarısız)         │
    │ 4. Win Rate < %40 → ZAYIF (devre dışı bırakma adayı)      │
    │ 5. Win Rate %40-55 → ORTA                                  │
    │ 6. Win Rate > %55 → GÜÇLÜ                                  │
    │ 7. Önceki raporla karşılaştır, 2 kez ZAYIF olanları       │
    │    otomatik devre dışı bırakılacaklar listesine ekle       │
    └──────────────────────────────────────────────────────────────┘
    
    Parametreler:
        son_gun: Kaç günlük işlem geçmişine bakılacak
        min_islem: Bir indikatörün değerlendirilmesi için min işlem sayısı
        
    Dönüş:
        {
            'rapor_tarihi': str,
            'toplam_islem': int,
            'basarili': int,
            'basarisiz': int,
            'genel_win_rate': float,
            'indikatorler': [
                {
                    'isim': str,
                    'toplam_al_sinyali': int,
                    'basarili_sinyal': int,
                    'basarisiz_sinyal': int,
                    'win_rate': float,
                    'kalite': 'GÜÇLÜ' | 'ORTA' | 'ZAYIF' | 'YETERSIZ',
                    'onceki_kalite': str,
                    'devre_disi': bool,
                    'aciklama': str
                },
                ...
            ],
            'ozet': str,
            'devre_disi_onerilen': [str, ...]
        }
    """
    # ── ADIM 1: Veritabanından kapanan işlemleri çek ──
    df = _veritabanindan_kapanan_islemleri_cek(son_gun)
    
    if df.empty:
        return {
            'rapor_tarihi': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'toplam_islem': 0,
            'basarili': 0,
            'basarisiz': 0,
            'genel_win_rate': 0.0,
            'indikatorler': [],
            'ozet': "📊 Henüz yeterli kapanmış işlem yok.",
            'devre_disi_onerilen': []
        }
    
    # ── ADIM 2: Her işlemin başarı durumunu ve sinyal detayını analiz et ──
    basarili_df = df[df['durum'].str.contains('BAŞARILI', na=False)]
    basarisiz_df = df[df['durum'].str.contains('BAŞARISIZ', na=False)]
    
    toplam_islem = len(df)
    basarili = len(basarili_df)
    basarisiz = len(basarisiz_df)
    genel_win_rate = round(basarili / max(basarili + basarisiz, 1) * 100, 1)
    
    # İndikatör bazında sayaçlar: {indikator_key: {'al_toplam': 0, 'al_basarili': 0, 'al_basarisiz': 0}}
    indikator_sayaclari = defaultdict(lambda: {'al_toplam': 0, 'al_basarili': 0, 'al_basarisiz': 0})
    
    # Tüm kapanan işlemleri tara
    for _, row in df.iterrows():
        islem_id = row['id']
        durum = str(row['durum'])
        hisse = str(row['hisse'])
        tarih_val = row['tarih']
        
        if pd.isna(tarih_val):
            continue
        
        # Tarihi datetime'a çevir
        if isinstance(tarih_val, str):
            try:
                tarih_val = datetime.strptime(tarih_val, "%Y-%m-%d %H:%M:%S")
            except:
                try:
                    tarih_val = datetime.strptime(tarih_val, "%Y-%m-%d")
                except:
                    continue
        
        # Sinyal detayını al veya yeniden oluştur
        detay_metni = _sinyal_detaylarini_al(islem_id)
        
        if not detay_metni:
            detay_metni = _sinyal_detayi_yeniden_olustur(hisse, tarih_val)
        
        if not detay_metni:
            continue
        
        # Detayı parse et
        indikator_sinyalleri = _sinyal_detayini_parse_et(detay_metni)
        
        # Başarılı mı başarısız mı?
        is_basarili = 'BAŞARILI' in durum
        
        # Her indikatör için sayacı güncelle
        for ind_sinyal in indikator_sinyalleri:
            ind_key = ind_sinyal['indikator']
            sinyal_yonu = ind_sinyal['sinyal']
            
            # Sadece AL sinyallerini say (SAT sinyalleri tersi durumda başarılı olabilir)
            if sinyal_yonu == "AL":
                indikator_sayaclari[ind_key]['al_toplam'] += 1
                if is_basarili:
                    indikator_sayaclari[ind_key]['al_basarili'] += 1
                else:
                    indikator_sayaclari[ind_key]['al_basarisiz'] += 1
    
    # ── ADIM 3: İndikatör kalite metriklerini hesapla ──
    indikator_raporlari = []
    
    for ind_key, sayac in sorted(indikator_sayaclari.items()):
        toplam_al = sayac['al_toplam']
        al_basarili = sayac['al_basarili']
        al_basarisiz = sayac['al_basarisiz']
        
        if toplam_al < min_islem:
            kalite = "YETERSIZ"
            win_rate = 0.0
        else:
            win_rate = round(al_basarili / toplam_al * 100, 1)
            
            if win_rate >= 55:
                kalite = "GÜÇLÜ"
            elif win_rate >= 40:
                kalite = "ORTA"
            else:
                kalite = "ZAYIF"
        
        # İndikatör açıklamasını bul
        ind_bilgi = INDIKATOR_PARSER.get(ind_key, (None, ind_key.replace('_', ' ').title(), ""))
        ind_isim = ind_bilgi[1] if len(ind_bilgi) > 1 else ind_key
        ind_aciklama = ind_bilgi[2] if len(ind_bilgi) > 2 else ""
        
        indikator_raporlari.append({
            'indikator_key': ind_key,
            'isim': ind_isim,
            'toplam_al_sinyali': toplam_al,
            'basarili_sinyal': al_basarili,
            'basarisiz_sinyal': al_basarisiz,
            'win_rate': win_rate,
            'kalite': kalite,
            'onceki_kalite': None,  # ADIM 7'de doldurulacak
            'devre_disi': False,
            'aciklama': ind_aciklama
        })
    
    # ── ADIM 4: Win Rate'e göre sırala ──
    indikator_raporlari.sort(key=lambda x: x['win_rate'], reverse=True)
    
    # ── ADIM 5-6: Önceki raporla karşılaştır, 2 kez ZAYIF olanları işaretle ──
    onceki_rapor = _onceki_raporu_yukle()
    devre_disi_onerilen = []
    
    for ind_rapor in indikator_raporlari:
        ind_key = ind_rapor['indikator_key']
        
        # Önceki raporda bu indikatör var mı?
        if onceki_rapor and 'indikatorler' in onceki_rapor:
            for prev in onceki_rapor['indikatorler']:
                if prev.get('indikator_key') == ind_key:
                    ind_rapor['onceki_kalite'] = prev.get('kalite', '?')
                    
                    # 2 ardışık ZAYIF → devre dışı öner
                    if prev.get('kalite') == 'ZAYIF' and ind_rapor['kalite'] == 'ZAYIF':
                        ind_rapor['devre_disi'] = True
                        devre_disi_onerilen.append(ind_key)
                    break
    
    # ── ADIM 7: Raporu JSON'a kaydet ──
    rapor = {
        'rapor_tarihi': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'toplam_islem': toplam_islem,
        'basarili': basarili,
        'basarisiz': basarisiz,
        'genel_win_rate': genel_win_rate,
        'indikatorler': indikator_raporlari,
        'ozet': _ozet_metni_olustur(indikator_raporlari, genel_win_rate, devre_disi_onerilen),
        'devre_disi_onerilen': devre_disi_onerilen
    }
    
    _raporu_kaydet(rapor)
    
    return rapor


def _onceki_raporu_yukle() -> dict:
    """Bir önceki kalite raporunu JSON'dan yükler."""
    try:
        if os.path.exists(KALITE_DOSYASI):
            with open(KALITE_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def _raporu_kaydet(rapor: dict):
    """Kalite raporunu JSON dosyasına kaydeder."""
    try:
        with open(KALITE_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(rapor, f, indent=2, ensure_ascii=False, default=str)
    except IOError as e:
        _logger.error(f"Rapor kaydedilemedi: {e}")


def _ozet_metni_olustur(indikatorler: list, genel_win_rate: float, 
                        devre_disi_onerilen: list) -> str:
    """
    İnsan tarafından okunabilir özet metni oluşturur.
    
    Örnek Çıktı:
    📊 SİNYAL KALİTE RAPORU
    Genel Win Rate: %52.3 (156 işlem)
    
    🟢 GÜÇLÜ İNDİKATÖRLER (Win Rate ≥ %55):
      • RSI: %68.2 (45/66 AL sinyali başarılı)
      • MACD: %61.5 (40/65)
      • Market Yapısı: %58.0 (29/50)
    
    🟡 ORTA İNDİKATÖRLER (Win Rate %40-55):
      • Bollinger: %48.3 (28/58)
      • ADX: %44.0 (22/50)
    
    🔴 ZAYIF İNDİKATÖRLER (Win Rate < %40):
      • Williams %R: %32.1 (9/28) ⚠️ DEVRE DIŞI ÖNERİLİR
      • NLP: %35.0 (7/20) ⚠️ DEVRE DIŞI ÖNERİLİR
    """
    gucluler = [i for i in indikatorler if i['kalite'] == 'GÜÇLÜ']
    ortalar = [i for i in indikatorler if i['kalite'] == 'ORTA']
    zayiflar = [i for i in indikatorler if i['kalite'] == 'ZAYIF']
    yetersizler = [i for i in indikatorler if i['kalite'] == 'YETERSIZ']
    
    satirlar = []
    satirlar.append("📊 SİNYAL KALİTE RAPORU")
    satirlar.append(f"Genel Win Rate: %{genel_win_rate:.1f} "
                   f"({sum(i['toplam_al_sinyali'] for i in indikatorler)} toplam AL sinyali)")
    satirlar.append("")
    
    if gucluler:
        satirlar.append("🟢 GÜÇLÜ İNDİKATÖRLER (Win Rate ≥ %55):")
        for i in gucluler:
            satirlar.append(
                f"  • {i['isim']}: %{i['win_rate']:.1f} "
                f"({i['basarili_sinyal']}/{i['toplam_al_sinyali']} AL sinyali başarılı)"
            )
        satirlar.append("")
    
    if ortalar:
        satirlar.append("🟡 ORTA İNDİKATÖRLER (Win Rate %40-55):")
        for i in ortalar:
            satirlar.append(
                f"  • {i['isim']}: %{i['win_rate']:.1f} "
                f"({i['basarili_sinyal']}/{i['toplam_al_sinyali']})"
            )
        satirlar.append("")
    
    if zayiflar:
        satirlar.append("🔴 ZAYIF İNDİKATÖRLER (Win Rate < %40):")
        for i in zayiflar:
            devre_disi_uyari = " ⚠️ DEVRE DIŞI ÖNERİLİR" if i['devre_disi'] else ""
            satirlar.append(
                f"  • {i['isim']}: %{i['win_rate']:.1f} "
                f"({i['basarili_sinyal']}/{i['toplam_al_sinyali']}){devre_disi_uyari}"
            )
        satirlar.append("")
    
    if yetersizler:
        satirlar.append("⚪ YETERSİZ VERİ (En az 5 işlem yok):")
        for i in yetersizler:
            satirlar.append(f"  • {i['isim']}: {i['toplam_al_sinyali']} işlem (analiz için yetersiz)")
        satirlar.append("")
    
    if devre_disi_onerilen:
        satirlar.append("─" * 50)
        satirlar.append("⚠️ OTOMATİK DEVRE DIŞI ÖNERİLEN İNDİKATÖRLER:")
        for key in devre_disi_onerilen:
            satirlar.append(f"  • {key} (2 ardışık raporda ZAYIF)")
        satirlar.append("Bu indikatörler bir sonraki taramada otomatik pasifleştirilecek.")
    
    return "\n".join(satirlar)


def devre_disi_indikatorleri_uygula() -> list:
    """
    Kalite raporuna göre ZAYIF indikatörleri otomatik devre dışı bırakır.
    
    Algoritma:
    1. Son kalite raporunu yükle
    2. devre_disi_onerilen listesini al
    3. sinyal_hesapla'da bu indikatörlerin puanlamasını atla
    4. Aktif/pasif indikatör listesini döndür
    
    Dönüş: Devre dışı bırakılan indikatörlerin listesi
    """
    rapor = _onceki_raporu_yukle()
    if not rapor:
        return []
    
    devre_disi = rapor.get('devre_disi_onerilen', [])
    
    if devre_disi:
        _logger.info(f"  🔧 Devre dışı bırakılan indikatörler: {devre_disi}")
        
        # Aktif indikatörleri JSON'a kaydet (analiz.py'nin okuyacağı)
        aktifler = [k for k in INDIKATOR_PARSER.keys() if k not in devre_disi]
        aktif_dosyasi = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "aktif_indikatorler.json"
        )
        try:
            with open(aktif_dosyasi, "w", encoding="utf-8") as f:
                json.dump({
                    'aktif_indikatorler': aktifler,
                    'devre_disi': devre_disi,
                    'guncelleme_tarihi': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, f, indent=2, ensure_ascii=False)
        except IOError:
            pass
    
    return devre_disi


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  SİNYAL KALİTE TAKİP MOTORU TEST")
    print("=" * 60)
    
    rapor = kalite_raporu_olustur(son_gun=90)
    
    print(f"\nRapor Tarihi: {rapor['rapor_tarihi']}")
    print(f"Toplam İşlem: {rapor['toplam_islem']}")
    print(f"Genel Win Rate: %{rapor['genel_win_rate']:.1f}")
    print()
    print(rapor['ozet'])
    
    if rapor['devre_disi_onerilen']:
        print(f"\nDevre dışı önerilenler: {rapor['devre_disi_onerilen']}")
        onay = input("\nOtomatik devre dışı bırakılsın mı? (e/h): ").strip().lower()
        if onay in ['e', 'evet', 'y', 'yes']:
            devre_disi = devre_disi_indikatorleri_uygula()
            print(f"✅ {len(devre_disi)} indikatör devre dışı bırakıldı.")