"""
╔══════════════════════════════════════════════╗
║   BORSA SİNYAL SİSTEMİ — ML Destekli CLI ║
╚══════════════════════════════════════════════╝

Kullanım:
    python main.py                                    → interaktif menü
    python main.py --symbol THYAO.IS                  → tek hisse analizi
    python main.py --symbol AAPL --hedef 5             → 5 günlük tahmin
    python main.py --auto                              → toplu tarama başlat
    python main.py --surekli                           → sürekli tarama motoru
    python main.py --backtest THYAO.IS                 → strateji testi
    python main.py --sinyaller                         → son sinyalleri listele
    python main.py --egitim-baslat                     → ML eğitim motoru başlat
"""

import argparse
import time
import sys
import os
import json

# Proje kök dizinini Python yoluna ekle
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ── Renk kodları ──────────────────────────────────────────────────────────────
G   = "\033[92m"
R   = "\033[91m"
Y   = "\033[93m"
B   = "\033[94m"
W   = "\033[97m"
C   = "\033[96m"
BLD = "\033[1m"
DIM = "\033[2m"
RST = "\033[0m"


def clr(text, color=W):
    return f"{color}{BLD}{text}{RST}"


def banner():
    print(f"""
{B}{'='*56}
  ██████╗  ██████╗ ██████╗ ███████╗ █████╗
  ██╔══██╗██╔═══██╗██╔══██╗██╔════╝██╔══██╗
  ██████╔╝██║   ██║██████╔╝███████╗███████║
  ██╔══██╗██║   ██║██╔══██╗╚════██║██╔══██║
  ██████╔╝╚██████╔╝██║  ██║███████║██║  ██║
  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
  SİNYAL SİSTEMİ  ·  ML Destekli Terminal v3.1
{'='*56}{RST}\n""")



def _guncel_fiyat_cek(symbol: str) -> float:
    """Bir sembol için güncel fiyat çeker, başarısız olursa 0 döner."""
    try:
        from mod_veri_kaynagi import canli_fiyat_cek
        sonuc = canli_fiyat_cek(symbol)
        if sonuc and sonuc.get('fiyat'):
            return float(sonuc['fiyat'])
    except Exception:
        pass

    try:
        import yfinance as yf
        h = yf.Ticker(symbol).history(period="2d")
        if not h.empty and len(h) >= 1:
            return float(h["Close"].iloc[-1])
    except Exception:
        pass

    return 0.0


def tek_hisse_analiz_et(symbol: str, hedef_gun: int = 5):
    """Tek hisse için ML analizi yap ve sonuçları yazdır."""
    print(f"\n{clr(f'► {symbol}', B)}")
    print(f"  Analiz yapılıyor...", end=" ", flush=True)

    fiyat = _guncel_fiyat_cek(symbol)

    try:
        from mod_yapay_zeka import yapay_zeka_tahmin_et
        sonuc, mesaj = yapay_zeka_tahmin_et(symbol, hedef_gun=hedef_gun)

        if sonuc is None:
            print(f"\n  {clr(f'✗ Hata: {mesaj}', R)}")
            return

        guncel = sonuc.get('Guncel_Fiyat', fiyat)

        print(f"\r  {clr('✓ Analiz Tamamlandı', G)}")
        print(f"\n  {clr('╔══════════════════════════════════╗', C)}")
        print(f"  {clr('║        ML ANALİZ SONUCU         ║', C)}")
        print(f"  {clr('╚══════════════════════════════════╝', C)}")
        print(f"  Sembol        : {symbol}")
        print(f"  Güncel Fiyat  : {guncel:.4f}" if guncel > 0 else f"  Güncel Fiyat  : {fiyat:.4f}")
        print(f"  Tahmini Fiyat : {sonuc['Tahmini_Fiyat']:.4f}")
        print(f"  Fiyat Aralığı : {sonuc['Fiyat_Alt_Bant']:.4f} - {sonuc['Fiyat_Ust_Bant']:.4f}")
        print(f"  Karar         : {clr(sonuc['Karar'], G if 'YÜKSELİŞ' in sonuc['Karar'] else R)}")
        print(f"  Olasılık      : %{sonuc['Olasilik']:.1f}")
        print(f"  Geçmiş Başarı : %{sonuc['Gecmis_Basari']:.1f}")

        if sonuc.get('Kelly_Pozisyon'):
            print(f"  Kelly Pozisyon: %{sonuc['Kelly_Pozisyon']:.1f}")
        if sonuc.get('Piyasa_Rejimi'):
            print(f"  Piyasa Rejimi : {sonuc['Piyasa_Rejimi']}")
        if sonuc.get('Guven_Seviyesi'):
            renk = G if sonuc['Guven_Seviyesi'] == 'YÜKSEK' else (Y if sonuc['Guven_Seviyesi'] == 'ORTA' else R)
            print(f"  Güven Seviyesi: {clr(sonuc['Guven_Seviyesi'], renk)}")

        # Etkenler tablosu
        if sonuc.get('Etkenler') is not None and not sonuc['Etkenler'].empty:
            print(f"\n  {clr('Etken Faktörler:', C)}")
            for _, row in sonuc['Etkenler'].head(5).iterrows():
                bar = '█' * int(row['Önem'] / 5)
                print(f"    {row['Faktör']:<20s} {bar} %{row['Önem']:.1f}")

    except Exception as e:
        print(f"\n  {clr(f'✗ Analiz hatası: {e}', R)}")


