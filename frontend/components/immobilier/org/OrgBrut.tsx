'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Lock } from 'lucide-react';
import { useAccess } from '@/components/AccessProvider';
import {
  FormatCsv, JeuBrut, OrgBrutApercu, OrgBrutCatalogue, ParametresBrut, getOrgBrutApercu, getOrgBrutCatalogue, urlExportBrut,
} from '@/lib/immobilierOrgApi';
import { ARRONDISSEMENTS, CLASSE_CHAMP, formatDate, formatEntier, libelleArrondissement } from '@/lib/immobilier';
import { CarteGraphique, Explication } from '../ImmobilierCharts';
import Lecture from '../bdnb/Lecture';

// Paramètres
const ARRONDISSEMENT_DEFAUT = 1;     // aperçu chargé à l'ouverture
const DELAI_APERCU_MS = 300;         // attente après le dernier changement avant de relire l'aperçu
const LIBELLES_FORMAT: Record<FormatCsv, string> = {
  excel: 'Excel (séparateur « ; », virgule décimale)',
  standard: 'Standard (séparateur « , », point décimal)',
};

function formaterCellule(valeur: string | number | boolean | null): string {
  if (valeur === null) return '';
  if (typeof valeur === 'boolean') return valeur ? 'oui' : 'non';
  if (typeof valeur === 'number') return valeur.toLocaleString('fr-FR', { maximumFractionDigits: 6, useGrouping: false });
  return valeur;
}

