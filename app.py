"""Prototype Sola Conseil — analyse d'un DCE avec Mistral.

Lancement : streamlit run app.py
"""

import os
from datetime import datetime

import importlib

import streamlit as st
from dotenv import load_dotenv

import dossier_io, export_word, extraction, llm_client, mail_client, matrice, prompts_ao
for _module in (export_word, extraction, llm_client, mail_client, matrice, prompts_ao, dossier_io):
    importlib.reload(_module)  # toujours la version la plus récente déposée sur GitHub

import time

from dossier_io import exporter_client, exporter_dossier, importer_client, importer_dossier, nom_fichier
from export_word import markdown_vers_docx
from extraction import decouper, deviner_type, lire_fichier
from llm_client import LLMError, appeler_ia, cle_depuis_env
from mail_client import envoyer, lien_mailto, separer_objet, smtp_configure
from matrice import (COLONNES_MATRICE, checklist_vers_excel, compter, lignes_checklist,
                     lignes_de_tableaux, lignes_matrice, vers_excel, vers_markdown)
from prompts_ao import (EXEMPLE_CLIENT_FICTIF, P1_FICHE_FLASH, P2_GO_NO_GO, P3_EXIGENCES,
                        P3B_CONSOLIDATION, P4_MATRICE, P5_MAIL_CLIENT, P6_DC1_DC2)

VERSION = "v10 (04/11/2026)"
LOGO = "logo_sola.png"

load_dotenv()

BUDGET_FICHE_FLASH = 200_000  # caractères envoyés pour la fiche flash
BUDGET_CLIENT = 150_000       # caractères du dossier client envoyés à la matrice
EXIGENCES_PAR_LOT = 25        # exigences envoyées par appel pour la matrice
ORDRE_PIECES = ["Avis", "RC", "Cadre de réponse", "CCAP", "AE", "CCTP", "DQE", "BPU", "DPGF", "Annexe", "Autre"]

st.set_page_config(page_title="Pôle Marchés Publics — Sola Conseils", page_icon=LOGO, layout="wide")

STATUT_STYLE = {"CONFORME": ("#DDF3E4", "#1E6B3A"), "PARTIEL": ("#FFF1D6", "#8A5A00"),
                "NON CONFORME": ("#FDE2E2", "#9B1C1C"), "À VÉRIFIER": ("#E2ECF8", "#1F4E8C"),
                "SANS OBJET": ("#EEF0F2", "#4B5563")}

st.markdown("""<style>
button[data-baseweb="tab"] p {font-size: 1rem; font-weight: 600;}
.stButton button, .stDownloadButton button, .stLinkButton a {min-height: 2.75rem;}
div[data-testid="stMetric"] {border-left: 4px solid #00788A; padding-left: .75rem;}
</style>""", unsafe_allow_html=True)


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


# ---------- Mot de passe d'accès (version en ligne) ----------
MOT_DE_PASSE = secret("APP_PASSWORD")
if MOT_DE_PASSE and not st.session_state.get("connecte"):
    st.image(LOGO, width=120)
    st.title("Pôle Marchés Publics — Sola Conseils")
    saisie = st.text_input("Mot de passe", type="password")
    if st.button("Entrer"):
        if saisie == MOT_DE_PASSE:
            st.session_state.connecte = True
            st.rerun()
        st.error("Mot de passe incorrect.")
    st.stop()

