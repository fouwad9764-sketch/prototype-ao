"""Stockage sécurisé du pôle : utilisateurs, clients, dossiers et journal.

- En production (Scalingo) : base PostgreSQL indiquée par la variable DATABASE_URL
  (ou SCALINGO_POSTGRESQL_URL).
- En test : fichier SQLite local (temporaire sur l'hébergement gratuit).
- Le contenu des clients et des dossiers est CHIFFRÉ (Fernet / AES) avec la clé
  CLE_CHIFFREMENT : sans cette clé, la base est illisible, même pour l'hébergeur.
- Les mots de passe ne sont jamais stockés : seulement leur empreinte (PBKDF2-SHA256).
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken

ROLES = ["admin", "chargé d'affaires"]
STATUTS_DOSSIER = ["En analyse", "Go", "No-go", "En préparation", "Déposé", "Gagné", "Perdu", "Abandonné"]
ITERATIONS = 240_000

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS utilisateurs (
        id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, nom TEXT NOT NULL, role TEXT NOT NULL,
        empreinte TEXT NOT NULL, actif INTEGER NOT NULL DEFAULT 1, cree_le TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS clients (
        id TEXT PRIMARY KEY, nom TEXT NOT NULL, contenu TEXT NOT NULL,
        cree_le TEXT NOT NULL, maj_le TEXT NOT NULL, maj_par TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS dossiers (
        id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), nom TEXT NOT NULL,
        statut TEXT NOT NULL, date_limite TEXT NOT NULL, contenu TEXT NOT NULL,
        cree_le TEXT NOT NULL, maj_le TEXT NOT NULL, maj_par TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS journal (
        id TEXT PRIMARY KEY, quand TEXT NOT NULL, qui TEXT NOT NULL, action TEXT NOT NULL,
        objet TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS parametres (
        cle TEXT PRIMARY KEY, contenu TEXT NOT NULL, maj_le TEXT NOT NULL, maj_par TEXT NOT NULL)""",
]


def _maintenant() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


# ---------- Mots de passe ----------
def empreinte_mot_de_passe(mot_de_passe: str) -> str:
    sel = secrets.token_bytes(16)
    calcul = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${base64.b64encode(sel).decode()}${base64.b64encode(calcul).decode()}"


def verifier_mot_de_passe(mot_de_passe: str, empreinte: str) -> bool:
    try:
        _, iterations, sel, attendu = empreinte.split("$")
        calcul = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"),
                                     base64.b64decode(sel), int(iterations))
        return hmac.compare_digest(calcul, base64.b64decode(attendu))
    except (ValueError, TypeError):
        return False


def mot_de_passe_valable(mot_de_passe: str) -> str:
    """Renvoie un message d'erreur, ou "" si le mot de passe est acceptable."""
    if len(mot_de_passe) < 10:
        return "Le mot de passe doit contenir au moins 10 caractères."
    if mot_de_passe.isalpha() or mot_de_passe.isdigit():
        return "Le mot de passe doit mélanger lettres et chiffres (ou symboles)."
    return ""


# ---------- Chiffrement ----------
def nouvelle_cle() -> str:
    return Fernet.generate_key().decode()


class Coffre:
    """Chiffre et déchiffre le contenu des clients et des dossiers."""

    def __init__(self, cle: str):
        self._fernet = Fernet(cle.encode() if isinstance(cle, str) else cle)

    def chiffrer(self, donnees) -> str:
        return self._fernet.encrypt(json.dumps(donnees, ensure_ascii=False).encode("utf-8")).decode()

    def dechiffrer(self, texte: str):
        try:
            return json.loads(self._fernet.decrypt(texte.encode()).decode("utf-8"))
        except InvalidToken as exc:
            raise ValueError("Impossible de déchiffrer : la clé de chiffrement ne correspond pas.") from exc


