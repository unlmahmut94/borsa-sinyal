@echo off
cd /d "%~dp0"
echo ═══════════════════════════════════════════════════
echo   ZAMANLI EGITIM MOTORU (22:00)
echo   ⏰ Her gun 22:00 + 2 gunde bir derin Optuna
echo ═══════════════════════════════════════════════════
echo.
echo   ⏰ Her gun 22:00'de standart egitim
echo   🔬 2 gunde bir derin Optuna optimizasyonu
echo   🛑 Guvenlik siniri: 07:00 (ertesi gun)
echo   📦 Tum semboller (BIST+NQ+SP500+Kripto)
echo   📝 Rapor: logs/egitim_log.txt
echo.
echo   Bu pencereyi kapatmayin! 22:00'de otomatik baslar
echo ═══════════════════════════════════════════════════
echo.
python mod_egitim_kontrol.py zamanli
echo.
echo ═══════════════════════════════════════════════════
echo   EGITIM DURDURULDU!
echo ═══════════════════════════════════════════════════
pause