"""Devis du pôle : catalogue des prestations, calcul des totaux et export PDF."""

import io
import os
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TURQUOISE = colors.HexColor("#00788A")
MARINE = colors.HexColor("#004269")

COLONNES = ["Prestation", "Description", "Unité", "Prix unitaire HT"]
UNITES = ["forfait", "mois", "heure", "jour", "% du marché attribué"]

# Prix à 0 : c'est la direction qui fixe les tarifs dans l'application (Administration).
CATALOGUE_DEFAUT = [
    {"Prestation": "Veille ciblée des marchés", "Unité": "mois", "Prix unitaire HT": 0.0,
     "Description": "Recherche quotidienne des avis correspondant au client sur les plateformes, alerte par e-mail."},
    {"Prestation": "Qualification et go/no-go", "Unité": "forfait", "Prix unitaire HT": 0.0,
     "Description": "Analyse du DCE, fiche flash, matrice de conformité, recommandation go/no-go."},
    {"Prestation": "Réponse complète – dossier simple", "Unité": "forfait", "Prix unitaire HT": 0.0,
     "Description": "Candidature, mémoire technique, offre financière et dépôt (charge estimée < 15 h)."},
    {"Prestation": "Réponse complète – dossier moyen", "Unité": "forfait", "Prix unitaire HT": 0.0,
     "Description": "Candidature, mémoire technique, offre financière et dépôt (charge estimée 15 à 30 h)."},
    {"Prestation": "Réponse complète – dossier complexe", "Unité": "forfait", "Prix unitaire HT": 0.0,
     "Description": "Candidature, mémoire technique, offre financière et dépôt (charge estimée > 30 h)."},
    {"Prestation": "Rédaction ou mise à jour du mémoire technique", "Unité": "forfait", "Prix unitaire HT": 0.0,
     "Description": "Mémoire adapté aux critères du règlement de la consultation."},
    {"Prestation": "Dépôt du dossier", "Unité": "forfait", "Prix unitaire HT": 0.0,
     "Description": "Dépôt dématérialisé sur le profil d'acheteur, accusé de réception."},
    {"Prestation": "Suivi pendant l'exécution du marché", "Unité": "mois", "Prix unitaire HT": 0.0,
     "Description": "Suivi administratif : ordres de service, situations, avenants, réception."},
    {"Prestation": "Prime de succès", "Unité": "% du marché attribué", "Prix unitaire HT": 0.0,
     "Description": "Due uniquement si le marché est attribué au client."},
]

INFOS_DEFAUT = {
    "emetteur": "Sola Conseils\nAdresse à compléter\nSIRET à compléter\nTéléphone – e-mail à compléter",
    "taux_tva": 0.0,
    "mention_tva": "TVA non applicable, article 294 du CGI (Mayotte).",
    "validite_jours": 30,
    "conditions": "Paiement à 30 jours à réception de facture. Prime de succès facturée à la notification "
                  "du marché au client.",
}

NIVEAU_VERS_LIGNE = {"Simple": "Réponse complète – dossier simple",
                     "Moyen": "Réponse complète – dossier moyen",
                     "Complexe": "Réponse complète – dossier complexe"}


def est_variable(ligne: dict) -> bool:
    return "%" in str(ligne.get("Unité", ""))


def _nombre(valeur) -> float:
    try:
        return float(str(valeur).replace(",", ".").replace(" ", "") or 0)
    except ValueError:
        return 0.0


def calculer(lignes: list, taux_tva: float) -> dict:
    """lignes : dicts avec Prestation, Unité, Quantité, Prix unitaire HT."""
    total_ht = sum(_nombre(l.get("Quantité")) * _nombre(l.get("Prix unitaire HT"))
                   for l in lignes if not est_variable(l))
    tva = round(total_ht * _nombre(taux_tva) / 100, 2)
    return {"total_ht": round(total_ht, 2), "tva": tva, "total_ttc": round(total_ht + tva, 2)}


def euros(montant: float) -> str:
    entier, decimales = f"{montant:,.2f}".split(".")
    return entier.replace(",", " ") + "," + decimales + " €"


def numero_devis(aujourd_hui: date | None = None, rang: int = 1) -> str:
    return f"DEV-{(aujourd_hui or date.today()).strftime('%Y%m%d')}-{rang:02d}"


