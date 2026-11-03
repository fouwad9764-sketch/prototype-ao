"""Lecture des pièces du DCE : PDF, Word, Excel, texte et archives ZIP."""

import io
import re
import zipfile
from dataclasses import dataclass, field

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

EXTENSIONS = (".pdf", ".docx", ".xlsx", ".txt")


@dataclass
class Piece:
    nom: str
    texte: str
    alertes: list = field(default_factory=list)

    @property
    def nb_caracteres(self) -> int:
        return len(self.texte)


def _lire_pdf(data: bytes, nom: str) -> Piece:
    lecteur = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(lecteur.pages, start=1):
        contenu = (page.extract_text() or "").strip()
        pages.append(f"[{nom} — page {i}]\n{contenu}")
    piece = Piece(nom, "\n\n".join(pages))
    # Peu de texte par page = probablement un scan (pas d'OCR dans cette version)
    if lecteur.pages and piece.nb_caracteres / len(lecteur.pages) < 100:
        piece.alertes.append("PDF probablement scanné : texte quasi absent (OCR non géré en v1).")
    return piece


def _lire_docx(data: bytes, nom: str) -> Piece:
    doc = Document(io.BytesIO(data))
    lignes = [p.text for p in doc.paragraphs if p.text.strip()]
    for t_index, table in enumerate(doc.tables, start=1):
        lignes.append(f"[Tableau {t_index}]")
        for row in table.rows:
            lignes.append(" | ".join(c.text.strip() for c in row.cells))
    return Piece(nom, f"[{nom}]\n" + "\n".join(lignes))


def _lire_xlsx(data: bytes, nom: str) -> Piece:
    classeur = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    lignes = []
    for feuille in classeur.worksheets:
        lignes.append(f"[{nom} — onglet {feuille.title}]")
        for row in feuille.iter_rows(values_only=True):
            cellules = [str(v) for v in row if v is not None]
            if cellules:
                lignes.append(" | ".join(cellules))
    return Piece(nom, "\n".join(lignes))


def lire_fichier(nom: str, data: bytes) -> list:
    """Renvoie la liste des pièces lues (une archive ZIP peut en contenir plusieurs)."""
    bas = nom.lower()
    try:
        if bas.endswith(".zip"):
            pieces = []
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for info in archive.infolist():
                    if info.is_dir() or info.file_size > 50_000_000:
                        continue
                    sous_nom = info.filename.split("/")[-1]
                    if sous_nom.lower().endswith(EXTENSIONS + (".zip",)):
                        pieces.extend(lire_fichier(sous_nom, archive.read(info)))
            return pieces
        if bas.endswith(".pdf"):
            return [_lire_pdf(data, nom)]
        if bas.endswith(".docx"):
            return [_lire_docx(data, nom)]
        if bas.endswith(".xlsx"):
            return [_lire_xlsx(data, nom)]
        if bas.endswith(".txt"):
            return [Piece(nom, f"[{nom}]\n" + data.decode("utf-8", errors="replace"))]
    except Exception as exc:  # fichier corrompu ou protégé
        return [Piece(nom, "", [f"Lecture impossible : {exc}"])]
    return [Piece(nom, "", ["Format non géré (formats acceptés : PDF, DOCX, XLSX, TXT, ZIP)."])]


def decouper(texte: str, taille: int = 60_000) -> list:
    """Découpe un long texte en morceaux, en coupant de préférence entre deux paragraphes."""
    morceaux, debut = [], 0
    while debut < len(texte):
        fin = min(debut + taille, len(texte))
        if fin < len(texte):
            coupure = texte.rfind("\n\n", debut, fin)
            if coupure > debut + taille // 2:
                fin = coupure
        morceaux.append(texte[debut:fin])
        debut = fin
    return morceaux


def deviner_type(nom: str) -> str:
    """Repère le type de pièce d'après son nom de fichier (RC, CCAP, CCTP...)."""
    bas = nom.lower().rsplit(".", 1)[0]
    mots = set(re.split(r"[^a-z0-9éèêà]+", bas))
    if "annexe" in mots:
        return "Annexe"
    regles = [
        ("Avis", {"aapc", "avis"}), ("CCAP", {"ccap"}), ("CCTP", {"cctp"}),
        ("RC", {"rc", "reglement", "règlement"}), ("AE", {"ae", "acte"}),
        ("BPU", {"bpu"}), ("DQE", {"dqe"}), ("DPGF", {"dpgf"}),
        ("Cadre de réponse", {"cadre", "memoire", "mémoire", "crt"}),
    ]
    for libelle, cles in regles:
        if mots & cles:
            return libelle
    return "Autre"