def sinyalleri_listele(n: int = 10, symbol: str = None):
    """Veritabanındaki son sinyalleri listeler."""
    import sqlite3

    db_yolu = os.path.join(ROOT, "ai_hafiza.db")
    try:
        conn = sqlite3.connect(db_yolu)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_sinyaller'"
        )
        if not cursor.fetchone():
            print(f"\n  {clr('Henüz kayıtlı sinyal yok.', Y)}")
            conn.close()
            return

        if symbol:
            cursor.execute(
                "SELECT * FROM ai_sinyaller WHERE hisse=? ORDER BY id DESC LIMIT ?",
                (symbol.upper(), n)
            )
        else:
            cursor.execute(
                "SELECT * FROM ai_sinyaller ORDER BY id DESC LIMIT ?", (n,)
            )

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print(f"\n  {clr('Kayıt bulunamadı.', Y)}")
            return

        print(f"\n  {clr(f'SON {len(rows)} SİNYAL', C)}")
        print(f"  {'─' * 90}")
        print(f"  {'Tarih':<20s} {'Hisse':<14s} {'Sinyal':<19s} {'Giriş':>10s} {'Hedef':>10s} {'Durum':<16s}")
        print(f"  {'─' * 90}")

        for row in rows:
            tarih, hisse, sinyal_tipi, giris_f, hedef_f, stop_f, durum, kapanis_f = row
            durum_color = (G if 'BAŞARILI' in str(durum) else
                           R if 'BAŞARISIZ' in str(durum) else
                           Y if 'BEKLİYOR' in str(durum) else W)
            print(
                f"  {str(tarih):<20s} {str(hisse):<14s} "
                f"{clr(str(sinyal_tipi)[:18], G if 'AL' in str(sinyal_tipi) else R):<19s}"
                f" {str(giris_f):>10s} {str(hedef_f):>10s} "
                f"{clr(str(durum), durum_color):<16s}"
            )

    except Exception as e:
        print(f"\n  {clr(f'Sinyal listeleme hatası: {e}', R)}")


