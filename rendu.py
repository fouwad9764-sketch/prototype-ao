"""Compte rendu au client : un document qui récapitule chaque action réalisée,
selon les prestations commandées (celles cochées dans le devis)."""

from matrice import compter

# Ce que chaque prestation du catalogue fait apparaître dans le compte rendu.
CONTENU_PRESTATION = {
    "veille": ["avis"],
    "qualification": ["avis", "dce", "fiche_flash", "type", "go_no_go", "matrice"],
    "réponse complète": ["avis", "dce", "fiche_flash", "type", "go_no_go", "exigences", "matrice", "checklist",
                         "dc1_dc2", "memoire", "mails", "depot"],
    "mémoire": ["memoire", "notation"],
    "dépôt": ["checklist", "depot"],
    "suivi": ["suivi"],
}


def blocs_pour(prestation: str) -> list:
    nom = prestation.lower()
    for cle, blocs in CONTENU_PRESTATION.items():
        if cle in nom:
            return blocs
    return ["libre"]


def _fait(ok: bool, texte: str) -> str:
    return f"- {'✔' if ok else '☐'} {texte}"


P11_SYNTHESE_CLIENT = """Rôle : responsable du Pôle Marchés Publics de Sola Conseils. Rédige la
SYNTHÈSE destinée au client {client}, en tête de son compte rendu. Il est chef d'entreprise,
pas juriste : il doit comprendre en deux minutes où en est son dossier et ce qu'il doit faire.

Format Markdown, une page maximum, exactement ces parties :
### Le marché en bref
Tableau | Élément | Information | avec : acheteur, objet, type et phase de la procédure (ex. phase
candidature seulement), date et heure limite (heure locale de l'acheteur), durée et montant si
connus.
### Notre recommandation
Une ligne en gras : « Candidater », « Candidater sous conditions » ou « Ne pas candidater », puis
2 à 4 raisons courtes, factuelles et formulées positivement pour le client. Si des conditions
existent, liste-les.
### Ce qui est prêt
Liste courte de ce que le pôle a déjà réalisé.
### Ce que nous attendons de vous
Liste numérotée des pièces et informations à fournir, avec la date de retour si elle est connue.
Si rien n'est attendu, écris-le.
### Prochaines étapes
3 à 5 étapes datées jusqu'au dépôt (et au-delà si la procédure le prévoit).

Règles :
- Ton professionnel, clair et bienveillant. Pas de jargon interne : pas de notes sur 5,
  pas d'« arguments contre », pas de spéculation sur les concurrents ou sur les prix.
- Recopie les dates, montants et références exactement tels qu'écrits ci-dessous. N'invente
  rien ; si une information manque, ne la mentionne pas.
- La recommandation reprend celle de l'analyse go/no-go si elle existe ; sinon écris
  « Recommandation en cours d'analyse ».

PRESTATIONS : {prestations}
DATE DU JOUR : {date}

FICHE FLASH DU MARCHÉ :
{fiche_flash}

ANALYSE GO/NO-GO (interne) :
{go_no_go}

POINTS À TRAITER (matrice de conformité) :
{points}

PIÈCES ENCORE ATTENDUES DU CLIENT :
{attendues}

INFORMATIONS DU RESPONSABLE (dépôt, prochaines étapes) :
{infos}
"""


