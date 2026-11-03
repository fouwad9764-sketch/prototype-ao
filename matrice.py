"""Matrice de conformité : lecture des tableaux produits par l'IA et export Excel."""

import io
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

STATUTS = ["CONFORME", "PARTIEL", "NON CONFORME", "À VÉRIFIER"]
COULEURS = {"CONFORME": "C6EFCE", "PARTIEL": "FFEB9C", "NON CONFORME": "FFC7CE", "À VÉRIFIER": "DDEBF7"}
COLONNES_MATRICE = ["N°", "Exigence", "Source DCE", "Ce que le client apporte", "Statut",
                    "Preuve (document client)", "Écart et action"]


def _cellules(ligne: str) -> list:
    return [c.strip() for c in ligne.strip().strip("|").split("|")]


def _est_separateur(cellules: list) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cellules if c) and any(cellules)


def lignes_de_tableaux(markdown: str) -> list:
    """Renvoie les lignes de données (hors en-têtes et séparateurs) de tous les tableaux Markdown."""
    resultats, en_tete_vu = [], False
    for ligne in (markdown or "").splitlines():
        if not ligne.strip().startswith("|"):
            en_tete_vu = False
            continue
        cellules = _cellules(ligne)
        if _est_separateur(cellules):
            continue
        if not en_tete_vu:  # première ligne d'un tableau = en-tête
            en_tete_vu = True
            continue
        if any(cellules):
            resultats.append(cellules)
    return resultats


def normaliser_statut(texte: str) -> str:
    t = texte.upper().replace("**", "").strip()
    if "NON" in t and "CONFORME" in t:
        return "NON CONFORME"
    if "PARTIEL" in t:
        return "PARTIEL"
    if "VÉRIFIER" in t or "VERIFIER" in t:
        return "À VÉRIFIER"
    if "CONFORME" in t:
        return "CONFORME"
    return "À VÉRIFIER"


def lignes_matrice(markdown: str) -> list:
    """Transforme la sortie Markdown de l'IA en lignes de matrice (dictionnaires)."""
    lignes = []
    for cellules in lignes_de_tableaux(markdown):
        cellules = (cellules + [""] * len(COLONNES_MATRICE))[:len(COLONNES_MATRICE)]
        ligne = dict(zip(COLONNES_MATRICE, cellules))
        ligne["Statut"] = normaliser_statut(ligne["Statut"])
        lignes.append(ligne)
    return lignes


def compter(lignes: list) -> dict:
    return {s: sum(1 for l in lignes if l["Statut"] == s) for s in STATUTS}


def vers_markdown(lignes: list) -> str:
    entete = "| " + " | ".join(COLONNES_MATRICE) + " |"
    sep = "|" + "---|" * len(COLONNES_MATRICE)
    corps = ["| " + " | ".join(l[c].replace("|", "/") for c in COLONNES_MATRICE) + " |" for l in lignes]
    synthese = " · ".join(f"{s} : {n}" for s, n in compter(lignes).items())
    return f"Synthèse : {synthese}\n\n" + "\n".join([entete, sep] + corps)


def vers_excel(lignes: list, nom_client: str) -> bytes:
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Matrice"
    feuille.append(COLONNES_MATRICE)
    for cell in feuille[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="44546A")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for l in lignes:
        feuille.append([l[c].replace("<br>", "\n") for c in COLONNES_MATRICE])
        statut = feuille.cell(row=feuille.max_row, column=5)
        statut.fill = PatternFill("solid", fgColor=COULEURS[l["Statut"]])
        statut.font = Font(bold=True)
    for col, largeur in zip("ABCDEFG", [6, 45, 22, 40, 15, 28, 40]):
        feuille.column_dimensions[col].width = largeur
    for row in feuille.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    feuille.freeze_panes = "B2"
    feuille.auto_filter.ref = feuille.dimensions

    synthese = classeur.create_sheet("Synthèse")
    synthese.append(["Client", nom_client or "non renseigné"])
    synthese.append([])
    synthese.append(["Statut", "Nombre d'exigences"])
    for s, n in compter(lignes).items():
        synthese.append([s, n])
        synthese.cell(row=synthese.max_row, column=1).fill = PatternFill("solid", fgColor=COULEURS[s])
    synthese.append(["Total", len(lignes)])
    synthese.append([])
    synthese.append(["Brouillon généré par l'outil Sola Conseil : chaque statut est à valider par le chargé d'affaires."])
    synthese.column_dimensions["A"].width = 22
    synthese.column_dimensions["B"].width = 22
    for r in (1, 3):
        for cell in synthese[r]:
            cell.font = Font(bold=True)

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()
