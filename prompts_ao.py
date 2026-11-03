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

Liste les OBLIGATIONS qui s'imposent au candidat dans cet extrait : pièces à fournir,
capacités à démontrer (chiffre d'affaires, références, habilitations, certifications,
moyens, assurances), règles de forme et de dépôt, engagements d'exécution.

Ne liste PAS : les simples informations sur la procédure (nombre de titulaires, codes CPV,
montant du marché, déroulé des phases), ni ce qui ne concerne que l'acheteur.

Règles de découpage :
- Une ligne par obligation. Une capacité distincte = une ligne distincte (ex. habilitation
  B1V, habilitation TST et CACES nacelle = trois lignes).
- Un modèle de déclaration sur l'honneur à signer = UNE seule ligne (« Signer la déclaration
  sur l'honneur de l'annexe X »), pas une ligne par cas d'exclusion.
- Pas de doublon : une même obligation répétée dans l'extrait n'apparaît qu'une fois.

Tableau | Exigence reformulée | Source (nom exact de la pièce, article/page) | Obligatoire / souhaitée / optionnelle | Preuve attendue | Ambiguïté |

Si l'extrait ne contient aucune obligation pour le candidat, réponds seulement :
« Aucune exigence dans cet extrait. »

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
- Statut : uniquement CONFORME, PARTIEL, NON CONFORME, À VÉRIFIER ou SANS OBJET.
  - CONFORME : uniquement si le dossier du client contient EXPLICITEMENT l'élément de preuve.
    Dans la colonne Preuve, cite cet élément (ex. « fiche client : B1V pour 11 électriciens »).
    Une simple intention, une pratique supposée ou un engagement futur ne sont pas des preuves.
  - PARTIEL : le client répond en partie (ex. capacité insuffisante, une habilitation sur deux).
  - NON CONFORME : le dossier montre que le client ne remplit pas l'exigence
    (ex. « aucune habilitation TST » face à une exigence TST).
  - À VÉRIFIER : l'information est absente du dossier, ou c'est une déclaration ou un
    engagement que le client doit signer, ou une règle de dépôt à respecter le moment venu.
  - SANS OBJET : simple information sur la procédure, ou exigence qui ne concerne pas un
    candidat seul (ex. règles de groupement pour une candidature individuelle), ou doublon
    d'une exigence déjà listée (écris alors « doublon du n° X »).
- Compare les chiffres : un chiffre d'affaires inférieur à un seuil exigé est NON CONFORME ;
  en l'absence de seuil, ne conclus pas.
- Preuve : élément précis du dossier du client, sinon « aucune ».
- Écart et action : pour tout statut autre que CONFORME et SANS OBJET, une action concrète
  limitée à ce que le DCE demande (pièce à obtenir, déclaration à faire signer, formation,
  cotraitance, sous-traitance autorisée, renoncer). Ne demande pas de documents que le DCE
  n'exige pas. Pour CONFORME et SANS OBJET, écris « — ».
- N'invente aucune capacité, aucun chiffre, aucun document du client.
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
