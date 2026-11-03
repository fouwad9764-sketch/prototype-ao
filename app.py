"""Prototype Sola Conseil — analyse d'un DCE avec Mistral.

Lancement : streamlit run app.py
"""

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from export_word import markdown_vers_docx
from extraction import decouper, deviner_type, lire_fichier
from llm_client import LLMError, appeler_ia, cle_depuis_env
from matrice import (COLONNES_MATRICE, compter, lignes_de_tableaux, lignes_matrice,
                     vers_excel, vers_markdown)
from prompts_ao import (EXEMPLE_CLIENT_FICTIF, P1_FICHE_FLASH, P2_GO_NO_GO, P3_EXIGENCES,
                        P4_MATRICE)

load_dotenv()

BUDGET_FICHE_FLASH = 200_000  # caractères envoyés pour la fiche flash
BUDGET_CLIENT = 150_000       # caractères du dossier client envoyés à la matrice
EXIGENCES_PAR_LOT = 25        # exigences envoyées par appel pour la matrice
ORDRE_PIECES = ["Avis", "RC", "Cadre de réponse", "CCAP", "AE", "CCTP", "DQE", "BPU", "DPGF", "Annexe", "Autre"]

st.set_page_config(page_title="Analyse DCE — Sola Conseil", page_icon="📑", layout="wide")


def secret(nom: str) -> str:
    """Lit un secret : d'abord les secrets de l'hébergement en ligne, sinon le fichier .env."""
    try:
        valeur = st.secrets.get(nom, "")
    except Exception:  # pas de fichier de secrets en local
        valeur = ""
    return str(valeur or os.getenv(nom, "")).strip()


# ---------- Mot de passe d'accès (version en ligne) ----------
MOT_DE_PASSE = secret("APP_PASSWORD")
if MOT_DE_PASSE and not st.session_state.get("connecte"):
    st.title("Analyse de DCE — Sola Conseil")
    saisie = st.text_input("Mot de passe", type="password")
    if st.button("Entrer"):
        if saisie == MOT_DE_PASSE:
            st.session_state.connecte = True
            st.rerun()
        st.error("Mot de passe incorrect.")
    st.stop()

# ---------- Barre latérale : réglages ----------
with st.sidebar:
    st.header("Réglages")
    cle_enregistree = secret("MISTRAL_API_KEY") or cle_depuis_env()
    if cle_enregistree:
        cle = cle_enregistree
        st.success("Clé API Mistral chargée.")
    else:
        cle = st.text_input("Clé API Mistral", type="password",
                            help="À enregistrer dans les secrets de l'hébergement pour ne plus la saisir.")
    modele = st.selectbox("Modèle", ["mistral-large-latest", "mistral-medium-latest",
                                     "mistral-small-latest"],
                          help="Large = plus fiable, Small = plus rapide et moins cher.")
    st.info("Phase de test : hébergement hors UE. Déposez uniquement des DCE publics, "
            "pas de données confidentielles de clients.")
    if st.button("Recommencer à zéro"):
        st.session_state.clear()
        st.rerun()

st.title("Analyse de DCE")
st.caption("Prototype Pôle Marchés Publics — Sola Conseil. Toute sortie est un brouillon à vérifier.")

for k in ("pieces", "fiche_flash", "go_no_go", "exigences", "docs_client", "matrice"):
    st.session_state.setdefault(k, None)

# ---------- 1. Import ----------
st.subheader("1. Importer le DCE")
fichiers = st.file_uploader("Pièces du DCE (PDF, DOCX, XLSX, TXT ou ZIP)", accept_multiple_files=True,
                            type=["pdf", "docx", "xlsx", "txt", "zip"])

if fichiers and st.button("Lire les fichiers", type="primary"):
    pieces = []
    with st.spinner("Lecture des pièces…"):
        for f in fichiers:
            pieces.extend(lire_fichier(f.name, f.getvalue()))
    for p in pieces:
        p.type = deviner_type(p.nom)
    pieces.sort(key=lambda p: ORDRE_PIECES.index(p.type))
    st.session_state.pieces = pieces
    st.session_state.fiche_flash = st.session_state.go_no_go = st.session_state.exigences = None
    st.session_state.matrice = None

pieces = st.session_state.pieces
if pieces:
    st.dataframe(
        [{"Pièce": p.nom, "Type présumé": p.type, "Caractères": p.nb_caracteres,
          "Alertes": " ; ".join(p.alertes)} for p in pieces],
        use_container_width=True, hide_index=True)
    lisibles = [p for p in pieces if p.texte.strip()]
    if not lisibles:
        st.error("Aucun texte lisible. Les PDF scannés ne sont pas encore gérés.")
        st.stop()


def lancer(prompt: str) -> str | None:
    try:
        return appeler_ia(prompt, cle, modele)
    except LLMError as exc:
        st.error(str(exc))
        return None


# ---------- 2. Fiche flash ----------
if pieces:
    st.subheader("2. Fiche flash (P1)")
    if st.button("Générer la fiche flash"):
        corpus, total = [], 0
        for p in lisibles:
            reste = BUDGET_FICHE_FLASH - total
            if reste <= 0:
                break
            corpus.append(f"===== {p.nom} ({p.type}) =====\n{p.texte[:reste]}")
            total += min(len(p.texte), reste)
        if total >= BUDGET_FICHE_FLASH:
            st.info("DCE long : seule la première partie (Avis, RC, CCAP en priorité) a servi à la fiche flash.")
        with st.spinner("Mistral lit le dossier…"):
            st.session_state.fiche_flash = lancer(P1_FICHE_FLASH.format(documents="\n\n".join(corpus)))
    if st.session_state.fiche_flash:
        st.markdown(st.session_state.fiche_flash)

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


