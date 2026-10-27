@echo off
if not exist "backend\app\services\immobilier_geoplateforme.py" type nul > "backend\app\services\immobilier_geoplateforme.py"
if not exist "backend\routers\immobilier\point_router.py" type nul > "backend\routers\immobilier\point_router.py"
echo Fichiers crees
dir "backend\app\services\immobilier_geoplateforme.py" "backend\routers\immobilier\point_router.py"