def toplu_tarama_baslat(borsalar: list = None):
    """Tüm hisseleri tarar ve GÜÇLÜ AL sinyallerini kaydeder."""
    from analiz import tum_hisseleri_tara
    from hisseler_bist import BIST
    from hisseler_sp500 import SP500
    from hisseler_nasdaq import NASDAQ
    from mod_hafiza import sinyal_kaydet, bekleyenleri_kontrol_et

    if borsalar is None:
        borsalar = ["BIST"]

    tarama_listesi = []
    if "BIST" in borsalar:
        tarama_listesi.extend(BIST)
    if "SP500" in borsalar:
        tarama_listesi.extend(SP500)
    if "NASDAQ" in borsalar:
        tarama_listesi.extend(NASDAQ)

    tarama_listesi = list(dict.fromkeys(tarama_listesi))

    # Ölü havuz filtrelemesi
    try:
        from mod_veri_kaynagi import dead_listeyi_temizle, dead_liste_yukle
        dead_set = dead_liste_yukle()
        if dead_set:
            print(f"  💀 {len(dead_set)} ölü/delisted hisse filtrelendi")
        tarama_listesi = dead_listeyi_temizle(tarama_listesi)
    except ImportError:
        pass

    print(f"\n  {clr(f'◈ TOPLU TARAMA BAŞLATILDI ◈', B)}")
    print(f"  Toplam Hisse : {len(tarama_listesi)}")
    print(f"  Borsalar     : {', '.join(borsalar)}")
    print(f"  {'─' * 50}")

    class CLI_Progress:
        def progress(self, val):
            bar_len = 30
            filled = int(bar_len * val)
            bar_str = '█' * filled + '░' * (bar_len - filled)
            print(f"\r  [{bar_str}] %{int(val * 100):3d}", end="", flush=True)

        def text(self, msg):
            pass  # CLI'da durum metni göstermiyoruz

    progress_bar = CLI_Progress()
    durum = CLI_Progress()

    sonuclar = tum_hisseleri_tara(tarama_listesi, "1mo", progress_bar, durum)
    print()  # progress bar sonrası satır başı

    if not sonuclar:
        print(f"\n  {clr('Hiç sonuç bulunamadı.', Y)}")
        return

    guclu_al_sayisi = 0
    for row in sonuclar:
        sinyal = str(row.get('Sinyal', ''))
        if "GUCLU AL" in sinyal:
            hisse = row['Hisse']
            fiyat = row['Son Fiyat']

            # Hedef/stop hesapla
            from otomatik_tarayici import piyasa_tipine_gore_esikler
            hedef_yuzde, piyasa_tipi = piyasa_tipine_gore_esikler(hisse)
            # stop_yuzde: piyasa tipine gore dinamik (BIST %5, kripto %7, diger %5)
            stop_yuzde = 0.07 if piyasa_tipi == "kripto" else 0.05
            hedef_fiyat = round(fiyat * (1 + hedef_yuzde), 2)
            stop_fiyat = round(fiyat * (1 - stop_yuzde), 2)

            try:
                sinyal_kaydet(hisse, "GUCLU AL", fiyat, hedef_fiyat, stop_fiyat)
                guclu_al_sayisi += 1
            except Exception:
                pass

    print(f"\n  {clr('✓ Tarama Tamamlandı!', G)}")
    print(f"  Analiz Edilen : {len(sonuclar)} hisse")
    print(f"  GÜÇLÜ AL      : {guclu_al_sayisi} yeni fırsat")

    # Bekleyenleri kontrol et
    bekleyenleri_kontrol_et()


def backtest_calistir(symbol: str, gun: int = 365):
    """Seçilen hisse için strateji testi yapar."""
    print(f"\n  {clr(f'► {symbol} Backtest', B)}")
    print(f"  Test yapılıyor...", end=" ", flush=True)

    try:
        from backtest import backtest_calistir as bt_run
        sonuc = bt_run(symbol, periyot_gun=gun)

        if sonuc is None:
            print(f"\n  {clr('✗ Yetersiz veri veya hata.', R)}")
            return

        print(f"\r  {clr('✓ Test Tamamlandı', G)}")
        print(f"\n  {clr('╔══════════════════════════════════╗', C)}")
        print(f"  {clr('║         BACKTEST SONUCU          ║', C)}")
        print(f"  {clr('╚══════════════════════════════════╝', C)}")
        print(f"  Başlangıç     : ₺{sonuc['Baslangic']:,}")
        print(f"  Final Bakiye  : ₺{sonuc['Final']:,}")
        renk = G if sonuc['Getiri %'] >= 0 else R
        getiri_degeri = sonuc.get('Getiri %', 0)
        print(f"  Net Getiri    : {clr(f'%{getiri_degeri}', renk)}")
        print(f"  Win Rate      : %{sonuc['Win Rate %']}")
        print(f"  Max Drawdown  : %{sonuc['Max Drawdown %']}")
        print(f"  İflas İhtimali: %{sonuc['İflas İhtimali %']}")
        print(f"  Kelly Kriteri : %{sonuc['Kelly Kriteri %']}")

        # İşlem özeti
        islemler = sonuc.get('Islemler')
        if islemler is not None and not islemler.empty:
            al_sayisi = len(islemler[islemler['İşlem'].str.contains('AL', na=False)])
            sat_sayisi = len(islemler[~islemler['İşlem'].str.contains('AL', na=False)])
            print(f"\n  İşlem Sayısı  : {len(islemler)} ({al_sayisi} AL, {sat_sayisi} SAT)")

    except Exception as e:
        print(f"\n  {clr(f'✗ Backtest hatası: {e}', R)}")


