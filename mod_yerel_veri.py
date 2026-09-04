# mod_yerel_veri.py
import sqlite3
import pandas as pd
import yfinance as yf
import os
from datetime import datetime, timedelta

DB_FIYAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fiyat_hafiza.db")

def fiyat_veritabanini_kur():
    """Hisse fiyatları için yerel veritabanını oluşturur."""
    conn = sqlite3.connect(DB_FIYAT)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute('''CREATE TABLE IF NOT EXISTS ohlcv (
                    sembol TEXT,
                    tarih TEXT,
                    acilis REAL,
                    yuksek REAL,
                    dusuk REAL,
                    kapanis REAL,
                    hacim REAL,
                    PRIMARY KEY (sembol, tarih))''')
    conn.close()

def yerel_veriyi_getir_ve_guncelle(sembol: str, limit_gun: int = 90) -> pd.DataFrame:
    """
    Sistemin asıl hızlandığı yer:
    Eğer veri varsa sadece eksik olan günleri (Delta) yfinance'den çeker,
    DB'ye ekler ve tüm seti hızlıca (milisaniyeler içinde) pandas DataFrame olarak döner.
    """
    fiyat_veritabanini_kur()
    conn = sqlite3.connect(DB_FIYAT)
    
    # 1. DB'den bu hissenin son kayıt tarihini bul
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(tarih) FROM ohlcv WHERE sembol=?", (sembol,))
    son_tarih_str = cursor.fetchone()[0]
    
    bugun = datetime.now()
    veri_indirilecek = False
    baslangic_tarihi = None

    if not son_tarih_str:
        # Hissede hiç veri yoksa son 90 günü indir
        veri_indirilecek = True
        baslangic_tarihi = (bugun - timedelta(days=limit_gun)).strftime("%Y-%m-%d")
    else:
        # Veri var, sadece son tarihten bugüne kadar olan kısmı (Delta) indir
        son_tarih = datetime.strptime(son_tarih_str[:10], "%Y-%m-%d")
        if (bugun - son_tarih).days >= 1:
            veri_indirilecek = True
            # Güvence için son 3 günü çekip üzerine yazdırıyoruz (düzeltmeler için)
            baslangic_tarihi = (bugun - timedelta(days=3)).strftime("%Y-%m-%d")

    # 2. Eğer eksik veri varsa yfinance'den sadece o küçük kısmı çek ve DB'ye ekle
    if veri_indirilecek:
        try:
            df_yeni = yf.download(sembol, start=baslangic_tarihi, progress=False)
            if not df_yeni.empty:
                if isinstance(df_yeni.columns, pd.MultiIndex):
                    df_yeni.columns = df_yeni.columns.get_level_values(0)
                
                # SQLite'a kaydet (var olan tarihleri atlar/günceller)
                for index, row in df_yeni.iterrows():
                    cursor.execute('''INSERT OR REPLACE INTO ohlcv 
                                      (sembol, tarih, acilis, yuksek, dusuk, kapanis, hacim)
                                      VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                   (sembol, str(index), row['Open'], row['High'], row['Low'], row['Close'], row.get('Volume', 0)))
                conn.commit()
        except Exception as e:
            print(f"Delta güncelleme hatası ({sembol}): {e}")

    # 3. Tüm veriyi yerel SSD/NVMe hızında (SQLite'tan) çek ve Modele ver
    df_tamami = pd.read_sql_query(
        "SELECT tarih, acilis as Open, yuksek as High, dusuk as Low, kapanis as Close, hacim as Volume FROM ohlcv WHERE sembol=? ORDER BY tarih ASC", 
        conn, params=(sembol,), index_col="tarih"
    )
    conn.close()
    
    # Tarih indeksini pandas formatına çevir
    if not df_tamami.empty:
        df_tamami.index = pd.to_datetime(df_tamami.index)
        
    return df_tamami