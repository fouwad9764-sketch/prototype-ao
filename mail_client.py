"""Préparation et envoi des e-mails du pôle (lien Mail ou envoi direct par SMTP)."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from urllib.parse import quote


def separer_objet(texte: str) -> tuple:
    """Sépare « Objet : … » du corps du message produit par l'IA."""
    lignes = texte.strip().splitlines()
    objet = ""
    if lignes and lignes[0].lower().replace("*", "").strip().startswith("objet"):
        objet = lignes[0].split(":", 1)[-1].replace("*", "").strip()
        lignes = lignes[1:]
    return objet, "\n".join(lignes).strip()


def lien_mailto(destinataire: str, objet: str, corps: str, copie: str = "") -> str:
    lien = f"mailto:{quote(destinataire)}?subject={quote(objet)}&body={quote(corps)}"
    if copie:
        lien += f"&cc={quote(copie)}"
    return lien


def smtp_configure(config: dict) -> bool:
    return all(config.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EXPEDITEUR"))


def envoyer(config: dict, destinataire: str, objet: str, corps: str, copie: str = "",
            pieces_jointes: list | None = None) -> str:
    """Envoie l'e-mail depuis la boîte du pôle. Renvoie l'identifiant du message."""
    msg = EmailMessage()
    msg["From"] = formataddr((config.get("NOM_EXPEDITEUR", ""), config["EXPEDITEUR"]))
    msg["To"] = destinataire
    if copie:
        msg["Cc"] = copie
    msg["Reply-To"] = config["EXPEDITEUR"]
    msg["Subject"] = objet
    msg["Message-ID"] = make_msgid()
    msg.set_content(corps)
    for nom, donnees, type_mime in pieces_jointes or []:
        principal, secondaire = type_mime.split("/", 1)
        msg.add_attachment(donnees, maintype=principal, subtype=secondaire, filename=nom)

    port = int(config.get("SMTP_PORT") or 465)
    contexte = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(config["SMTP_HOST"], port, context=contexte, timeout=30) as serveur:
            serveur.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            serveur.send_message(msg)
    else:
        with smtplib.SMTP(config["SMTP_HOST"], port, timeout=30) as serveur:
            serveur.starttls(context=contexte)
            serveur.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            serveur.send_message(msg)
    return msg["Message-ID"]
