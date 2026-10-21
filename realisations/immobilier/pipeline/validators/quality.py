from pipeline.config import ETIQUETTES, PRIX_M2_MAX, PRIX_M2_MIN



def valider_dpe(df, numeros_vus):
    """Écarte les lignes invalides ; retourne (df valide, dict des rejets par raison).
    numeros_vus est mis à jour pour détecter les doublons entre pages."""
    rejets = {}

    def garder(masque, raison):
        nonlocal df
        rejets[raison] = int((~masque).sum())
        df = df[masque]

    garder(df["numero_dpe"].notna(), "numero_dpe_nul")
    garder(~df["numero_dpe"].duplicated() & ~df["numero_dpe"].isin(numeros_vus), "numero_dpe_doublon")
    garder(df["etiquette_dpe"].isin(ETIQUETTES), "etiquette_invalide")
    garder(df["surface_habitable_logement"] > 0, "surface_invalide")

    numeros_vus.update(df["numero_dpe"])
    return df, rejets



def valider_dvf(df):
    """Écarte les ventes sans surface ou hors bornes de prix_m2 ; retourne (df valide, dict des rejets par raison)."""
    rejets = {}

    def garder(masque, raison):
        nonlocal df
        rejets[raison] = int((~masque).sum())
        df = df[masque]

    garder(df["surface_reelle_bati"] > 0, "surface_invalide")
    garder(df["prix_m2"].between(PRIX_M2_MIN, PRIX_M2_MAX), "prix_m2_hors_bornes")
    return df, rejets
