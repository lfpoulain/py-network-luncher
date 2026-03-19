# Py Network Launcher

Application desktop Windows basée sur Flet pour construire et exécuter des séquences locales et distantes sur un réseau local.

Py Network Launcher permet d'automatiser l'ouverture d'applications, de commandes shell, de pages web, de webhooks et de séquences distantes entre plusieurs PC Windows sur un même réseau local.

## Aperçu

Le projet a été pensé pour les setups multi-postes où tu veux lancer plusieurs actions dans le bon ordre sans passer par des scripts compliqués.

Exemples d'usage :

- lancer un environnement de stream sur un setup dual-PC
- ouvrir un ensemble d'outils de travail ou de démo en un clic
- réveiller un poste à distance puis démarrer une séquence dessus
- enchaîner des actions locales et distantes sur plusieurs machines du LAN

## Fonctionnalités

- séquences locales et distantes dans une même interface
- découverte automatique des postes via beacon UDP JSON
- API HTTP locale pour exposer les séquences d'un poste
- exécution d'étapes locales, shell, web, webhook, Wake-on-LAN et distantes
- support Home Assistant pour piloter des entités `light` et `switch`
- lancement manuel d'une étape ou d'une séquence complète
- exécution automatique d'une séquence au démarrage de l'application
- démarrage automatique avec Windows
- démarrage caché avec Windows
- fermeture configurable : minimiser dans la zone de notification ou quitter réellement
- system tray Windows avec actions afficher, masquer et quitter
- configuration sauvegardée en JSON dans `%USERPROFILE%\py-network-launcher.json`

## Types d'étapes pris en charge

- **Lancer une application**
  - lance un exécutable ou un programme local
  - gère le chemin, les arguments et le dossier de travail
- **Commande shell**
  - exécute une ligne de commande via le shell Windows
  - utile pour `cmd`, les pipes, les redirections et les commandes composées
- **Ouvrir une page web**
- **Appeler un webhook**
- **Wake-on-LAN**
- **Délai**
- **Lancer une séquence distante**
- **Home Assistant**
  - contrôle une entité `light` ou `switch` à partir de son `Entity ID`
  - actions disponibles : `on` et `off`

## Utilisation

Dans l'application, tu peux :

- créer plusieurs séquences locales
- ajouter des étapes de différents types
- choisir un mode d'attente après un lancement d'application ou de commande shell
- lancer chaque étape individuellement
- lancer la séquence complète à la demande
- déclencher une séquence locale au démarrage de l'application

Comportements utiles :

- les étapes sont **repliées par défaut** pour garder l'éditeur lisible
- le type d'une étape est défini à sa création
- le comportement à la fermeture peut être réglé depuis l'onglet **Réglages**
- les séquences distantes sont affichées avec le **nom du poste** et le **nom de la séquence**
- les étapes Home Assistant utilisent l'URL serveur et le token configurés dans **Réglages**
- pour Home Assistant, il suffit de saisir un `Entity ID` complet comme `light.salon` ou `switch.prise_bureau`

### Modes d'attente disponibles

Pour les étapes **Lancer une application** et **Commande shell**, plusieurs modes d'attente sont disponibles :

- `Ne pas attendre`
- `Valider quand l'application est ouverte`
- `Valider que l'application reste ouverte`
- `Attendre qu'un port réponde`
- `Attendre la fermeture`

## Fonctionnement réseau

Au démarrage, chaque instance :

- expose une API HTTP locale
- diffuse sa présence sur le LAN
- écoute les autres postes découverts
- récupère les séquences distantes publiées

Ports par défaut :

- API HTTP locale : `8765`
- discovery UDP : `8766`

Pour que la découverte fonctionne correctement entre plusieurs postes Windows, il faut autoriser l'application dans le pare-feu Windows sur le réseau privé.

## Exemple concret

Séquence `hello` sur PC1 :

1. lancer Chrome
2. appeler un webhook

Séquence `stream-start` sur PC2 :

1. lancer OBS
2. attendre 10 secondes
3. lancer la séquence `hello` sur PC1

## Installation

### Télécharger une version Windows

Les builds Windows peuvent être publiés via les releases GitHub ou les builds CI du dépôt :

- releases : `https://github.com/lfpoulain/py-network-luncher/releases`

### Installation en développement

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Lancement local

```powershell
python main.py
```

Pour lancer l'application cachée :

```powershell
python main.py --hidden
```

## Réglages du poste

Depuis l'onglet **Réglages**, tu peux configurer :

- le nom du poste
- le port API HTTP local
- le port de discovery UDP
- l'URL du serveur Home Assistant
- le token d'accès Home Assistant
- le lancement automatique avec Windows
- le démarrage caché avec Windows
- le comportement à la fermeture

Le nom du poste est sauvegardé automatiquement. Les réglages réseau et Home Assistant sont appliqués via le bouton dédié. Les options de démarrage Windows sont appliquées automatiquement.

## Packaging Windows

Le dépôt contient déjà la chaîne de packaging Windows :

- `py-network-launcher.spec` pour générer l'exécutable avec PyInstaller
- `installer\py-network-launcher.iss` pour générer un installateur Inno Setup
- `installer\build-installer.ps1` pour enchaîner le build de l'exécutable et du setup

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
- installateur Windows dans `installer\dist\PyNetworkLauncherSetup.exe`

## CI GitHub Actions

Le dépôt contient un workflow GitHub Actions dans `.github/workflows/windows-build.yml`.

Ce workflow :

- se lance à chaque `push` sur `main` ou `master`
- peut être lancé manuellement via `workflow_dispatch`
- installe Inno Setup sur le runner Windows
- génère une archive portable PyInstaller
- génère un installateur Windows Inno Setup
- publie les artefacts du build
- crée une **pre-release CI** pour les commits poussés

Artefacts attendus :

- `PyNetworkLauncher-portable.zip`
- `PyNetworkLauncherSetup.exe`

## Licence

Ce projet est distribué sous une licence **propriétaire non commerciale**.

Sans autorisation écrite préalable, tu ne peux pas :

- utiliser le logiciel à des fins commerciales
- redistribuer le projet
- republier le projet
- reproduire le projet, sauf une copie de sauvegarde strictement personnelle

Consulte le fichier `LICENSE` pour le texte complet.
