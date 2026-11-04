"""Identification du type de marché et estimation du temps de traitement du dossier.

L'IA lit le DCE et renvoie des caractéristiques (nature, procédure, prix, mémoire…).
Le calcul des heures est fait ici, en Python, avec des règles visibles et modifiables :
pas de « boîte noire », chaque poste du total est expliqué.
"""

import json
import re
from datetime import datetime

NATURES = ["Travaux", "Fournitures", "Services", "Prestations intellectuelles", "Mixte"]

P7_TYPE_MARCHE = """Tu es un expert de la commande publique française. Lis les pièces du DCE
ci-dessous et identifie les caractéristiques du marché.

Réponds UNIQUEMENT par un objet JSON valide (sans texte autour, sans ```), avec ces clés :
{{
 "objet": "objet du marché en une phrase",
 "acheteur": "nom de l'acheteur",
 "nature": "Travaux" | "Fournitures" | "Services" | "Prestations intellectuelles" | "Mixte",
 "sous_type": "précision en quelques mots (ex. maîtrise d'œuvre, AMO, nettoyage, VRD, fourniture de mobilier…)",
 "procedure": "Procédure adaptée (MAPA)" | "Appel d'offres ouvert" | "Appel d'offres restreint" | "Procédure avec négociation" | "Dialogue compétitif" | "Concours" | "Marché sans publicité ni mise en concurrence" | "non trouvé",
 "forme": "Marché ordinaire" | "Accord-cadre à bons de commande" | "Accord-cadre à marchés subséquents" | "Accord-cadre mixte" | "Marché à tranches" | "non trouvé",
 "nb_lots": nombre entier (1 si non alloti),
 "montant_estime": "montant indiqué dans le DCE avec sa source, sinon non trouvé",
 "duree": "durée du marché, sinon non trouvé",
 "date_limite": "JJ/MM/AAAA HH:MM (heure de l'acheteur), sinon non trouvé",
 "memoire_technique": "oui" | "non" | "non trouvé",
 "poids_technique": pourcentage entier de la valeur technique dans les critères, ou null,
 "type_prix": "DPGF" | "BPU/DQE" | "Forfait (acte d'engagement seul)" | "Mixte" | "non trouvé",
 "visite_obligatoire": "oui" | "non" | "non trouvé",
 "echantillons": "oui" | "non" | "non trouvé",
 "variantes": "exigées" | "autorisées" | "interdites" | "non trouvé",
 "negociation": "oui" | "non" | "possible" | "non trouvé",
 "justification": "2 phrases maximum citant les pièces et pages qui fondent la nature et la procédure"
}}

Règles :
- Maîtrise d'œuvre, études, AMO, conseil, OPC, CSPS, contrôle technique = "Prestations intellectuelles".
- N'invente rien : une information absente vaut "non trouvé" (ou null pour poids_technique).
- Si l'avis et le règlement de consultation se contredisent, retiens le règlement et signale-le
  dans "justification".

PIÈCES DU DCE :
{documents}
"""

# Heures de référence du mémoire technique selon la nature (dossier d'un lot, client déjà connu)
MEMOIRE_PAR_NATURE = {"Travaux": 10, "Fournitures": 6, "Services": 8,
                      "Prestations intellectuelles": 14, "Mixte": 12}
PRIX_PAR_TYPE = {"DPGF": 4, "BPU/DQE": 3, "Forfait (acte d'engagement seul)": 1, "Mixte": 4}
SEUILS_NIVEAU = ((15, "Simple"), (30, "Moyen"))  # au-delà : Complexe


