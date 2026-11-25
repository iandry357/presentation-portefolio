"""Purge les réponses de recherche vides et les offres dont l'étape A n'a rien renvoyé, pour pouvoir les rejouer."""
import common


def main():
    supprimes_recherche = 0
    for chemin in common.DOSSIER_CACHE_SEARCH.glob("*.json"):
        donnees = common.lire_json(chemin)
        if donnees is not None and not donnees.get("resultats"):
            chemin.unlink()
            supprimes_recherche += 1

    supprimes_offres = 0
    for chemin in common.DOSSIER_CACHE_OFFRES.glob("*.json"):
        offre = common.lire_json(chemin)
        if offre and not offre.get("urls_etape_A") and offre.get("cause_echec") == "domaine_non_identifie":
            chemin.unlink()
            supprimes_offres += 1

    print(f"Recherches vides supprimées : {supprimes_recherche}")
    print(f"Offres sans résultat à l'étape A supprimées : {supprimes_offres}")


if __name__ == "__main__":
    main()
