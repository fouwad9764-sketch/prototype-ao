"""Sauvegarde et reprise d'un dossier (fichier JSON), sans base de données.

Le fichier contient tout le travail d'un dossier : pièces lues, analyses, fiche client,
matrice, check-list. On le télécharge, on le range dans Fichiers, et on le recharge plus tard.
"""

import json
from datetime import datetime

from extraction import Piece

FORMAT = "sola-dossier-ao"
VERSION_FORMAT = 1

CHAMPS_TEXTE = ["fiche_flash", "go_no_go", "exigences", "fiche_client_txt", "dc1_dc2", "memoire_notation"]
CHAMPS_LISTES = ["exigences_brutes", "matrice", "checklist", "journal_mails", "chronos", "devis_lignes", "memoire_plan", "demandes"]
CHAMPS_OBJETS = ["type_marche", "devis_infos", "memoire_criteres", "memoire_sections", "rendu_infos"]


def _piece_vers_dict(p) -> dict:
    return {"nom": p.nom, "texte": p.texte, "alertes": list(p.alertes), "type": getattr(p, "type", "Autre")}


def _dict_vers_piece(d: dict) -> Piece:
    p = Piece(d.get("nom", ""), d.get("texte", ""), list(d.get("alertes", [])))
    p.type = d.get("type", "Autre")
    return p


def exporter_dossier(etat, nom_dossier: str) -> bytes:
    """etat = st.session_state (ou un dict). Renvoie le fichier JSON en octets."""
    donnees = {
        "format": FORMAT, "version": VERSION_FORMAT, "nom": nom_dossier,
        "enregistre_le": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "pieces": [_piece_vers_dict(p) for p in (etat.get("pieces") or [])],
        "docs_client": [_piece_vers_dict(p) for p in (etat.get("docs_client") or [])],
        "mail_brouillon": list(etat.get("mail_brouillon") or []) or None,
    }
    for champ in CHAMPS_TEXTE:
        donnees[champ] = etat.get(champ) or ""
    for champ in CHAMPS_LISTES:
        donnees[champ] = etat.get(champ) or []
    for champ in CHAMPS_OBJETS:
        donnees[champ] = etat.get(champ) or {}
    return json.dumps(donnees, ensure_ascii=False, indent=1).encode("utf-8")


def importer_dossier(contenu: bytes) -> dict:
    """Renvoie les valeurs à replacer dans la session. Lève ValueError si le fichier n'est pas un dossier."""
    try:
        donnees = json.loads(contenu.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Ce fichier n'est pas une sauvegarde de dossier lisible.") from exc
    if donnees.get("format") != FORMAT:
        raise ValueError("Ce fichier n'est pas une sauvegarde de dossier de l'outil Sola.")
    etat = {
        "pieces": [_dict_vers_piece(d) for d in donnees.get("pieces", [])] or None,
        "docs_client": [_dict_vers_piece(d) for d in donnees.get("docs_client", [])] or None,
        "mail_brouillon": tuple(donnees["mail_brouillon"]) if donnees.get("mail_brouillon") else None,
    }
    for champ in CHAMPS_TEXTE:
        etat[champ] = donnees.get(champ) or None
    for champ in CHAMPS_LISTES:
        etat[champ] = donnees.get(champ) or None
    for champ in CHAMPS_OBJETS:
        etat[champ] = donnees.get(champ) or None
    etat["fiche_client_txt"] = etat["fiche_client_txt"] or ""
    return {"nom": donnees.get("nom", ""), "enregistre_le": donnees.get("enregistre_le", ""), "etat": etat}


# ---------- Fiches clients réutilisables ----------
FORMAT_CLIENT = "sola-fiche-client"


def exporter_client(fiche_texte: str, docs_client) -> bytes:
    donnees = {"format": FORMAT_CLIENT, "version": VERSION_FORMAT,
               "enregistre_le": datetime.now().strftime("%d/%m/%Y %H:%M"),
               "fiche": fiche_texte or "",
               "documents": [_piece_vers_dict(p) for p in (docs_client or [])]}
    return json.dumps(donnees, ensure_ascii=False, indent=1).encode("utf-8")


def importer_client(contenu: bytes) -> tuple:
    try:
        donnees = json.loads(contenu.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Ce fichier n'est pas une fiche client lisible.") from exc
    if donnees.get("format") != FORMAT_CLIENT:
        raise ValueError("Ce fichier n'est pas une fiche client de l'outil Sola.")
    return donnees.get("fiche", ""), [_dict_vers_piece(d) for d in donnees.get("documents", [])] or None


def nom_fichier(texte: str) -> str:
    """Nom de fichier propre à partir d'un libellé."""
    propre = "".join(c if c.isalnum() else "_" for c in (texte or "dossier").strip())[:40].strip("_")
    return propre or "dossier"