def lire_json(texte: str) -> dict:
    """Extrait l'objet JSON renvoyé par l'IA (tolère les ``` et le texte parasite)."""
    if not texte:
        raise ValueError("Réponse vide de l'IA.")
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        raise ValueError("L'IA n'a pas renvoyé de données exploitables. Relance l'identification.")
    try:
        return json.loads(texte[debut:fin + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Réponse de l'IA mal formée. Relance l'identification.") from exc


def _oui(valeur) -> bool:
    return str(valeur or "").strip().lower() == "oui"


def estimer_charge(carac: dict, nb_lots_vises: int = 1, nb_caracteres: int = 0,
                   client_nouveau: bool = False) -> dict:
    """Renvoie {"postes": [(poste, heures, explication)], "total": h, "niveau": ...}."""
    nature = carac.get("nature") if carac.get("nature") in NATURES else "Services"
    lots = max(1, int(nb_lots_vises or 1))
    postes = []

    lecture = max(2.0, round(nb_caracteres / 100_000, 1)) if nb_caracteres else 3.0
    postes.append(("Lecture et analyse du DCE", lecture, "2 h minimum, 1 h par tranche de 100 000 caractères"))
    postes.append(("Qualification et go/no-go", 1.0, "fiche flash, matrice, décision avec le client"))
    if client_nouveau:
        postes.append(("Constitution du dossier client", 3.0, "premier dossier : collecte des pièces et références"))
    postes.append(("Candidature administrative", 2.0, "DC1, DC2 ou DUME, attestations, pouvoirs"))

    if carac.get("memoire_technique") != "non":
        base = MEMOIRE_PAR_NATURE[nature]
        poids = carac.get("poids_technique")
        explication = f"référence {nature.lower()} : {base} h"
        if isinstance(poids, (int, float)) and poids >= 50:
            base *= 1.5
            explication += f", × 1,5 car la valeur technique pèse {int(poids)} %"
        if lots > 1:
            supplement = base * 0.4 * (lots - 1)
            explication += f", + 40 % par lot supplémentaire ({lots} lots)"
            base += supplement
        postes.append(("Mémoire technique", round(base, 1), explication))

    prix = PRIX_PAR_TYPE.get(carac.get("type_prix"), 2)
    if lots > 1:
        prix += prix * 0.5 * (lots - 1)
    postes.append(("Offre financière", round(prix, 1),
                   f"{carac.get('type_prix') or 'type de prix non trouvé'}"
                   + (f", + 50 % par lot supplémentaire" if lots > 1 else "")))

    if _oui(carac.get("visite_obligatoire")):
        postes.append(("Visite obligatoire", 3.0, "déplacement, visite et compte rendu"))
    if _oui(carac.get("echantillons")):
        postes.append(("Échantillons", 2.0, "préparation et remise des échantillons"))
    if carac.get("variantes") == "exigées":
        postes.append(("Variante exigée", 3.0, "solution variante à rédiger et chiffrer"))
    if str(carac.get("forme", "")).startswith("Accord-cadre à marchés subséquents"):
        postes.append(("Accord-cadre à marchés subséquents", 1.0, "veille et préparation des remises en concurrence"))

    postes.append(("Relecture, validation client, signature", 2.0, "relecture croisée et signature électronique"))
    postes.append(("Dépôt sur la plateforme", 1.0, "dépôt, accusé de réception, archivage"))

    total = round(sum(h for _, h, _ in postes), 1)
    niveau = next((nom for seuil, nom in SEUILS_NIVEAU if total < seuil), "Complexe")
    return {"postes": postes, "total": total, "niveau": niveau}


def jours_ouvres_restants(date_limite: str, aujourd_hui: datetime | None = None) -> int | None:
    """Nombre de jours ouvrés (lundi-vendredi) entre aujourd'hui et la date limite, sinon None."""
    trouve = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", str(date_limite or ""))
    if not trouve:
        return None
    j, m, a = (int(x) for x in trouve.groups())
    if a < 100:
        a += 2000
    try:
        fin = datetime(a, m, j)
    except ValueError:
        return None
    debut = (aujourd_hui or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    jours, courant = 0, debut
    from datetime import timedelta
    while courant < fin:
        courant += timedelta(days=1)
        if courant.weekday() < 5:
            jours += 1
    return jours
