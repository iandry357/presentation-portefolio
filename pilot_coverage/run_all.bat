@echo off
rem Pilote de couverture : enchaine toutes les etapes.
rem Duree de chaque script dans output\executions.log, recapitulatif du lot a la fin.
rem A lancer avec le .venv deja active.
setlocal
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8

rem --- Parametres ---
rem JOURS_MAX : offres publiees depuis N jours (1 = hier et aujourd'hui, 0 = pas de filtre).
rem Valeur par defaut ci-dessous, ou en argument : run_all.bat 7
set JOURS_MAX=1
if not "%~1"=="" set JOURS_MAX=%~1
rem RELECTURE=1 : pause pour relire output\domaines_alternatifs.csv (homonymes) avant l'injection
set RELECTURE=0
set FOURNISSEURS=duckduckgo

cd /d "%~dp0"

echo Lot sur JOURS_MAX=%JOURS_MAX% jour(s)
python recap.py --debut || goto :erreur
python 00_inspect_schema.py --jours %JOURS_MAX% || goto :erreur
python purge_vides.py || goto :erreur
python run_pilot.py --etape-a-seule --fournisseurs %FOURNISSEURS% || goto :erreur
if "%RELECTURE%"=="1" (
  python domaine_alternatif.py || goto :erreur
  echo.
  echo Relire output\domaines_alternatifs.csv, completer EXCLUSIONS_MANUELLES si besoin, puis une touche pour injecter.
  pause
)
python domaine_alternatif.py --injecter || goto :erreur
python sitemap_check.py --verifier || goto :erreur
python regrouper.py --telecharger || goto :erreur
python exporter.py --jours %JOURS_MAX% || goto :erreur

python recap.py --archiver
exit /b 0

:erreur
echo.
echo ECHEC de l'etape precedente : arret du lot.
python recap.py --archiver
exit /b 1
