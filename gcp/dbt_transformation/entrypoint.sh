#!/bin/sh
set -u

echo "=== [dbt] Démarrage transformation emploi_marche - $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

echo "=== [dbt run] ==="
if ! dbt run --target prod --log-format json; then
    echo "=== [dbt run] ECHEC - dbt test ignoré, execution Job marquée en échec ==="
    exit 1
fi

echo "=== [dbt test] ==="
if ! dbt test --target prod --log-format json; then
    echo "=== [dbt test] ECHEC - vérifier les logs Cloud Logging du Job pour le detail des tests cassés ==="
    exit 1
fi

echo "=== [dbt] Transformation terminée avec succès - $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="