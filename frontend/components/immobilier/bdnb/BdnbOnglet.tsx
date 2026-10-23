'use client';

import { useState } from 'react';
import BdnbSidebar, { BdnbView } from './BdnbSidebar';
import AnalyseView from './AnalyseView';
import BdnbStats from './BdnbStats';
import ParcView from './ParcView';
import PrixDpeView from './PrixDpeView';
import SourcesView from './SourcesView';

export default function BdnbOnglet() {
  const [vue, setVue] = useState<BdnbView>('prix');

  return (
    <>
      <div className="mb-6">
        <BdnbStats />
      </div>

      <div className="flex flex-col md:flex-row gap-6 items-stretch md:items-start">
        <BdnbSidebar activeView={vue} onViewChange={setVue} />

        <div className="flex-1 min-w-0 w-full">
          {vue === 'prix' && <PrixDpeView />}
          {vue === 'analyse' && <AnalyseView />}
          {vue === 'parc' && <ParcView />}
          {vue === 'sources' && <SourcesView />}
        </div>
      </div>
    </>
  );
}