# ---------- Barre latérale : réglages ----------
with st.sidebar:
    st.image(LOGO, width=110)
    st.markdown("**Sola Conseils**  \nPôle Marchés Publics")
    st.divider()
    st.header("Réglages")
    st.caption(f"Version de l'outil : {VERSION}")
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

    st.divider()
    st.subheader("Dossiers et clients")
    st.caption("L'outil oublie tout à la fermeture : sauvegarde ton dossier dans Fichiers, "
               "puis recharge-le pour reprendre.")
    nom_dossier = st.text_input("Nom du dossier", key="nom_dossier",
                                placeholder="ex. EDM réseaux BT - Électro Lagon")
    st.download_button("Sauvegarder le dossier", use_container_width=True,
                       data=exporter_dossier(st.session_state, nom_dossier or "dossier"),
                       file_name=f"dossier_{nom_fichier(nom_dossier)}_{datetime.now():%Y%m%d_%H%M}.json",
                       mime="application/json")
    fichier_dossier = st.file_uploader("Reprendre un dossier (.json)", type=["json"], key="up_dossier")
    if fichier_dossier and st.button("Charger ce dossier", use_container_width=True):
        try:
            charge = importer_dossier(fichier_dossier.getvalue())
            for cle_etat, valeur in charge["etat"].items():
                st.session_state[cle_etat] = valeur
            st.session_state.pop("editeur_checklist", None)
            st.session_state["nom_dossier_charge"] = f"{charge['nom']} (enregistré le {charge['enregistre_le']})"
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.get("nom_dossier_charge"):
        st.success(f"Dossier repris : {st.session_state['nom_dossier_charge']}")

    st.download_button("Sauvegarder la fiche client", use_container_width=True,
                       data=exporter_client(st.session_state.get("fiche_client_txt", ""),
                                            st.session_state.get("docs_client")),
                       file_name="client_" + nom_fichier((st.session_state.get("fiche_client_txt", "").strip()
                                                          .splitlines() or ["client"])[0]) + ".json",
                       mime="application/json",
                       disabled=not st.session_state.get("fiche_client_txt", "").strip())
    fichier_client = st.file_uploader("Charger une fiche client (.json)", type=["json"], key="up_fiche_client")
    if fichier_client and st.button("Utiliser cette fiche client", use_container_width=True):
        try:
            fiche, docs_c = importer_client(fichier_client.getvalue())
            st.session_state["fiche_client_txt"] = fiche
            st.session_state["docs_client"] = docs_c
            st.session_state["matrice"] = st.session_state["checklist"] = st.session_state["go_no_go"] = None
            st.session_state.pop("editeur_checklist", None)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

st.title("Préparer une réponse à un appel d'offres")
st.caption("Pôle Marchés Publics — Sola Conseils · Toute sortie est un brouillon à valider avant usage.")

for k in ("pieces", "fiche_flash", "go_no_go", "exigences", "exigences_brutes", "docs_client", "matrice",
          "checklist", "mail_brouillon", "journal_mails", "chronos", "dc1_dc2"):
    st.session_state.setdefault(k, None)

def lancer(prompt: str, etape: str = "Analyse") -> str | None:
    """Appelle l'IA et chronomètre l'appel (pour mesurer le temps gagné)."""
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

t_dossier, t_client, t_exigences, t_matrice, t_candidature, t_export = st.tabs(
    ["1. Dossier", "2. Client et go/no-go", "3. Exigences", "4. Matrice", "5. Candidature", "6. Export"])

pieces = st.session_state.pieces
lisibles = [p for p in (pieces or []) if p.texte.strip()]
PROFIL = ""

with t_dossier:
    # ---------- 1. Import ----------
    st.subheader("Importer le DCE")
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


    # ---------- 2. Fiche flash ----------
    if pieces:
        st.subheader("Fiche flash")
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
                st.session_state.fiche_flash = lancer(P1_FICHE_FLASH.format(documents="\n\n".join(corpus)), "Fiche flash")
        if st.session_state.fiche_flash:
            st.markdown(st.session_state.fiche_flash)

with t_client:
    if not pieces:
        st.info("Commence par importer et lire le DCE dans l'onglet « 1. Dossier ».")
    if pieces:
        st.subheader("Profil du client")
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
        st.subheader("Go/no-go")
        if st.button("Analyser le go/no-go", disabled=not PROFIL):
            with st.spinner("Analyse en cours…"):
                st.session_state.go_no_go = lancer(P2_GO_NO_GO.format(
                    fiche_flash=st.session_state.fiche_flash, fiche_client=PROFIL,
                    date_du_jour=datetime.now().strftime("%d/%m/%Y")), "Go/no-go")
        if not PROFIL:
            st.caption("Renseigne d'abord le profil du client (onglet 2).")
        if st.session_state.go_no_go:
            st.markdown(st.session_state.go_no_go)

with t_exigences:
    if not pieces:
        st.info("Commence par importer et lire le DCE dans l'onglet « 1. Dossier ».")
    # ---------- 5. Exigences ----------
    if pieces:
        st.subheader("Liste des exigences")
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
                st.success(f"{len(st.session_state.exigences_brutes)} exigences brutes regroupées en "
                           f"{nb_final} exigences utiles.")
            with st.expander("Voir les exigences", expanded=True):
                st.markdown(st.session_state.exigences)

