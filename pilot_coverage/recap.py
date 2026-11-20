"""Récapitulatif d'un lot (run_all.bat). --debut marque le début du lot dans output/executions.log ;
sans option, affiche les exécutions depuis la dernière marque, la durée de chaque script et la durée du lot.
--archiver copie en plus les sorties produites pendant le lot dans output/lots/<AAAA-MM-JJ_HH-MM du lancement>/."""
import argparse
import re
import shutil
from datetime import datetime

import common

MARQUE = "=== LOT"
DOSSIER_LOTS = common.DOSSIER_OUTPUT / "lots"
DOSSIERS_A_ARCHIVER = ["entreprises"]  # sous-dossiers de output/ (en plus des CSV de output/ et de l'échantillon)


def mmss(secondes):
    return f"{secondes // 60:3d} min {secondes % 60:02d} s"


def archiver(debut_lot, lignes_recap):
    """Copie les sorties modifiées depuis le début du lot (les fichiers d'un lot précédent ne sont pas repris)."""
    debut_lot = debut_lot or datetime.now()
    seuil = debut_lot.timestamp()
    dossier = DOSSIER_LOTS / f"{debut_lot:%Y-%m-%d_%H-%M}"
    dossier.mkdir(parents=True, exist_ok=True)
    copies = []
    for f in sorted(common.DOSSIER_OUTPUT.glob("*.csv")) + [common.FICHIER_ECHANTILLON]:
        if f.exists() and f.stat().st_mtime >= seuil:
            shutil.copy2(f, dossier / f.name)
            copies.append(f.name)
    for nom in DOSSIERS_A_ARCHIVER:
        source = common.DOSSIER_OUTPUT / nom
        if source.exists() and source.stat().st_mtime >= seuil:
            shutil.copytree(source, dossier / nom, dirs_exist_ok=True)
            copies.append(nom + "/")
    (dossier / "recap.txt").write_text("\n".join(lignes_recap) + "\n", encoding="utf-8")
    print(f"Archive du lot -> {dossier}")
    print(f"  {', '.join(copies) or 'aucune sortie produite pendant le lot'} + recap.txt")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debut", action="store_true", help="marquer le début d'un lot dans le journal")
    parser.add_argument("--archiver", action="store_true", help="copier les sorties du lot dans output/lots/<date>/")
    args = parser.parse_args()

    common.DOSSIER_OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.debut:
        with open(common.FICHIER_JOURNAL, "a", encoding="utf-8") as f:
            f.write(f"{MARQUE} {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        return

    try:
        lignes = common.FICHIER_JOURNAL.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print("Aucun journal d'exécution.")
        return
    indice = max((i for i, l in enumerate(lignes) if l.startswith(MARQUE)), default=-1)
    debut_lot = datetime.strptime(lignes[indice][len(MARQUE):].strip(), "%Y-%m-%d %H:%M:%S") if indice >= 0 else None

    sortie = []
    ecrire = lambda texte="": (print(texte), sortie.append(texte))
    ecrire("\n" + "=" * 80)
    ecrire(f"RÉCAPITULATIF DU LOT (démarré {debut_lot or 'à une date inconnue'})")
    ecrire("=" * 80)
    cumul = 0
    for ligne in lignes[indice + 1:]:
        champs = ligne.split(" | ")
        if len(champs) < 4:
            continue
        duree = re.match(r"(\d+)", champs[2])
        secondes = int(duree.group(1)) if duree else 0
        cumul += secondes
        ecrire(f"{champs[1]:<20} {mmss(secondes)}")
        ecrire(f"    {' | '.join(champs[3:])}")
    ecrire("-" * 80)
    ecrire(f"{'Somme des scripts':<20} {mmss(cumul)}")
    if debut_lot:
        ecrire(f"{'Durée du lot':<20} {mmss(int((datetime.now() - debut_lot).total_seconds()))}")
    print(f"Journal complet : {common.FICHIER_JOURNAL}")
    if args.archiver:
        archiver(debut_lot, sortie)


if __name__ == "__main__":
    main()