export default function OrgBrut({ jeu }: { jeu: JeuBrut }) {
  const { state, unlocked } = useAccess();
  const [catalogue, setCatalogue] = useState<OrgBrutCatalogue | null>(null);
  const [arrondissement, setArrondissement] = useState(ARRONDISSEMENT_DEFAUT);
  const [debut, setDebut] = useState('');
  const [fin, setFin] = useState('');
  const [colonnes, setColonnes] = useState<string[]>([]);   // sélection, dans l'ordre du catalogue
  const [format, setFormat] = useState<FormatCsv>('excel');
  const [libelles, setLibelles] = useState(false);
  const [apercu, setApercu] = useState<OrgBrutApercu | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const derniereRequete = useRef(0);

  const definition = catalogue?.jeux.find(j => j.jeu === jeu) ?? null;
  const avecDate = !!definition?.colonne_date;

  // Catalogue : lu une fois l'accès connu (privé : 403 sans code)
  useEffect(() => {
    if (state === 'loading' || !unlocked) return;
    getOrgBrutCatalogue()
      .then(c => {
        setCatalogue(c);
        setFormat(c.format_defaut);
        setDebut(c.date_debut_defaut);
        setColonnes(c.jeux.find(j => j.jeu === jeu)?.colonnes.filter(col => col.defaut).map(col => col.nom) ?? []);
      })
      .catch(e => setError(e instanceof Error ? e.message : 'Erreur de chargement'));
  }, [state, unlocked, jeu]);

  const parametres = useMemo<ParametresBrut>(
    () => ({
      arrondissement,
      debut: avecDate && debut ? debut : undefined,
      fin: avecDate && fin ? fin : undefined,
      colonnes,
    }),
    [arrondissement, avecDate, debut, fin, colonnes],
  );

  // Aperçu : relu après chaque changement (attente courte : plusieurs cases cochées de suite font une seule lecture)
  useEffect(() => {
    if (!catalogue || !unlocked || colonnes.length === 0) return;
    const numero = ++derniereRequete.current;
    const minuteur = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const reponse = await getOrgBrutApercu(jeu, parametres);
        if (numero === derniereRequete.current) setApercu(reponse);
      } catch (e) {
        if (numero === derniereRequete.current) {
          setApercu(null);
          setError(e instanceof Error ? e.message : 'Erreur de chargement');
        }
      } finally {
        if (numero === derniereRequete.current) setLoading(false);
      }
    }, DELAI_APERCU_MS);
    return () => clearTimeout(minuteur);
  }, [catalogue, unlocked, jeu, parametres, colonnes.length]);

  if (state === 'loading') return <div className="min-h-[40vh]" aria-busy="true" />;

  if (!unlocked) {
    return (
      <div className="px-4 py-16 text-center">
        <Lock className="w-8 h-8 mx-auto mb-3 text-gray-400" />
        <h2 className="text-lg font-semibold text-gray-900">Zone privée</h2>
        <p className="mt-1 text-sm text-gray-500">Utilisez le bouton « Déverrouiller » en haut de la page.</p>
      </div>
    );
  }

  if (!definition) {
    return error
      ? <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg">{error}</div>
      : <div className="h-64 border rounded-lg bg-white animate-pulse" />;
  }

  const basculer = (nom: string) =>
    setColonnes(courantes =>
      definition.colonnes.map(c => c.nom).filter(n => (n === nom ? !courantes.includes(nom) : courantes.includes(n))),
    );

  const parDefaut = definition.colonnes.filter(c => c.defaut);
  const options = definition.colonnes.filter(c => !c.defaut && !c.sensible);
  const sensibles = definition.colonnes.filter(c => c.sensible);
  const choisies = definition.colonnes.filter(c => colonnes.includes(c.nom));
  const exportable = !!apercu && !error && colonnes.length > 0;

  const Case = ({ nom, libelle, description }: { nom: string; libelle: string; description: string }) => (
    <label className="flex items-start gap-2 text-sm text-gray-700 cursor-pointer" title={description}>
      <input
        type="checkbox"
        checked={colonnes.includes(nom)}
        onChange={() => basculer(nom)}
        className="mt-0.5 w-4 h-4 rounded border-gray-300"
      />
      <span>{libelle}</span>
    </label>
  );

  return (
    <div className="space-y-6">
      <CarteGraphique titre={`Tableau brut : ${definition.libelle}`} sousTitre={definition.source}>
        <Lecture
          voir="Le jeu de données lui-même, ligne par ligne, pour un arrondissement : rien n’est agrégé ni corrigé."
          retenir={`Un seul arrondissement à la fois, au plus ${formatEntier(catalogue!.plafond_lignes)} lignes par téléchargement. Les colonnes sensibles (adresses, coordonnées, identifiants) restent derrière le code d’accès, comme tout ce tableau.`}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <label className="block text-sm text-gray-600">
            Arrondissement
            <select
              value={arrondissement}
              onChange={e => setArrondissement(Number(e.target.value))}
              className={`${CLASSE_CHAMP} mt-1 w-full`}
            >
              {ARRONDISSEMENTS.map(n => (
                <option key={n} value={n}>{libelleArrondissement(n)}</option>
              ))}
            </select>
          </label>
          {avecDate && (
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm text-gray-600">
                Du
                <input type="date" value={debut} onChange={e => setDebut(e.target.value)} className={`${CLASSE_CHAMP} mt-1 w-full`} />
              </label>
              <label className="block text-sm text-gray-600">
                Au (facultatif)
                <input type="date" value={fin} onChange={e => setFin(e.target.value)} className={`${CLASSE_CHAMP} mt-1 w-full`} />
              </label>
            </div>
          )}
        </div>

        <fieldset className="mb-3">
          <legend className="text-xs font-medium text-gray-500 mb-1">Colonnes par défaut</legend>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
            {parDefaut.map(c => <Case key={c.nom} {...c} />)}
          </div>
        </fieldset>

        {options.length > 0 && (
          <details className="mb-3">
            <summary className="cursor-pointer text-sm text-blue-700 hover:underline select-none">
              Colonnes en option ({options.length})
            </summary>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-1">
              {options.map(c => <Case key={c.nom} {...c} />)}
            </div>
          </details>
        )}

        {sensibles.length > 0 && (
          <details className="mb-4">
            <summary className="cursor-pointer text-sm text-blue-700 hover:underline select-none">
              Adresses, coordonnées et identifiants ({sensibles.length})
            </summary>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-1">
              {sensibles.map(c => <Case key={c.nom} {...c} />)}
            </div>
          </details>
        )}

        <Explication titre="Explication des colonnes choisies">
          <dl className="space-y-1.5">
            {choisies.map(c => (
              <div key={c.nom}>
                <dt className="font-medium text-gray-800">
                  {c.libelle} <span className="font-normal text-gray-400">({c.nom})</span>
                </dt>
                <dd>{c.description}</dd>
              </div>
            ))}
          </dl>
        </Explication>

        {colonnes.length === 0 && (
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-3">
            Cochez au moins une colonne.
          </p>
        )}
        {error && <div className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-lg mb-3">{error}</div>}

        {apercu && (
          <div className={loading ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
            <p className="text-sm text-gray-600 mb-2">
              {formatEntier(apercu.nb_lignes)} ligne{apercu.nb_lignes > 1 ? 's' : ''}
              {apercu.date_debut &&
                ` du ${formatDate(apercu.date_debut)} ${apercu.date_fin ? `au ${formatDate(apercu.date_fin)}` : 'aux dernières données'}`}
              {' '}· aperçu des {formatEntier(apercu.lignes.length)} premières.
            </p>
            <div className="overflow-auto max-h-96 border rounded-lg">
              <table className="min-w-full text-xs">
                <thead className="sticky top-0 bg-gray-50">
                  <tr className="text-left text-gray-500 border-b">
                    {apercu.colonnes.map(c => (
                      <th key={c.nom} title={c.description} className="py-1.5 px-3 font-medium whitespace-nowrap">
                        {libelles ? c.libelle : c.nom}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {apercu.lignes.map((ligne, i) => (
                    <tr key={i} className="border-b last:border-0">
                      {apercu.colonnes.map(c => (
                        <td key={c.nom} className="py-1 px-3 text-gray-700 whitespace-nowrap">
                          {formaterCellule(ligne[c.nom])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-end gap-4">
          <label className="block text-sm text-gray-600">
            Format du fichier
            <select value={format} onChange={e => setFormat(e.target.value as FormatCsv)} className={`${CLASSE_CHAMP} mt-1 block`}>
              {catalogue!.formats.map(f => (
                <option key={f} value={f}>{LIBELLES_FORMAT[f]}</option>
              ))}
            </select>
          </label>
          <label className="inline-flex items-center gap-2 text-sm text-gray-600 cursor-pointer pb-1.5">
            <input
              type="checkbox"
              checked={libelles}
              onChange={e => setLibelles(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300"
            />
            En-têtes lisibles (sinon : noms techniques)
          </label>
          {exportable ? (
            <a
              href={urlExportBrut(jeu, parametres, format, libelles)}
              className="inline-flex items-center px-4 py-2 text-sm font-medium rounded border border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100"
            >
              Télécharger en CSV
            </a>
          ) : (
            <span className="inline-flex items-center px-4 py-2 text-sm font-medium rounded border border-gray-200 bg-gray-50 text-gray-400">
              Télécharger en CSV
            </span>
          )}
        </div>
      </CarteGraphique>
    </div>
  );
}
