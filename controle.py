"""Garde-fou contre les inventions de l'IA : repère dans un texte produit les années, dates,
références et montants qui n'existent nulle part dans les documents sources."""

import re

MOTIFS = [
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",                 # dates
    r"\b(?:19|20)\d{2}\b",                          # années
    r"\b[A-Z]{1,6}[-_/]?\d{2,}(?:[-_/][A-Z0-9]+)*\b",  # références type M001-2026, DAUF/13
    r"\b\d{1,3}(?:[ .  ]\d{3})+(?:,\d+)?\s?€",  # montants
]


def _normaliser(texte: str) -> str:
    return re.sub(r"[\s  .]", "", texte or "").lower()


def elements_absents(texte: str, sources: list, ignorer: tuple = ()) -> list:
    """Liste des éléments du texte introuvables dans les sources (dédoublonnée, dans l'ordre)."""
    base = _normaliser(" ".join(s or "" for s in sources))
    vus, absents = set(), []
    for motif in MOTIFS:
        for m in re.finditer(motif, texte or ""):
            brut = m.group(0).strip()
            cle = _normaliser(brut)
            if not cle or cle in vus or any(_normaliser(i) == cle for i in ignorer):
                continue
            vus.add(cle)
            variantes = {cle}
            d = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", brut)
            if d:
                j, mo, a = d.groups()
                annee = a if len(a) == 4 else "20" + a
                variantes |= {_normaliser(f"{int(j):02d}/{int(mo):02d}/{x}") for x in (annee, annee[2:])}
                variantes |= {_normaliser(f"{int(j)}/{int(mo)}/{x}") for x in (annee, annee[2:])}
            if "€" in brut:
                variantes.add(_normaliser(re.sub(r",\d+", "", brut).replace("€", "")))
            if not any(v in base for v in variantes):
                absents.append(brut)
    return absents
