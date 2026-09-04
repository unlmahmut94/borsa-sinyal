# ══════════════════════════════════════════════════════════════════════
#  backtest.py — Gelişmiş Strateji Test Motoru v3.1
#  Metrikler: Sharpe, Sortino, Max Drawdown, Calmar, Benchmark
#  Gerçekçi: Komisyon, Slippage, İşlem Maliyeti
# ══════════════════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
import yfinance as yf
import datetime
import json
import os
from analiz import rsi_serisi

CONFIG_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strateji_config.json")


def _strateji_ayarlari() -> dict:
    """Konfigürasyon dosyasından tüm strateji parametrelerini yükler."""
    varsayilan = {
        "stop_loss_yuzde": 0.03,
        "take_profit_yuzde": 0.08,
        "rsi_al_esigi": 30,
        "komisyon_orani": 0.002,
        "slippage_yuzde": 0.001,
        "backtest_varsayilan_sermaye": 10000,
        "backtest_varsayilan_gun": 365,
        "backtest_monte_carlo_simulasyon": 1000,
        "rsi_periyot": 14,
        "adx_esik": 25,
        "atr_stop_carpani": 1.5,
        "bb_std_carpan": 2.0,
        "max_paralel_islem": 5,
    }
    try:
        if os.path.exists(CONFIG_YOLU):
            with open(CONFIG_YOLU, "r", encoding="utf-8") as f:
                kayitli = json.load(f)
            return {**varsayilan, **kayitli}
    except (json.JSONDecodeError, IOError):
        pass
    return varsayilan


def _sharpe_orani(getiriler: list, risksiz_oran: float = 0.05) -> float:
    """
    Sharpe Oranı hesaplar.
    Sharpe = (Ortalama Getiri - Risksiz Oran) / Getiri Std Sapması
    
    Yıllıklandırılmış değer döndürür.
    """
    if not getiriler or len(getiriler) < 2:
        return 0.0
    getiri_arr = np.array(getiriler, dtype=float)
    ort_getiri = np.mean(getiri_arr)
    std_getiri = np.std(getiri_arr, ddof=1)
    if std_getiri == 0:
        return 0.0
    # Günlük Sharpe'ı yıllıklandır (252 işlem günü)
    gunluk_sharpe = (ort_getiri - risksiz_oran / 252) / std_getiri
    return round(gunluk_sharpe * np.sqrt(252), 3)


def _sortino_orani(getiriler: list, risksiz_oran: float = 0.05) -> float:
    """
    Sortino Oranı hesaplar.
    Sortino = (Ortalama Getiri - Risksiz Oran) / Negatif Getiri Std Sapması
    Sadece aşağı yönlü riski cezalandırır.
    """
    if not getiriler or len(getiriler) < 2:
        return 0.0
    getiri_arr = np.array(getiriler, dtype=float)
    ort_getiri = np.mean(getiri_arr)
    negatif_getiriler = getiri_arr[getiri_arr < 0]
    if len(negatif_getiriler) < 2:
        return 999.0 if ort_getiri > 0 else 0.0  # Hiç kayıp yoksa mükemmel
    down_std = np.std(negatif_getiriler, ddof=1)
    if down_std == 0:
        return 999.0 if ort_getiri > 0 else 0.0
    gunluk_sortino = (ort_getiri - risksiz_oran / 252) / down_std
    return round(gunluk_sortino * np.sqrt(252), 3)


def _calmar_orani(getiri_yuzde: float, max_drawdown: float) -> float:
    """
    Calmar Oranı hesaplar.
    Calmar = Yıllık Getiri % / Max Drawdown %
    """
    if max_drawdown == 0:
        return 999.0 if getiri_yuzde > 0 else 0.0
    return round(abs(getiri_yuzde / max_drawdown), 3)


