@echo off
if not exist "backend\app\services\immobilier_bdnb_bati.py" type nul > "backend\app\services\immobilier_bdnb_bati.py"
if not exist "backend\routers\immobilier\bati_router.py" type nul > "backend\routers\immobilier\bati_router.py"
echo Fichiers crees
dir "backend\app\services\immobilier_bdnb_bati.py" "backend\routers\immobilier\bati_router.py"
