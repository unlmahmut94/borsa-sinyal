@echo off
cd /d "%~dp0"
echo ═══════════════════════════════════════════════════
echo   DERIN OPTUNA EGITIM MOTORU
echo   🔬 Optuna ACIK — n_trials=30 (AGIR)
echo ═══════════════════════════════════════════════════
echo.
echo   🎯 Tek tur egitir ve durur
echo   📦 BIST + NASDAQ + SP500 + Kripto (tum semboller)
echo    Kaldigi yerden devam eder (checkpoint)
echo   ⚠️  UYARI: 1722 sembol ~20-40 saat surebilir!
echo   � Rapor: logs/egitim_log.txt
echo ═══════════════════════════════════════════════════
echo.
python mod_egitim_kontrol.py optuna
echo.
echo ═══════════════════════════════════════════════════
echo   EGITIM DURDU!
echo ═══════════════════════════════════════════════════
pause