def egitim_baslat(tip: str = "eski"):
    """Arka planda ML eğitim motorunu başlatır."""
    try:
        from mod_egitim_kontrol import eski_sistemi_arka_planda_baslat, agir_egitimi_arka_planda_baslat

        if tip == "akilli":
            ok, msg = agir_egitimi_arka_planda_baslat()
        else:
            ok, msg = eski_sistemi_arka_planda_baslat()

        if ok:
            print(f"\n  {clr('✓ ' + msg, G)}")
        else:
            print(f"\n  {clr('✗ ' + msg, R)}")

    except Exception as e:
        print(f"\n  {clr(f'✗ Eğitim başlatılamadı: {e}', R)}")


def surekli_tarama_baslat():
    """Sürekli tarama motorunu başlatır."""
    print(f"\n  {clr('◈ SÜREKLİ TARAMA MOTORU BAŞLATILIYOR...', B)}")
    print(f"  {DIM}CTRL+C ile durdurabilirsiniz.{RST}\n")

    try:
        from otomatik_tarayici import surekli_tarama_dongusu
        surekli_tarama_dongusu()
    except KeyboardInterrupt:
        print(f"\n  {clr('◈ Tarama durduruldu.', Y)}")
    except Exception as e:
        print(f"\n  {clr(f'✗ Sürekli tarama hatası: {e}', R)}")


# ── İnteraktif menü ───────────────────────────────────────────────────────────

def interactive_menu():
    banner()
    while True:
        print(f"""
{clr('ANA MENÜ', B)}
  1. Tek hisse/coin analiz et (ML)
  2. Toplu piyasa tara (GÜÇLÜ AL fırsatları)
  3. Son sinyalleri görüntüle
  4. Backtest (strateji testi)
  5. ML eğitim motoru başlat
  6. Sürekli tarama motoru başlat
  0. Çıkış
""")
        choice = input("  Seçiminiz: ").strip()

        if choice == "1":
            sym = input("  Sembol (örn: THYAO.IS, AAPL, BTC-USD): ").strip().upper()
            if not sym:
                print(f"  {clr('Sembol girilmedi.', R)}")
                continue
            hedef_str = input("  Tahmin günü [varsayılan: 5]: ").strip()
            hedef = int(hedef_str) if hedef_str.isdigit() else 5
            tek_hisse_analiz_et(sym, hedef)

        elif choice == "2":
            print(f"\n  Piyasa seçin (virgülle ayırın):")
            print(f"  1 = BIST  2 = S&P 500  3 = NASDAQ  4 = Hepsi")
            piyasa_str = input("  Seçim [1]: ").strip() or "1"
            borsa_map = {
                "1": ["BIST"], "2": ["SP500"], "3": ["NASDAQ"],
                "4": ["BIST", "SP500", "NASDAQ"]
            }
            borsalar = borsa_map.get(piyasa_str, ["BIST"])
            toplu_tarama_baslat(borsalar)

        elif choice == "3":
            n_str = input("  Kaç kayıt? [10]: ").strip() or "10"
            sym = input("  Sembol filtresi (boş=hepsi): ").strip().upper() or None
            sinyalleri_listele(int(n_str), sym)

        elif choice == "4":
            sym = input("  Sembol (örn: THYAO.IS, AAPL): ").strip().upper()
            if not sym:
                print(f"  {clr('Sembol girilmedi.', R)}")
                continue
            gun_str = input("  Test periyodu (gün) [365]: ").strip() or "365"
            backtest_calistir(sym, int(gun_str))

        elif choice == "5":
            print(f"\n  Eğitim tipi:")
            print(f"  1 = Eski sistem (her gün 22:00'de)")
            print(f"  2 = Sürekli akıllı eğitim (şimdi başla)")
            tip_str = input("  Seçim [1]: ").strip() or "1"
            tip = "akilli" if tip_str == "2" else "eski"
            egitim_baslat(tip)

        elif choice == "6":
            onay = input(f"  {clr('Sürekli tarama başlatılsın mı? (e/h): ', Y)}").strip().lower()
            if onay in ["e", "evet", "y", "yes"]:
                surekli_tarama_baslat()

        elif choice == "0":
            print(f"\n  {clr('Görüşürüz!', G)}\n")
            break
        else:
            print(f"  {clr('Geçersiz seçim.', R)}")

        input(f"\n  {DIM}Devam etmek için ENTER...{RST}")


