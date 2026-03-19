# Py Network Launcher

Application desktop Windows basée sur Flet pour construire et exécuter des séquences locales et distantes sur un réseau local.

## Licence

Ce projet est distribué sous une licence **propriétaire non commerciale**.

Usage autorisé :

- usage personnel
- usage interne non commercial
- tests, démonstration, évaluation, apprentissage

Usage interdit sans autorisation écrite préalable :

- usage commercial
- redistribution
- republication
- reproduction, sauf une copie de sauvegarde strictement personnelle

Consulte le fichier `LICENSE` pour le texte complet.

## Fonctions

- découverte automatique des postes via beacon UDP JSON
- API HTTP locale pour exposer les séquences d'un poste
- séquences composées d'étapes locales et distantes
- configuration sauvegardée en JSON dans `%USERPROFILE%\py-network-launcher.json`
- lancement automatique avec Windows via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- démarrage caché avec Windows
- fermeture configurable :
  - minimiser dans la zone de notification
  - quitter réellement l'application
- system tray Windows avec actions afficher, masquer et quitter
- interface graphique Flet pour gérer les séquences

## Types d'étapes pris en charge

- **Lancer une application**
  - lance un exécutable ou un programme local
  - champs dédiés pour le chemin/commande, les arguments et le dossier de travail
- **Commande shell**
  - exécute une ligne de commande via le shell Windows
  - utile pour `cmd`, les pipes, les redirections et les commandes composées
- **Ouvrir une page web**
- **Appeler un webhook**
- **Wake-on-LAN**
- **Délai**
- **Lancer une séquence distante**

## Comportement des séquences

- le type d'une étape est choisi à la création puis n'est plus modifiable
- le nom affiché d'une étape est automatique et correspond à son type
- les étapes sont **repliées par défaut** pour garder l'éditeur lisible
- chaque étape peut être lancée individuellement
- les séquences peuvent être lancées manuellement ou au démarrage de l'application

## Modes d'attente après lancement

Pour les étapes **Lancer une application** et **Commande shell**, plusieurs modes d'attente sont disponibles :

- `Ne pas attendre`
- `Valider quand l'application est ouverte`
- `Valider que l'application reste ouverte`
- `Attendre qu'un port réponde`
- `Attendre la fermeture`

## Installation en développement

```powershell
python -m venv .venv
\.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Lancement

```powershell
python main.py
```

Pour lancer l'application cachée au démarrage :

```powershell
python main.py --hidden
```

## Réglages du poste

Depuis l'onglet **Réglages**, tu peux configurer :

- le nom du poste
- le port API HTTP local
- le port de discovery UDP
- le lancement automatique avec Windows
- le démarrage caché avec Windows
- le comportement à la fermeture

Le nom du poste est sauvegardé au blur. Les réglages réseau sont appliqués avec le bouton dédié. Les options de démarrage Windows sont appliquées automatiquement.

## Fonctionnement réseau

Au démarrage, chaque instance :

- expose une API HTTP locale
- diffuse sa présence sur le LAN
- écoute les autres postes découverts
- récupère les séquences distantes publiées

Par défaut :

- API HTTP locale sur le port `8765`
- discovery UDP sur le port `8766`

Pour que le discovery fonctionne entre plusieurs postes Windows, il faut autoriser l'application dans le pare-feu Windows sur le réseau privé. Il n'est pas nécessaire de désactiver complètement le firewall.

## Exemple de séquence

Séquence `hello` sur PC1 :

1. lancer Chrome
2. appeler un webhook

Séquence `stream-start` sur PC2 :

1. lancer OBS
2. attendre 10 secondes
3. lancer la séquence `hello` sur PC1

## Packaging Windows

Le dépôt contient déjà la chaîne de packaging Windows :

- `py-network-launcher.spec` pour générer l'exécutable avec PyInstaller
- `installer\py-network-launcher.iss` pour générer un installateur Inno Setup
- `installer\build-installer.ps1` pour enchaîner build de l'exécutable et du setup

### Pré-requis

- Python 3.11+
- Inno Setup 6 installé, avec `ISCC.exe` disponible

### Générer l'exécutable et l'installateur

```powershell
.\installer\build-installer.ps1
```

Ou avec un chemin Inno Setup personnalisé :

```powershell
.\installer\build-installer.ps1 -Python ".\.venv\Scripts\python.exe" -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

### Résultat attendu

- build PyInstaller dans `dist\Py Network Launcher\`
- installateur Windows généré à partir du script Inno Setup

## GitHub et build automatique

Le dépôt est prêt pour GitHub avec :

- une licence propriétaire dans `LICENSE`
- un workflow GitHub Actions dans `.github/workflows/windows-build.yml`
- un `.gitignore` pour éviter de versionner la venv et les builds

### Comportement du workflow GitHub Actions

Le workflow Windows :

- se lance à chaque `push` sur `main` ou `master`
- peut aussi être lancé manuellement via `workflow_dispatch`
- installe Inno Setup sur le runner Windows
- génère l'exécutable portable PyInstaller
- génère l'installateur Windows Inno Setup
- publie les artefacts du build dans GitHub Actions
- crée une **pre-release CI** GitHub pour chaque commit poussé

### Fichiers publiés par la CI

- `PyNetworkLauncher-portable.zip`
- `PyNetworkLauncherSetup.exe`

### Mise en ligne sur GitHub

Après création du dépôt GitHub, tu peux publier avec la séquence classique :

```powershell
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <URL_DU_REPO>
git push -u origin main
```

À partir de là, chaque nouveau commit poussé sur `main` déclenchera le build Windows automatique.
