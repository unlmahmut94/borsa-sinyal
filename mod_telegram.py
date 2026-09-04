import requests
import os

# Güvenlik: Bilgiler artık .env dosyasından okunur
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv yoksa ortam değişkenlerinden okumayı dene

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def telegram_mesaj_gonder(mesaj):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False, "Telegram yapılandırılmamış (.env eksik)"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML"
    }

    try:
        # Bağlantı hatalarını önlemek için session kullanıyoruz
        session = requests.Session()
        session.trust_env = False 
        
        response = session.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, "Mesaj başarıyla iletildi."
        else:
            return False, f"Telegram reddetti. Hata kodu: {response.status_code}"
            
    except Exception as e:
        return False, f"Bağlantı hatası: {str(e)}"