# ---------- Base de données ----------
class Base:
    """Accès à la base (SQLite ou PostgreSQL), avec chiffrement du contenu."""

    def __init__(self, url: str, cle: str):
        self.coffre = Coffre(cle)
        self.postgres = url.startswith(("postgres://", "postgresql://"))
        if self.postgres:
            import psycopg  # installé en production
            self._connexion = psycopg.connect(url, autocommit=True)
        else:
            chemin = url.replace("sqlite:///", "") if url else "pole_ao.sqlite"
            self._connexion = sqlite3.connect(chemin, check_same_thread=False)
            self._connexion.execute("PRAGMA foreign_keys = ON")
        for requete in SCHEMA:
            self._executer(requete)

    @property
    def est_temporaire(self) -> bool:
        return not self.postgres

    def _executer(self, requete: str, parametres: tuple = ()):
        if self.postgres:
            requete = requete.replace("?", "%s")
        curseur = self._connexion.cursor()
        curseur.execute(requete, parametres)
        if not self.postgres:
            self._connexion.commit()
        return curseur

    def _lignes(self, requete: str, parametres: tuple = ()) -> list:
        curseur = self._executer(requete, parametres)
        colonnes = [c[0] for c in curseur.description]
        return [dict(zip(colonnes, ligne)) for ligne in curseur.fetchall()]

    # --- journal
    def tracer(self, qui: str, action: str, objet: str = "") -> None:
        self._executer("INSERT INTO journal (id, quand, qui, action, objet) VALUES (?, ?, ?, ?, ?)",
                       (uuid.uuid4().hex, _maintenant(), qui, action, objet[:200]))

    def journal(self, limite: int = 200) -> list:
        return self._lignes("SELECT quand, qui, action, objet FROM journal ORDER BY quand DESC LIMIT ?",
                            (limite,))

    # --- utilisateurs
    def nb_utilisateurs(self) -> int:
        return self._lignes("SELECT COUNT(*) AS n FROM utilisateurs")[0]["n"]

    def creer_utilisateur(self, email: str, nom: str, mot_de_passe: str, role: str, par: str) -> None:
        email = email.strip().lower()
        if role not in ROLES:
            raise ValueError("Rôle inconnu.")
        erreur = mot_de_passe_valable(mot_de_passe)
        if erreur:
            raise ValueError(erreur)
        if self._lignes("SELECT id FROM utilisateurs WHERE email = ?", (email,)):
            raise ValueError("Un compte existe déjà avec cette adresse.")
        self._executer("INSERT INTO utilisateurs (id, email, nom, role, empreinte, actif, cree_le) "
                       "VALUES (?, ?, ?, ?, ?, 1, ?)",
                       (uuid.uuid4().hex, email, nom.strip(), role, empreinte_mot_de_passe(mot_de_passe),
                        _maintenant()))
        self.tracer(par, "Création de compte", email)

    def connecter(self, email: str, mot_de_passe: str) -> dict | None:
        lignes = self._lignes("SELECT * FROM utilisateurs WHERE email = ? AND actif = 1",
                              (email.strip().lower(),))
        if lignes and verifier_mot_de_passe(mot_de_passe, lignes[0]["empreinte"]):
            utilisateur = {k: lignes[0][k] for k in ("id", "email", "nom", "role")}
            self.tracer(utilisateur["email"], "Connexion")
            return utilisateur
        self.tracer(email.strip().lower() or "inconnu", "Échec de connexion")
        return None

    def utilisateurs(self) -> list:
        return self._lignes("SELECT email, nom, role, actif, cree_le FROM utilisateurs ORDER BY nom")

    def changer_mot_de_passe(self, email: str, nouveau: str, par: str) -> None:
        erreur = mot_de_passe_valable(nouveau)
        if erreur:
            raise ValueError(erreur)
        self._executer("UPDATE utilisateurs SET empreinte = ? WHERE email = ?",
                       (empreinte_mot_de_passe(nouveau), email))
        self.tracer(par, "Changement de mot de passe", email)

    def activer(self, email: str, actif: bool, par: str) -> None:
        self._executer("UPDATE utilisateurs SET actif = ? WHERE email = ?", (1 if actif else 0, email))
        self.tracer(par, "Compte activé" if actif else "Compte désactivé", email)

    # --- clients
    def creer_client(self, nom: str, par: str) -> str:
        identifiant = uuid.uuid4().hex
        moment = _maintenant()
        self._executer("INSERT INTO clients (id, nom, contenu, cree_le, maj_le, maj_par) VALUES (?, ?, ?, ?, ?, ?)",
                       (identifiant, nom.strip(), self.coffre.chiffrer({"fiche": "", "documents": []}),
                        moment, moment, par))
        self.tracer(par, "Création de client", nom)
        return identifiant

    def clients(self) -> list:
        return self._lignes("SELECT id, nom, maj_le FROM clients ORDER BY nom")

    def lire_client(self, client_id: str) -> dict:
        lignes = self._lignes("SELECT contenu FROM clients WHERE id = ?", (client_id,))
        return self.coffre.dechiffrer(lignes[0]["contenu"]) if lignes else {"fiche": "", "documents": []}

    def enregistrer_client(self, client_id: str, contenu: dict, par: str) -> None:
        self._executer("UPDATE clients SET contenu = ?, maj_le = ?, maj_par = ? WHERE id = ?",
                       (self.coffre.chiffrer(contenu), _maintenant(), par, client_id))

    def renommer_client(self, client_id: str, nom: str, par: str) -> None:
        self._executer("UPDATE clients SET nom = ? WHERE id = ?", (nom.strip(), client_id))
        self.tracer(par, "Client renommé", nom)

    # --- dossiers (toujours filtrés par client : cloisonnement)
    def creer_dossier(self, client_id: str, nom: str, par: str) -> str:
        identifiant = uuid.uuid4().hex
        moment = _maintenant()
        self._executer("INSERT INTO dossiers (id, client_id, nom, statut, date_limite, contenu, cree_le, maj_le, "
                       "maj_par) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (identifiant, client_id, nom.strip(), STATUTS_DOSSIER[0], "",
                        self.coffre.chiffrer({}), moment, moment, par))
        self.tracer(par, "Création de dossier", nom)
        return identifiant

    def dossiers(self, client_id: str | None = None) -> list:
        requete = ("SELECT d.id, d.client_id, c.nom AS client, d.nom, d.statut, d.date_limite, d.maj_le, d.maj_par "
                   "FROM dossiers d JOIN clients c ON c.id = d.client_id")
        if client_id:
            return self._lignes(requete + " WHERE d.client_id = ? ORDER BY d.maj_le DESC", (client_id,))
        return self._lignes(requete + " ORDER BY d.maj_le DESC")

    def lire_dossier(self, client_id: str, dossier_id: str) -> dict:
        lignes = self._lignes("SELECT contenu FROM dossiers WHERE id = ? AND client_id = ?", (dossier_id, client_id))
        if not lignes:
            raise ValueError("Dossier introuvable pour ce client.")
        return self.coffre.dechiffrer(lignes[0]["contenu"])

    def enregistrer_dossier(self, client_id: str, dossier_id: str, contenu: dict, par: str) -> None:
        self._executer("UPDATE dossiers SET contenu = ?, maj_le = ?, maj_par = ? WHERE id = ? AND client_id = ?",
                       (self.coffre.chiffrer(contenu), _maintenant(), par, dossier_id, client_id))

    # --- paramètres du pôle (catalogue de prestations, mentions du devis…), chiffrés
    def lire_parametre(self, cle: str, defaut=None):
        lignes = self._lignes("SELECT contenu FROM parametres WHERE cle = ?", (cle,))
        return self.coffre.dechiffrer(lignes[0]["contenu"]) if lignes else defaut

    def ecrire_parametre(self, cle: str, valeur, par: str) -> None:
        self._executer(
            "INSERT INTO parametres (cle, contenu, maj_le, maj_par) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (cle) DO UPDATE SET contenu = excluded.contenu, maj_le = excluded.maj_le, "
            "maj_par = excluded.maj_par",
            (cle, self.coffre.chiffrer(valeur), _maintenant(), par))
        self.tracer(par, "Paramètre modifié", cle)

    def maj_suivi(self, dossier_id: str, statut: str, date_limite: str, par: str) -> None:
        if statut not in STATUTS_DOSSIER:
            raise ValueError("Statut inconnu.")
        self._executer("UPDATE dossiers SET statut = ?, date_limite = ?, maj_le = ?, maj_par = ? WHERE id = ?",
                       (statut, date_limite, _maintenant(), par, dossier_id))
        self.tracer(par, f"Statut : {statut}", dossier_id[:8])


def url_base() -> str:
    return (os.getenv("DATABASE_URL") or os.getenv("SCALINGO_POSTGRESQL_URL") or "").strip()
