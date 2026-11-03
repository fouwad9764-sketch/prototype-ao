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

P4_MATRICE = """Rôle : chargé d'affaires qui prépare la candidature d'un client et doit être honnête
sur ce que le client peut réellement prouver.

Tu reçois une liste numérotée d'exigences du pouvoir adjudicateur et le dossier du client.
Mets-les face à face dans UN SEUL tableau, avec exactement ces colonnes, dans cet ordre :

| N° | Exigence | Source DCE | Ce que le client apporte | Statut | Preuve (document client) | Écart et action |

Règles :
- Une ligne par exigence de la liste, dans le même ordre, avec le même numéro. N'en omets
  aucune, n'en ajoute aucune, ne fusionne pas de lignes.
- Recopie l'exigence et sa source telles quelles (tu peux raccourcir l'exigence).
- Statut : uniquement CONFORME, PARTIEL, NON CONFORME ou À VÉRIFIER.
  - CONFORME : uniquement si le dossier du client contient l'élément de preuve.
  - PARTIEL : le client répond en partie (ex. habilitation détenue par trop peu de personnes).
  - NON CONFORME : le dossier montre que le client ne remplit pas l'exigence.
  - À VÉRIFIER : l'information est absente du dossier du client, ou c'est une déclaration
    que le client doit signer.
- Preuve : nom du document du client (ou « fiche client ») et l'élément précis. Sinon « aucune ».
- Écart et action : pour tout statut autre que CONFORME, une action concrète (pièce à demander
  au client, formation, cotraitance, sous-traitance autorisée, renoncer à ce marché…).
  Pour CONFORME, écris « — ».
- N'invente aucune capacité, aucun chiffre, aucune certification du client.
- Pas de texte avant ni après le tableau.

EXIGENCES DU POUVOIR ADJUDICATEUR :
{exigences}

DOSSIER DU CLIENT :
{profil_client}
"""

EXEMPLE_CLIENT_FICTIF = """Client FICTIF pour test : Électro Lagon Services SARL (Mamoudzou, Mayotte)
Activité : travaux d'électricité basse tension, réseaux aériens et souterrains, branchements.
Création : 2014. Effectif : 18 salariés dont 11 électriciens réseaux et 2 chefs d'équipe.
Chiffre d'affaires : 2023 : 2,1 M€ ; 2024 : 2,6 M€ ; 2025 : 3,0 M€.
Habilitations électriques : H0B0 pour tout le personnel ; B1V pour 11 électriciens ; B2V pour
2 chefs d'équipe. Aucune habilitation TST (travaux sous tension) à ce jour.
Travaux en hauteur : formation port du harnais pour 9 salariés.
CACES : R486 (nacelles) catégorie B pour 4 salariés ; pas de CACES grue auxiliaire.
Matériel : 2 camions nacelle 14 m, 1 mini-pelle, 3 véhicules utilitaires.
Certifications : Qualifelec en cours de demande (dossier déposé en 2026).
Assurances : RC professionnelle et décennale en cours (assureur local, attestation 2026).
Références (5 dernières années) :
- 2025 : Commune de Dembéni, rénovation éclairage public, 420 k€ HT
- 2024 : Promoteur privé, raccordement BT d'un lotissement de 40 lots, 310 k€ HT
- 2025 : EDM en sous-traitance d'un titulaire, remise en état de branchements après Chido, 180 k€ HT
Zone d'intervention : toute l'île de Mayotte.
Positionnement prix : prix moyens du marché local.
Point faible connu : capacité limitée à 2 équipes simultanées.
"""