def donnees_synthese(etat: dict, prestations: list, infos: dict) -> dict:
    """Prépare les éléments envoyés à l'IA pour la synthèse client."""
    matrice = etat.get("matrice") or []
    points = [f"- {l.get('Exigence', '')} ({l.get('Statut')}) : {l.get('Écart et action', '')}"
              for l in matrice if l.get("Statut") in ("NON CONFORME", "PARTIEL")]
    attendues = []
    for dem in etat.get("demandes") or []:
        for e in dem.get("elements", []):
            if not e.get("recu"):
                attendues.append(f"- {e['libelle']} (retour demandé le {dem.get('date_retour')})")
    if not attendues:
        attendues = [f"- {l.get('Exigence', '')}" for l in (etat.get("checklist") or [])
                     if not l.get("Fait") and l.get("Qui") == "Client"]
    return {"client": infos.get("client", ""), "prestations": ", ".join(prestations), "date": infos.get("date", ""),
            "fiche_flash": etat.get("fiche_flash") or "non disponible",
            "go_no_go": etat.get("go_no_go") or "non réalisée",
            "points": "\n".join(points) or "aucun", "attendues": "\n".join(attendues) or "aucune",
            "infos": "\n".join(f"{k} : {v}" for k, v in (("Dépôt", infos.get("depot")),
                                                         ("Prochaines étapes", infos.get("suite"))) if v) or "aucune"}


