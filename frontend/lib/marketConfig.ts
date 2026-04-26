// Catalogue des requêtes — miroir du catalogue backend
// Toute modification du catalogue backend doit être répercutée ici

export type RenduType =
  | "courbe"
  | "courbe_multi"
  | "camembert"
  | "barres_horizontales"
  | "indicateur"
  | "indicateur_comparatif"
  | "tableau"

export type Periode = "7j" | "30j" | "90j"
export type Source =
  | "toutes"
  | "france_travail_api"
  | "email_linkedin"
  | "email_apec"
  | "email_hellowork"
  | "email_talent"
  | "email_indeed"
  | "email_wttj"
  | "email_jobijoba"
  | "email_freework"

export interface QueryMeta {
  id: string
  titre: string
  description: string
  colonnes: string[]
  rendu: RenduType
  sourceRequise?: Source  // si présent, filtre source désactivé
}

export interface MarketQueryParams {
  periode: Periode
  source: Source
}

export interface MarketQueryResult {
  query_id: string
  titre: string
  description: string
  colonnes: string[]
  lignes: Record<string, unknown>[]
  total: number
  params: MarketQueryParams
}

export interface ExcludedCompaniesResponse {
  entreprises: string[]
  total: number
}

// ── Catalogue ─────────────────────────────────────────────────────────────────

export const QUERIES: QueryMeta[] = [
  {
    id: "Q01",
    titre: "Volume d'offres dans le temps",
    description: "Nombre d'offres par jour sur la période sélectionnée",
    colonnes: ["date_publication", "nb_offres"],
    rendu: "courbe",
  },
  {
    id: "Q02",
    titre: "Répartition par source",
    description: "Nombre d'offres par plateforme source",
    colonnes: ["source", "nb_offres"],
    rendu: "camembert",
  },
  {
    id: "Q03",
    titre: "Top entreprises qui recrutent",
    description: "Entreprises avec le plus d'offres publiées",
    colonnes: ["entreprise_nom", "nb_offres"],
    rendu: "barres_horizontales",
  },
  {
    id: "Q04",
    titre: "Top localisations",
    description: "Villes et zones avec le plus d'offres",
    colonnes: ["localisation_libelle", "nb_offres"],
    rendu: "barres_horizontales",
  },
  {
    id: "Q05",
    titre: "Proportion d'offres avec salaire",
    description: "Part des offres mentionnant un salaire",
    colonnes: ["salaire_present", "nb_offres", "pourcentage"],
    rendu: "indicateur",
  },
  {
    id: "Q06",
    titre: "Aujourd'hui vs hier",
    description: "Comparaison du volume de collecte sur 2 jours",
    colonnes: ["jour", "nb_offres"],
    rendu: "indicateur_comparatif",
  },
  {
    id: "Q07",
    titre: "Évolution par source",
    description: "Volume comparatif des sources semaine par semaine",
    colonnes: ["semaine", "source", "nb_offres"],
    rendu: "courbe_multi",
  },
  {
    id: "Q08",
    titre: "Répartition par type de contrat",
    description: "CDI / CDD / Freelance / Alternance",
    colonnes: ["type_contrat", "nb_offres"],
    rendu: "camembert",
    sourceRequise: "france_travail_api",
  },
  {
    id: "Q09",
    titre: "Top codes ROME",
    description: "Métiers les plus représentés",
    colonnes: ["code_rome", "libelle_rome", "nb_offres"],
    rendu: "barres_horizontales",
    sourceRequise: "france_travail_api",
  },
  {
    id: "Q10",
    titre: "Répartition par département",
    description: "Concentration géographique",
    colonnes: ["localisation_departement", "nb_offres"],
    rendu: "barres_horizontales",
    sourceRequise: "france_travail_api",
  },
  {
    id: "Q11",
    titre: "Entreprises finales actives data/IA",
    description: "Entreprises non-ESN avec plusieurs postes data/IA ouverts",
    colonnes: ["entreprise_nom", "nb_titres_distincts", "nb_sources", "premiere_offre", "derniere_offre", "duree_jours", "score_signal"],
    rendu: "tableau",
  },
]

// ── Filtres ───────────────────────────────────────────────────────────────────

export const PERIODES: { value: Periode; label: string }[] = [
  { value: "7j",  label: "7 derniers jours" },
  { value: "30j", label: "30 derniers jours" },
  { value: "90j", label: "90 derniers jours" },
]

export const SOURCES: { value: Source; label: string }[] = [
  { value: "toutes",              label: "Toutes les sources" },
  { value: "france_travail_api",  label: "France Travail API" },
  { value: "email_linkedin",      label: "LinkedIn" },
  { value: "email_apec",          label: "APEC" },
  { value: "email_hellowork",     label: "Hellowork" },
  { value: "email_talent",        label: "Talent.com" },
  { value: "email_indeed",        label: "Indeed" },
  { value: "email_wttj",          label: "Welcome to the Jungle" },
  { value: "email_jobijoba",      label: "Jobijoba" },
  { value: "email_freework",      label: "Free-Work" },
]

// ── API calls ─────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? ""

export async function fetchMarketQuery(
  queryId: string,
  params: MarketQueryParams
): Promise<MarketQueryResult> {
  const qs = new URLSearchParams({ periode: params.periode, source: params.source })
  const res = await fetch(`${API}/market/${queryId}?${qs}`)
  if (!res.ok) throw new Error(`Erreur API : ${res.status}`)
  return res.json()
}

export async function fetchExcludedCompanies(): Promise<ExcludedCompaniesResponse> {
  const res = await fetch(`${API}/market/excluded-companies`)
  if (!res.ok) throw new Error(`Erreur API : ${res.status}`)
  return res.json()
}

export async function toggleExcludedCompany(
  nom: string,
  currentlyExcluded: boolean
): Promise<ExcludedCompaniesResponse> {
  const res = await fetch(
    `${API}/market/excluded-companies${currentlyExcluded ? `/${encodeURIComponent(nom)}` : ""}`,
    {
      method: currentlyExcluded ? "DELETE" : "POST",
      headers: { "Content-Type": "application/json" },
      body: currentlyExcluded ? undefined : JSON.stringify({ nom }),
    }
  )
  if (!res.ok) throw new Error(`Erreur API : ${res.status}`)
  return res.json()
}

export async function batchExcludeCompanies(noms: string[]): Promise<ExcludedCompaniesResponse> {
  const res = await fetch(`${API}/market/excluded-companies/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ noms }),
  })
  if (!res.ok) throw new Error("Erreur batch exclusion")
  return res.json()
}