if pieces:
    st.subheader("3. Profil du client")
    st.caption("Utilisé par le go/no-go et par la matrice de conformité.")
    st.button("Charger un client fictif (test)", on_click=charger_exemple)
    st.text_area(
        "Fiche client", key="fiche_client_txt", height=200,
        placeholder="Nom, activité, chiffre d'affaires des 3 dernières années, effectifs, "
                    "habilitations et certifications, matériel, assurances, références "
                    "(acheteur, objet, montant, année), zone d'intervention…")
    docs = st.file_uploader("Documents du client (facultatif : plaquette, Kbis, attestations, CV, références…)",
                            accept_multiple_files=True, type=["pdf", "docx", "xlsx", "txt"], key="up_client")
    if docs and st.button("Lire les documents du client"):
        lus = []
        for f in docs:
            lus.extend(lire_fichier(f.name, f.getvalue()))
        st.session_state.docs_client = lus
    if st.session_state.docs_client:
        st.dataframe([{"Document client": d.nom, "Caractères": d.nb_caracteres,
                       "Alertes": " ; ".join(d.alertes)} for d in st.session_state.docs_client],
                     use_container_width=True, hide_index=True)

PROFIL = profil_client() if pieces else ""

# ---------- 4. Go/no-go ----------
if st.session_state.fiche_flash:
    st.subheader("4. Go/no-go (P2)")
    if st.button("Analyser le go/no-go", disabled=not PROFIL):
        with st.spinner("Analyse en cours…"):
            st.session_state.go_no_go = lancer(P2_GO_NO_GO.format(
                fiche_flash=st.session_state.fiche_flash, fiche_client=PROFIL))
    if not PROFIL:
        st.caption("Renseigne d'abord le profil du client (étape 3).")
    if st.session_state.go_no_go:
        st.markdown(st.session_state.go_no_go)

# ---------- 4. Exigences ----------
if pieces:
    st.subheader("5. Liste des exigences (P3)")
    st.caption("Chaque pièce est analysée séparément, puis les résultats sont regroupés.")
    choix = st.multiselect("Pièces à analyser", [p.nom for p in lisibles],
                           default=[p.nom for p in lisibles if p.type in ("RC", "CCAP", "CCTP", "Cadre de réponse")])
    if st.button("Extraire les exigences", disabled=not choix):
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
                                                partie=partie, texte=morceau))
            if sortie is None:
                break
            resultats.append(f"## {p.nom}{partie}\n\n{sortie}")
        barre.progress(1.0, text="Terminé")
        if resultats:
            st.session_state.exigences = "\n\n".join(resultats)
    if st.session_state.exigences:
        with st.expander("Voir les exigences", expanded=True):
            st.markdown(st.session_state.exigences)

# ---------- 6. Matrice de conformité ----------
if st.session_state.exigences:
    st.subheader("6. Matrice de conformité : exigences face aux capacités du client (P4)")
    exigences_lignes = lignes_de_tableaux(st.session_state.exigences)
    st.caption(f"{len(exigences_lignes)} exigences repérées à l'étape 5. Chaque statut reste à valider.")
    if st.button("Construire la matrice", disabled=not (PROFIL and exigences_lignes)):
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
            sortie = lancer(P4_MATRICE.format(exigences="\n".join(liste), profil_client=PROFIL))
            if sortie is None:
                break
            sorties.append(sortie)
        barre.progress(1.0, text="Terminé")
        if sorties:
            st.session_state.matrice = lignes_matrice("\n\n".join(sorties))
            if len(st.session_state.matrice) != len(exigences_lignes):
                st.warning(f"{len(st.session_state.matrice)} lignes produites pour "
                           f"{len(exigences_lignes)} exigences : vérifie qu'aucune n'a été oubliée.")
    if not PROFIL:
        st.caption("Renseigne d'abord le profil du client (étape 3).")

    matrice = st.session_state.matrice
    if matrice:
        comptes = compter(matrice)
        colonnes = st.columns(len(comptes))
        for col, (statut, nombre) in zip(colonnes, comptes.items()):
            col.metric(statut.capitalize(), nombre)
        filtre = st.multiselect("Afficher les statuts", list(comptes),
                                default=[s for s in comptes if s != "SANS OBJET"])
        st.dataframe([l for l in matrice if l["Statut"] in filtre], column_order=COLONNES_MATRICE,
                     use_container_width=True, hide_index=True)
        nom_client = (st.session_state.get("fiche_client_txt", "").strip().splitlines() or [""])[0][:80]
        st.download_button("Télécharger la matrice en Excel", data=vers_excel(matrice, nom_client),
                           file_name=f"matrice_conformite_{datetime.now():%Y%m%d_%H%M}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------- 7. Export ----------
sections = [(t, st.session_state[k]) for t, k in [
    ("Fiche flash", "fiche_flash"), ("Analyse go/no-go", "go_no_go"),
    ("Liste des exigences", "exigences")] if st.session_state[k]]
if st.session_state.matrice:
    sections.append(("Matrice de conformité", vers_markdown(st.session_state.matrice)))
if sections:
    st.subheader("7. Exporter")
    nom = f"analyse_dce_{datetime.now():%Y%m%d_%H%M}.docx"
    st.download_button("Télécharger en Word", data=markdown_vers_docx(sections, "Analyse du DCE"),
                       file_name=nom,
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