def sections_compte_rendu(etat: dict, prestations: list, infos: dict, detail: bool = True) -> list:
    """Renvoie une liste de (titre, markdown) pour export Word.
    detail=False : uniquement les actions réalisées (l'analyse détaillée n'est pas transmise)."""
    tm = etat.get("type_marche") or {}
    pieces = etat.get("pieces") or []
    matrice = etat.get("matrice") or []
    checklist = etat.get("checklist") or []
    sections_memoire = etat.get("memoire_sections") or {}
    chronos = etat.get("chronos") or []

    synthese = [f"**Client :** {infos.get('client', '')}",
                f"**Marché :** {tm.get('objet') or infos.get('dossier', '')}",
                f"**Acheteur :** {tm.get('acheteur') or '—'}",
                f"**Date limite de remise :** {tm.get('date_limite') or '—'}"
                + (f" ({tm['fuseau']})" if tm.get("fuseau") else ""),
                f"**Prestations couvertes :** {', '.join(prestations) or '—'}",
                f"**Compte rendu établi le :** {infos.get('date', '')} par {infos.get('auteur', '')}"]
    if infos.get("synthese"):
        entete_cr = [f"**Client :** {infos.get('client', '')}",
                     f"**Prestations couvertes :** {', '.join(prestations) or '—'}",
                     f"**Compte rendu établi le :** {infos.get('date', '')} par {infos.get('auteur', '')}"]
        sortie = [("Synthèse", "\n\n".join(entete_cr) + ("\n\n" + infos["message"] if infos.get("message") else "")
                   + "\n\n" + infos["synthese"])]
    else:
        sortie = [("Synthèse", "\n\n".join(synthese) + ("\n\n" + infos["message"] if infos.get("message") else ""))]

    deja = set()
    for prestation in prestations:
        actions, contenu = [], []
        for bloc in blocs_pour(prestation):
            if bloc == "avis":
                actions.append(_fait(bool(tm), "Identification et qualification de l'avis de marché"))
                if tm and "avis" not in deja:
                    contenu.append("| Caractéristique | Valeur |\n|---|---|\n" + "\n".join(
                        f"| {lib} | {tm.get(cle) or '—'} |" for lib, cle in (
                            ("Nature", "nature"), ("Procédure", "procedure"), ("Forme", "forme"),
                            ("Lots", "nb_lots"), ("Montant estimé", "montant_estime"), ("Durée", "duree"),
                            ("Date limite", "date_limite"))))
            elif bloc == "dce":
                actions.append(_fait(bool(pieces), f"Lecture du dossier de consultation ({len(pieces)} pièces)"))
                if pieces and "dce" not in deja:
                    contenu.append("**Pièces analysées :** " + ", ".join(f"{p.nom} ({p.type})" for p in pieces))
            elif bloc == "fiche_flash":
                actions.append(_fait(bool(etat.get("fiche_flash")), "Fiche de synthèse du marché (fiche flash)"))
                if etat.get("fiche_flash") and "fiche_flash" not in deja:
                    contenu.append("### Fiche flash\n\n" + etat["fiche_flash"])
            elif bloc == "type":
                est = tm.get("estimation") or {}
                actions.append(_fait(bool(est), "Estimation de la charge de travail"
                                     + (f" : {est['total']:g} h, dossier {est['niveau'].lower()}" if est else "")))
            elif bloc == "go_no_go":
                actions.append(_fait(bool(etat.get("go_no_go")), "Analyse go/no-go (opportunité de candidater)"))
                if etat.get("go_no_go") and "go_no_go" not in deja:
                    contenu.append("### Analyse go/no-go\n\n" + etat["go_no_go"])
            elif bloc == "exigences":
                actions.append(_fait(bool(etat.get("exigences")), "Extraction des exigences du DCE"))
            elif bloc == "matrice":
                actions.append(_fait(bool(matrice), "Matrice de conformité : exigences face à vos capacités"))
                if matrice and "matrice" not in deja:
                    comptes = compter(matrice)
                    contenu.append("### Conformité de votre dossier\n\n| Statut | Nombre |\n|---|---|\n" + "\n".join(
                        f"| {s} | {n} |" for s, n in comptes.items() if n))
                    ecarts = [l for l in matrice if l.get("Statut") in ("NON CONFORME", "PARTIEL")]
                    if ecarts:
                        contenu.append("**Points à traiter :**\n\n" + "\n".join(
                            f"- **{l.get('Exigence', '')}** ({l.get('Statut')}) : {l.get('Écart et action', '')}"
                            for l in ecarts))
            elif bloc == "checklist":
                faits = sum(1 for l in checklist if l.get("Fait"))
                actions.append(_fait(bool(checklist) and faits == len(checklist),
                                     f"Check-list de candidature ({faits} / {len(checklist)} éléments réunis)"))
                restants = [l for l in checklist if not l.get("Fait")]
                if restants and "checklist" not in deja:
                    contenu.append("**Éléments restant à fournir ou à traiter :**\n\n" + "\n".join(
                        f"- {l.get('Exigence', '')} ({l.get('Qui', '')})" for l in restants))
            elif bloc == "dc1_dc2":
                actions.append(_fait(bool(etat.get("dc1_dc2")), "Préparation des formulaires de candidature DC1 / DC2"))
            elif bloc == "memoire":
                rediges = [t for t, v in sections_memoire.items() if (v or "").strip()]
                actions.append(_fait(bool(rediges), f"Rédaction du mémoire technique ({len(rediges)} partie(s))"))
                if rediges and "memoire" not in deja:
                    contenu.append("**Plan du mémoire rédigé :**\n\n" + "\n".join(f"- {t}" for t in rediges))
            elif bloc == "notation":
                actions.append(_fait(bool(etat.get("memoire_notation")), "Relecture critique (notation à blanc)"))
            elif bloc == "mails":
                for m in etat.get("journal_mails") or []:
                    actions.append(_fait(True, f"E-mail envoyé le {m.get('Date')} : {m.get('Objet')}"))
            elif bloc == "depot":
                depot = infos.get("depot") or ""
                actions.append(_fait(bool(depot), "Dépôt dématérialisé de l'offre" + (f" : {depot}" if depot else "")))
            elif bloc == "suivi":
                actions.append(_fait(bool(infos.get("suivi")), "Suivi de l'exécution du marché"))
                if infos.get("suivi"):
                    contenu.append(infos["suivi"])
            elif bloc == "libre":
                actions.append(_fait(True, "Prestation réalisée (détail ci-dessous)"))
            deja.add(bloc)
        texte = "**Actions réalisées**\n\n" + "\n".join(dict.fromkeys(actions))
        if contenu and detail:
            texte += "\n\n" + "\n\n".join(contenu)
        sortie.append((prestation, texte))

    if chronos and detail:
        sortie.append(("Journal de la démarche", "| Date | Étape |\n|---|---|\n" + "\n".join(
            f"| {c.get('Heure', '')} | {c.get('Étape', '')} |" for c in chronos)))
    if infos.get("suite") and not infos.get("synthese"):
        sortie.append(("Prochaines étapes", infos["suite"]))
    return sortie
