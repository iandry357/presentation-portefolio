import sys
sys.path.insert(0, 'synthetic')
from pdf_generator import _faker, _styles, _page_contrat, _page_formulaire, _page_echeance

fk = _faker('fr')
styles = _styles('fr')

try:
    result = _page_contrat(fk, styles, 0)
    print('contrat p0 OK:', type(result))
except Exception as e:
    print('contrat p0 FAIL:', e)

try:
    result = _page_contrat(fk, styles, 1)
    print('contrat p1 OK:', type(result))
except Exception as e:
    print('contrat p1 FAIL:', e)

try:
    result = _page_formulaire(fk, styles, 0)
    print('formulaire p0 OK:', type(result))
except Exception as e:
    print('formulaire p0 FAIL:', e)

try:
    result = _page_echeance(fk, styles, 0)
    print('echeance p0 OK:', type(result))
except Exception as e:
    print('echeance p0 FAIL:', e)