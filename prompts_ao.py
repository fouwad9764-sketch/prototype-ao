"""Prompts du prototype, repris de la bibliothèque prompts.md de Sola Conseil (P1, P2, P3)."""

P1_FICHE_FLASH = """Rôle : chargé d'affaires marchés publics chez Sola Conseil.
À partir des pièces ci-dessous (avis, RC et autres pièces disponibles), produis une fiche
de synthèse d'une page.

# Fiche flash

Tableau à deux colonnes | Rubrique | Information (source) | avec ces lignes :
- Objet du marché (une phrase)
- Acheteur
- Procédure
- Allotissement et lots
- Date et heure limite de remise des offres
- Date limite des questions
- Durée et reconductions
- Montant estimé ou maximum
- Critères d'attribution et pondérations
- Formule de notation du prix
- Conditions de participation (CA minimum, références, certifications, assurances)
- Visite obligatoire
- Négociation prévue
- Variantes et PSE
- Modalités de dépôt et de signature

Puis une section « ## Points de vigilance » avec trois points maximum.
Pas de commentaire commercial. Source (pièce et page) pour chaque ligne ; « non trouvé » sinon.

PIÈCES :
{documents}
"""

P2_GO_NO_GO = """Rôle : analyste chargé de protéger le temps de l'équipe. Tu cherches les
raisons de NE PAS répondre autant que celles de répondre.

# Analyse go/no-go

## Arguments contre (à exposer en premier)

## Notation
Tableau | Critère | Note /5 | Justification (une ligne) | avec :
1. Adéquation entre le besoin et le savoir-faire du client
2. Capacités exigées atteintes (oui / non / partiellement, avec la preuve)
3. Références comparables disponibles
4. Compétitivité prix probable au regard de la pondération du prix
5. Délai restant face à la charge de travail
6. Intérêt stratégique

## Points bloquants
## Besoin de groupement ou de sous-traitance
## Recommandation
GO / NO-GO / À ARBITRER, puis les deux faits qui inverseraient la décision.

Règles : ne te fonde que sur la fiche client fournie. Si une information manque dans la fiche
client, note-la « à demander au client » au lieu de supposer. La décision finale reste humaine.

FICHE FLASH DU MARCHÉ :
{fiche_flash}

FICHE CLIENT :
{fiche_client}
"""

P3_EXIGENCES = """Rôle : juriste de la commande publique.
Pièce analysée : {nom_piece} (type présumé : {type_piece}){partie}.

Liste TOUTES les exigences de cet extrait (administratives, techniques, financières,
environnementales, sociales). Une ligne par obligation, ne résume pas.

Tableau | Exigence reformulée | Source (pièce, article/page) | Obligatoire / souhaitée / optionnelle | Preuve attendue | Ambiguïté |

Si l'extrait ne contient aucune exigence, réponds seulement : « Aucune exigence dans cet extrait. »

EXTRAIT :
{texte}
"""
