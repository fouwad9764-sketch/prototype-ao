"""Persistance des données : la base reste d'une ouverture à l'autre, et une copie complète peut être restaurée.

Ce fichier accompagne stockage.py (il ne le remplace pas) :
- Le stockage durable est PostgreSQL (addon Scalingo). Un fichier ne peut pas rendre durable
  un disque temporaire : sans cet addon, les données disparaissent au redémarrage.
- En mode test, la clé de chiffrement est gardée dans un fichier : les données enregistrées
  restent lisibles après un redémarrage (sinon une nouvelle clé est créée à chaque démarrage).
- La sauvegarde complète (fichier .sola) contient toutes les tables, chiffrées avec la clé
  de l'application. Elle permet de tout restaurer si la base est perdue.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

FORMAT_SAUVEGARDE = "sola-sauvegarde-complete"
VERSION_SAUVEGARDE = 1
TABLES = ["utilisateurs", "clients", "dossiers", "journal", "parametres"]


def dossier_donnees() -> Path:
    """Dossier de la base de test et de sa clé. Modifiable avec la variable DOSSIER_DONNEES."""
    dossier = Path(os.getenv("DOSSIER_DONNEES", ".")).expanduser()
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def url_effective(url_postgres: str) -> str:
    """URL PostgreSQL si elle est configurée, sinon fichier SQLite dans le dossier de données."""
    if url_postgres:
        return url_postgres
    return f"sqlite:///{dossier_donnees() / 'pole_ao.sqlite'}"


def cle_locale() -> str:
    """Clé de chiffrement du mode test : créée une seule fois, relue à chaque démarrage.

    Sans ce fichier, chaque démarrage crée une nouvelle clé : les données déjà enregistrées
    deviennent illisibles, même si la base est toujours là.
    """
    fichier = dossier_donnees() / "cle_test.key"
    if fichier.exists():
        return fichier.read_text(encoding="utf-8").strip()
    cle = Fernet.generate_key().decode()
    fichier.write_text(cle, encoding="utf-8")
    return cle


def statut_stockage(base, cle_secrete_definie: bool) -> tuple:
    """Renvoie (niveau, message) à afficher dans la barre latérale. Niveau : « ok » ou « warning »."""
    if not base.est_temporaire and cle_secrete_definie:
        return "ok", "Données durables (PostgreSQL) et chiffrées : elles restent à la réouverture."
    return "warning", ("Mode test : les données sont dans un fichier temporaire et peuvent disparaître "
                       "au redémarrage. Ajoute l'addon PostgreSQL et la variable CLE_CHIFFREMENT dans Scalingo.")


def exporter_sauvegarde(base, cle: str, par: str) -> bytes:
    """Copie complète de toutes les tables, chiffrée. Renvoie les octets du fichier .sola.

    base : objet stockage.Base. cle : la clé de chiffrement de l'application.
    """
    tables = {t: base._lignes(f"SELECT * FROM {t}") for t in TABLES}
    donnees = {"format": FORMAT_SAUVEGARDE, "version": VERSION_SAUVEGARDE,
               "enregistre_le": datetime.now().strftime("%d/%m/%Y %H:%M"), "tables": tables}
    base.tracer(par, "Sauvegarde complète exportée")
    return Fernet(cle.encode()).encrypt(json.dumps(donnees, ensure_ascii=False, default=str).encode("utf-8"))


def importer_sauvegarde(base, contenu: bytes, cle: str, par: str) -> dict:
    """Restaure une sauvegarde. Les lignes déjà présentes ne sont jamais écrasées.

    Renvoie le nombre de lignes lues par table. Lève ValueError si le fichier est invalide.
    """
    try:
        donnees = json.loads(Fernet(cle.encode()).decrypt(contenu).decode("utf-8"))
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Sauvegarde illisible : fichier abîmé ou clé de chiffrement différente.") from exc
    if donnees.get("format") != FORMAT_SAUVEGARDE:
        raise ValueError("Ce fichier n'est pas une sauvegarde complète de l'outil Sola.")

    compte = {}
    for table in TABLES:
        lignes = donnees.get("tables", {}).get(table, [])
        # Seules les colonnes qui existent réellement dans la base sont acceptées.
        colonnes_base = [c[0] for c in base._executer(f"SELECT * FROM {table} LIMIT 0").description]
        for ligne in lignes:
            colonnes = [c for c in colonnes_base if c in ligne]
            if not colonnes:
                continue
            marques = ", ".join("?" for _ in colonnes)
            base._executer(f"INSERT INTO {table} ({', '.join(colonnes)}) VALUES ({marques}) ON CONFLICT DO NOTHING",
                           tuple(ligne[c] for c in colonnes))
        compte[table] = len(lignes)
    base.tracer(par, "Sauvegarde complète restaurée", f"{sum(compte.values())} ligne(s)")
    return compte