def _max_drawdown_hesapla(bakiye_serisi: list) -> tuple:
    """
    Maksimum Drawdown ve süresini hesaplar.
    Dönüş: (max_dd_yuzde, max_dd_gun)
    """
    if not bakiye_serisi:
        return 0.0, 0
    
    seri = pd.Series(bakiye_serisi)
    cummax = seri.cummax()
    drawdown = (seri - cummax) / cummax * 100
    max_dd = abs(float(drawdown.min())) if not drawdown.empty else 0.0
    
    # En uzun drawdown süresi (gün)
    su_an_dd_suresi = 0
    max_dd_suresi = 0
    for dd_val in drawdown:
        if dd_val < 0:
            su_an_dd_suresi += 1
            max_dd_suresi = max(max_dd_suresi, su_an_dd_suresi)
        else:
            su_an_dd_suresi = 0
    
    return round(max_dd, 2), max_dd_suresi


def monte_carlo_simulasyonu(getiriler: list, baslangic_sermayesi: float, 
                            simulasyon_sayisi: int = 1000) -> dict:
    """
    Monte Carlo simülasyonu ile risk metriklerini hesaplar.
    Dönüş: {'Max_DD': float, 'Iflas': float, 'VaR_95': float, 'CVaR_95': float}
    """
    if len(getiriler) < 5:
        return {"Max_DD": 0.0, "Iflas": 0.0, "VaR_95": 0.0, "CVaR_95": 0.0}
    
    getiri_arr = np.array(getiriler, dtype=float)
    max_dd_list = []
    iflas_sayaci = 0
    final_bakiyeler = []
    
    for _ in range(simulasyon_sayisi):
        r_getiri = np.random.choice(getiri_arr, size=len(getiri_arr), replace=True)
        egri = [baslangic_sermayesi]
        for g in r_getiri:
            egri.append(egri[-1] * (1 + g))
        seri = pd.Series(egri)
        
        # Max DD
        dd = ((seri - seri.cummax()) / seri.cummax()) * 100
        max_dd_list.append(abs(float(dd.min())) if not dd.empty else 0.0)
        
        # İflas (sermayenin %50'sinden fazlasını kaybetme)
        if seri.min() <= baslangic_sermayesi * 0.5:
            iflas_sayaci += 1
        
        final_bakiyeler.append(seri.iloc[-1])
    
    # VaR %95 (Value at Risk)
    final_getiriler = [(f - baslangic_sermayesi) / baslangic_sermayesi * 100 for f in final_bakiyeler]
    var_95 = abs(np.percentile(final_getiriler, 5))
    
    # CVaR %95 (Conditional VaR)
    tail_losses = [g for g in final_getiriler if g <= -var_95]
    cvar_95 = abs(np.mean(tail_losses)) if tail_losses else var_95
    
    return {
        "Max_DD": round(float(np.mean(max_dd_list)), 2),
        "Iflas": round((iflas_sayaci / simulasyon_sayisi) * 100, 2),
        "VaR_95": round(float(var_95), 2),
        "CVaR_95": round(float(cvar_95), 2),
    }


def benchmark_getirisi_hesapla(hisse_kodu: str, baslangic_tarihi: str, bitis_tarihi: str) -> float:
    """
    Benchmark olarak BIST100 veya SP500 endeks getirisini hesaplar.
    Hisse .IS ise XU100, değilse ^GSPC (S&P 500) kullanır.
    """
    if ".IS" in hisse_kodu.upper():
        benchmark_sembol = "XU100.IS"
    else:
        benchmark_sembol = "^GSPC"
    
    try:
        df = yf.download(benchmark_sembol, start=baslangic_tarihi, end=bitis_tarihi, progress=False)
        if df.empty or "Close" not in df.columns:
            return 0.0
        bas = float(df["Close"].iloc[0])
        son = float(df["Close"].iloc[-1])
        return round(((son - bas) / bas) * 100, 2)
    except Exception:
        return 0.0