with t_matrice:
    if not st.session_state.exigences:
        st.info("Extrais d'abord les exigences dans l'onglet « 3. Exigences ».")
    # ---------- 6. Matrice de conformité ----------
    if st.session_state.exigences:
        st.subheader("Matrice de conformité : exigences face aux capacités du client")
        toutes = lignes_de_tableaux(st.session_state.exigences)
        phases = ["Candidature", "Dépôt", "Offre", "Exécution"]
        if any(len(c) > 2 and c[2].strip() for c in toutes):
            retenues = st.multiselect("Phases à inclure dans la matrice", phases,
                                      default=["Candidature", "Dépôt"])
            exigences_lignes = [c for c in toutes if len(c) < 3 or not c[2].strip()
                                or any(p.lower() in c[2].lower() for p in retenues)]
        else:
            exigences_lignes = toutes
        st.caption(f"{len(exigences_lignes)} exigences retenues sur {len(toutes)}. Chaque statut reste à valider.")
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
                sortie = lancer(P4_MATRICE.format(exigences="\n".join(liste), profil_client=PROFIL), "Matrice")
                if sortie is None:
                    break
                sorties.append(sortie)
            barre.progress(1.0, text="Terminé")
            if sorties:
                st.session_state.matrice = lignes_matrice("\n\n".join(sorties))
                st.session_state.checklist = None
                st.session_state.mail_brouillon = None
                if len(st.session_state.matrice) != len(exigences_lignes):
                    st.warning(f"{len(st.session_state.matrice)} lignes produites pour "
                               f"{len(exigences_lignes)} exigences : vérifie qu'aucune n'a été oubliée.")
        if not PROFIL:
            st.caption("Renseigne d'abord le profil du client (onglet 2).")

        matrice = st.session_state.matrice
        if matrice:
            comptes = compter(matrice)
            colonnes = st.columns(len(comptes))
            for col, (statut, nombre) in zip(colonnes, comptes.items()):
                col.metric(statut.capitalize(), nombre)
            if comptes["NON CONFORME"]:
                st.error(f"{comptes['NON CONFORME']} point(s) bloquant(s) : à régler avant de décider de candidater.")
            filtre = st.multiselect("Afficher les statuts", list(comptes),
                                    default=[s for s in comptes if s != "SANS OBJET"])
            visibles = [l for l in matrice if l["Statut"] in filtre]
            if visibles:
                st.dataframe(tableau_statuts(visibles, COLONNES_MATRICE),
                             use_container_width=True, hide_index=True)
            nom_client = (st.session_state.get("fiche_client_txt", "").strip().splitlines() or [""])[0][:80]
            st.download_button("Télécharger la matrice en Excel", data=vers_excel(matrice, nom_client),
                               file_name=f"matrice_conformite_{datetime.now():%Y%m%d_%H%M}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with t_candidature:
    if not st.session_state.matrice:
        st.info("Construis d'abord la matrice dans l'onglet « 4. Matrice ».")
    if st.session_state.matrice:
        st.subheader("Check-list de candidature et e-mail au client")
        nom_client = (st.session_state.get("fiche_client_txt", "").strip().splitlines() or [""])[0][:80]

        if st.session_state.checklist is None:
            st.session_state.checklist = lignes_checklist(st.session_state.matrice)
        st.caption("Coche au fur et à mesure. « Bloquant » = à régler avant de décider de candidater.")
        edite = st.data_editor(st.session_state.checklist, key="editeur_checklist", hide_index=True,
                               use_container_width=True, disabled=["Priorité", "Exigence", "Statut", "Source DCE"],
                               column_config={"Fait": st.column_config.CheckboxColumn("Fait"),
                                              "Qui": st.column_config.SelectboxColumn(
                                                  "Qui", options=["Client", "Sola Conseil"])})
        st.session_state.checklist = edite
        faits = sum(1 for l in edite if l["Fait"])
        st.progress(faits / max(len(edite), 1), text=f"{faits} / {len(edite)} éléments traités")
        st.download_button("Télécharger la check-list en Excel",
                           data=checklist_vers_excel(edite, f"Check-list de candidature : {nom_client}"),
                           file_name=f"checklist_candidature_{datetime.now():%Y%m%d_%H%M}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("**E-mail au client : pièces et informations à transmettre**")
        a_obtenir = [l for l in edite if not l["Fait"] and l["Statut"] != "CONFORME"
                     and (l["Qui"] == "Client" or l["Statut"] == "NON CONFORME")]
        col1, col2 = st.columns(2)
        email_client = col1.text_input("E-mail du client")
        date_retour = col2.date_input("Date de retour souhaitée", format="DD/MM/YYYY")
        signature = CONFIG_MAIL["SIGNATURE"] or st.text_input(
            "Signature", value="Responsable Pôle Marchés Publics\nSola Conseil")
        if st.button(f"Rédiger l'e-mail ({len(a_obtenir)} éléments à demander)", disabled=not a_obtenir):
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
            corps = st.text_area("Message (modifiable)", value=st.session_state.mail_brouillon[1], height=320)
            responsable = CONFIG_MAIL["EXPEDITEUR"]
            copie = responsable if responsable and st.checkbox("Mettre le responsable du pôle en copie", value=True) else ""
            if email_client:
                st.link_button("Ouvrir dans l'app Mail", lien_mailto(email_client, objet, corps, copie))
            if smtp_configure(CONFIG_MAIL):
                relu = st.checkbox("J'ai relu l'e-mail et je confirme l'envoi au client")
                joindre = st.checkbox("Joindre la check-list Excel", value=True)
                if st.button("Envoyer maintenant depuis la boîte du pôle", type="primary",
                             disabled=not (relu and email_client and "@" in email_client)):
                    pj = [("checklist_candidature.xlsx", checklist_vers_excel(edite, f"Check-list : {nom_client}"),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")] if joindre else []
                    try:
                        envoyer(CONFIG_MAIL, email_client, objet, corps, copie, pj)
                        journal = st.session_state.journal_mails or []
                        journal.append({"Date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                        "À": email_client, "Objet": objet})
                        st.session_state.journal_mails = journal
                        st.success(f"E-mail envoyé à {email_client}" + (f" (copie : {copie})" if copie else "") + ".")
                    except Exception as exc:
                        st.error(f"Envoi impossible : {exc}. Vérifie les réglages SMTP dans les Secrets.")
            else:
                st.caption("Envoi direct non configuré : utilise « Ouvrir dans l'app Mail », ou ajoute les "
                           "réglages SMTP de la boîte du pôle dans les Secrets.")
            if st.session_state.journal_mails:
                st.dataframe(st.session_state.journal_mails, hide_index=True, use_container_width=True)

with t_candidature:
    if st.session_state.fiche_flash:
        st.divider()
        st.subheader("Préparer le DC1 et le DC2")
        st.caption("Fiche d'aide au remplissage des formulaires officiels (à télécharger sur le site "
                   "du ministère de l'Économie), ou du DUME. Les cases « [À COMPLÉTER] » restent à remplir.")
        profil_dc = profil_client()
        if st.button("Préparer la fiche DC1 / DC2", disabled=not profil_dc):
            synthese = "\n".join(f"- {l['Exigence']} → {l['Statut']}" for l in (st.session_state.matrice or []))
            with st.spinner("Préparation des formulaires…"):
                st.session_state.dc1_dc2 = lancer(P6_DC1_DC2.format(
                    fiche_flash=st.session_state.fiche_flash, fiche_client=profil_dc,
                    matrice=synthese or "Matrice non construite."), "DC1 / DC2")
        if not profil_dc:
            st.caption("Renseigne d'abord le profil du client (onglet 2).")
        if st.session_state.dc1_dc2:
            a_completer = st.session_state.dc1_dc2.count("[À COMPLÉTER")
            if a_completer:
                st.warning(f"{a_completer} champ(s) à compléter avec le client.")
            st.markdown(st.session_state.dc1_dc2)
            st.download_button("Télécharger la fiche DC1 / DC2 en Word",
                               data=markdown_vers_docx([("Fiche d'aide au remplissage DC1 / DC2",
                                                         st.session_state.dc1_dc2)], "Préparation DC1 / DC2"),
                               file_name=f"preparation_DC1_DC2_{datetime.now():%Y%m%d_%H%M}.docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

with t_export:
    if st.session_state.chronos:
        st.subheader("Temps de travail de l'IA sur ce dossier")
        total = sum(c["Durée (s)"] for c in st.session_state.chronos)
        c1, c2 = st.columns(2)
        c1.metric("Temps total de l'IA", f"{total / 60:.1f} min")
        c2.metric("Appels réalisés", len(st.session_state.chronos))
        st.caption("Ajoute ton temps de relecture pour obtenir le temps réel du dossier, "
                   "et compare-le au temps d'une analyse manuelle.")
        with st.expander("Détail par étape"):
            st.dataframe(st.session_state.chronos, hide_index=True, use_container_width=True)

    # ---------- 8. Export ----------
    sections = [(t, st.session_state[k]) for t, k in [
        ("Fiche flash", "fiche_flash"), ("Analyse go/no-go", "go_no_go"),
        ("Liste des exigences", "exigences"), ("Préparation DC1 / DC2", "dc1_dc2")] if st.session_state[k]]
    if st.session_state.matrice:
        sections.append(("Matrice de conformité", vers_markdown(st.session_state.matrice)))
    if sections:
        st.subheader("Exporter le dossier d'analyse")
        nom = f"analyse_dce_{datetime.now():%Y%m%d_%H%M}.docx"
        st.download_button("Télécharger en Word", data=markdown_vers_docx(sections, "Analyse du DCE"),
                           file_name=nom,
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

