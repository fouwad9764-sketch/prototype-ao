"""Suivi des demandes de pièces au client : relances planifiées et e-mails de confirmation.

Les e-mails de relance sont construits ici (sans IA) : ils reprennent uniquement les pièces
encore manquantes, avec un ton qui se renforce à l'approche de la date de retour.
Aucun envoi n'est fait sans le bouton « Envoyer » de l'utilisateur.
"""

import uuid
from datetime import date, datetime, timedelta

FORMAT_DATE = "%d/%m/%Y"
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _d(texte: str) -> date | None:
    try:
        return datetime.strptime(str(texte), FORMAT_DATE).date()
    except (TypeError, ValueError):
        return None


def jour_fr(d: date) -> str:
    return f"{JOURS[d.weekday()]} {d.strftime(FORMAT_DATE)}"


def nouvelle_demande(destinataire: str, objet: str, date_retour: date, elements: list,
                     date_limite_dossier: str = "", marche: str = "", par: str = "") -> dict:
    """elements : liste de libellés (pièce ou information à obtenir)."""
    return {"id": uuid.uuid4().hex[:8], "envoyee_le": date.today().strftime(FORMAT_DATE), "par": par,
            "destinataire": destinataire, "objet": objet, "marche": marche,
            "date_retour": date_retour.strftime(FORMAT_DATE), "date_limite_dossier": date_limite_dossier,
            "elements": [{"libelle": e, "recu": False} for e in elements if str(e).strip()],
            "relances": [], "close": False}


def manquants(demande: dict) -> list:
    return [e["libelle"] for e in demande.get("elements", []) if not e.get("recu")]


def calendrier(demande: dict) -> list:
    """Dates prévues des relances : 2 jours avant le retour, le jour du retour, le lendemain."""
    retour = _d(demande.get("date_retour"))
    envoi = _d(demande.get("envoyee_le")) or date.today()
    if not retour:
        return []
    prevues = [retour - timedelta(days=2), retour, retour + timedelta(days=1)]
    return [d for d in prevues if d > envoi]


def prochaine_relance(demande: dict, aujourd_hui: date | None = None) -> tuple:
    """Renvoie (rang 1-3, date prévue) de la prochaine relance, ou (None, None)."""
    if demande.get("close") or not manquants(demande):
        return None, None
    dates = calendrier(demande)
    rang = len(demande.get("relances", []))
    if rang >= len(dates):
        return None, None
    return rang + 1, dates[rang]


def relance_due(demande: dict, aujourd_hui: date | None = None) -> bool:
    rang, quand = prochaine_relance(demande)
    return bool(rang) and quand <= (aujourd_hui or date.today())


def texte_relance(demande: dict, rang: int, signature: str) -> tuple:
    """Renvoie (objet, corps) de la relance n° rang (1, 2 ou 3)."""
    retour = _d(demande.get("date_retour"))
    liste = "\n".join(f"- {m}" for m in manquants(demande))
    marche = demande.get("marche") or "le dossier en cours"
    limite = demande.get("date_limite_dossier")
    rappel_limite = f" La date limite de dépôt du dossier est fixée au {limite}." if limite else ""
    if rang == 1:
        objet = f"Rappel – Pièces attendues pour {marche}"
        intro = (f"Je me permets de revenir vers vous concernant {marche}. Pour rappel, nous avons besoin des "
                 f"éléments suivants d'ici le {jour_fr(retour)} :")
        fin = "Merci par avance, cela nous permettra de finaliser le dossier sereinement."
    elif rang == 2:
        objet = f"Relance – Pièces à transmettre aujourd'hui pour {marche}"
        intro = (f"Sauf erreur de ma part, les éléments suivants ne nous sont pas encore parvenus. "
                 f"Ils sont attendus aujourd'hui pour {marche} :")
        fin = "Pouvez-vous me les transmettre dans la journée, ou m'indiquer quand vous pourrez le faire ?"
    else:
        objet = f"URGENT – Pièces manquantes pour {marche}"
        intro = (f"Les éléments suivants manquent toujours et bloquent la finalisation de {marche}."
                 f"{rappel_limite} Sans eux, la candidature risque d'être incomplète :")
        fin = "Merci de me les envoyer au plus vite ou de m'appeler pour trouver une solution."
    corps = f"Bonjour,\n\n{intro}\n\n{liste}\n\n{fin}\n\nBien cordialement,\n\n{signature}"
    return objet, corps


def texte_confirmation_reception(demande: dict, signature: str) -> tuple:
    marche = demande.get("marche") or "le dossier"
    objet = f"Pièces bien reçues – {marche}"
    corps = (f"Bonjour,\n\nNous avons bien reçu l'ensemble des pièces demandées pour {marche}. Merci pour votre "
             f"réactivité. Nous finalisons le dossier et revenons vers vous avant le dépôt.\n\n"
             f"Bien cordialement,\n\n{signature}")
    return objet, corps


def texte_confirmation_depot(marche: str, acheteur: str, quand: str, accuse: str, signature: str) -> tuple:
    objet = f"Dossier déposé – {marche}"
    corps = (f"Bonjour,\n\nNous vous confirmons que votre dossier pour {marche}"
             + (f" ({acheteur})" if acheteur else "") + f" a bien été déposé le {quand}"
             + (f", accusé de réception n° {accuse}" if accuse else "") + ".\n\n"
             "Nous vous tiendrons informé dès que l'acheteur communiquera sa décision ou nous adressera une "
             "demande de complément.\n\nBien cordialement,\n\n" + signature)
    return objet, corps


def noter_relance(demande: dict, objet: str) -> None:
    demande.setdefault("relances", []).append({"date": datetime.now().strftime("%d/%m/%Y %H:%M"), "objet": objet})
