"""Prototype Sola Conseil — analyse d'un DCE avec Mistral.

Lancement : streamlit run app.py
"""

import os
from datetime import datetime, timedelta

import importlib

import streamlit as st
from dotenv import load_dotenv

import controle, devis, dossier_io, fiche_client, export_word, extraction, llm_client, mail_client, matrice, memoire, prompts_ao, qualification, relances, rendu, stockage
for _module in (export_word, extraction, llm_client, mail_client, matrice, prompts_ao, dossier_io, stockage,
                qualification, devis, memoire, rendu, relances, controle, fiche_client):
    importlib.reload(_module)  # toujours la version la plus récente déposée sur GitHub

import copy
import hashlib
import json
import time
from datetime import date

import pandas as pd

from devis import CATALOGUE_DEFAUT, INFOS_DEFAUT, NIVEAU_VERS_LIGNE, UNITES, est_variable
from memoire import (P8A_CRITERES, P8B_SECTION, P8C_NOTATION, compter_a_completer, corpus_memoire,
                     grille_texte, plan_depuis_criteres, separer_sources)
from rendu import P11_SYNTHESE_CLIENT, donnees_synthese, sections_compte_rendu
from qualification import P7_TYPE_MARCHE, estimer_charge, jours_ouvres_restants, lire_json, valeur_courte
from stockage import ROLES, STATUTS_DOSSIER, Base, nouvelle_cle, url_base

from dossier_io import exporter_client, exporter_dossier, importer_client, importer_dossier, nom_fichier
from export_word import markdown_vers_docx
from extraction import decouper, deviner_type, lire_fichier
from llm_client import LLMError, appeler_ia, cle_depuis_env
from mail_client import envoyer, lien_mailto, separer_objet, smtp_configure
from matrice import (COLONNES_MATRICE, checklist_vers_excel, compter, lignes_checklist,
                     lignes_de_tableaux, lignes_matrice, vers_excel, vers_markdown)
from prompts_ao import (EXEMPLE_CLIENT_FICTIF, P1_FICHE_FLASH, P2_GO_NO_GO, P3_EXIGENCES,
                        P3B_CONSOLIDATION, P4_MATRICE, P5_MAIL_CLIENT, P6_DC1_DC2)

VERSION = "v15.1 (06/11/2026)"
LOGO = "logo_sola.png"

load_dotenv()

BUDGET_FICHE_FLASH = 200_000  # caractères envoyés pour la fiche flash
BUDGET_CLIENT = 150_000       # caractères du dossier client envoyés à la matrice
EXIGENCES_PAR_LOT = 25        # exigences envoyées par appel pour la matrice
ORDRE_PIECES = ["Avis", "RC", "Cadre de réponse", "CCAP", "AE", "CCTP", "DQE", "BPU", "DPGF", "Annexe",
                "Autre", "Plan", "Photo"]

st.set_page_config(page_title="Pôle Marchés Publics — Sola Conseils", page_icon=LOGO, layout="wide")

STATUT_STYLE = {"CONFORME": ("#DDF3E4", "#1E6B3A"), "PARTIEL": ("#FFF1D6", "#8A5A00"),
                "NON CONFORME": ("#FDE2E2", "#9B1C1C"), "À VÉRIFIER": ("#E2ECF8", "#1F4E8C"),
                "SANS OBJET": ("#EEF0F2", "#4B5563")}

TURQUOISE, MARINE, VERT, ORANGE, ROUGE, BLEU, GRIS = ("#00788A", "#004269", "#2E9E3E", "#FA7F0B",
                                                     "#C62828", "#1F4E8C", "#6B7A83")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,500,0..1,0&display=block');
