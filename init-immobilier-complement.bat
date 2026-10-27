@echo off
set PKG=realisations\immobilier\pipeline\bdnb_complement
if not exist "%PKG%" mkdir "%PKG%"
for %%F in (__init__.py config.py selection.py loader.py orchestrator.py attributs.py) do (
    if not exist "%PKG%\%%F" type nul > "%PKG%\%%F"
)
echo Paquet cree : %PKG%
dir "%PKG%"