def _p(texte: str, style) -> Paragraph:
    propre = (str(texte or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
              .replace("\n", "<br/>"))
    return Paragraph(propre, style)


def vers_pdf(infos: dict, lignes: list, logo: str | None = None) -> bytes:
    """infos : numero, date, validite_jours, emetteur, client_nom, client_adresse, objet,
    taux_tva, mention_tva, conditions, charge (texte facultatif)."""
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"Devis {infos.get('numero', '')}", author="Sola Conseils")
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12)
    gras = ParagraphStyle("g", parent=normal, fontName="Helvetica-Bold")
    titre = ParagraphStyle("t", parent=normal, fontName="Helvetica-Bold", fontSize=18, leading=22,
                           textColor=MARINE)
    droite = ParagraphStyle("d", parent=normal, alignment=TA_RIGHT)
    petit = ParagraphStyle("p", parent=normal, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
    entete_tab = ParagraphStyle("e", parent=gras, textColor=colors.white)

    elements = []
    gauche = []
    if logo and os.path.exists(logo):
        gauche.append(Image(logo, width=26 * mm, height=26 * mm, kind="proportional"))
    gauche.append(_p(infos.get("emetteur", ""), normal))
    date_devis = infos.get("date") or date.today()
    validite = date_devis + timedelta(days=int(_nombre(infos.get("validite_jours", 30))))
    bloc_titre = [_p("DEVIS", titre),
                  _p(f"N° {infos.get('numero', '')}", gras),
                  _p(f"Date : {date_devis.strftime('%d/%m/%Y')}", normal),
                  _p(f"Valable jusqu'au : {validite.strftime('%d/%m/%Y')}", normal)]
    entete = Table([[gauche, bloc_titre]], colWidths=[95 * mm, 79 * mm])
    entete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements += [entete, Spacer(1, 6 * mm)]

    client = Table([[[_p("Client", gras), _p(infos.get("client_nom", ""), normal),
                      _p(infos.get("client_adresse", ""), normal)]]], colWidths=[174 * mm])
    client.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, TURQUOISE),
                                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    elements += [client, Spacer(1, 4 * mm)]
    if infos.get("objet"):
        objet = str(infos["objet"]).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        elements.append(Paragraph("<b>Objet :</b> " + objet, normal))
    if infos.get("charge"):
        elements.append(_p(infos["charge"], petit))
    elements.append(Spacer(1, 4 * mm))

    donnees = [[_p(t, entete_tab) for t in ("Prestation", "Qté", "Unité", "Prix unitaire HT", "Montant HT")]]
    variables = []
    for l in lignes:
        if est_variable(l):
            variables.append(l)
            continue
        qte, pu = _nombre(l.get("Quantité")), _nombre(l.get("Prix unitaire HT"))
        libelle = [_p(l.get("Prestation", ""), gras)]
        if l.get("Description"):
            libelle.append(_p(l["Description"], petit))
        donnees.append([libelle, _p(f"{qte:g}".replace(".", ","), droite), _p(l.get("Unité", ""), normal),
                        _p(euros(pu), droite), _p(euros(qte * pu), droite)])
    tableau = Table(donnees, colWidths=[82 * mm, 14 * mm, 22 * mm, 28 * mm, 28 * mm], repeatRows=1)
    tableau.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TURQUOISE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F8F9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    elements += [tableau, Spacer(1, 3 * mm)]

    totaux = calculer(lignes, infos.get("taux_tva", 0))
    lignes_totaux = [["Total HT", euros(totaux["total_ht"])]]
    if _nombre(infos.get("taux_tva")) > 0:
        lignes_totaux += [[f"TVA {_nombre(infos['taux_tva']):g} %".replace(".", ","), euros(totaux["tva"])],
                          ["Total TTC", euros(totaux["total_ttc"])]]
    else:
        lignes_totaux += [["Net à payer", euros(totaux["total_ht"])]]
    bloc = Table([[_p(a, gras), _p(b, droite)] for a, b in lignes_totaux], colWidths=[40 * mm, 34 * mm],
                 hAlign="RIGHT")
    bloc.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 1, MARINE),
                              ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E6F2F4"))]))
    elements.append(bloc)
    if _nombre(infos.get("taux_tva")) == 0 and infos.get("mention_tva"):
        elements.append(_p(infos["mention_tva"], ParagraphStyle("m", parent=petit, alignment=TA_RIGHT)))

    if variables:
        elements += [Spacer(1, 5 * mm), _p("Rémunération variable", gras)]
        for l in variables:
            taux = f"{_nombre(l.get('Prix unitaire HT')):g}".replace(".", ",")
            elements.append(_p(f"• {l.get('Prestation', '')} : {taux} % du montant HT du marché attribué au "
                               f"client. {l.get('Description', '')}", normal))

    if infos.get("conditions"):
        elements += [Spacer(1, 5 * mm), _p("Conditions", gras), _p(infos["conditions"], normal)]

    signature = Table([[[_p("Pour Sola Conseils", gras), Spacer(1, 18 * mm)],
                        [_p("Bon pour accord – le client", gras),
                         _p("Date, nom, signature et cachet", petit), Spacer(1, 14 * mm)]]],
                      colWidths=[87 * mm, 87 * mm])
    signature.setStyle(TableStyle([("BOX", (1, 0), (1, 0), 0.6, colors.HexColor("#999999")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    elements += [Spacer(1, 8 * mm), signature]
    doc.build(elements)
    return tampon.getvalue()
