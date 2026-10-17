@echo off
setlocal enableextensions

rem Lancement quotidien de Top Offres : orchestrator.py run --auto (ou les options passees au script).
rem Prerequis : Docker Desktop et Ollama lances. Sortie affichee et enregistree dans results\logs.
rem Usage : run_quotidien.bat [--pause] [options de run, ex. --derniers-jours 3 ou --forcer]
rem Codes de retour : 0 succes, 2 Docker indisponible, 3 Ollama indisponible, sinon code du run.

for %%i in ("%~dp0..") do set "RACINE=%%~fi"
set "PAUSE_FIN="
if /i "%~1"=="--pause" (
    set "PAUSE_FIN=1"
    shift
)
set "OPTIONS=%1 %2 %3 %4 %5 %6 %7 %8 %9"
if "%OPTIONS: =%"=="" set "OPTIONS=--auto"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "HORODATAGE=%%i"
if not exist "%RACINE%\results\logs" mkdir "%RACINE%\results\logs"
set "JOURNAL=%RACINE%\results\logs\run_%HORODATAGE%.log"

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Docker ne repond pas : lancer Docker Desktop.
    set "CODE=2"
    goto fin
)
curl -s -f -m 5 http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Ollama ne repond pas sur localhost:11434 : le lancer.
    set "CODE=3"
    goto fin
)

echo Run %OPTIONS% - journal : %JOURNAL%
cd /d "%RACINE%\pipeline"
powershell -NoProfile -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; cmd /c 'docker-compose run --rm -T pipeline pipeline/orchestrator.py run %OPTIONS% 2>&1' | ForEach-Object { Write-Host $_; Add-Content -LiteralPath '%JOURNAL%' -Value $_ -Encoding UTF8 }; exit $LASTEXITCODE"
set "CODE=%ERRORLEVEL%"
echo Fin du run, code %CODE% - journal : %JOURNAL%

:fin
if defined PAUSE_FIN pause
exit /b %CODE%
