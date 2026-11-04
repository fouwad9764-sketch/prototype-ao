"""Lecture des pièces du DCE : PDF, Word, Excel, texte et archives ZIP."""

import io
import re
import zipfile
from dataclasses import dataclass, field

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

EXTENSIONS = (".pdf", ".docx", ".xlsx", ".txt")
EXT_PHOTOS = (".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".bmp", ".gif", ".webp")
EXT_PLANS = (".dwg", ".dxf", ".dwf", ".rvt", ".ifc", ".skp")
MOTS_PLANS = ("plan", "plans", "coupe", "coupes", "facade", "façade", "facades", "façades",
              "elevation", "élévation", "implantation", "masse", "synoptique", "schema", "schéma")
FORMAT_PLAN_PT = 1300  # côté de page (en points) au-delà duquel on considère un plan (> A3)
NON_ANALYSE = "Plan ou photo : non analysé par l'IA, à consulter manuellement."


@dataclass
class Piece:
    nom: str
    texte: str
    alertes: list = field(default_factory=list)

    @property
    def nb_caracteres(self) -> int:
        return len(self.texte)


OCR_PAGES_MAX = 40   # au-delà, la lecture des scans devient trop longue en ligne
SEUIL_PAGE_VIDE = 50  # caractères en dessous desquels une page est considérée comme scannée


def ocr_disponible() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_page(data: bytes, numero: int) -> str:
    """Reconnaissance du texte d'une page de PDF scannée (français)."""
    import pytesseract
    from pdf2image import convert_from_bytes
    images = convert_from_bytes(data, dpi=200, first_page=numero, last_page=numero)
    return "\n".join(pytesseract.image_to_string(img, lang="fra") for img in images).strip()


def _est_nom_de_plan(nom: str) -> bool:
    mots = set(re.split(r"[^a-z0-9éèêàç]+", nom.lower().rsplit(".", 1)[0]))
    return bool(mots & set(MOTS_PLANS))


def _lire_pdf(data: bytes, nom: str) -> Piece:
    lecteur = PdfReader(io.BytesIO(data))
    pages, alertes = [], []
    grand_format = [i for i, page in enumerate(lecteur.pages, start=1)
                    if max(float(page.mediabox.width), float(page.mediabox.height)) > FORMAT_PLAN_PT]
    tout_en_plan = _est_nom_de_plan(nom) or (lecteur.pages and len(grand_format) == len(lecteur.pages))
    if tout_en_plan:
        # Un plan : on garde seulement le texte déjà présent (cartouche, légendes), sans reconnaissance
        textes = [(p.extract_text() or "").strip() for p in lecteur.pages]
        piece = Piece(nom, "\n\n".join(f"[{nom} — planche {i}]\n{t}" for i, t in enumerate(textes, 1) if t),
                      [NON_ANALYSE])
        piece.est_plan = True
        return piece
    pages_scannees = [i for i, page in enumerate(lecteur.pages, start=1)
                      if len((page.extract_text() or "").strip()) < SEUIL_PAGE_VIDE and i not in grand_format]
    ocr_ok = bool(pages_scannees) and ocr_disponible()
    lues_ocr = 0
    for i, page in enumerate(lecteur.pages, start=1):
        contenu = (page.extract_text() or "").strip()
        if i in pages_scannees and ocr_ok and lues_ocr < OCR_PAGES_MAX:
            try:
                contenu = _ocr_page(data, i) or contenu
                lues_ocr += 1
            except Exception as exc:
                alertes.append(f"Page {i} : lecture du scan impossible ({exc}).")
        pages.append(f"[{nom} — page {i}]\n{contenu}")
    if grand_format:
        alertes.append(f"{len(grand_format)} page(s) grand format (plans) non lues par reconnaissance de texte.")
    if pages_scannees:
        if not ocr_ok:
            alertes.append(f"{len(pages_scannees)} page(s) scannée(s) non lue(s) : reconnaissance de texte indisponible.")
        else:
            alertes.append(f"{lues_ocr} page(s) scannée(s) lue(s) par reconnaissance de texte : à vérifier.")
            if len(pages_scannees) > OCR_PAGES_MAX:
                alertes.append(f"Seules les {OCR_PAGES_MAX} premières pages scannées ont été lues.")
    return Piece(nom, "\n\n".join(pages), alertes)


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
                    if not sous_nom or sous_nom.startswith(".") or "__MACOSX" in info.filename:
                        continue
                    if sous_nom.lower().endswith(EXTENSIONS + EXT_PHOTOS + EXT_PLANS + (".zip",)):
                        pieces.extend(lire_fichier(sous_nom, archive.read(info)))
                    else:
                        pieces.append(Piece(sous_nom, "", ["Format non géré : fichier listé mais non lu."]))
            return pieces
        if bas.endswith(EXT_PHOTOS) or bas.endswith(EXT_PLANS):
            return [Piece(nom, "", [NON_ANALYSE])]
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
    if nom.lower().endswith(EXT_PHOTOS):
        return "Photo"
    if nom.lower().endswith(EXT_PLANS) or _est_nom_de_plan(nom):
        return "Plan"
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
