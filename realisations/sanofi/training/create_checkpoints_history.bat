@echo off
REM ============================================================
REM Script de creation du fichier checkpoints_history.json
REM A lancer depuis : realisations\sanofi\training
REM ============================================================

if not exist "models" (
    echo [ERREUR] Le dossier "models" n'existe pas a cet emplacement.
    echo Lance ce script depuis realisations\sanofi\training
    exit /b 1
)

if exist "models\checkpoints_history.json" (
    echo [INFO] models\checkpoints_history.json existe deja - rien a faire.
    exit /b 0
)

type nul > "models\checkpoints_history.json"
echo [OK] Fichier cree : models\checkpoints_history.json