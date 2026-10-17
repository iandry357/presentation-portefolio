@echo off
setlocal enableextensions

rem Balayage de la taille de lot : meme jeu (graine 42) pour chaque taille, un rapport results\benchmark_*.json par taille.
rem Lot 1 : reconstruit int_offres_a_scorer (30 jours, table ecrasee) ; les suivants : --sans-amont.
rem Prerequis : Docker Desktop et Ollama lances. Ne pas lancer run_quotidien.bat pendant le balayage.
rem Usage : balayage_lots.bat [--pause]
rem Codes de retour : 0 tout est passe, 1 au moins un benchmark en echec, 2 Docker indisponible, 3 Ollama indisponible.

rem --- Parametres ---
set "MODELE=gemma4:e4b"
set "LOT1=20"
set "LOT2=10"
set "LOT3=5"
set "LOT4=1"

for %%i in ("%~dp0..") do set "RACINE=%%~fi"
set "PAUSE_FIN="
if /i "%~1"=="--pause" set "PAUSE_FIN=1"
set "ECHEC=0"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "HORODATAGE=%%i"
if not exist "%RACINE%\results\logs" mkdir "%RACINE%\results\logs"

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Docker ne repond pas : lancer Docker Desktop.
    set "ECHEC=2"
    goto fin
)
curl -s -f -m 5 http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Ollama ne repond pas sur localhost:11434 : le lancer.
    set "ECHEC=3"
    goto fin
)

cd /d "%RACINE%\pipeline"

call :lancer %LOT1% ""
if not "%CODE%"=="0" (
    echo [ERREUR] Le lot de %LOT1% a echoue : les autres dependent de son amont, arret.
    goto fin
)
call :lancer %LOT2% --sans-amont
call :lancer %LOT3% --sans-amont
call :lancer %LOT4% --sans-amont

:fin
echo Balayage termine, code %ECHEC% - journaux : %RACINE%\results\logs\balayage_%HORODATAGE%_lot*.log
if defined PAUSE_FIN pause
exit /b %ECHEC%

:lancer
set "LOT=%~1"
set "OPTION=%~2"
set "JOURNAL=%RACINE%\results\logs\balayage_%HORODATAGE%_lot%LOT%.log"
echo.
echo === Lots de %LOT% - debut %TIME% - journal : %JOURNAL%
powershell -NoProfile -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; cmd /c 'docker-compose run --rm -T pipeline scripts/benchmark.py --modeles %MODELE% --taille-lot %LOT% %OPTION% 2>&1' | ForEach-Object { Write-Host $_; Add-Content -LiteralPath '%JOURNAL%' -Value $_ -Encoding UTF8 }; exit $LASTEXITCODE"
set "CODE=%ERRORLEVEL%"
echo === Lots de %LOT% - fin %TIME% - code %CODE%
if not "%CODE%"=="0" set "ECHEC=1"
exit /b %CODE%
