'use client';

import { useState } from 'react';
import { EntreeOrg } from '@/lib/immobilierOrg';
import OrgEntrees from './OrgEntrees';
import OrgPeriode from './OrgPeriode';
import OrgPartie from './OrgPartie';
import OrgCroise from './OrgCroise';
import QualiteOrg from './QualiteOrg';
import SourcesOrg from './SourcesOrg';
import OrgExploration from './OrgExploration';


const ENTREE_DEFAUT: EntreeOrg = 'dvf';

export default function OrgPage() {
  const [entree, setEntree] = useState<EntreeOrg>(ENTREE_DEFAUT);

  return (
    <div className="space-y-6">
      <OrgPeriode />
      <OrgEntrees active={entree} onChange={setEntree} />
      {entree === 'dvf' && <OrgPartie cube="dvf" onCroisement={() => setEntree('croise')} />}
      {entree === 'dpe' && <OrgPartie cube="dpe" onCroisement={() => setEntree('croise')} />}
      {entree === 'batiment' && <OrgPartie cube="batiment" onCroisement={() => setEntree('croise')} />}
      {entree === 'sources' && <SourcesOrg />}
      {entree === 'qualite' && <QualiteOrg />}
      {entree === 'croise' && <OrgCroise />}
      {entree === 'exploration' && <OrgExploration />}
    </div>
  );
}
