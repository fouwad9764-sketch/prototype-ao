# Mettre l'application en ligne depuis un iPad

L'application est hébergée gratuitement sur Streamlit Community Cloud et s'ouvre dans
Safari, comme un site web. Tout se fait depuis l'iPad, sans installer de logiciel.
Compter environ 30 minutes la première fois.

## Étape 1 — Décompresser le dossier

1. Dans l'app **Fichiers**, touche `prototype-ao.zip` : l'iPad crée le dossier `prototype-ao`.

## Étape 2 — Mettre le code sur GitHub

1. Dans Safari, crée un compte gratuit sur github.com.
2. Bouton **+** en haut > **New repository**.
   - Nom : `prototype-ao`
   - Choisis **Private** (le code reste privé).
   - Coche **Add a README file**, puis **Create repository**.
3. Dans le dépôt : **Add file** > **Upload files** > **choose your files**, puis sélectionne
   dans Fichiers tous les fichiers du dossier `prototype-ao` :
   `app.py`, `llm_client.py`, `extraction.py`, `export_word.py`, `prompts_ao.py`,
   `requirements.txt`, `LISEZMOI.md`.
   Ne téléverse jamais de fichier `.env` contenant ta clé.
4. Bouton **Commit changes**.

## Étape 3 — Créer la clé Mistral

1. Sur console.mistral.ai, crée un compte puis une clé dans **API Keys**. Copie-la.
2. Plan gratuit « Experiment » : uniquement des DCE publics, jamais de données clients
   (les données peuvent servir à l'entraînement de Mistral).

## Étape 4 — Mettre en ligne

1. Va sur share.streamlit.io et connecte-toi avec ton compte GitHub (autorise l'accès,
   y compris aux dépôts privés si on te le demande).
2. **Create app** > **Deploy a public app from GitHub** (le code reste privé, seule
   l'adresse de l'app est accessible, protégée par le mot de passe ci-dessous).
3. Renseigne :
   - Repository : `ton-pseudo/prototype-ao`
   - Branch : `main`
   - Main file path : `app.py`
4. Ouvre **Advanced settings** :
   - Python : 3.12
   - Dans **Secrets**, colle ces deux lignes avec tes valeurs :

   ```
   MISTRAL_API_KEY = "ta-cle-mistral"
   APP_PASSWORD = "un-mot-de-passe-solide"
   ```

5. **Deploy**. Après quelques minutes, l'application s'ouvre à une adresse en
   `.streamlit.app`. Ajoute-la à l'écran d'accueil de l'iPad (bouton Partager >
   Sur l'écran d'accueil).

## Utilisation

- Ouvre l'adresse, saisis le mot de passe, puis dépose les fichiers du DCE depuis l'app
  Fichiers (téléchargés depuis le profil acheteur dans Safari).
- Le Word final se télécharge dans Fichiers > Téléchargements.
- Si l'app n'a pas servi depuis plusieurs jours, elle se met en veille : un bouton permet
  de la réveiller (environ une minute).

## Sécurité, à garder en tête

- L'hébergement Streamlit Community Cloud est gratuit mais situé hors de l'UE : réservé aux
  essais avec des DCE publics. Pour des données clients, il faudra migrer vers un
  hébergeur en France (voir le cahier des charges).
- Ne partage l'adresse et le mot de passe qu'avec l'équipe.
- Pour changer la clé ou le mot de passe : sur share.streamlit.io, menu de l'app >
  Settings > Secrets.

## Modifier le code plus tard

Sur github.com, ouvre le fichier, touche l'icône crayon, modifie, puis **Commit changes** :
l'application se met à jour toute seule en une minute.
