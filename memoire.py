"""Rédaction du mémoire technique, calée sur la notation du règlement de la consultation.

Méthode (celle du pôle) :
1. extraire les critères et sous-critères notés du RC ;
2. construire le plan à partir de ces critères (modifiable) ;
3. rédiger chaque partie à partir du CCTP, des études et de la fiche du client ;
4. marquer [À COMPLÉTER : …] tout élément manquant, ne rien inventer ;
5. noter le mémoire « à blanc » comme le ferait la commission.
"""

import re

P8A_CRITERES = """Tu es un expert de la commande publique française. Lis les pièces ci-dessous
(surtout le règlement de la consultation) et extrais la grille de notation des offres.

Réponds UNIQUEMENT par un objet JSON valide (sans texte autour), avec ces clés :
{{
 "criteres": [
   {{"code": "1", "intitule": "Valeur technique", "points": 50, "est_prix": false,
     "sous_criteres": [
       {{"code": "1.1", "intitule": "Compréhension du projet et de ses contraintes", "points": 20,
         "attendus": "ce que l'acheteur dit apprécier pour ce sous-critère, avec ses mots exacts"}}
     ]}}
 ],
 "cadre_impose": "titre du cadre de réponse imposé s'il existe, sinon vide",
 "limite_pages": "limite de pages ou de format du mémoire si elle existe, sinon vide",
 "pieces_offre": ["liste des pièces de l'offre exigées par le RC (mémoire, note méthodologique, planning…)"],
 "sources": "pièces et pages utilisées"
}}

Règles :
- Recopie les intitulés et les points exactement comme dans le RC. "points" est un nombre
  (pondération en % ou en points), null si absent.
- "est_prix" vaut true pour le critère prix.
- Un critère sans sous-critère a une liste "sous_criteres" vide et ses "attendus" au niveau
  du critère (ajoute la clé "attendus").
- Si un cadre de réponse est imposé, ses rubriques priment : mets-les comme sous-critères.
- N'invente aucun critère. Si la grille est introuvable, renvoie "criteres": [].

PIÈCES :
{documents}
"""

P8B_SECTION = """Tu rédiges une partie du mémoire technique du candidat {nom_client} pour le
marché suivant : {objet}.

PARTIE À RÉDIGER : « {titre} »
Critère noté : {critere} ({points} points)
Ce que l'acheteur apprécie (mots du RC) : {attendus}
Consigne du rédacteur : {consigne}

Méthode à suivre :
- Montre d'abord que tu as compris le besoin : reprends les mots exacts de l'acheteur
  (CCTP, études, RC) et les données précises du dossier (sites, quantités, montants, délais,
  contraintes). Cite l'article ou la page du DCE quand tu reprends une donnée.
- Réponds à TOUS les attendus listés, dans l'ordre, avec un intertitre (###) par attendu
  quand c'est utile.
- Utilise des tableaux Markdown quand ils clarifient (contraintes / réponse, phases /
  actions / livrables, rôle / nom / qualification…).
- Phrases courtes. Chaque engagement est relié à la façon de le tenir (moyen, méthode,
  personne). Pas de superlatifs ni de formules creuses.
- Pour le candidat, utilise EXCLUSIVEMENT les éléments du dossier client ci-dessous
  (fiche, CV, références, moyens, ancien mémoire en cas de renouvellement : reprends ses
  preuves en les actualisant). Tout élément du candidat absent du dossier s'écrit
  [À COMPLÉTER : ce qu'il faut fournir]. N'invente aucun nom, chiffre, délai, référence
  ou moyen du candidat.
- Un choix qui engage le candidat (délai, prix, sous-traitance, engagement) s'écrit
  [À VALIDER : proposition].
- N'écris pas le titre de la partie (il est ajouté automatiquement). Commence directement
  par le texte.
- Termine par une dernière ligne qui commence exactement par « SOURCES : » et liste les
  pièces et pages utilisées (cette ligne ne sera pas mise dans le mémoire).

DOSSIER CLIENT :
{fiche_client}

PIÈCES DU DCE :
{documents}
"""

P8C_NOTATION = """Rôle : membre sévère de la commission d'analyse des offres de l'acheteur.

Grille de notation :
{grille}

Mémoire technique du candidat :
{memoire}

Pour chaque critère et sous-critère, donne sous forme de tableau Markdown :
| Critère | Note probable | Justification | Ce qui manque pour la note maximale |
Utilise le barème du RC s'il figure dans la grille, sinon une note sur 5.
Puis liste : les affirmations non prouvées, les risques de non-conformité, et termine par
« Cinq corrections prioritaires » (liste numérotée). Les cases [À COMPLÉTER] comptent comme
absentes : signale-les.
"""

ORDRE_CORPUS = ["RC", "CCTP", "Annexe", "Autre", "Cadre de réponse", "CCAP", "Avis", "AE", "DPGF", "BPU", "DQE"]


def plan_depuis_criteres(grille: dict) -> list:
    """Une partie par sous-critère technique (ou par critère sans sous-critère). Le prix est exclu."""
    plan = []
    for critere in grille.get("criteres") or []:
        if critere.get("est_prix"):
            continue
        sous = critere.get("sous_criteres") or []
        if sous:
            for s in sous:
                plan.append({"Titre": s.get("intitule", ""), "Critère": f"{s.get('code', '')} {s.get('intitule', '')}".strip(),
                             "Points": s.get("points"), "Attendus": s.get("attendus", ""), "Consigne": ""})
        else:
            plan.append({"Titre": critere.get("intitule", ""),
                         "Critère": f"{critere.get('code', '')} {critere.get('intitule', '')}".strip(),
                         "Points": critere.get("points"), "Attendus": critere.get("attendus", ""), "Consigne": ""})
    return plan


def separer_sources(texte: str) -> tuple:
    """Renvoie (texte sans la ligne SOURCES, sources)."""
    lignes = (texte or "").rstrip().splitlines()
    sources = ""
    while lignes and not lignes[-1].strip():
        lignes.pop()
    if lignes and re.match(r"^\W*SOURCES\s*:", lignes[-1].strip(), re.I):
        sources = re.sub(r"^\W*SOURCES\s*:\s*", "", lignes.pop().strip(), flags=re.I)
    return "\n".join(lignes).strip(), sources


def corpus_memoire(pieces: list, budget: int) -> str:
    """Pièces triées pour la rédaction : RC et CCTP d'abord, puis études et annexes."""
    tries = sorted(pieces, key=lambda p: ORDRE_CORPUS.index(p.type) if p.type in ORDRE_CORPUS else 99)
    morceaux, total = [], 0
    for p in tries:
        reste = budget - total
        if reste <= 0:
            break
        morceaux.append(f"===== {p.nom} ({p.type}) =====\n{p.texte[:reste]}")
        total += min(len(p.texte), reste)
    return "\n\n".join(morceaux)


def grille_texte(grille: dict) -> str:
    lignes = []
    for c in grille.get("criteres") or []:
        lignes.append(f"- {c.get('code', '')} {c.get('intitule', '')} : {c.get('points')} points"
                      + (f" — {c['attendus']}" if c.get("attendus") else ""))
        for s in c.get("sous_criteres") or []:
            lignes.append(f"  - {s.get('code', '')} {s.get('intitule', '')} : {s.get('points')} points — "
                          f"{s.get('attendus', '')}")
    return "\n".join(lignes)


def compter_a_completer(texte: str) -> int:
    return len(re.findall(r"\[À (?:COMPLÉTER|VALIDER)", texte or ""))
