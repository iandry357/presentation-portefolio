// CSV des tableaux de résultats : format « excel » comme les tableaux bruts (« ; », BOM UTF-8, virgule décimale)

export type CelluleCsv = string | number | null;

function echapper(valeur: CelluleCsv): string {
  const texte = valeur === null ? '' : typeof valeur === 'number' ? String(valeur).replace('.', ',') : valeur;
  return /[;"\r\n]/.test(texte) ? `"${texte.replace(/"/g, '""')}"` : texte;
}

export function telechargerCsv(nom: string, entetes: string[], lignes: CelluleCsv[][]) {
  const contenu = [entetes, ...lignes].map(ligne => ligne.map(echapper).join(';')).join('\r\n');
  const url = URL.createObjectURL(new Blob(['\ufeff', contenu], { type: 'text/csv;charset=utf-8' }));
  const lien = document.createElement('a');
  lien.href = url;
  lien.download = nom;
  lien.click();
  URL.revokeObjectURL(url);
}
