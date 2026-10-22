// Les trois lignes sous le titre d'un graphique : ce qu'on voit, ce qu'il faut en retenir, la limite principale.
// « À retenir » et « Attention » sont calculés à partir des données (lib/immobilierBdnbTextes.ts) ; absents s'ils sont null.

function Ligne({ titre, texte, fort = false }: { titre: string; texte: string; fort?: boolean }) {
  return (
    <p className={fort ? 'text-gray-900' : 'text-gray-600'}>
      <span className="font-semibold text-gray-900">{titre}. </span>
      {texte}
    </p>
  );
}

export default function Lecture({
  voir,
  retenir,
  attention,
}: {
  voir: string;
  retenir?: string | null;
  attention?: string | null;
}) {
  return (
    <div className="mb-3 space-y-1.5 text-sm">
      <Ligne titre="Ce que vous voyez" texte={voir} />
      {retenir && <Ligne titre="À retenir" texte={retenir} fort />}
      {attention && <Ligne titre="Attention" texte={attention} />}
    </div>
  );
}
