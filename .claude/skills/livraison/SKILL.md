---
name: livraison
description: Clôture une session de travail (mise à jour de STATUS.md) ou, avec l'argument "mvp", la livraison d'un MVP (STATUS.md + CLAUDE.md + README.md). Lancé uniquement par l'utilisateur.
disable-model-invocation: true
argument-hint: "[mvp]"
---

# /livraison — clôture de session ou de MVP

Argument reçu : `$ARGUMENTS`

- Argument vide → **mode FIN DE SESSION** (étapes 1 à 3).
- Argument `mvp` → **mode FIN DE MVP** (étapes 1 à 3, puis 4 à 7).

Règles valables pour tout le skill :
- Tu proposes chaque modification sous forme de diff ciblé, **un fichier à la fois**, et tu attends ma
  validation avant de passer au suivant. Jamais de réécriture complète d'un fichier.
- Tu n'inventes rien : tout ce que tu écris doit venir de la conversation en cours ou des fichiers que
  tu as lus. Si une information manque (statut de déploiement, métrique, port), demande-la-moi.
- Tu n'exécutes rien (pas de shell). Les commandes à lancer, tu me les donnes pour Cmder.
- Tu ne lis aucun secret (`.env`, clés, `tfvars`, `tfstate`, tokens).

## Étape 1 — Bilan de la session

À partir de la conversation en cours, prépare un bilan court :
- **Fait** : fichiers créés / modifiés (chemins), fonctionnalités avancées.
- **Décisions** prises pendant la session (choix d'architecture, renoncements, compromis).
- **Arrêt** : où on s'est arrêté précisément (fichier, fonction, étape du cahier des charges).
- **Prochaine étape** : la première action concrète à la reprise.
- **Points ouverts** : questions non tranchées, bugs connus, commandes que je dois encore exécuter
  ou vérifier (avec leur résultat attendu).

Si la conversation est vide ou presque (session vidée par `/clear`), dis-le-moi et demande-moi
ce qui a été fait au lieu de deviner.

## Étape 2 — Lecture de STATUS.md

Lis `_docs-local/STATUS.md` (et le cahier des charges qu'il référence dans `_docs-local/specs/`)
pour situer le bilan par rapport à l'objectif de la feature.

## Étape 3 — Diff de STATUS.md

Propose le diff de `_docs-local/STATUS.md` en respectant ces règles :
- « Où je me suis arrêté » et « Prochaine étape » : **remplacés** par le bilan du jour.
- « Points ouverts / à vérifier » : remplacé (on retire ce qui est résolu, on ajoute le nouveau).
- « Décisions prises » : **cumulatif**, on ajoute les nouvelles décisions sans supprimer les anciennes.
- « Historique » : **ajout** d'une ligne `- AAAA-MM-JJ : <résumé en une phrase>` (date du jour).
- Ne touche pas à la ligne d'import du cahier des charges actif (sauf en mode MVP, étape 6).

En mode FIN DE SESSION, termine ici par : « Tu peux faire /clear : STATUS.md sera rechargé
automatiquement à la prochaine session. »

## Étape 4 — (mode MVP) Relecture du MVP

Identifie le MVP concerné (d'après STATUS.md et le cahier des charges ; en cas de doute, demande).
Lis son code selon le pattern du projet : `realisations/<mvp>/` (pipeline, ml, training, scripts),
`gcp/<mvp>/infra/`, `backend/routers/<mvp>/`, `frontend/app/realisations/<mvp>/`.
Relève : finalité, briques ML / IA, services et ports OVH, dataset BigQuery, route frontend,
métriques obtenues (si présentes dans la conversation ou les fichiers), statut de déploiement.

## Étape 5 — (mode MVP) Diff de CLAUDE.md

Propose le diff de `CLAUDE.md` :
- ligne du MVP dans le tableau « MVPs sectoriels » (ajout ou mise à jour) ;
- si de nouveaux ports OVH ou services sont apparus, mise à jour du bloc « Architecture ».
Garde le tableau compact : une ligne par MVP.

## Étape 6 — (mode MVP) Diff de README.md

Propose le diff de `README.md` :
- section du MVP dans « MVPs sectoriels » (statut, briques, métriques, serving) ;
- table « Pages de la plateforme » (route du MVP) ;
- tableau OVH dans « Infrastructure » si un port a été ajouté ;
- « Roadmap » : retire ce qui est livré, ajoute le backlog assumé du MVP.

Puis le diff final de `_docs-local/STATUS.md` : feature marquée clôturée dans l'historique,
et ligne d'import pointant vers le prochain cahier des charges (demande-moi lequel ; si aucun,
mets la ligne d'import en commentaire).

## Étape 7 — (mode MVP) Rappels

Termine par :
1. Les commandes git à lancer dans Cmder pour commiter la documentation **séparément du code**
   (`CLAUDE.md`, `README.md` ; jamais `_docs-local/`, qui est ignoré).
2. Le rappel : « Remplace CLAUDE.md dans le projet Claude chat pour qu'il ait le même état du projet. »
