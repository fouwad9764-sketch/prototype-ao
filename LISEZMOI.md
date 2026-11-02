# Prototype d'analyse de DCE — Sola Conseil

Petite application web qui tourne sur ton ordinateur. Tu déposes les pièces d'un DCE,
Mistral produit la fiche flash, l'analyse go/no-go et la liste des exigences, et tu
récupères le tout en Word.

## 1. Installer Python (une seule fois)

- **Windows** : télécharge Python 3.12 sur python.org. À l'installation, coche
  **« Add python.exe to PATH »** en bas de la première fenêtre.
- **Mac** : télécharge Python 3.12 sur python.org et installe-le normalement.

## 2. Créer ta clé Mistral (une seule fois)

1. Crée un compte sur console.mistral.ai.
2. Choisis un plan : le plan gratuit « Experiment » suffit pour tester avec des DCE publics
   (attention : les données peuvent alors servir à l'entraînement de Mistral, donc jamais
   de données clients). Pour des données clients, passe au plan payant à l'usage.
3. Dans « API Keys », crée une clé et copie-la.

## 3. Installer le prototype

1. Décompresse le dossier `prototype-ao` où tu veux (par exemple dans Documents).
2. Lance l'outil une première fois :
   - **Windows** : double-clic sur `lancer_windows.bat`.
   - **Mac** : clic droit sur `lancer_mac.command` > Ouvrir (la première fois, macOS
     demande une confirmation).
3. La première installation prend quelques minutes. Un fichier `.env` est créé.
4. Ferme la fenêtre, ouvre `.env` avec le Bloc-notes (Windows) ou TextEdit (Mac), colle ta
   clé après `MISTRAL_API_KEY=`, enregistre.

Astuce : sur Mac, les fichiers commençant par un point sont cachés ; dans le Finder,
appuie sur Cmd + Maj + . pour les afficher. Tu peux aussi coller la clé directement dans
la barre latérale de l'application.

## 4. Utiliser l'outil

1. Relance `lancer_windows.bat` ou `lancer_mac.command` : l'application s'ouvre dans ton
   navigateur (adresse http://localhost:8501).
2. **Importer** : dépose les pièces du DCE ou directement le ZIP téléchargé sur le profil
   acheteur, puis « Lire les fichiers ». Vérifie le tableau : type de pièce, alertes.
3. **Fiche flash** : un clic.
4. **Go/no-go** : colle la fiche client (activité, CA, effectifs, références,
   certifications, zone), puis lance l'analyse.
5. **Exigences** : choisis les pièces (RC, CCAP, CCTP par défaut) et lance l'extraction.
   Sur un gros DCE, compte plusieurs minutes.
6. **Exporter** : télécharge le Word.

Pour arrêter l'application, ferme la fenêtre noire (terminal).

## 5. Limites de cette version

- Les PDF scannés (images) ne sont pas lus : l'outil le signale par une alerte.
- La fiche flash lit environ 200 000 caractères en priorité (avis, RC, CCAP).
- Pas encore de veille BOAMP ni de base de connaissances clients.
- Tout résultat est un brouillon : dates, pondérations et exigences sont à revérifier dans
  les pièces avant usage.

## 6. En cas de problème

| Message | Solution |
| --- | --- |
| « py » ou « python3 » introuvable | Réinstalle Python en cochant « Add to PATH » (Windows) |
| Clé API refusée | Vérifie la clé dans `.env`, sans espace ni guillemets |
| Erreur 429 | Limite du plan gratuit : attends une minute et relance |
| Aucun texte lisible | PDF scanné : demande une version texte ou attends la v2 (OCR) |

## Organisation du code (pour un développeur)

| Fichier | Rôle |
| --- | --- |
| `app.py` | Interface Streamlit et enchaînement des étapes |
| `extraction.py` | Lecture PDF, DOCX, XLSX, TXT, ZIP ; découpage des longs textes |
| `llm_client.py` | Seul point d'appel à l'IA (changer de fournisseur = modifier ce fichier) |
| `prompts_ao.py` | Prompts P1, P2, P3 issus de la méthode `methode-reponse-ao` |
| `export_word.py` | Conversion des résultats en document Word |
