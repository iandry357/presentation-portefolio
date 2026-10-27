@echo off
set SCR=realisations\immobilier\scripts
set RAP=realisations\immobilier\pipeline\data\bdnb\rapports
if not exist "%RAP%" mkdir "%RAP%"
if not exist "%SCR%\explore_bdnb_complement.py" type nul > "%SCR%\explore_bdnb_complement.py"
echo Exploration creee : %SCR%\explore_bdnb_complement.py
dir "%SCR%\explore_bdnb_complement.py"