html {font-size: 17.5px;}
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp h1, .stApp h2, .stApp h3,
.stApp h4, .stApp button, .stApp td, .stApp th {font-family: 'Plus Jakarta Sans', sans-serif !important;}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {font-weight: 800 !important; color: #004269;}
.stApp h4 {margin-top: .8rem;}
.stApp h4 span[data-testid="stIconMaterial"] {color: #00788A;}
button[data-baseweb="tab"] p {font-size: 1.02rem !important; font-weight: 700 !important;}
.stButton button, .stDownloadButton button, .stLinkButton a, .stFormSubmitButton button {
  min-height: 3rem; border-radius: 12px !important; font-weight: 700 !important;}
div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stExpander"] details {border-radius: 16px !important;}
.ms {font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1;
  letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap;
  font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased; vertical-align: middle;}
.bandeau {background: linear-gradient(120deg, #004269 0%, #00788A 100%); color: #fff; border-radius: 20px;
  padding: 1.1rem 1.4rem; display: flex; justify-content: space-between; align-items: center; gap: .8rem;
  flex-wrap: wrap; margin-bottom: .6rem;}
.bandeau .titre {font-size: 1.55rem; font-weight: 800; line-height: 1.2; font-family: 'Plus Jakarta Sans', sans-serif;}
.bandeau .sous {opacity: .85; font-size: .92rem; font-family: 'Plus Jakarta Sans', sans-serif;}
.puce {background: rgba(255,255,255,.16); border-radius: 999px; padding: .4rem .85rem; font-weight: 700;
  font-size: .9rem; display: inline-flex; align-items: center; gap: .35rem; margin: .15rem;
  font-family: 'Plus Jakarta Sans', sans-serif;}
.grille {display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: .75rem; margin: .4rem 0 1rem;}
.carte {background: #fff; border: 1px solid #E3EAEE; border-radius: 16px; padding: .9rem 1rem; display: flex;
  gap: .8rem; align-items: center; box-shadow: 0 1px 3px rgba(0,66,105,.07);
  font-family: 'Plus Jakarta Sans', sans-serif;}
.carte .ico {width: 2.7rem; height: 2.7rem; border-radius: 12px; display: flex; align-items: center;
  justify-content: center; flex-shrink: 0;}
.carte .ico .ms {font-size: 1.55rem;}
.carte > div:last-child {min-width: 0;}
.carte .val {font-size: 1.3rem; font-weight: 800; color: #0F2B3A; line-height: 1.2; overflow-wrap: anywhere;
  hyphens: auto;}
.carte .lib {font-size: .82rem; color: #5B6B75; font-weight: 700; text-transform: uppercase; letter-spacing: .02em;}
.carte.petite .val {font-size: 1rem; font-weight: 700;}
.carte .note {font-size: .78rem; color: #5B6B75; font-weight: 600;}
.etapes {display: flex; flex-wrap: wrap; gap: .45rem; margin: .1rem 0 .9rem;}
.etape {display: inline-flex; align-items: center; gap: .35rem; padding: .4rem .8rem; border-radius: 999px;
  font-weight: 700; font-size: .86rem; border: 1.5px solid #D5DEE3; color: #6B7A83; background: #fff;
  font-family: 'Plus Jakarta Sans', sans-serif;}
.etape.ok {background: #E6F4EA; border-color: #2E9E3E; color: #1E6B2E;}
.etape .ms {font-size: 1.15rem;}
.stApp [data-testid="stMarkdownContainer"] table {display: block; max-width: 100%; overflow-x: auto;
  border-collapse: collapse;}
.stApp [data-testid="stMarkdownContainer"] td, .stApp [data-testid="stMarkdownContainer"] th {
  overflow-wrap: anywhere; min-width: 7rem; vertical-align: top;}
.stApp div[data-testid="stCheckbox"] label p {line-height: 1.35;}
</style>""", unsafe_allow_html=True)


def _h(texte) -> str:
    return (str(texte if texte is not None else "—").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def ms(nom: str) -> str:
    return '<span class="ms">' + nom + '</span>'


def cartes(elements, petite: bool = False) -> None:
    """elements : liste de (icône, libellé, valeur, couleur). Affiche des tuiles encadrées."""
    classe = "carte petite" if petite else "carte"
    html = "".join(
        f'<div class="{classe}"><div class="ico" style="background:{c}1F;color:{c}">{ms(i)}</div>'
        f'<div><div class="val">{_h(v)}</div><div class="lib">{_h(l)}</div></div></div>'
        for i, l, v, c in elements)
    st.markdown(f'<div class="grille" lang="fr">{html}</div>', unsafe_allow_html=True)


def alerte_inventions(texte: str, *autres_sources: str) -> None:
    """Affiche les dates, années, références ou montants du texte absents de tous les documents."""
    sources = [p.texte for p in (st.session_state.get("pieces") or [])]
    sources += [d.texte for d in (st.session_state.get("docs_client") or [])]
    sources += [st.session_state.get("fiche_client_txt", ""), *autres_sources]
    absents = controle.elements_absents(texte, sources, ignorer=(datetime.now().strftime("%d/%m/%Y"),))
    if absents:
        st.warning("À vérifier : l'IA a écrit des éléments introuvables dans les documents du dossier : "
                   + ", ".join(f"**{a}**" for a in absents[:12]) + ". Corrige-les ou supprime-les.",
                   icon=":material/report:")


def entete(icone: str, titre: str) -> None:
    st.markdown(f"#### :material/{icone}: {titre}")


def style_statut(valeur):
    fond, texte = STATUT_STYLE.get(valeur, ("", ""))
    return f"background-color: {fond}; color: {texte}; font-weight: 600" if fond else ""


def tableau_statuts(lignes, colonnes):
    """Tableau avec la colonne Statut en pastilles de couleur (le mot reste affiché)."""
    import pandas as pd
    df = pd.DataFrame(lignes)[colonnes]
    return df.style.map(style_statut, subset=["Statut"])


def secret(nom: str) -> str:
    """Lit un secret : d'abord les secrets de l'hébergement en ligne, sinon le fichier .env."""
    try:
        valeur = st.secrets.get(nom, "")
    except Exception:  # pas de fichier de secrets en local
        valeur = ""
    return str(valeur or os.getenv(nom, "")).strip()


# ---------- Base de données sécurisée ----------
CHAMPS_ANALYSE = ("pieces", "fiche_flash", "go_no_go", "exigences", "exigences_brutes", "matrice",
                  "checklist", "mail_brouillon", "journal_mails", "chronos", "dc1_dc2",
                  "type_marche", "devis_lignes", "devis_infos", "memoire_criteres", "memoire_plan",
                  "memoire_sections", "memoire_notation", "rendu_infos", "demandes")


@st.cache_resource
def cle_de_test() -> str:
    return nouvelle_cle()


@st.cache_resource
def ouvrir_base(url: str, cle_chiffrement: str) -> Base:
    return Base(url, cle_chiffrement)


CLE_CHIFFREMENT = secret("CLE_CHIFFREMENT")
if url_base() and not CLE_CHIFFREMENT:
    st.image(LOGO, width=120)
    st.title("Installation : clé de chiffrement")
    st.warning("La base de données est branchée, mais la clé de chiffrement n'est pas encore configurée.")
    st.markdown("1. Copie la clé ci-dessous **et garde-en une copie en lieu sûr** (coffre de mots de passe "
                "de l'entreprise). Sans elle, les données enregistrées seront définitivement illisibles.\n"
                "2. Dans Scalingo, ajoute la variable d'environnement **CLE_CHIFFREMENT** avec cette valeur.\n"
                "3. Redémarre l'application.")
    st.code(nouvelle_cle(), language=None)
    st.caption("Une nouvelle clé est proposée à chaque affichage : n'en enregistre qu'une seule.")
    st.stop()
MODE_TEST = not (url_base() and CLE_CHIFFREMENT)
try:
    BASE = ouvrir_base(url_base(), CLE_CHIFFREMENT or cle_de_test())
except Exception as exc:
    st.error(f"Base de données inaccessible : {exc}")
    st.stop()


def ecran_titre():
    """Écran centré avec le logo ; renvoie la colonne centrale."""
    _, centre, _ = st.columns([1, 1.4, 1])
    with centre:
        st.image(LOGO, width=130)
        st.markdown("### Pôle Marchés Publics")
        st.caption("Sola Conseils")
    return centre


# ---------- Premier lancement : création du compte administrateur ----------
if BASE.nb_utilisateurs() == 0:
    admin_email, admin_mdp = secret("ADMIN_EMAIL"), secret("ADMIN_PASSWORD")
    if admin_email and admin_mdp:
        BASE.creer_utilisateur(admin_email, secret("ADMIN_NOM") or "Responsable du pôle",
                               admin_mdp, "admin", "système")
    else:
        with ecran_titre(), st.form("premier_admin"):
            st.markdown("#### :material/admin_panel_settings: Créer le compte administrateur")
            code = st.text_input("Code d'installation", type="password", help="Le mot de passe APP_PASSWORD des Secrets.")
            nom_admin = st.text_input("Nom et prénom")
            email_admin = st.text_input("Adresse e-mail professionnelle")
            mdp_admin = st.text_input("Mot de passe", type="password", help="10 caractères minimum, lettres et chiffres.")
            if st.form_submit_button("Créer le compte", type="primary", icon=":material/person_add:",
                                     use_container_width=True):
                if not secret("APP_PASSWORD") or code != secret("APP_PASSWORD"):
                    st.error("Code d'installation incorrect.")
                else:
                    try:
                        BASE.creer_utilisateur(email_admin, nom_admin, mdp_admin, "admin", "installation")
                        st.success("Compte créé. Tu peux te connecter.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        st.stop()

# ---------- Connexion ----------
if not st.session_state.get("utilisateur"):
    echecs = st.session_state.get("echecs_connexion", 0)
    with ecran_titre():
        if echecs >= 5:
            st.error("Trop de tentatives. Recharge la page dans quelques minutes.", icon=":material/lock:")
            st.stop()
        formulaire = st.form("connexion")
    with formulaire:
        email_saisi = st.text_input("E-mail", placeholder="prenom.nom@…")
        mdp_saisi = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter", type="primary", icon=":material/login:", use_container_width=True):
            utilisateur = BASE.connecter(email_saisi, mdp_saisi)
            if utilisateur:
                st.session_state.utilisateur = utilisateur
                st.rerun()
            st.session_state.echecs_connexion = echecs + 1
            st.error("Adresse ou mot de passe incorrect.")
    st.stop()

UTILISATEUR = st.session_state.utilisateur
QUI = UTILISATEUR["email"]

for k in CHAMPS_ANALYSE + ("docs_client",):
    st.session_state.setdefault(k, None)
st.session_state.setdefault("fiche_client_txt", "")


def vider_analyse():
    for k in CHAMPS_ANALYSE:
        st.session_state[k] = None
    for k in [k for k in st.session_state if str(k).startswith(("chk_", "qui_"))]:
        del st.session_state[k]


def charger_client(client_id: str):
    contenu = BASE.lire_client(client_id)
    fiche, docs = importer_client(json.dumps({"format": "sola-fiche-client", "fiche": contenu.get("fiche", ""),
                                              "documents": contenu.get("documents", [])}).encode())
    structure = contenu.get("structure")
    if not structure:  # ancienne fiche en texte libre : reprise dans les notes (sauf client fictif de test)
        structure = fiche_client.structure_vide()
        if fiche and "Client FICTIF pour test" not in fiche:
            structure["notes"] = fiche
    st.session_state.fiche_structure = structure
    st.session_state.fiche_client_txt = fiche_client.vers_texte(structure)
    st.session_state.docs_client = docs
    st.session_state.pop("fiche_marqueur", None)
    st.session_state.client_charge = client_id
    st.session_state.empreinte_client = None


def charger_dossier(client_id: str, dossier_id: str):
    contenu = BASE.lire_dossier(client_id, dossier_id)
    vider_analyse()
    if contenu:
        etat = importer_dossier(json.dumps(contenu).encode())["etat"]
        for k in CHAMPS_ANALYSE:
            st.session_state[k] = etat.get(k)
    st.session_state.dossier_charge = dossier_id
    st.session_state.empreinte_dossier = None


def creer_client_cb():
    st.session_state.client_choisi = BASE.creer_client(st.session_state.nom_nouveau_client, QUI)
    st.session_state.nom_nouveau_client = ""


def creer_dossier_cb(client_id: str):
    st.session_state.dossier_choisi = BASE.creer_dossier(client_id, st.session_state.nom_nouveau_dossier, QUI)
    st.session_state.nom_nouveau_dossier = ""


# ---------- Barre latérale ----------
with st.sidebar:
    st.image(LOGO, width=96)
    st.markdown(f":material/account_circle: **{UTILISATEUR['nom']}**  \n:gray[{UTILISATEUR['role']}]")
    if st.button("Se déconnecter", icon=":material/logout:"):
        BASE.tracer(QUI, "Déconnexion")
        st.session_state.clear()
        st.rerun()
    if MODE_TEST:
        st.warning("Mode test : données effacées au redémarrage. DCE publics et clients fictifs uniquement.",
                   icon=":material/science:")

    st.divider()
    st.markdown("#### :material/folder_shared: Client et dossier")
    liste_clients = BASE.clients()
    noms_clients = {c["id"]: c["nom"] for c in liste_clients}
    client_id = st.selectbox("Client", [None] + list(noms_clients), key="client_choisi",
                             format_func=lambda i: "— Choisir un client —" if i is None else noms_clients[i])
    with st.expander("Nouveau client", icon=":material/add_business:"):
        nom_nouveau_client = st.text_input("Nom du client", key="nom_nouveau_client")
        st.button("Créer", icon=":material/add:", disabled=not nom_nouveau_client.strip(), on_click=creer_client_cb)

    dossier_id = None
    if client_id:
        if st.session_state.get("client_charge") != client_id:
            charger_client(client_id)
            st.session_state.dossier_charge = None
            vider_analyse()
        liste_dossiers = BASE.dossiers(client_id)
        noms_dossiers = {d["id"]: f"{d['nom']} · {d['statut']}" for d in liste_dossiers}
        dossier_id = st.selectbox("Dossier", [None] + list(noms_dossiers), key="dossier_choisi",
                                  format_func=lambda i: "— Choisir un dossier —" if i is None else noms_dossiers[i])
        with st.expander("Nouveau dossier", icon=":material/create_new_folder:"):
            nom_nouveau_dossier = st.text_input("Nom du dossier", key="nom_nouveau_dossier",
                                                placeholder="ex. Sada - MOE escaliers")
            st.button("Créer", icon=":material/add:", key="creer_dossier", disabled=not nom_nouveau_dossier.strip(),
                      on_click=creer_dossier_cb, args=(client_id,))
        if dossier_id and st.session_state.get("dossier_charge") != dossier_id:
            charger_dossier(client_id, dossier_id)
        if dossier_id:
            st.success("Sauvegarde automatique", icon=":material/cloud_done:")
        else:
            st.info("Choisis ou crée un dossier.", icon=":material/folder_open:")
    else:
        st.info("Choisis ou crée un client.", icon=":material/apartment:")

    st.divider()
    with st.expander("Réglages de l'IA", icon=":material/tune:"):
        cle_enregistree = secret("MISTRAL_API_KEY") or cle_depuis_env()
        if cle_enregistree:
            cle = cle_enregistree
            st.success("Clé API Mistral chargée.")
        else:
            cle = st.text_input("Clé API Mistral", type="password")
        modele = st.selectbox("Modèle", ["mistral-large-latest", "mistral-medium-latest",
                                         "mistral-small-latest"],
                              help="Large = plus fiable, Small = plus rapide et moins cher.")
        if st.button("Vider l'analyse en cours", icon=":material/delete_sweep:"):
            vider_analyse()
            st.rerun()

    with st.expander("Copie de secours", icon=":material/backup:"):
        st.download_button("Télécharger une copie", icon=":material/download:", use_container_width=True,
                           data=exporter_dossier(st.session_state, "dossier"),
                           file_name=f"dossier_{datetime.now():%Y%m%d_%H%M}.json", mime="application/json")
        fichier_dossier = st.file_uploader("Importer un dossier (.json)", type=["json"], key="up_dossier")
        if fichier_dossier and st.button("Importer", icon=":material/upload:", disabled=not dossier_id):
            try:
                charge = importer_dossier(fichier_dossier.getvalue())
                for k in CHAMPS_ANALYSE:
                    st.session_state[k] = charge["etat"].get(k)
                if charge["etat"].get("fiche_client_txt"):
                    st.session_state.fiche_client_txt = charge["etat"]["fiche_client_txt"]
                    st.session_state.docs_client = charge["etat"].get("docs_client")
                for k in [k for k in st.session_state if str(k).startswith(("chk_", "qui_"))]:
                    del st.session_state[k]
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if UTILISATEUR["role"] == "admin":
        with st.expander("Administration", icon=":material/admin_panel_settings:"):
            st.markdown("**:material/person_add: Créer un compte**")
            n_nom = st.text_input("Nom", key="n_nom")
            n_email = st.text_input("E-mail", key="n_email")
            n_mdp = st.text_input("Mot de passe provisoire", type="password", key="n_mdp")
            n_role = st.selectbox("Rôle", ROLES, index=1, key="n_role")
            if st.button("Créer le compte", icon=":material/person_add:"):
                try:
                    BASE.creer_utilisateur(n_email, n_nom, n_mdp, n_role, QUI)
                    st.success("Compte créé.")
                except ValueError as exc:
                    st.error(str(exc))
            st.dataframe(BASE.utilisateurs(), hide_index=True, use_container_width=True)
            st.markdown("**:material/history: Journal des actions**")
            st.dataframe(BASE.journal(100), hide_index=True, use_container_width=True)

    with st.expander("Signaler une erreur de l'IA", icon=":material/flag:"):
        etape_err = st.selectbox("Étape", ["Fiche flash", "Type de marché", "Temps de traitement", "Go/no-go",
                                           "Exigences", "Matrice", "Check-list", "E-mail client", "DC1 / DC2",
                                           "Devis", "Affichage", "Autre"], key="err_etape")
        constat = st.text_area("Ce que l'IA a mis", key="err_constat", height=80)
        correct = st.text_area("Ce qui est juste (avec la page du DCE)", key="err_correct", height=80)

        def signaler_cb():
            retours = BASE.lire_parametre("retours_fiabilite", []) or []
            retours.append({"Date": datetime.now().strftime("%d/%m/%Y %H:%M"), "Par": UTILISATEUR["nom"],
                            "Type de marché": (st.session_state.type_marche or {}).get("nature", ""),
                            "Étape": st.session_state.err_etape, "Constat": st.session_state.err_constat.strip(),
                            "Correction": st.session_state.err_correct.strip(), "Version": VERSION})
            BASE.ecrire_parametre("retours_fiabilite", retours, QUI)
            st.session_state.err_constat = st.session_state.err_correct = ""
            st.session_state.err_ok = True

        st.button("Envoyer le signalement", icon=":material/flag:", disabled=not constat.strip(), on_click=signaler_cb)
        if st.session_state.pop("err_ok", False):
            st.success("Merci, signalement enregistré.", icon=":material/check:")
        if UTILISATEUR["role"] == "admin":
            retours = BASE.lire_parametre("retours_fiabilite", []) or []
            if retours:
                st.caption(f"{len(retours)} signalement(s) enregistré(s)")
                st.download_button("Exporter les signalements", icon=":material/download:",
                                   data=pd.DataFrame(retours).to_csv(index=False, sep=";").encode("utf-8-sig"),
                                   file_name=f"signalements_{datetime.now():%Y%m%d}.csv", mime="text/csv")

    with st.expander("Mon mot de passe", icon=":material/key:"):
        nouveau_mdp = st.text_input("Nouveau mot de passe", type="password", key="nouveau_mdp")
        if st.button("Changer", icon=":material/lock_reset:"):
            try:
                BASE.changer_mot_de_passe(QUI, nouveau_mdp, QUI)
                st.success("Mot de passe changé.")
            except ValueError as exc:
                st.error(str(exc))
    st.caption(f"Version {VERSION}")

_puces = [f'<span class="puce">{ms("person")} {_h(UTILISATEUR["nom"])}</span>']
if client_id:
    _puces.insert(0, f'<span class="puce">{ms("apartment")} {_h(noms_clients.get(client_id))}</span>')
if dossier_id:
    _puces.insert(1, f'<span class="puce">{ms("folder_open")} '
                     f'{_h(noms_dossiers.get(dossier_id, "").split(" · ")[0])}</span>')
st.markdown(f'<div class="bandeau"><div><div class="titre">Pôle Marchés Publics</div>'
            f'<div class="sous">Sola Conseils · tout résultat est un brouillon à valider</div></div>'
            f'<div>{"".join(_puces)}</div></div>', unsafe_allow_html=True)
if st.session_state.pieces or dossier_id:
    _etapes = [("upload_file", "DCE", "pieces"), ("bolt", "Fiche flash", "fiche_flash"),
               ("category", "Type", "type_marche"), ("thumbs_up_down", "Go/no-go", "go_no_go"),
               ("checklist", "Exigences", "exigences"), ("table_chart", "Matrice", "matrice"),
               ("badge", "DC1/DC2", "dc1_dc2"), ("edit_document", "Mémoire", "memoire_sections"),
               ("request_quote", "Devis", "devis_infos"), ("summarize", "Compte rendu", "rendu_infos")]
    st.markdown('<div class="etapes">' + "".join(
        f'<span class="etape{" ok" if st.session_state.get(k) else ""}">'
        f'{ms("check_circle" if st.session_state.get(k) else i)} {t}</span>' for i, t, k in _etapes)
        + "</div>", unsafe_allow_html=True)


def lancer(prompt: str, etape: str = "Analyse") -> str | None:
    """Appelle l'IA et chronomètre l'appel (pour mesurer le temps gagné)."""
    nom_actif = (noms_clients.get(client_id, "") if client_id else "").lower()
    if "Client FICTIF pour test" in prompt and not ("fictif" in nom_actif or "test" in nom_actif):
        st.error("Analyse bloquée : la fiche contient encore le client fictif de test. Vide-la dans l'onglet "
                 "« Fiche client ».", icon=":material/block:")
        return None
    debut = time.time()
    try:
        reponse = appeler_ia(prompt, cle, modele)
    except LLMError as exc:
        st.error(str(exc))
        return None
    journal = st.session_state.chronos or []
    journal.append({"Heure": datetime.now().strftime("%d/%m %H:%M"), "Étape": etape,
                    "Durée (s)": round(time.time() - debut, 1)})
    st.session_state.chronos = journal
    return reponse


# ---------- 3. Profil du client ----------
def charger_exemple():
    st.session_state.fiche_client_txt = EXEMPLE_CLIENT_FICTIF


def profil_client() -> str:
    """Fiche saisie + documents du client, dans la limite du budget."""
    blocs = []
    if st.session_state.get("fiche_client_txt", "").strip():
        blocs.append("===== Fiche client =====\n" + st.session_state.fiche_client_txt.strip())
    for d in st.session_state.docs_client or []:
        if d.texte.strip():
            blocs.append(f"===== Document client : {d.nom} =====\n{d.texte}")
    return "\n\n".join(blocs)[:BUDGET_CLIENT]


# ---------- 7. Dossier de candidature : check-list et e-mail au client ----------
CONFIG_MAIL = {k: secret(k) for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                                       "EXPEDITEUR", "NOM_EXPEDITEUR", "SIGNATURE")}

SIGNATURE_MAIL = CONFIG_MAIL["SIGNATURE"] or f"{UTILISATEUR['nom']}\nPôle Marchés Publics\nSola Conseils"


def envoyer_trace(destinataire: str, objet: str, corps: str, copie: str = "", pj=None,
                  journal: list | None = None) -> bool:
    """Envoie depuis la boîte du pôle et ajoute l'envoi au journal fourni (ou à celui du dossier ouvert)."""
    try:
        envoyer(CONFIG_MAIL, destinataire, objet, corps, copie, pj or [])
    except Exception as exc:
        st.error(f"Envoi impossible : {exc}. Vérifie les réglages SMTP dans les Secrets.", icon=":material/error:")
        return False
    ligne = {"Date": datetime.now().strftime("%d/%m/%Y %H:%M"), "À": destinataire, "Objet": objet}
    if journal is None:
        st.session_state.journal_mails = (st.session_state.journal_mails or []) + [ligne]
    else:
        journal.append(ligne)
    BASE.tracer(QUI, "E-mail envoyé", objet[:60])
    return True


t_accueil, t_dossier, t_fiche, t_client, t_exigences, t_matrice, t_candidature, t_memoire, t_export, t_devis, t_rendu = st.tabs(
    [":material/dashboard: Mes dossiers", ":material/upload_file: Dossier", ":material/badge: Fiche client",
     ":material/thumbs_up_down: Go/no-go",
     ":material/checklist: Exigences", ":material/table_chart: Matrice", ":material/assignment: Candidature",
     ":material/edit_document: Mémoire", ":material/download: Export", ":material/request_quote: Devis",
     ":material/summarize: Compte rendu"])

with t_accueil:
    tous = BASE.dossiers()
    if not tous:
        st.info("Aucun dossier : crée un client puis un dossier dans le menu de gauche.",
                icon=":material/create_new_folder:")
    else:
        cartes([("apartment", "Clients", len({d["client"] for d in tous}), MARINE),
                ("folder_open", "Dossiers", len(tous), TURQUOISE),
                ("pending_actions", "En cours", sum(1 for d in tous if d["statut"] in
                                                    ("En analyse", "Go", "En préparation")), ORANGE),
                ("send", "Déposés", sum(1 for d in tous if d["statut"] == "Déposé"), BLEU),
                ("emoji_events", "Gagnés", sum(1 for d in tous if d["statut"] == "Gagné"), VERT)])
        # ---------- Relances à envoyer aujourd'hui (tous dossiers) ----------
        dues = []
        for d in tous:
            try:
                contenu_d = None if d["id"] == dossier_id else BASE.lire_dossier(d["client_id"], d["id"])
            except Exception:
                continue
            liste_d = st.session_state.demandes if contenu_d is None else contenu_d.get("demandes")
            for i_dem, dem in enumerate(liste_d or []):
                if relances.relance_due(dem):
                    dues.append((d, contenu_d, i_dem, dem))
        if dues:
            entete("notifications_active", f"Relances à envoyer aujourd'hui ({len(dues)})")
            for d, contenu_d, i_dem, dem in dues:
                rang, _ = relances.prochaine_relance(dem)
                objet_r, corps_r = relances.texte_relance(dem, rang, SIGNATURE_MAIL)
                with st.container(border=True):
                    st.markdown(f"**{d['client']}** · {d['nom']}  \n:material/forward_to_inbox: Relance {rang}/3 à "
                                f"{dem['destinataire']} · {len(relances.manquants(dem))} pièce(s) manquante(s)")
                    with st.expander("Voir le message", icon=":material/mail:"):
                        st.text(f"Objet : {objet_r}\n\n{corps_r}")
                    if not smtp_configure(CONFIG_MAIL):
                        st.link_button("Ouvrir dans Mail", icon=":material/mail:",
                                       url=lien_mailto(dem["destinataire"], objet_r, corps_r))
                    elif st.button("Envoyer la relance", icon=":material/send:", type="primary",
                                   key=f"rel_{d['id']}_{dem['id']}"):
                        if contenu_d is None:
                            if envoyer_trace(dem["destinataire"], objet_r, corps_r, CONFIG_MAIL["EXPEDITEUR"]):
                                relances.noter_relance(st.session_state.demandes[i_dem], objet_r)
                                st.rerun()
                        else:
                            journal_d = contenu_d.get("journal_mails") or []
                            if envoyer_trace(dem["destinataire"], objet_r, corps_r, CONFIG_MAIL["EXPEDITEUR"],
                                             journal=journal_d):
                                relances.noter_relance(contenu_d["demandes"][i_dem], objet_r)
                                contenu_d["journal_mails"] = journal_d
                                BASE.enregistrer_dossier(d["client_id"], d["id"], contenu_d, QUI)
                                st.rerun()
        entete("view_list", "Suivi des dossiers")
        tableau = [{"id": d["id"], "Client": d["client"], "Dossier": d["nom"], "Statut": d["statut"],
                    "Date limite": d["date_limite"], "Mis à jour": d["maj_le"][:16], "Par": d["maj_par"]}
                   for d in tous]
        modifie = st.data_editor(pd.DataFrame(tableau), key="suivi_dossiers", hide_index=True, use_container_width=True,
                                 column_order=["Client", "Dossier", "Statut", "Date limite", "Mis à jour", "Par"],
                                 disabled=["Client", "Dossier", "Mis à jour", "Par"],
                                 column_config={"Statut": st.column_config.SelectboxColumn(
                                     "Statut", options=STATUTS_DOSSIER),
                                     "Date limite": st.column_config.TextColumn(
                                         "Date limite", help="JJ/MM/AAAA")})
        for avant, apres in zip(tableau, modifie.to_dict("records")):
            if (avant["Statut"], avant["Date limite"]) != (apres["Statut"], apres["Date limite"]):
                BASE.maj_suivi(avant["id"], apres["Statut"], apres["Date limite"] or "", QUI)
        st.caption(":material/edit: Statut et date limite modifiables directement dans le tableau.")

def corpus_dce(lisibles_dce: list, budget: int = BUDGET_FICHE_FLASH) -> tuple:
    """Texte des pièces dans la limite du budget. Renvoie (texte, complet)."""
    corpus, total = [], 0
    for p in lisibles_dce:
        reste = budget - total
        if reste <= 0:
            break
        corpus.append(f"===== {p.nom} ({p.type}) =====\n{p.texte[:reste]}")
        total += min(len(p.texte), reste)
    return "\n\n".join(corpus), total < budget


pieces = st.session_state.pieces
lisibles = [p for p in (pieces or []) if p.texte.strip() and getattr(p, "type", "") not in ("Plan", "Photo")]
PROFIL = ""

with t_dossier:
    # ---------- 1. Import ----------
    entete("upload_file", "Importer le DCE")
    fichiers = st.file_uploader("Pièces du DCE", accept_multiple_files=True,
                                help="PDF, Word, Excel, texte ou ZIP. Plans et photos sont mis de côté.",
                                type=["pdf", "docx", "xlsx", "txt", "zip", "jpg", "jpeg", "png", "heic",
                                      "dwg", "dxf"])

    if fichiers and st.button("Lire les fichiers", type="primary", icon=":material/auto_stories:"):
        pieces = []
        with st.spinner("Lecture des pièces…"):
            for f in fichiers:
                pieces.extend(lire_fichier(f.name, f.getvalue()))
        for p in pieces:
            p.type = "Plan" if getattr(p, "est_plan", False) else deviner_type(p.nom)
        pieces.sort(key=lambda p: ORDRE_PIECES.index(p.type))
        st.session_state.pieces = pieces
        st.session_state.fiche_flash = st.session_state.go_no_go = st.session_state.exigences = None
        st.session_state.matrice = None

    pieces = st.session_state.pieces
    if pieces:
        lisibles = [p for p in pieces if p.texte.strip() and p.type not in ("Plan", "Photo")]
        a_part = [p for p in pieces if p.type in ("Plan", "Photo")]
        alertes = sum(1 for p in pieces if p.alertes)
        cartes([("description", "Pièces", len(pieces), TURQUOISE),
                ("task_alt", "Lues par l'IA", len(lisibles), VERT),
                ("architecture", "Plans / photos", len(a_part), MARINE),
                ("warning", "Alertes", alertes, ORANGE if alertes else GRIS)])
        with st.expander("Détail des pièces", icon=":material/list:"):
            st.dataframe(
                [{"Pièce": p.nom, "Type": p.type, "Caractères": p.nb_caracteres,
                  "Alertes": " ; ".join(p.alertes)} for p in pieces],
                use_container_width=True, hide_index=True)
        if not lisibles:
            st.error("Aucun texte lisible dans ces pièces.", icon=":material/error:")
            st.stop()


    # ---------- 2. Fiche flash ----------
    if pieces:
        entete("bolt", "Fiche flash")
        if st.button("Générer la fiche flash", icon=":material/bolt:", type="primary"
                     if not st.session_state.fiche_flash else "secondary"):
            documents, complet = corpus_dce(lisibles)
            if not complet:
                st.info("DCE long : lecture des pièces principales (Avis, RC, CCAP).", icon=":material/info:")
            with st.spinner("Mistral lit le dossier…"):
                st.session_state.fiche_flash = lancer(P1_FICHE_FLASH.format(documents=documents), "Fiche flash")
        if st.session_state.fiche_flash:
            alerte_inventions(st.session_state.fiche_flash)
            with st.container(border=True):
                st.markdown(st.session_state.fiche_flash)

    # ---------- Type de marché et temps de traitement ----------
    if pieces:
        entete("category", "Type de marché")
        if st.button("Identifier le type de marché", icon=":material/search:", type="primary"
                     if st.session_state.fiche_flash and not st.session_state.type_marche else "secondary"):
            documents, _ = corpus_dce(lisibles)
            with st.spinner("Mistral identifie le type de marché…"):
                reponse = lancer(P7_TYPE_MARCHE.format(documents=documents), "Type de marché")
            if reponse:
                try:
                    st.session_state.type_marche = lire_json(reponse)
                except ValueError as exc:
                    st.error(str(exc))
        tm = st.session_state.type_marche
        if tm:
            if tm.get("objet"):
                st.markdown(f"**{tm['objet']}**" + (f"  \n:gray[{tm['sous_type']}]" if tm.get("sous_type") else ""))
            icones_nature = {"Travaux": "construction", "Fournitures": "inventory_2", "Services": "support_agent",
                             "Prestations intellectuelles": "psychology", "Mixte": "join_inner"}
            v = lambda cle: valeur_courte(tm.get(cle))
            date_affichee = v("date_limite")
            if tm.get("fuseau") and date_affichee != "non trouvé":
                date_affichee += " · " + str(tm["fuseau"]).replace("heure de ", "")
            cartes([(icones_nature.get(tm.get("nature"), "category"), "Nature", v("nature"), TURQUOISE),
                    ("gavel", "Procédure", str(tm.get("procedure", "—")).replace("Procédure adaptée (MAPA)", "MAPA"),
                     MARINE),
                    ("account_tree", "Forme", v("forme"), BLEU),
                    ("view_module", "Lots", tm.get("nb_lots") or 1, ORANGE)])
            poids = tm.get("poids_technique")
            cartes([("event", "Date limite", date_affichee, ROUGE),
                    ("euro", "Montant estimé", v("montant_estime"), VERT),
                    ("schedule", "Durée", v("duree"), MARINE),
                    ("description", "Mémoire technique", v("memoire_technique"), TURQUOISE),
                    ("balance", "Poids technique", f"{poids} %" if poids is not None else "non trouvé", TURQUOISE),
                    ("receipt_long", "Type de prix", v("type_prix"), BLEU),
                    ("directions_walk", "Visite obligatoire", v("visite_obligatoire"), ORANGE),
                    ("inventory_2", "Échantillons", v("echantillons"), GRIS),
                    ("alt_route", "Variantes", v("variantes"), GRIS),
                    ("handshake", "Négociation", v("negociation"), GRIS)], petite=True)
            if tm.get("heure_paris"):
                st.caption(f":material/schedule: Soit {tm['heure_paris']} heure de Paris.")
            if tm.get("justification"):
                with st.expander("Sources", icon=":material/menu_book:"):
                    st.write(tm["justification"])
                    for cle, libelle in (("date_limite", "Date limite"), ("montant_estime", "Montant"),
                                         ("duree", "Durée")):
                        if valeur_courte(tm.get(cle), 10_000) != str(tm.get(cle) or "non trouvé"):
                            st.caption(f"{libelle} : {tm.get(cle)}")

            entete("timer", "Temps de traitement")
            c1, c2 = st.columns(2)
            tm["lots_vises"] = c1.number_input("Lots visés", min_value=1,
                                               max_value=max(1, int(tm.get("nb_lots") or 1)),
                                               value=int(tm.get("lots_vises") or 1))
            tm["client_nouveau"] = c2.checkbox("Premier dossier du client", help="Pièces du client à collecter.",
                                               value=bool(tm.get("client_nouveau")))
            estimation = estimer_charge(tm, tm["lots_vises"], sum(len(p.texte) for p in lisibles),
                                        tm["client_nouveau"])
            tm["estimation"] = {"total": estimation["total"], "niveau": estimation["niveau"]}
            jours = jours_ouvres_restants(tm.get("date_limite"))
            couleur_niveau = {"Simple": VERT, "Moyen": ORANGE, "Complexe": ROUGE}[estimation["niveau"]]
            cartes([("timer", "Charge estimée", f"{estimation['total']:g} h".replace(".", ","), TURQUOISE),
                    ("signal_cellular_alt", "Niveau", estimation["niveau"], couleur_niveau),
                    ("event_available", "Jours ouvrés restants", "?" if jours is None else jours,
                     ROUGE if jours is not None and jours <= 5 else MARINE)])
            if jours is not None and jours <= 2:
                st.error("Délai très court.", icon=":material/alarm:")
            elif jours is not None and estimation["total"] > jours * 4:
                st.warning("Délai serré : plus de 4 h de travail par jour restant.", icon=":material/alarm:")
            with st.expander("Détail du calcul", icon=":material/calculate:"):
                st.dataframe(pd.DataFrame(estimation["postes"], columns=["Poste", "Heures", "Base de calcul"]),
                             hide_index=True, use_container_width=True)
                st.caption("Temps de référence indicatifs, à ajuster après les premiers dossiers.")


# ---------- Fiche client structurée ----------
with t_fiche:
    if not client_id:
        st.info("Choisis un client dans le menu de gauche.", icon=":material/apartment:")
    else:
        struct = st.session_state.get("fiche_structure") or fiche_client.structure_vide()
        st.session_state.fiche_structure = struct
        nom_c = noms_clients.get(client_id, "")
        marqueur_f = (client_id, st.session_state.get("fiche_version", 0))
        if st.session_state.get("fiche_marqueur") != marqueur_f:
            st.session_state.fiche_base = copy.deepcopy(struct)
            for k in [k for k in st.session_state if str(k).startswith(("fc_", "fct_"))]:
                del st.session_state[k]
            st.session_state.fiche_marqueur = marqueur_f
        base_f = st.session_state.fiche_base

        scores = fiche_client.completude(struct)
        nature_f = (st.session_state.type_marche or {}).get("nature")
        prio = fiche_client.PRIORITES.get(nature_f, [])
        admin_dispo = sum(1 for l in struct.get("administratif", []) if l.get("Disponible"))
        cartes([("donut_large", "Fiche complète", f"{round(scores['global'] * 100)} %",
                 VERT if scores["global"] >= .8 else ORANGE if scores["global"] >= .4 else ROUGE),
                ("workspace_premium", "Références", len([l for l in struct.get("references", []) if l.get("Objet")]), MARINE),
                ("verified", "Habilitations", len([l for l in struct.get("qualifications", []) if l.get("Intitulé")]), TURQUOISE),
                ("folder_shared", "Pièces admin.", f"{admin_dispo} / {len(struct.get('administratif', []))}", BLEU)])

        entete("auto_awesome", "Remplir avec l'IA")
        docs_f = st.file_uploader("Documents du client", accept_multiple_files=True,
                                  type=["pdf", "docx", "xlsx", "txt"], key=f"up_client_{client_id}",
                                  help="Kbis, bilans, attestations d'assurance, plaquette, CV, liste de références, "
                                       "ancien mémoire… L'IA remplit les cases vides, sans écraser ce que tu as saisi.")
        c1, c2 = st.columns(2)
        lire_nouveaux = c1.button("Lire et remplir la fiche", icon=":material/auto_awesome:", type="primary",
                                  disabled=not docs_f, use_container_width=True)
        relire = c2.button("Relire les documents enregistrés", icon=":material/refresh:",
                           disabled=not st.session_state.docs_client, use_container_width=True)
        if lire_nouveaux or relire:
            documents_c = list(st.session_state.docs_client or [])
            if lire_nouveaux:
                with st.spinner("Lecture des documents…"):
                    deja_lus = {d.nom for d in documents_c}
                    for f in docs_f:
                        for p in lire_fichier(f.name, f.getvalue()):
                            if p.nom not in deja_lus:
                                documents_c.append(p)
                st.session_state.docs_client = documents_c
            texte_c = "\n\n".join(f"===== {d.nom} =====\n{d.texte}" for d in documents_c if d.texte.strip())[:150_000]
            with st.spinner("Mistral remplit la fiche…"):
                reponse_c = lancer(fiche_client.P10_EXTRACTION_CLIENT.format(
                    identite=fiche_client.format_identite_json(), documents=texte_c), "Lecture des documents client")
            if reponse_c:
                try:
                    struct, ajouts = fiche_client.fusionner(struct, fiche_client.depuis_json(reponse_c))
                    st.session_state.fiche_structure = struct
                    st.session_state.fiche_version = st.session_state.get("fiche_version", 0) + 1
                    st.session_state.fiche_message = f"{ajouts} information(s) ajoutée(s) à la fiche. Vérifie-les."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if st.session_state.get("fiche_message"):
            st.success(st.session_state.pop("fiche_message"), icon=":material/check_circle:")
        if st.session_state.docs_client:
            with st.expander(f"Documents enregistrés ({len(st.session_state.docs_client)})", icon=":material/folder:"):
                for d in st.session_state.docs_client:
                    st.markdown(f"- {d.nom}" + (f" :orange[({' ; '.join(d.alertes)})]" if d.alertes else ""))
                if struct.get("sources"):
                    st.caption(f"Sources utilisées par l'IA : {struct['sources']}")

        if prio:
            st.info(f"Marché de type « {nature_f} » : sections prioritaires en premier.", icon=":material/priority_high:")

        entete("badge", "Identité")
        ident = struct.setdefault("identite", {})
        colonnes_i = st.columns(2)
        for i_f, champ in enumerate(fiche_client.IDENTITE):
            cle_i = f"fc_{client_id}_{i_f}"
            st.session_state.setdefault(cle_i, str(base_f.get("identite", {}).get(champ, "") or ""))
            ident[champ] = colonnes_i[i_f % 2].text_input(champ, key=cle_i)

        ordre_t = prio + [t for t in fiche_client.TABLEAUX if t not in prio]
        for nom_t in ordre_t:
            icone_t, titre_t, colonnes_t = fiche_client.TABLEAUX[nom_t]
            lignes_t = [l for l in struct.get(nom_t, []) if any(v not in ("", None, False) for v in l.values())]
            with st.expander(f"{titre_t} ({len(lignes_t)})", icon=f":material/{icone_t}:",
                             expanded=nom_t in prio[:2] or not lignes_t):
                config_t = {c: st.column_config.CheckboxColumn(c, default=False)
                            for c in colonnes_t if c in fiche_client.COLONNES_COCHE}
                edite_t = st.data_editor(pd.DataFrame(base_f.get(nom_t, []), columns=colonnes_t),
                                         key=f"fct_{client_id}_{nom_t}", num_rows="dynamic", hide_index=True,
                                         use_container_width=True, column_config=config_t)
                remplissage = {c: (False if c in fiche_client.COLONNES_COCHE else "") for c in colonnes_t}
                struct[nom_t] = [l for l in edite_t.fillna(remplissage).to_dict("records")
                                 if any(v not in ("", None, False) for v in l.values())]

        cle_n = f"fc_{client_id}_notes"
        st.session_state.setdefault(cle_n, base_f.get("notes", ""))
        struct["notes"] = st.text_area("Notes libres (points forts, points faibles, contexte…)", key=cle_n, height=110)
        st.session_state.fiche_structure = struct
        st.session_state.fiche_client_txt = fiche_client.vers_texte(struct, nom_c)
        with st.expander("Ce que l'IA lira pour les analyses", icon=":material/visibility:"):
            st.text(st.session_state.fiche_client_txt)

with t_client:
    if not pieces:
        st.info("Importe d'abord le DCE (onglet Dossier).", icon=":material/upload_file:")
    if pieces and client_id:
        score_f = fiche_client.completude(st.session_state.get("fiche_structure") or fiche_client.structure_vide())
        st.info(f"Fiche client complète à {round(score_f['global'] * 100)} % : complète-la dans l'onglet "
                "« Fiche client » pour un go/no-go fiable.", icon=":material/badge:")


    PROFIL = profil_client() if pieces else ""

    # ---------- 4. Go/no-go ----------
    if st.session_state.fiche_flash:
        entete("thumbs_up_down", "Go/no-go")
        if st.button("Analyser le go/no-go", icon=":material/psychology:", type="primary", disabled=not PROFIL):
            with st.spinner("Analyse en cours…"):
                st.session_state.go_no_go = lancer(P2_GO_NO_GO.format(
                    fiche_flash=st.session_state.fiche_flash, fiche_client=PROFIL,
                    date_du_jour=datetime.now().strftime("%d/%m/%Y")), "Go/no-go")
        if not PROFIL:
            st.caption(":material/info: Remplis d'abord le profil du client.")
        if st.session_state.go_no_go:
            alerte_inventions(st.session_state.go_no_go)
            with st.container(border=True):
                st.markdown(st.session_state.go_no_go)

with t_exigences:
    if not pieces:
        st.info("Importe d'abord le DCE (onglet Dossier).", icon=":material/upload_file:")
    # ---------- 5. Exigences ----------
    if pieces:
        entete("checklist", "Exigences du DCE")
        choix = st.multiselect("Pièces à analyser", [p.nom for p in lisibles],
                               default=[p.nom for p in lisibles if p.type in ("RC", "CCAP", "CCTP", "Cadre de réponse")])
        if st.button("Extraire les exigences", icon=":material/manage_search:", type="primary", disabled=not choix):
            resultats = []
            travaux = []
            for p in lisibles:
                if p.nom in choix:
                    morceaux = decouper(p.texte)
                    for i, m in enumerate(morceaux, start=1):
                        travaux.append((p, m, i, len(morceaux)))
            barre = st.progress(0.0, text="Démarrage…")
            for n, (p, morceau, i, total) in enumerate(travaux, start=1):
                barre.progress((n - 1) / len(travaux), text=f"{p.nom} — partie {i}/{total}")
                partie = f", partie {i} sur {total}" if total > 1 else ""
                sortie = lancer(P3_EXIGENCES.format(nom_piece=p.nom, type_piece=p.type,
                                                    partie=partie, texte=morceau), "Extraction des exigences")
                if sortie is None:
                    break
                resultats.append(f"## {p.nom}{partie}\n\n{sortie}")
            barre.progress(1.0, text="Terminé")
            if resultats:
                brutes = [c for c in lignes_de_tableaux("\n\n".join(resultats))
                          if len(c) > 1 and c[1].strip() and c[0].strip()]  # sans titres de section
                st.session_state.exigences_brutes = brutes
                st.session_state.matrice = None
                liste = "\n".join(f"{i}. {c[0]} (source : {c[1]})" for i, c in enumerate(brutes, start=1))
                with st.spinner(f"Regroupement de {len(brutes)} exigences brutes (doublons, informations)…"):
                    consolidee = lancer(P3B_CONSOLIDATION.format(exigences=liste), "Regroupement des exigences")
                st.session_state.exigences = consolidee or "\n\n".join(resultats)
        if st.session_state.exigences:
            nb_final = len(lignes_de_tableaux(st.session_state.exigences))
            if st.session_state.exigences_brutes:
                cartes([("manage_search", "Exigences trouvées", len(st.session_state.exigences_brutes), GRIS),
                        ("filter_alt", "Exigences utiles", nb_final, TURQUOISE)])
            alerte_inventions(st.session_state.exigences)
            with st.expander("Voir les exigences", expanded=True, icon=":material/list_alt:"):
                st.markdown(st.session_state.exigences)

with t_matrice:
    if not st.session_state.exigences:
        st.info("Extrais d'abord les exigences.", icon=":material/checklist:")
    # ---------- 6. Matrice de conformité ----------
    if st.session_state.exigences:
        entete("table_chart", "Matrice de conformité")
        toutes = lignes_de_tableaux(st.session_state.exigences)
        phases = ["Candidature", "Dépôt", "Offre", "Exécution"]
        if any(len(c) > 2 and c[2].strip() for c in toutes):
            retenues = st.multiselect("Phases", phases,
                                      default=["Candidature", "Dépôt"])
            exigences_lignes = [c for c in toutes if len(c) < 3 or not c[2].strip()
                                or any(p.lower() in c[2].lower() for p in retenues)]
        else:
            exigences_lignes = toutes
        st.caption(f":material/filter_alt: {len(exigences_lignes)} exigences retenues sur {len(toutes)}")
        if st.button("Construire la matrice", icon=":material/table_chart:", type="primary",
                     disabled=not (PROFIL and exigences_lignes)):
            lots = [exigences_lignes[i:i + EXIGENCES_PAR_LOT]
                    for i in range(0, len(exigences_lignes), EXIGENCES_PAR_LOT)]
            sorties, numero = [], 1
            barre = st.progress(0.0, text="Démarrage…")
            for n, lot in enumerate(lots, start=1):
                barre.progress((n - 1) / len(lots), text=f"Lot {n}/{len(lots)}")
                liste = []
                for cellules in lot:
                    exigence = cellules[0] if cellules else ""
                    source = cellules[1] if len(cellules) > 1 else ""
                    liste.append(f"{numero}. {exigence} (source : {source})")
                    numero += 1
                sortie = lancer(P4_MATRICE.format(exigences="\n".join(liste), profil_client=PROFIL), "Matrice")
                if sortie is None:
                    break
                sorties.append(sortie)
            barre.progress(1.0, text="Terminé")
            if sorties:
                st.session_state.matrice = lignes_matrice("\n\n".join(sorties))
                st.session_state.checklist = None
                st.session_state.mail_brouillon = None
                for k in [k for k in st.session_state if str(k).startswith(("chk_", "qui_"))]:
                    del st.session_state[k]
                if len(st.session_state.matrice) != len(exigences_lignes):
                    st.warning(f"{len(st.session_state.matrice)} lignes produites pour "
                               f"{len(exigences_lignes)} exigences : vérifie qu'aucune n'a été oubliée.")
        if not PROFIL:
            st.caption(":material/info: Remplis d'abord le profil du client.")

        matrice = st.session_state.matrice
        if matrice:
            comptes = compter(matrice)
            icones_statut = {"CONFORME": ("check_circle", VERT), "PARTIEL": ("contrast", ORANGE),
                             "NON CONFORME": ("cancel", ROUGE), "À VÉRIFIER": ("help", BLEU),
                             "SANS OBJET": ("remove_circle", GRIS)}
            cartes([(*icones_statut.get(statut, ("circle", GRIS))[:1], statut.capitalize(), nombre,
                     icones_statut.get(statut, ("", GRIS))[1]) for statut, nombre in comptes.items()])
            if comptes["NON CONFORME"]:
                st.error(f"{comptes['NON CONFORME']} point(s) bloquant(s) avant de candidater.", icon=":material/block:")
            filtre = st.multiselect("Statuts affichés", list(comptes),
                                    default=[s for s in comptes if s != "SANS OBJET"])
            visibles = [l for l in matrice if l["Statut"] in filtre]
            if visibles:
                st.dataframe(tableau_statuts(visibles, COLONNES_MATRICE),
                             use_container_width=True, hide_index=True)
            nom_client = (st.session_state.get("fiche_client_txt", "").strip().splitlines() or [""])[0][:80]
            st.download_button("Matrice Excel", icon=":material/download:", data=vers_excel(matrice, nom_client),
                               file_name=f"matrice_conformite_{datetime.now():%Y%m%d_%H%M}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with t_candidature:
    if not st.session_state.matrice:
        st.info("Construis d'abord la matrice.", icon=":material/table_chart:")
    if st.session_state.matrice:
        entete("assignment_turned_in", "Check-list de candidature")
        nom_client = (noms_clients.get(client_id) if client_id else "") or \
            (st.session_state.get("fiche_client_txt", "").strip().splitlines() or [""])[0][:80]

        if st.session_state.checklist is None:
            st.session_state.checklist = lignes_checklist(st.session_state.matrice)
        edite = [dict(l) for l in st.session_state.checklist]
        icones_prio = {"Bloquant": ":red[:material/block:]", "Haute": ":orange[:material/priority_high:]",
                       "Normale": ":blue[:material/help:]", "Basse": ":green[:material/check_circle:]"}
        for i_c, l in enumerate(edite):
            with st.container(border=True):
                c_ok, c_qui = st.columns([5, 1.3])
                l["Fait"] = c_ok.checkbox(
                    f"{icones_prio.get(l['Priorité'], '')} **{l['Exigence']}**  \n"
                    f":gray[{l['Statut']} · {l['Action']} · {l.get('Source DCE', '')}]",
                    value=bool(l["Fait"]), key=f"chk_{dossier_id}_{i_c}")
                l["Qui"] = c_qui.selectbox("Qui", ["Client", "Sola Conseil"], key=f"qui_{dossier_id}_{i_c}",
                                           index=0 if l["Qui"] == "Client" else 1, label_visibility="collapsed")
        st.session_state.checklist = edite
        faits = sum(1 for l in edite if l["Fait"])
        st.progress(faits / max(len(edite), 1), text=f"{faits} / {len(edite)} éléments traités")
        st.download_button("Check-list Excel", icon=":material/download:",
                           data=checklist_vers_excel(edite, f"Check-list de candidature : {nom_client}"),
                           file_name=f"checklist_candidature_{datetime.now():%Y%m%d_%H%M}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        entete("mail", "E-mail au client")
        a_obtenir = [l for l in edite if not l["Fait"] and l["Statut"] != "CONFORME"
                     and (l["Qui"] == "Client" or l["Statut"] == "NON CONFORME")]
        col1, col2 = st.columns(2)
        email_client = col1.text_input("E-mail du client")
        jours = [datetime.now().date() + timedelta(days=n) for n in range(1, 22)]
        jours_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        date_retour = col2.selectbox("Date de retour souhaitée", jours, index=4,
                                     format_func=lambda d: f"{jours_fr[d.weekday()]} {d:%d/%m/%Y}")
        signature = CONFIG_MAIL["SIGNATURE"] or st.text_area(
            "Signature", value="Prénom Nom\nResponsable Pôle Marchés Publics\nSola Conseils", height=100)
        if st.button(f"Rédiger l'e-mail ({len(a_obtenir)} éléments)", icon=":material/edit_note:",
                     type="primary", disabled=not a_obtenir):
            elements = "\n".join(f"- [{l['Statut']}] {l['Exigence']} → {l['Action']}" for l in a_obtenir)
            with st.spinner("Rédaction…"):
                texte = lancer(P5_MAIL_CLIENT.format(
                    date_retour=date_retour.strftime("%d/%m/%Y"), signature=signature,
                    fiche_flash=st.session_state.fiche_flash or "", nom_client=nom_client, elements=elements),
                    "E-mail client")
            if texte:
                st.session_state.mail_brouillon = separer_objet(texte)

        if st.session_state.mail_brouillon:
            objet = st.text_input("Objet", value=st.session_state.mail_brouillon[0])
            corps = st.text_area("Message (modifiable)", value=st.session_state.mail_brouillon[1],
                                 height=min(900, 140 + 26 * len(st.session_state.mail_brouillon[1].splitlines())))
            alerte_inventions(f"{objet}\n{corps}", st.session_state.fiche_flash or "", signature,
                              date_retour.strftime("%d/%m/%Y"))
            responsable = CONFIG_MAIL["EXPEDITEUR"]
            copie = responsable if responsable and st.checkbox("Mettre le responsable du pôle en copie", value=True) else ""
            if email_client:
                st.link_button("Ouvrir dans Mail", icon=":material/mail:", url=lien_mailto(email_client, objet, corps, copie))
            if smtp_configure(CONFIG_MAIL):
                relu = st.checkbox("J'ai relu l'e-mail et je confirme l'envoi au client")
                joindre = st.checkbox("Joindre la check-list Excel", value=True)
                if st.button("Envoyer depuis la boîte du pôle", type="primary", icon=":material/send:",
                             disabled=not (relu and email_client and "@" in email_client)):
                    pj = [("checklist_candidature.xlsx", checklist_vers_excel(edite, f"Check-list : {nom_client}"),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")] if joindre else []
                    if envoyer_trace(email_client, objet, corps, copie, pj):
                        st.session_state.demandes = (st.session_state.demandes or []) + [relances.nouvelle_demande(
                            email_client, objet, date_retour, [l["Exigence"] for l in a_obtenir],
                            str((st.session_state.type_marche or {}).get("date_limite") or ""),
                            (st.session_state.type_marche or {}).get("objet") or nom_client, QUI)]
                        st.success(f"E-mail envoyé à {email_client}. Demande ajoutée au suivi : les relances "
                                   "sont planifiées.", icon=":material/check_circle:")
            else:
                st.caption(":material/info: Envoi direct non configuré : utilise « Ouvrir dans Mail ».")
            if email_client and st.button("Je l'ai envoyé par Mail : suivre cette demande", icon=":material/add_task:"):
                st.session_state.demandes = (st.session_state.demandes or []) + [relances.nouvelle_demande(
                    email_client, objet, date_retour, [l["Exigence"] for l in a_obtenir],
                    str((st.session_state.type_marche or {}).get("date_limite") or ""),
                    (st.session_state.type_marche or {}).get("objet") or nom_client, QUI)]
                st.success("Demande ajoutée au suivi.", icon=":material/check_circle:")
            if st.session_state.journal_mails:
                st.dataframe(st.session_state.journal_mails, hide_index=True, use_container_width=True)

with t_candidature:
    if st.session_state.fiche_flash:
        st.divider()
        entete("badge", "DC1 / DC2")
        profil_dc = profil_client()
        if st.button("Préparer la fiche DC1 / DC2", icon=":material/badge:", disabled=not profil_dc,
                     help="Aide au remplissage des formulaires officiels DC1, DC2 ou du DUME."):
            synthese = "\n".join(f"- {l['Exigence']} → {l['Statut']}" for l in (st.session_state.matrice or []))
            with st.spinner("Préparation des formulaires…"):
                st.session_state.dc1_dc2 = lancer(P6_DC1_DC2.format(
                    fiche_flash=st.session_state.fiche_flash, fiche_client=profil_dc,
                    matrice=synthese or "Matrice non construite."), "DC1 / DC2")
        if not profil_dc:
            st.caption(":material/info: Remplis d'abord le profil du client.")
        if st.session_state.dc1_dc2:
            a_completer = st.session_state.dc1_dc2.count("[À COMPLÉTER")
            if a_completer:
                st.warning(f"{a_completer} champ(s) à compléter avec le client.", icon=":material/edit:")
            alerte_inventions(st.session_state.dc1_dc2)
            with st.container(border=True):
                st.markdown(st.session_state.dc1_dc2)
            st.download_button("Fiche DC1 / DC2 (Word)", icon=":material/download:",
                               data=markdown_vers_docx([("Fiche d'aide au remplissage DC1 / DC2",
                                                         st.session_state.dc1_dc2)], "Préparation DC1 / DC2"),
                               file_name=f"preparation_DC1_DC2_{datetime.now():%Y%m%d_%H%M}.docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ---------- Suivi des demandes de pièces et confirmations ----------
with t_candidature:
    if dossier_id:
        st.divider()
        entete("pending_actions", "Suivi des demandes de pièces")
        demandes_s = st.session_state.demandes or []
        if not demandes_s:
            st.caption(":material/info: Aucune demande suivie. Elle s'ajoute automatiquement à l'envoi de l'e-mail "
                       "au client, ou manuellement ci-dessous.")
        for i_s, dem in enumerate(demandes_s):
            restants = relances.manquants(dem)
            total = len(dem.get("elements", []))
            rang, quand = relances.prochaine_relance(dem)
            etat = ("Complète" if not restants else "Close" if dem.get("close") else
                    f"Relance {rang}/3 le {relances.jour_fr(quand)}" if rang else "Plus de relance prévue")
            with st.expander(f"{dem['destinataire']} · retour le {dem['date_retour']} · {total - len(restants)}/{total} reçues",
                             icon=":material/task_alt:" if not restants else ":material/hourglass_top:",
                             expanded=bool(restants) and not dem.get("close")):
                cartes([("inventory", "Pièces reçues", f"{total - len(restants)} / {total}", VERT if not restants else ORANGE),
                        ("event", "Retour demandé", dem["date_retour"], MARINE),
                        ("forward_to_inbox", "Relances envoyées", len(dem.get("relances", [])), BLEU),
                        ("schedule_send", "Prochaine étape", etat, TURQUOISE)], petite=True)
                tableau_e = st.data_editor(
                    pd.DataFrame([{"Reçu": e["recu"], "Pièce ou information": e["libelle"]} for e in dem["elements"]]),
                    key=f"elem_{dossier_id}_{dem['id']}", hide_index=True, use_container_width=True,
                    disabled=["Pièce ou information"],
                    column_config={"Reçu": st.column_config.CheckboxColumn("Reçu", width="small")})
                for e, ligne_e in zip(dem["elements"], tableau_e.to_dict("records")):
                    e["recu"] = bool(ligne_e["Reçu"])
                c1, c2, c3 = st.columns(3)
                if restants and rang and smtp_configure(CONFIG_MAIL):
                    objet_r, corps_r = relances.texte_relance(dem, rang, SIGNATURE_MAIL)
                    if c1.button("Relancer maintenant", icon=":material/send:", key=f"rn_{dem['id']}"):
                        if envoyer_trace(dem["destinataire"], objet_r, corps_r, CONFIG_MAIL["EXPEDITEUR"]):
                            relances.noter_relance(dem, objet_r)
                            st.rerun()
                if not restants and smtp_configure(CONFIG_MAIL) and not dem.get("merci"):
                    objet_c, corps_c = relances.texte_confirmation_reception(dem, SIGNATURE_MAIL)
                    if c1.button("Confirmer la réception au client", icon=":material/mark_email_read:",
                                 type="primary", key=f"ok_{dem['id']}"):
                        if envoyer_trace(dem["destinataire"], objet_c, corps_c, CONFIG_MAIL["EXPEDITEUR"]):
                            dem["merci"] = True
                            st.rerun()
                if not dem.get("close") and c2.button("Arrêter les relances", icon=":material/notifications_off:",
                                                      key=f"cl_{dem['id']}"):
                    dem["close"] = True
                    st.rerun()
                if dem.get("relances"):
                    c3.caption("Relances : " + ", ".join(r["date"] for r in dem["relances"]))
        st.session_state.demandes = demandes_s or st.session_state.demandes

        with st.expander("Suivre une demande envoyée en dehors de l'application", icon=":material/add_task:"):
            dest_m = st.text_input("E-mail du client", key=f"dm_dest_{dossier_id}")
            jours_m = [datetime.now().date() + timedelta(days=n) for n in range(0, 22)]
            retour_m = st.selectbox("Date de retour demandée", jours_m, index=5, key=f"dm_ret_{dossier_id}",
                                    format_func=relances.jour_fr)
            elements_m = st.text_area("Pièces demandées (une par ligne)", key=f"dm_el_{dossier_id}", height=140)
            if st.button("Ajouter au suivi", icon=":material/add:",
                         disabled=not (dest_m and "@" in dest_m and elements_m.strip())):
                tm_m = st.session_state.type_marche or {}
                st.session_state.demandes = (st.session_state.demandes or []) + [relances.nouvelle_demande(
                    dest_m, "Demande de pièces", retour_m, elements_m.splitlines(), str(tm_m.get("date_limite") or ""),
                    tm_m.get("objet") or noms_dossiers.get(dossier_id, "").split(" · ")[0], QUI)]
                st.success("Demande ajoutée : les relances sont planifiées.", icon=":material/check_circle:")

        entete("outgoing_mail", "Confirmer le dépôt au client")
        tm_c = st.session_state.type_marche or {}
        c1, c2 = st.columns(2)
        quand_c = c1.text_input("Déposé le", placeholder="ex. 13/11/2026 à 15h20", key=f"dep_q_{dossier_id}")
        accuse_c = c2.text_input("N° d'accusé de réception", key=f"dep_a_{dossier_id}")
        dest_c = st.text_input("E-mail du client", key=f"dep_d_{dossier_id}",
                               value=(st.session_state.demandes or [{}])[-1].get("destinataire", ""))
        if quand_c:
            objet_d, corps_d = relances.texte_confirmation_depot(
                tm_c.get("objet") or noms_dossiers.get(dossier_id, "").split(" · ")[0], tm_c.get("acheteur", ""),
                quand_c, accuse_c, SIGNATURE_MAIL)
            with st.expander("Voir le message", icon=":material/mail:"):
                st.text(f"Objet : {objet_d}\n\n{corps_d}")
            if smtp_configure(CONFIG_MAIL):
                if st.button("Envoyer la confirmation de dépôt", icon=":material/send:", type="primary",
                             disabled=not (dest_c and "@" in dest_c)):
                    if envoyer_trace(dest_c, objet_d, corps_d, CONFIG_MAIL["EXPEDITEUR"]):
                        ri_c = dict(st.session_state.rendu_infos or {})
                        ri_c["depot"] = f"{quand_c}" + (f", accusé de réception n° {accuse_c}" if accuse_c else "")
                        st.session_state.rendu_infos = ri_c
                        st.session_state[f"rendu_depot_{dossier_id}"] = ri_c["depot"]
                        st.success("Confirmation envoyée, et ajoutée au compte rendu.", icon=":material/check_circle:")
            elif dest_c:
                st.link_button("Ouvrir dans Mail", icon=":material/mail:", url=lien_mailto(dest_c, objet_d, corps_d))

# ---------- Mémoire technique ----------
BUDGET_MEMOIRE = 120_000  # caractères du DCE envoyés pour chaque partie

with t_memoire:
    if not pieces:
        st.info("Importe d'abord le DCE (onglet Dossier).", icon=":material/upload_file:")
    else:
        entete("rule", "Grille de notation")
        grille = st.session_state.memoire_criteres
        if st.button("Lire la grille de notation du RC", icon=":material/rule:",
                     type="secondary" if grille else "primary"):
            with st.spinner("Mistral lit les critères de jugement…"):
                reponse = lancer(P8A_CRITERES.format(documents=corpus_memoire(lisibles, BUDGET_FICHE_FLASH)),
                                 "Grille de notation")
            if reponse:
                try:
                    grille = lire_json(reponse)
                    st.session_state.memoire_criteres = grille
                    st.session_state.memoire_plan = plan_depuis_criteres(grille)
                    st.session_state.pop("memoire_marqueur", None)
                except ValueError as exc:
                    st.error(str(exc))
        if grille:
            if not grille.get("criteres"):
                st.warning("Aucune grille trouvée : complète le plan à la main ci-dessous.", icon=":material/warning:")
            couleurs = [TURQUOISE, MARINE, ORANGE, BLEU, VERT]
            cartes([("payments" if c.get("est_prix") else "star", valeur_courte(c.get("intitule"), 40),
                     f"{c.get('points')} pts" if c.get("points") is not None else "—", couleurs[i % 5])
                    for i, c in enumerate(grille.get("criteres") or [])])
            if grille.get("limite_pages"):
                st.warning(f"Limite : {grille['limite_pages']}", icon=":material/straighten:")
            if grille.get("cadre_impose"):
                st.info(f"Cadre de réponse imposé : {grille['cadre_impose']}", icon=":material/assignment:")
            if grille.get("pieces_offre"):
                with st.expander("Pièces de l'offre exigées", icon=":material/folder_zip:"):
                    for piece_offre in grille["pieces_offre"]:
                        st.markdown(f"- {piece_offre}")
                    if grille.get("sources"):
                        st.caption(f"Sources : {grille['sources']}")

        entete("format_list_numbered", "Plan du mémoire")
        marqueur_m = (client_id, dossier_id, id(grille))
        if st.session_state.get("memoire_marqueur") != marqueur_m:
            st.session_state.memoire_plan_base = st.session_state.memoire_plan or []
            st.session_state.pop("editeur_plan", None)
            st.session_state.memoire_marqueur = marqueur_m
        plan_df = st.data_editor(
            pd.DataFrame(st.session_state.memoire_plan_base, columns=["Titre", "Critère", "Points", "Attendus", "Consigne"]),
            key="editeur_plan", num_rows="dynamic", hide_index=True, use_container_width=True,
            column_config={"Points": st.column_config.NumberColumn("Points", width="small"),
                           "Attendus": st.column_config.TextColumn("Attendus de l'acheteur", width="large"),
                           "Consigne": st.column_config.TextColumn(
                               "Ta consigne", help="Ex. : insister sur la proximité, reprendre l'ancien mémoire…")})
        plan = [l for l in plan_df.fillna("").to_dict("records") if str(l.get("Titre") or "").strip()]
        st.session_state.memoire_plan = plan
        st.caption(":material/edit: Plan modifiable : ajoute, renomme ou supprime des parties. "
                   "Renouvellement : ajoute l'ancien mémoire dans les documents du client.")

        sections_m = dict(st.session_state.memoire_sections or {})
        if plan:
            entete("edit_document", "Rédaction")
            if not PROFIL:
                st.warning("Profil client vide : les éléments du candidat resteront « À COMPLÉTER ».",
                           icon=":material/apartment:")
            objet_m = (st.session_state.type_marche or {}).get("objet") or noms_dossiers.get(dossier_id, "") if client_id else ""
            c1, c2 = st.columns([1, 1])
            tout = c1.button("Rédiger tout le mémoire", icon=":material/auto_awesome:", type="primary",
                             disabled=not plan, use_container_width=True)
            titres = [l["Titre"] for l in plan]
            une = c2.selectbox("Ou une seule partie", ["—"] + titres, key="partie_a_rediger")
            refaire = c2.button("Rédiger cette partie", icon=":material/refresh:", disabled=une == "—",
                                use_container_width=True)
            a_faire = plan if tout else [l for l in plan if l["Titre"] == une] if refaire else []
            if a_faire:
                documents_m = corpus_memoire(lisibles, BUDGET_MEMOIRE)
                barre = st.progress(0.0, text="Rédaction…")
                for n, ligne in enumerate(a_faire, start=1):
                    barre.progress((n - 1) / len(a_faire), text=f"{ligne['Titre']} ({n}/{len(a_faire)})")
                    texte_m = lancer(P8B_SECTION.format(
                        nom_client=noms_clients.get(client_id, "le candidat") if client_id else "le candidat",
                        objet=objet_m or "voir DCE", titre=ligne["Titre"], critere=ligne.get("Critère") or ligne["Titre"],
                        points=ligne.get("Points") or "?", attendus=ligne.get("Attendus") or "voir RC",
                        consigne=ligne.get("Consigne") or "aucune", fiche_client=PROFIL or "Aucun élément fourni.",
                        documents=documents_m), f"Mémoire : {ligne['Titre'][:40]}")
                    if texte_m is None:
                        break
                    sections_m[ligne["Titre"]] = texte_m
                    st.session_state.memoire_sections = dict(sections_m)
                    st.session_state.pop(f"mem_{dossier_id}_{ligne['Titre']}", None)
                barre.progress(1.0, text="Terminé")

            rediges = [l["Titre"] for l in plan if (sections_m.get(l["Titre"]) or "").strip()]
            corps_m = {t: separer_sources(sections_m[t]) for t in rediges}
            a_completer_m = sum(compter_a_completer(corps_m[t][0]) for t in rediges)
            mots_m = sum(len(corps_m[t][0].split()) for t in rediges)
            cartes([("task_alt", "Parties rédigées", f"{len(rediges)} / {len(plan)}", VERT if len(rediges) == len(plan) else ORANGE),
                    ("edit", "À compléter / valider", a_completer_m, ROUGE if a_completer_m else VERT),
                    ("article", "Mots", mots_m, MARINE),
                    ("description", "Pages estimées", round(mots_m / 450, 1) if mots_m else 0, TURQUOISE)])
            for l in plan:
                titre_p = l["Titre"]
                if titre_p not in corps_m:
                    continue
                texte_p, sources_p = corps_m[titre_p]
                n_ac = compter_a_completer(texte_p)
                with st.expander(f"{titre_p}" + (f"  ·  {n_ac} à compléter" if n_ac else ""),
                                 icon=":material/article:"):
                    alerte_inventions(texte_p)
                    st.markdown(texte_p)
                    if sources_p:
                        st.caption(f":material/menu_book: Sources : {sources_p}")
                    cle_edit = f"mem_{dossier_id}_{titre_p}"
                    st.session_state.setdefault(cle_edit, texte_p)
                    nouveau = st.text_area("Modifier le texte", key=cle_edit, height=260)
                    if nouveau != texte_p:
                        sections_m[titre_p] = nouveau + (f"\nSOURCES : {sources_p}" if sources_p else "")
                        st.session_state.memoire_sections = dict(sections_m)

            if rediges:
                entete("gavel", "Notation à blanc")
                if st.button("Noter le mémoire comme la commission", icon=":material/gavel:"):
                    texte_complet = "\n\n".join(f"## {t}\n\n{corps_m[t][0]}" for t in rediges)
                    with st.spinner("Relecture critique…"):
                        st.session_state.memoire_notation = lancer(P8C_NOTATION.format(
                            grille=grille_texte(grille or {}) or "\n".join(
                                f"- {l['Critère']} : {l.get('Points')} points — {l.get('Attendus')}" for l in plan),
                            memoire=texte_complet), "Notation à blanc")
                if st.session_state.memoire_notation:
                    with st.container(border=True):
                        st.markdown(st.session_state.memoire_notation)

                entete("download", "Exporter le mémoire")
                nom_m = noms_clients.get(client_id, "") if client_id else ""
                st.download_button(
                    "Mémoire technique (Word)", icon=":material/description:", type="primary",
                    data=markdown_vers_docx([(t, corps_m[t][0]) for t in rediges], "Mémoire technique",
                                            note=None, saut_de_page=False,
                                            sous_titre=f"**{objet_m}**" + (f"\n\nCandidat : **{nom_m}**" if nom_m else "")),
                    file_name=f"memoire_technique_{nom_fichier(nom_m)}_{datetime.now():%Y%m%d_%H%M}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                st.caption(":material/visibility: Les cases [À COMPLÉTER] sont surlignées en jaune dans le Word.")

with t_export:
    if st.session_state.chronos:
        entete("speed", "Temps de travail de l'IA")
        total = sum(c["Durée (s)"] for c in st.session_state.chronos)
        cartes([("timer", "Temps total", f"{total / 60:.1f} min".replace(".", ","), TURQUOISE),
                ("smart_toy", "Appels à l'IA", len(st.session_state.chronos), MARINE)])
        with st.expander("Détail par étape", icon=":material/list:"):
            st.dataframe(st.session_state.chronos, hide_index=True, use_container_width=True)

    # ---------- 8. Export ----------
    sections = [(t, st.session_state[k]) for t, k in [
        ("Fiche flash", "fiche_flash"), ("Analyse go/no-go", "go_no_go"),
        ("Liste des exigences", "exigences"), ("Préparation DC1 / DC2", "dc1_dc2")] if st.session_state[k]]
    if st.session_state.matrice:
        sections.append(("Matrice de conformité", vers_markdown(st.session_state.matrice)))
    if sections:
        entete("download", "Exporter l'analyse")
        nom = f"analyse_dce_{datetime.now():%Y%m%d_%H%M}.docx"
        st.download_button("Analyse complète (Word)", icon=":material/description:", type="primary",
                           data=markdown_vers_docx(sections, "Analyse du DCE"),
                           file_name=nom,
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ---------- 9. Devis ----------
def lignes_depuis_catalogue(catalogue: list, niveau: str | None) -> list:
    a_cocher = {"Qualification et go/no-go", NIVEAU_VERS_LIGNE.get(niveau or "", "")}
    return [{"Inclure": l.get("Prestation") in a_cocher, "Prestation": l.get("Prestation", ""),
             "Description": l.get("Description", ""), "Unité": l.get("Unité", "forfait"), "Quantité": 1.0,
             "Prix unitaire HT": float(l.get("Prix unitaire HT") or 0)} for l in catalogue]


with t_devis:
    entete("request_quote", "Devis client")
    catalogue = BASE.lire_parametre("catalogue_prestations", CATALOGUE_DEFAUT)
    infos_pole = {**INFOS_DEFAUT, **(BASE.lire_parametre("infos_devis", {}) or {})}

    if UTILISATEUR["role"] == "admin":
        with st.expander("Tarifs et mentions (administrateur)", icon=":material/price_change:"):
            cat_edite = st.data_editor(
                pd.DataFrame(catalogue, columns=["Prestation", "Description", "Unité", "Prix unitaire HT"]),
                key="edit_catalogue", num_rows="dynamic", hide_index=True, use_container_width=True,
                column_config={"Unité": st.column_config.SelectboxColumn("Unité", options=UNITES),
                               "Prix unitaire HT": st.column_config.NumberColumn(
                                   "Prix unitaire HT", min_value=0.0, step=10.0, format="%.2f",
                                   help="En euros HT. Pour l'unité « % du marché attribué », indique le pourcentage.")})
            emetteur = st.text_area("Coordonnées de Sola Conseils (en-tête du devis)", infos_pole["emetteur"])
            c1, c2 = st.columns(2)
            taux_tva = c1.number_input("Taux de TVA (%)", min_value=0.0, max_value=30.0, step=0.5,
                                       value=float(infos_pole["taux_tva"]))
            validite = c2.number_input("Validité du devis (jours)", min_value=1, max_value=180,
                                       value=int(infos_pole["validite_jours"]))
            mention_tva = st.text_input("Mention si TVA à 0 %", infos_pole["mention_tva"])
            conditions = st.text_area("Conditions de paiement", infos_pole["conditions"])
            if st.button("Enregistrer", type="primary", icon=":material/save:"):
                propre = [{k: (v if not (isinstance(v, float) and pd.isna(v)) else 0.0) for k, v in l.items()}
                          for l in cat_edite.fillna({"Description": "", "Unité": "forfait"}).to_dict("records")
                          if str(l.get("Prestation") or "").strip()]
                BASE.ecrire_parametre("catalogue_prestations", propre, QUI)
                BASE.ecrire_parametre("infos_devis", {"emetteur": emetteur, "taux_tva": taux_tva,
                                                      "validite_jours": validite, "mention_tva": mention_tva,
                                                      "conditions": conditions}, QUI)
                st.success("Tarifs enregistrés.")
                st.rerun()

    if all(float(l.get("Prix unitaire HT") or 0) == 0 for l in catalogue):
        st.warning("Tarifs pas encore fixés (0 €) : à saisir par l'administrateur après validation de la direction.",
                   icon=":material/price_change:")

    if not client_id:
        st.info("Choisis un client dans le menu de gauche.", icon=":material/apartment:")
    else:
        tm = st.session_state.type_marche or {}
        niveau = (tm.get("estimation") or {}).get("niveau")
        marqueur = (client_id, dossier_id)
        if st.session_state.get("devis_marqueur") != marqueur:
            infos = st.session_state.devis_infos or {}
            st.session_state.devis_base = st.session_state.devis_lignes or lignes_depuis_catalogue(catalogue, niveau)
            st.session_state.dv_numero = infos.get("numero") or devis.numero_devis()
            st.session_state.dv_adresse = infos.get("client_adresse", "")
            st.session_state.dv_objet = infos.get("objet") or (
                f"Accompagnement à la réponse au marché : {tm['objet']}" if tm.get("objet") else "")
            st.session_state.dv_charge = bool(infos.get("afficher_charge", False))
            st.session_state.pop("editeur_devis", None)
            st.session_state.devis_marqueur = marqueur

        if niveau:
            st.info(f"Dossier « {niveau} » ({tm['estimation']['total']:g} h) : forfait correspondant coché.",
                    icon=":material/auto_awesome:")
        if st.button("Repartir du catalogue", icon=":material/restart_alt:"):
            st.session_state.devis_base = lignes_depuis_catalogue(catalogue, niveau)
            st.session_state.pop("editeur_devis", None)
            st.rerun()

        c1, c2 = st.columns(2)
        numero = c1.text_input("N° du devis", key="dv_numero")
        c2.text_input("Client", value=noms_clients.get(client_id, ""), disabled=True)
        adresse = st.text_area("Adresse du client", key="dv_adresse", height=80)
        objet = st.text_input("Objet du devis", key="dv_objet")

        edite = st.data_editor(
            pd.DataFrame(st.session_state.devis_base,
                         columns=["Inclure", "Prestation", "Description", "Unité", "Quantité", "Prix unitaire HT"]),
            key="editeur_devis", num_rows="dynamic", hide_index=True, use_container_width=True,
            column_config={"Inclure": st.column_config.CheckboxColumn("Inclure", default=False),
                           "Unité": st.column_config.SelectboxColumn("Unité", options=UNITES),
                           "Quantité": st.column_config.NumberColumn("Qté", min_value=0.0, step=1.0),
                           "Prix unitaire HT": st.column_config.NumberColumn("Prix unitaire HT", min_value=0.0,
                                                                             step=10.0, format="%.2f")})
        toutes = edite.fillna({"Inclure": False, "Description": "", "Unité": "forfait", "Quantité": 0.0,
                               "Prix unitaire HT": 0.0}).to_dict("records")
        st.session_state.devis_lignes = toutes
        retenues = [l for l in toutes if l.get("Inclure") and str(l.get("Prestation") or "").strip()]
        afficher_charge = st.checkbox("Indiquer la charge estimée sur le devis", key="dv_charge",
                                      disabled=not niveau)
        st.session_state.devis_infos = {"numero": numero, "client_adresse": adresse, "objet": objet,
                                        "afficher_charge": afficher_charge}

        totaux = devis.calculer(retenues, infos_pole["taux_tva"])
        cartes([("receipt_long", "Total HT", devis.euros(totaux["total_ht"]), MARINE),
                ("payments", "Total TTC" if infos_pole["taux_tva"] else "Net à payer",
                 devis.euros(totaux["total_ttc"]), VERT)])
        variables = [l for l in retenues if est_variable(l)]
        if variables:
            st.caption("Rémunération variable (hors total) : " + " ; ".join(
                f"{l['Prestation']} {float(l['Prix unitaire HT']):g} %" for l in variables))

        if not retenues:
            st.info("Coche au moins une prestation (colonne « Inclure »).", icon=":material/check_box:")
        else:
            infos_pdf = {**infos_pole, "numero": numero, "date": date.today(),
                         "client_nom": noms_clients.get(client_id, ""), "client_adresse": adresse,
                         "objet": objet,
                         "charge": (f"Charge de travail estimée pour ce dossier : {tm['estimation']['total']:g} h "
                                    f"(dossier {niveau.lower()})." if afficher_charge and niveau else "")}
            st.download_button("Devis PDF", type="primary", icon=":material/picture_as_pdf:",
                               data=devis.vers_pdf(infos_pdf, retenues, LOGO),
                               file_name=f"{nom_fichier(numero)}_{nom_fichier(noms_clients.get(client_id, ''))}.pdf",
                               mime="application/pdf")
            st.caption(":material/visibility: Relis le devis avant de l'envoyer.")



# ---------- Compte rendu au client ----------
with t_rendu:
    entete("summarize", "Compte rendu au client")
    if not client_id:
        st.info("Choisis un client dans le menu de gauche.", icon=":material/apartment:")
    else:
        commandees = [l["Prestation"] for l in (st.session_state.devis_lignes or [])
                      if l.get("Inclure") and str(l.get("Prestation") or "").strip()]
        options_r = list(dict.fromkeys([l.get("Prestation", "") for l in catalogue] + commandees))
        options_r = [o for o in options_r if o and "succès" not in o.lower()]
        prestations_r = st.multiselect("Prestations commandées par le client", options_r,
                                       default=[p for p in commandees if p in options_r],
                                       key=f"rendu_prest_{dossier_id}",
                                       help="Reprises du devis. Le document récapitule les actions de chacune.")
        ri = st.session_state.rendu_infos or {}
        champs_r = {"message": ri.get("message", "Vous trouverez ci-dessous le récapitulatif des actions réalisées "
                                                  "par le Pôle Marchés Publics de Sola Conseils pour votre dossier."),
                    "depot": ri.get("depot", ""), "suivi": ri.get("suivi", ""), "suite": ri.get("suite", "")}
        for k, v in champs_r.items():
            st.session_state.setdefault(f"rendu_{k}_{dossier_id}", v)
        message_r = st.text_area("Message d'introduction", key=f"rendu_message_{dossier_id}", height=90)
        depot_r = st.text_input("Dépôt de l'offre", key=f"rendu_depot_{dossier_id}",
                                placeholder="ex. déposé le 19/11/2026 à 15h20, accusé de réception n° …")
        suivi_r = ""
        if any("suivi" in p.lower() for p in prestations_r):
            suivi_r = st.text_area("Suivi de l'exécution", key=f"rendu_suivi_{dossier_id}", height=90)
        suite_r = st.text_area("Prochaines étapes", key=f"rendu_suite_{dossier_id}", height=90,
                               placeholder="ex. résultat attendu début décembre ; préparer la négociation…")
        synthese_r = ri.get("synthese", "")
        st.session_state.rendu_infos = {"message": message_r, "depot": depot_r, "suivi": suivi_r, "suite": suite_r,
                                        "prestations": prestations_r, "synthese": synthese_r} if prestations_r else (
                                        st.session_state.rendu_infos or None)
        if not prestations_r:
            st.info("Coche les prestations dans le devis, ou choisis-les ci-dessus.", icon=":material/request_quote:")
        else:
            infos_r = {"client": noms_clients.get(client_id, ""),
                       "dossier": noms_dossiers.get(dossier_id, "").split(" · ")[0] if dossier_id else "",
                       "date": datetime.now().strftime("%d/%m/%Y"), "auteur": UTILISATEUR["nom"],
                       "message": message_r, "depot": depot_r, "suivi": suivi_r, "suite": suite_r}
            entete("auto_awesome", "Synthèse pour le client")
            if st.button("Rédiger la synthèse pour le client", icon=":material/auto_awesome:",
                         type="secondary" if synthese_r else "primary"):
                with st.spinner("Rédaction de la synthèse…"):
                    texte_s = lancer(P11_SYNTHESE_CLIENT.format(**donnees_synthese(st.session_state, prestations_r,
                                                                                    infos_r)), "Synthèse client")
                if texte_s:
                    st.session_state.rendu_infos = {**st.session_state.rendu_infos, "synthese": texte_s}
                    st.session_state.pop(f"rendu_synth_{dossier_id}", None)
                    st.rerun()
            if synthese_r:
                cle_s = f"rendu_synth_{dossier_id}"
                st.session_state.setdefault(cle_s, synthese_r)
                with st.container(border=True):
                    st.markdown(st.session_state[cle_s])
                alerte_inventions(st.session_state[cle_s], st.session_state.fiche_flash or "", depot_r, suite_r)
                with st.expander("Modifier la synthèse", icon=":material/edit:"):
                    synthese_r = st.text_area("Synthèse", key=cle_s, height=420, label_visibility="collapsed")
                st.session_state.rendu_infos = {**st.session_state.rendu_infos, "synthese": synthese_r}
            else:
                st.caption(":material/info: Sans synthèse, le compte rendu ne contient que les actions réalisées "
                           "et l'analyse brute.")
            infos_r["synthese"] = synthese_r
            detail_r = st.checkbox("Joindre l'analyse détaillée en annexe (fiche flash, go/no-go, conformité)",
                                   value=not synthese_r, key=f"rendu_detail_{dossier_id}",
                                   help="Décoché : le client reçoit la synthèse et la liste des actions, "
                                        "sans notre analyse interne.")
            sections_r = sections_compte_rendu(st.session_state, prestations_r, infos_r, detail=detail_r)
            faites = sum(t.count("✔") for _, t in sections_r)
            a_venir = sum(t.count("☐") for _, t in sections_r)
            cartes([("checklist", "Prestations", len(prestations_r), TURQUOISE),
                    ("task_alt", "Actions réalisées", faites, VERT),
                    ("pending", "Actions restantes", a_venir, ORANGE if a_venir else GRIS)])
            with st.expander("Aperçu du compte rendu", icon=":material/visibility:"):
                for titre_r, texte_r in sections_r:
                    st.markdown(f"##### {titre_r}")
                    st.markdown(texte_r)
            st.download_button(
                "Compte rendu (Word)", icon=":material/description:", type="primary",
                data=markdown_vers_docx(sections_r, "Compte rendu de prestation",
                                        note="Pôle Marchés Publics · Sola Conseils · {date}", logo=LOGO,
                                        saut_de_page=False, sous_titre=f"**{infos_r['client']}**"),
                file_name=f"compte_rendu_{nom_fichier(infos_r['client'])}_{datetime.now():%Y%m%d}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.caption(":material/visibility: Relis le compte rendu avant de l'envoyer au client.")

# ---------- Enregistrement automatique (chiffré) ----------
def _empreinte(donnees) -> str:
    return hashlib.sha256(json.dumps(donnees, ensure_ascii=False, sort_keys=True, default=str)
                          .encode("utf-8")).hexdigest()


if client_id:
    contenu_client = json.loads(exporter_client(st.session_state.get("fiche_client_txt", ""),
                                                st.session_state.get("docs_client")).decode("utf-8"))
    contenu_client = {"fiche": contenu_client["fiche"], "documents": contenu_client["documents"],
                      "structure": st.session_state.get("fiche_structure") or fiche_client.structure_vide()}
    empreinte = _empreinte(contenu_client)
    if st.session_state.get("empreinte_client") is None:
        st.session_state.empreinte_client = empreinte
    elif empreinte != st.session_state.empreinte_client:
        BASE.enregistrer_client(client_id, contenu_client, QUI)
        st.session_state.empreinte_client = empreinte

if client_id and dossier_id:
    contenu_dossier = json.loads(exporter_dossier(st.session_state, "dossier").decode("utf-8"))
    contenu_dossier.pop("enregistre_le", None)
    empreinte = _empreinte(contenu_dossier)
    if st.session_state.get("empreinte_dossier") is None:
        st.session_state.empreinte_dossier = empreinte
    elif empreinte != st.session_state.empreinte_dossier:
        BASE.enregistrer_dossier(client_id, dossier_id, contenu_dossier, QUI)
        st.session_state.empreinte_dossier = empreinte
