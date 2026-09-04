import os
import sqlite3
import pandas as pd
import requests
from datetime import datetime

# Mevcut analiz algoritmalarınızı ve listelerinizi içe aktarıyoruz
from analiz import tum_hisseleri_tara
from hisseler_bist import BIST
from hisseler_kripto import KRIPTO_LISTESI

# ── TELEGRAM GÜVENLİK ANAHTARLARI ──
# Token'ları asla koda yazmıyoruz, GitHub Secrets üzerinden güvenle çekeceğiz.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def telegram_mesaj_gonder(mesaj):
    """Telegram botu üzerinden anlık bildirim atar."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram anahtarları bulunamadı, mesaj gönderilemedi.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram Hatası: {e}")

# ── STREAMLIT KUKLALARI (DUMMY) ──
# Arka planda Streamlit çalışmayacağı için, analiz fonksiyonunun hata vermemesi 
# adına progress_bar ve text_box yerine geçecek sahte sınıflar üretiyoruz.
class DummyUI:
    def progress(self, val): pass
    def text(self, val): print(val)
    def empty(self): pass

def oto_tarama_baslat():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Otomatik tarama başlatılıyor...")
    
    ui_kukla = DummyUI()
    
    # 1. Piyasayı Tara (Örnek olarak sadece BIST, isterseniz Kripto da eklenir)
    sonuclar = tum_hisseleri_tara(BIST, "1mo", ui_kukla, ui_kukla, max_workers=4)
    
    if not sonuclar:
        print("Veri çekilemedi, tarama iptal.")
        return

    df = pd.DataFrame(sonuclar)
    if "Degisim %" in df.columns:
        df.rename(columns={"Degisim %": "Değişim %"}, inplace=True)
        
    # 2. Telegram Bildirimlerini Kontrol Et
    guclu_allar = df[df["Sinyal"] == "GÜÇLÜ AL"]
    
    for _, row in guclu_allar.iterrows():
        msj = (
            f"🚀 *GÜÇLÜ AL SİNYALİ*\n\n"
            f"📊 *Hisse:* {row['Hisse']}\n"
            f"💰 *Fiyat:* {row['Son Fiyat']} (Değişim: %{row['Değişim %']})\n"
            f"📈 *RSI:* {row['RSI']} | *MACD:* {row['MACD Sinyal']}\n"
            f"⚙️ *Detay:* {row['Sinyal Detay']}"
        )
        telegram_mesaj_gonder(msj)
        
    # 3. Sonuçları Veritabanına (SQLite) Kaydet
    # Bulut sunucu bu DB dosyasını güncelleyip GitHub'a geri pushlayacak.
    db_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hafiza.db")
    conn = sqlite3.connect(db_yolu)
    df.to_sql("oto_tarama_sonuclari", conn, if_exists="replace", index=False)
    conn.close()
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Tarama tamamlandı. {len(guclu_allar)} adet Güçlü Al bulundu.")

if __name__ == "__main__":
    oto_tarama_baslat()