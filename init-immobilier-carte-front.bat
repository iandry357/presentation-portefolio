@echo off
set DIR=frontend\components\immobilier\bdnb
if not exist "%DIR%\PanneauPoint.tsx" type nul > "%DIR%\PanneauPoint.tsx"
echo Fichier cree : %DIR%\PanneauPoint.tsx
dir "%DIR%\PanneauPoint.tsx"