def backtest_calistir(hisse_kodu: str, periyot_gun: int = None, 
                      sermaye_baslangic: float = None,
                      stop_loss_yuzde: float = None, 
                      take_profit_yuzde: float = None) -> dict:
    """
    RSI tabanlı strateji için kapsamlı backtest yapar.
    
    Gerçekçi varsayımlar:
    - Her işlemde komisyon oranı düşülür
    - Slippage (kayma) dahil edilir
    - Benchmark karşılaştırması yapılır
    - Sharpe, Sortino, Calmar oranları hesaplanır
    
    Parametreler:
        hisse_kodu: THYAO.IS, AAPL vb.
        periyot_gun: Test periyodu (gün)
        sermaye_baslangic: Başlangıç sermayesi
        stop_loss_yuzde: Stop-loss oranı
        take_profit_yuzde: Take-profit oranı
        
    Dönüş: Kapsamlı backtest sonuçları dict veya None
    """
    ayarlar = _strateji_ayarlari()
    
    if periyot_gun is None:
        periyot_gun = ayarlar.get("backtest_varsayilan_gun", 365)
    if sermaye_baslangic is None:
        sermaye_baslangic = ayarlar.get("backtest_varsayilan_sermaye", 10000)
    if stop_loss_yuzde is None:
        stop_loss_yuzde = ayarlar["stop_loss_yuzde"]
    if take_profit_yuzde is None:
        take_profit_yuzde = ayarlar["take_profit_yuzde"]
    
    rsi_al_esigi = ayarlar.get("rsi_al_esigi", 30)
    komisyon = ayarlar.get("komisyon_orani", 0.002)
    slippage = ayarlar.get("slippage_yuzde", 0.001)
    simulasyon_sayisi = ayarlar.get("backtest_monte_carlo_simulasyon", 1000)
    
    try:
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=periyot_gun)
        baslangic_str = start_date.strftime("%Y-%m-%d")
        bitis_str = end_date.strftime("%Y-%m-%d")
        
        tk = yf.Ticker(hisse_kodu)
        df = tk.history(start=baslangic_str, end=bitis_str)
        
        if df.empty or "Close" not in df.columns:
            return None
        
        df = df.dropna(subset=["Close"])
        if df.empty or len(df) < 20:
            return None
        
        close_p = df["Close"].squeeze()
        df["RSI"] = rsi_serisi(close_p)
        
        # Buy & Hold getirisi (benchmark)
        buy_hold_bas = float(close_p.iloc[0])
        buy_hold_son = float(close_p.iloc[-1])
        buy_hold_getiri = round(((buy_hold_son - buy_hold_bas) / buy_hold_bas) * 100, 2)
        
        # Piyasa benchmark getirisi
        benchmark_getiri = benchmark_getirisi_hesapla(hisse_kodu, baslangic_str, bitis_str)
        
        # ── Alım-Satım simülasyonu ──
        sermaye = float(sermaye_baslangic)
        adet = 0.0
        islem_gecmisi = []
        getiri_listesi = []
        bakiye_serisi = [sermaye]  # Her gün sonu bakiyesi
        giris_fiyat = 0.0
        islem_sayisi = 0
        
        for i in range(len(df)):
            fiyat = float(close_p.iloc[i])
            rsi = float(df["RSI"].iloc[i]) if not pd.isna(df["RSI"].iloc[i]) else 50.0
            
            # Pozisyon varsa çıkış kontrolü
            if adet > 0:
                cikis_fiyat = 0.0
                islem_tipi = ""
                
                # Stop-loss kontrolü
                stop_fiyati = giris_fiyat * (1 - stop_loss_yuzde - slippage)
                if float(df["Low"].iloc[i]) <= stop_fiyati:
                    cikis_fiyat = stop_fiyati
                    islem_tipi = "🛑 STOP"
                
                # Take-profit kontrolü  
                elif float(df["High"].iloc[i]) >= giris_fiyat * (1 + take_profit_yuzde - slippage):
                    cikis_fiyat = giris_fiyat * (1 + take_profit_yuzde - slippage)
                    islem_tipi = "🎯 KAR-AL"
                
                # RSI çıkış sinyali
                elif rsi > 65:
                    cikis_fiyat = fiyat * (1 - slippage)
                    islem_tipi = "🔴 SAT (RSI)"
                
                if cikis_fiyat > 0:
                    # Komisyon düş
                    brut_gelir = adet * cikis_fiyat
                    komisyon_tutari = brut_gelir * komisyon
                    net_gelir = brut_gelir - komisyon_tutari
                    
                    getiri = (cikis_fiyat - giris_fiyat) / giris_fiyat
                    getiri_listesi.append(getiri)
                    
                    sermaye += net_gelir
                    islem_sayisi += 1
                    
                    islem_gecmisi.append({
                        "Tarih": df.index[i].strftime("%d-%m-%Y"),
                        "İşlem": islem_tipi,
                        "Fiyat": round(cikis_fiyat, 2),
                        "Bakiye": round(sermaye, 2),
                        "Getiri %": round(getiri * 100, 2)
                    })
                    adet = 0.0
            
            # AL sinyali kontrolü (pozisyon yoksa)
            elif rsi < rsi_al_esigi and sermaye > fiyat:
                # Komisyon ve slippage dahil giriş fiyatı
                giris_fiyat_efektif = fiyat * (1 + slippage)
                maksimum_adet = sermaye // giris_fiyat_efektif
                
                if maksimum_adet > 0:
                    brut_maliyet = maksimum_adet * giris_fiyat_efektif
                    komisyon_tutari = brut_maliyet * komisyon
                    toplam_maliyet = brut_maliyet + komisyon_tutari
                    
                    if toplam_maliyet <= sermaye:
                        adet = float(maksimum_adet)
                        sermaye -= toplam_maliyet
                        giris_fiyat = giris_fiyat_efektif
                        
                        islem_gecmisi.append({
                            "Tarih": df.index[i].strftime("%d-%m-%Y"),
                            "İşlem": "🟢 AL",
                            "Fiyat": round(giris_fiyat_efektif, 2),
                            "Bakiye": round(sermaye + (adet * fiyat), 2),
                            "Getiri %": 0.0
                        })
            
            # Gün sonu bakiye (açık pozisyon dahil)
            gun_sonu_bakiye = sermaye + (adet * fiyat)
            bakiye_serisi.append(gun_sonu_bakiye)
        
        # ── Kapanış hesaplamaları ──
        son_fiyat = float(close_p.iloc[-1])
        final_bakiye = sermaye + (adet * son_fiyat)  # Açık pozisyon varsa kapat
        
        # Komisyon: açık pozisyonu piyasa fiyatından kapat
        if adet > 0:
            kapanis_komisyon = adet * son_fiyat * komisyon
            final_bakiye -= kapanis_komisyon
        
        net_getiri_yuzde = round(((final_bakiye - sermaye_baslangic) / sermaye_baslangic) * 100, 2)
        
        # ── Getiri analizi ──
        wins = [g for g in getiri_listesi if g > 0]
        losses = [abs(g) for g in getiri_listesi if g <= 0]
        
        win_rate = round(len(wins) / len(getiri_listesi) * 100, 1) if getiri_listesi else 0.0
        avg_win = round(np.mean(wins) * 100, 2) if wins else 0.0
        avg_loss = round(np.mean(losses) * 100, 2) if losses else 0.0
        kazanc_kayip_orani = round(avg_win / avg_loss, 2) if avg_loss > 0 else 999.0
        
        # ── Risk metrikleri ──
        max_dd, max_dd_suresi = _max_drawdown_hesapla(bakiye_serisi)
        sharpe = _sharpe_orani(getiri_listesi)
        sortino = _sortino_orani(getiri_listesi)
        calmar = _calmar_orani(net_getiri_yuzde, max_dd)
        
        # Monte Carlo
        mc = monte_carlo_simulasyonu(getiri_listesi, sermaye_baslangic, simulasyon_sayisi)
        
        # Kelly Kriteri
        kelly = 0.0
        if avg_win > 0 and avg_loss > 0 and win_rate > 0:
            p = win_rate / 100
            q = 1 - p
            oran = avg_win / avg_loss
            kelly = round(max(0, p - q / oran) * 100, 1)
        
        # ── Alfa (strateji - benchmark farkı) ──
        alfa = round(net_getiri_yuzde - benchmark_getiri, 2)
        
        # ── İşlem sıklığı ──
        islem_sikligi = round(len(getiri_listesi) / (periyot_gun / 252), 1) if periyot_gun > 0 else 0.0  # yıllık
        
        return {
            "Baslangic": int(sermaye_baslangic),
            "Final": round(final_bakiye, 2),
            "Getiri %": net_getiri_yuzde,
            "BuyHold %": buy_hold_getiri,
            "Benchmark %": benchmark_getiri,
            "Alfa %": alfa,
            "Win Rate %": win_rate,
            "İşlem Sayısı": islem_sayisi,
            "Ort. Kar %": avg_win,
            "Ort. Zarar %": avg_loss,
            "Kar/Zarar Oranı": kazanc_kayip_orani,
            "Max Drawdown %": max_dd,
            "Max DD Süresi (gün)": max_dd_suresi,
            "Sharpe Oranı": sharpe,
            "Sortino Oranı": sortino,
            "Calmar Oranı": calmar,
            "Kelly Kriteri %": kelly,
            "İflas İhtimali %": mc["Iflas"],
            "VaR %95": mc["VaR_95"],
            "CVaR %95": mc["CVaR_95"],
            "MC Max DD %": mc["Max_DD"],
            "Yıllık İşlem": islem_sikligi,
            "Islemler": pd.DataFrame(islem_gecmisi) if islem_gecmisi else pd.DataFrame()
        }
        
    except Exception as e:
        print(f"[Backtest] Hata: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════
#  TEST
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    test_hisse = "THYAO.IS"
    
    print("=" * 70)
    print(f"  BACKTEST TEST — {test_hisse}")
    print("=" * 70)
    
    sonuc = backtest_calistir(test_hisse, periyot_gun=365)
    
    if sonuc:
        print(f"\n  📊 PERFORMANS ÖZETİ")
        print(f"  {'─' * 50}")
        print(f"  Başlangıç       : ₺{sonuc['Baslangic']:,}")
        print(f"  Final Bakiye    : ₺{sonuc['Final']:,}")
        print(f"  Net Getiri      : %{sonuc['Getiri %']}")
        print(f"  Buy & Hold      : %{sonuc['BuyHold %']}")
        print(f"  Benchmark       : %{sonuc['Benchmark %']}")
        print(f"  Alfa            : %{sonuc['Alfa %']}  {'✓' if sonuc['Alfa %'] > 0 else '✗'}")
        print(f"\n  ⚖️ RİSK METRİKLERİ")
        print(f"  {'─' * 50}")
        print(f"  Win Rate        : %{sonuc['Win Rate %']}")
        print(f"  Ort. Kar        : %{sonuc['Ort. Kar %']}")
        print(f"  Ort. Zarar      : %{sonuc['Ort. Zarar %']}")
        print(f"  Kar/Zarar Oranı : {sonuc['Kar/Zarar Oranı']}")
        print(f"  Max Drawdown    : %{sonuc['Max Drawdown %']} ({sonuc['Max DD Süresi (gün)']} gün)")
        print(f"  Sharpe Oranı    : {sonuc['Sharpe Oranı']}")
        print(f"  Sortino Oranı   : {sonuc['Sortino Oranı']}")
        print(f"  Calmar Oranı    : {sonuc['Calmar Oranı']}")
        print(f"  Kelly Kriteri   : %{sonuc['Kelly Kriteri %']}")
        print(f"\n  🎲 MONTE CARLO (%95 Güven)")
        print(f"  {'─' * 50}")
        print(f"  VaR %95         : %{sonuc['VaR %95']}")
        print(f"  CVaR %95        : %{sonuc['CVaR %95']}")
        print(f"  İflas İhtimali  : %{sonuc['İflas İhtimali %']}")
        print(f"  MC Max DD       : %{sonuc['MC Max DD %']}")
        print(f"\n  📈 İŞLEM İSTATİSTİKLERİ")
        print(f"  {'─' * 50}")
        print(f"  Toplam İşlem    : {sonuc['İşlem Sayısı']}")
        print(f"  Yıllık İşlem    : {sonuc['Yıllık İşlem']:.0f}")
    else:
        print(f"\n  ✗ Backtest başarısız — yeterli veri bulunamadı.")