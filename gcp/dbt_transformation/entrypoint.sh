#!/bin/sh
set -u

echo "=== [dbt] Démarrage transformation emploi_marche - $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# Fraîcheur de offres_brutes (alerte à 24 h, erreur à 48 h, voir _sources.yml) :
# signal non bloquant, la transformation est lancée quand même
FRAICHEUR_OK=1
echo "=== [dbt source freshness] ==="
if ! dbt source freshness --target prod --log-format json; then
    echo "=== [dbt source freshness] ECHEC - aucune collecte récente dans offres_brutes, transformation lancée quand même ==="
    FRAICHEUR_OK=0
fi

# build : chaque nœud est testé avant ses descendants ; un test en échec
# saute la reconstruction en aval, qui garde sa version précédente
echo "=== [dbt build] ==="
if ! dbt build --target prod --log-format json; then
    echo "=== [dbt build] ECHEC - modèles en aval non reconstruits, version précédente conservée ; détail dans Cloud Logging ==="
    exit 1
fi

if [ "$FRAICHEUR_OK" -eq 0 ]; then
    echo "=== [dbt] Transformation terminée, fraîcheur en échec - exécution marquée en échec ==="
    exit 1
fi

echo "=== [dbt] Transformation terminée avec succès - $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
