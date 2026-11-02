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
from prompts_ao import P1_FICHE_FLASH, P2_GO_NO_GO, P3_EXIGENCES

load_dotenv()

BUDGET_FICHE_FLASH = 200_000  # caractères envoyés pour la fiche flash
ORDRE_PIECES = ["Avis", "RC", "Cadre de réponse", "CCAP", "AE", "CCTP", "DQE", "BPU", "DPGF", "Autre"]

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
    st.warning("Plan gratuit Mistral : vos données peuvent servir à l'entraînement. "
               "N'utilisez alors que des DCE publics, jamais de données clients.")
    if st.button("Recommencer à zéro"):
        st.session_state.clear()
        st.rerun()

st.title("Analyse de DCE")
st.caption("Prototype Pôle Marchés Publics — Sola Conseil. Toute sortie est un brouillon à vérifier.")

for k in ("pieces", "fiche_flash", "go_no_go", "exigences"):
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

# ---------- 3. Go/no-go ----------
if st.session_state.fiche_flash:
    st.subheader("3. Go/no-go (P2)")
    fiche_client = st.text_area(
        "Fiche client",
        placeholder="Activité, chiffre d'affaires, effectifs, 3 à 5 références (acheteur, objet, "
                    "montant, année), certifications, assurances, zone d'intervention, "
                    "positionnement prix…",
        height=180)
    if st.button("Analyser le go/no-go", disabled=not fiche_client.strip()):
        with st.spinner("Analyse en cours…"):
            st.session_state.go_no_go = lancer(P2_GO_NO_GO.format(
                fiche_flash=st.session_state.fiche_flash, fiche_client=fiche_client))
    if st.session_state.go_no_go:
        st.markdown(st.session_state.go_no_go)

# ---------- 4. Exigences ----------
if pieces:
    st.subheader("4. Liste des exigences (P3)")
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

# ---------- 5. Export ----------
sections = [(t, st.session_state[k]) for t, k in [
    ("Fiche flash", "fiche_flash"), ("Analyse go/no-go", "go_no_go"),
    ("Liste des exigences", "exigences")] if st.session_state[k]]
if sections:
    st.subheader("5. Exporter")
    nom = f"analyse_dce_{datetime.now():%Y%m%d_%H%M}.docx"
    st.download_button("Télécharger en Word", data=markdown_vers_docx(sections, "Analyse du DCE"),
                       file_name=nom,
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
