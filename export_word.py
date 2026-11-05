"""Conversion du Markdown produit par l'IA en document Word (.docx)."""

import io
import re
from datetime import date

from docx import Document
from docx.shared import Cm, Pt


def _texte_avec_gras(paragraphe, texte: str) -> None:
    """Ajoute du texte en gérant le **gras** Markdown et en surlignant les [À COMPLÉTER : …]."""
    from docx.enum.text import WD_COLOR_INDEX
    for i, morceau in enumerate(re.split(r"\*\*(.+?)\*\*", texte)):
        if not morceau:
            continue
        for bout in re.split(r"(\[À (?:COMPLÉTER|VALIDER)[^\]]*\])", morceau):
            if not bout:
                continue
            run = paragraphe.add_run(bout)
            run.bold = i % 2 == 1 or bout.startswith("[À ")
            if bout.startswith("[À "):
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _ajouter_tableau(doc, lignes: list) -> None:
    rangees = []
    for ligne in lignes:
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cellules if c):
            continue  # ligne de séparation |---|---|
        rangees.append(cellules)
    if not rangees:
        return
    nb_col = max(len(r) for r in rangees)
    table = doc.add_table(rows=0, cols=nb_col)
    table.style = "Table Grid"
    for r_index, rangee in enumerate(rangees):
        cells = table.add_row().cells
        for c_index in range(nb_col):
            valeur = rangee[c_index] if c_index < len(rangee) else ""
            para = cells[c_index].paragraphs[0]
            _texte_avec_gras(para, valeur.replace("<br>", "\n"))
            if r_index == 0:
                for run in para.runs:
                    run.bold = True
    doc.add_paragraph()


NOTE_DEFAUT = ("Document généré le {date} par l'outil d'analyse Sola Conseil. Brouillon à vérifier : "
               "chaque information doit être contrôlée dans les pièces du DCE avant usage.")


def markdown_vers_docx(sections: list, titre: str, note: str | None = NOTE_DEFAUT, logo: str | None = None,
                       saut_de_page: bool = True, sous_titre: str = "") -> bytes:
    """sections = liste de (titre_section, texte_markdown). Renvoie le fichier Word en octets."""
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    if logo:
        try:
            doc.add_picture(logo, width=Cm(3))
        except Exception:
            pass
    doc.add_heading(titre, level=0)
    if sous_titre:
        _texte_avec_gras(doc.add_paragraph(), sous_titre)
    if note:
        para = doc.add_paragraph(note.format(date=date.today().strftime('%d/%m/%Y')))
        for run in para.runs:
            run.italic = True

    for titre_section, texte in sections:
        if saut_de_page:
            doc.add_page_break()
        doc.add_heading(titre_section, level=1)
        tampon_tableau = []
        for ligne in texte.splitlines() + [""]:
            if ligne.strip().startswith("|"):
                tampon_tableau.append(ligne)
                continue
            if tampon_tableau:
                _ajouter_tableau(doc, tampon_tableau)
                tampon_tableau = []
            brut = ligne.strip()
            if not brut or re.fullmatch(r"[-*_]{3,}", brut):
                continue
            titre_md = re.match(r"^(#{1,4})\s+(.*)", brut)
            if titre_md:
                niveau = min(len(titre_md.group(1)) + 1, 4)
                doc.add_heading(titre_md.group(2).strip("# ").replace("**", ""), level=niveau)
            elif re.match(r"^[-*•]\s+", brut):
                _texte_avec_gras(doc.add_paragraph(style="List Bullet"),
                                 re.sub(r"^[-*•]\s+", "", brut))
            elif re.match(r"^\d+[.)]\s+", brut):
                _texte_avec_gras(doc.add_paragraph(style="List Number"),
                                 re.sub(r"^\d+[.)]\s+", "", brut))
            else:
                _texte_avec_gras(doc.add_paragraph(), brut)

    tampon = io.BytesIO()
    doc.save(tampon)
    return tampon.getvalue()