# ── CLI giriş noktası ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Borsa Sinyal Sistemi — ML Destekli Terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python main.py                                          # İnteraktif menü
  python main.py --symbol THYAO.IS                        # THY analizi
  python main.py --symbol AAPL --hedef 10                 # 10 günlük tahmin
  python main.py --auto --borsa BIST                      # BIST toplu tarama
  python main.py --surekli                                # Sürekli tarama
  python main.py --sinyaller                              # Son 10 sinyal
  python main.py --sinyaller --adet 20 --filtre GARAN     # GARAN sinyalleri
  python main.py --backtest THYAO.IS --gun 180            # 6 aylık test
  python main.py --egitim-baslat                          # Eski sistem eğitimi
  python main.py --egitim-baslat --tip akilli             # Akıllı eğitim
        """
    )

    parser.add_argument("--symbol", help="Sembol (örn: THYAO.IS, AAPL, BTC-USD)")
    parser.add_argument("--hedef", type=int, default=5, help="Tahmin günü (varsayılan: 5)")
    parser.add_argument("--auto", action="store_true", help="Toplu tarama başlat")
    parser.add_argument("--borsa", default="BIST", help="Borsa filtresi: BIST,SP500,NASDAQ (virgülle)")
    parser.add_argument("--surekli", action="store_true", help="Sürekli tarama motoru")
    parser.add_argument("--sinyaller", action="store_true", help="Son sinyalleri listele")
    parser.add_argument("--adet", type=int, default=10, help="Listelenecek sinyal sayısı")
    parser.add_argument("--filtre", help="Sinyal sembol filtresi")
    parser.add_argument("--backtest", help="Backtest yapılacak hisse")
    parser.add_argument("--gun", type=int, default=365, help="Backtest periyodu (gün)")
    parser.add_argument("--egitim-baslat", action="store_true", help="ML eğitim motoru başlat")
    parser.add_argument("--tip", default="eski", choices=["eski", "akilli"],
                        help="Eğitim tipi: eski (22:00) / akilli (şimdi)")

    args = parser.parse_args()

    # ── Komut satırı argümanlarına göre yönlendirme ──
    if args.symbol:
        banner()
        tek_hisse_analiz_et(args.symbol.upper(), args.hedef)

    elif args.auto:
        banner()
        borsalar = [b.strip().upper() for b in args.borsa.split(",")]
        borsalar = [b if b != "SP500" else "SP500" for b in borsalar]
        toplu_tarama_baslat(borsalar)

    elif args.surekli:
        banner()
        surekli_tarama_baslat()

    elif args.sinyaller:
        banner()
        sinyalleri_listele(args.adet, args.filtre)

    elif args.backtest:
        banner()
        backtest_calistir(args.backtest.upper(), args.gun)

    elif args.egitim_baslat:
        banner()
        egitim_baslat(args.tip)

    else:
        interactive_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n  {clr('Program durduruldu.', Y)}\n")
    except Exception as e:
        print(f"\n  {clr(f'Kritik hata: {e}', R)}\n")