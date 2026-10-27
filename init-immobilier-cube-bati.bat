@echo off
set PKG=realisations\immobilier\pipeline\bdnb_complement
if not exist "%PKG%\cube_bati.py" type nul > "%PKG%\cube_bati.py"
echo Fichier cree : %PKG%\cube_bati.py
dir "%PKG%\cube_bati.py"
