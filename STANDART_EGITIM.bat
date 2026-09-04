@echo off
cd /d "%~dp0"
echo ═══════════════════════════════════════════════════
echo   STANDART EGITIM MOTORU
echo   ⚡ Optuna KAPALI — Hizli egitim
echo ═══════════════════════════════════════════════════
echo.
echo   🎯 Tek tur egitir ve durur
echo   📦 BIST + NASDAQ + SP500 + Kripto (tum semboller)
echo   📊 Oncelik: Guclu AL → YZ Karnesi → Tumu
echo   🔄 Kaldigi yerden devam eder (checkpoint)
echo   ⏱️ Tahmini sure: ~2 saat (1722 sembol)
echo   📝 Rapor: logs/egitim_log.txt
echo ═══════════════════════════════════════════════════
echo.
python mod_egitim_kontrol.py standart
echo.
echo ═══════════════════════════════════════════════════
echo   EGITIM DURDU!
echo ═══════════════════════════════════════════════════
pause