'use client';

import { useState } from 'react';
import { EntreeOrg } from '@/lib/immobilierOrg';
import OrgEntrees from './OrgEntrees';
import OrgPeriode from './OrgPeriode';
import OrgPartie from './OrgPartie';
import QualiteOrg from './QualiteOrg';
import SourcesOrg from './SourcesOrg';

// Étape de livraison où chaque entrée restante est branchée (en construction)
const ETAPES: Partial<Record<EntreeOrg, string>> = {
  croise: '6e', exploration: '6e',
};

const ENTREE_DEFAUT: EntreeOrg = 'dvf';

export default function OrgPage() {
  const [entree, setEntree] = useState<EntreeOrg>(ENTREE_DEFAUT);

  return (
    <div className="space-y-6">
      <OrgPeriode />
      <OrgEntrees active={entree} onChange={setEntree} />
      {entree === 'dvf' && <OrgPartie cube="dvf" />}
      {entree === 'dpe' && <OrgPartie cube="dpe" />}
      {entree === 'batiment' && <OrgPartie cube="batiment" />}
      {entree === 'sources' && <SourcesOrg />}
      {entree === 'qualite' && <QualiteOrg />}
      {(entree === 'croise' || entree === 'exploration') && (
        <div className="px-4 py-16 text-center text-sm text-gray-500 border rounded-lg bg-white">
          Cette partie arrive à l’étape {ETAPES[entree]}.
        </div>
      )}
    </div>
  );
}
