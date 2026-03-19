# 🚀 Py Network Launcher

<p align="center">
  <strong>Automatisation locale et distante pour postes Windows sur le même réseau local.</strong><br/>
  Construit avec <a href="https://flet.dev">Flet</a> · Python 3.11+ · Windows
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue?logo=windows" alt="Platform: Windows"/>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/UI-Flet-blueviolet" alt="Flet UI"/>
  <img src="https://img.shields.io/badge/licence-Propriétaire%20non%20commerciale-red" alt="Licence"/>
  <img src="https://img.shields.io/github/actions/workflow/status/lfpoulain/py-network-luncher/windows-build.yml?label=CI&logo=github" alt="CI Status"/>
</p>

---

Py Network Launcher permet de centraliser et d'orchestrer des **séquences d'actions** sur plusieurs PC Windows d'un même réseau, sans scripts complexes ni raccourcis bricolés.

> **Conçu pour les setups multi-postes** : streaming dual-PC, démarrage d'environnements de travail, automatisation réseau, pilotage Home Assistant…

---

## 📋 Table des matières

- [Cas d'usage](#-cas-dusage)
- [Points forts](#-points-forts)
- [Types d'étapes disponibles](#-types-détapes-disponibles)
- [Utilisation](#-utilisation)
- [Fonctionnement réseau](#-fonctionnement-réseau)
- [Exemple rapide](#-exemple-rapide)
- [Installation](#-installation)
- [Réglages du poste](#-réglages-du-poste)
- [Intégration Home Assistant](#-intégration-home-assistant)
- [Packaging Windows](#-packaging-windows)
- [CI GitHub Actions](#-ci-github-actions)
- [Licence](#-licence)

---

## 🎯 Cas d'usage

- Lancer un setup de stream sur un environnement **dual-PC**
- Ouvrir un ensemble d'outils de travail ou de démo **en un clic**
- Réveiller un poste à distance (Wake-on-LAN) puis **démarrer une séquence dessus**
- Orchestrer plusieurs actions entre plusieurs PC Windows du même réseau
- Piloter des équipements **Home Assistant** dans une routine de démarrage ou d'arrêt

---

## ✨ Points forts

| Fonctionnalité | Détail |
|---|---|
| 🖥️ Interface unique | Séquences locales et distantes dans un seul endroit |
| 📡 Découverte automatique | Les postes du LAN apparaissent sans configuration |
| 🔗 API HTTP locale | Expose les séquences d'un poste aux autres machines |
| ✏️ Éditeur visuel | Crée et modifie les étapes d'une séquence facilement |
| 🖱️ Drag & drop | Réordonne les étapes à la volée |
| 🟠 Suivi d'exécution | L'étape en cours est mise en évidence en temps réel |
| ✅ Progression | Les étapes terminées sont marquées visuellement |
| ⚡ Lancement auto | Déclenche une séquence au démarrage de l'app |
| 🏠 Home Assistant | Pilote des entités `light` et `switch` |
| 🔒 Config persistée | Sauvegardée en JSON dans `%USERPROFILE%\py-network-launcher.json` |

---

## 🧩 Types d'étapes disponibles

| Type | Description |
|---|---|
| 🟦 **Lancer une application** | Ouvre un exécutable local avec ses arguments et son dossier de travail |
| ⬛ **Commande shell** | Exécute une commande Windows, avec support des pipes et redirections |
| 🌐 **Ouvrir une page web** | Ouvre une URL dans le navigateur par défaut |
| 🔔 **Appeler un webhook** | Envoie une requête HTTP (GET, POST, PUT…) |
| 💡 **Wake-on-LAN** | Réveille un poste distant via son adresse MAC |
| ⏱️ **Délai** | Attend un nombre de secondes avant de passer à la suite |
| 🔗 **Séquence distante** | Déclenche une séquence sur un autre poste du réseau |
| 🏠 **Home Assistant** | Pilote une entité `light` ou `switch` via l'API HA |

### Modes d'attente (App & Shell)

Pour les étapes **Lancer une application** et **Commande shell** :

| Mode | Comportement |
|---|---|
| `Ne pas attendre` | Passe immédiatement à la suite |
| `Valider quand l'application est ouverte` | Attend que le processus démarre |
| `Valider que l'application reste ouverte` | Attend que le processus soit stable |
| `Attendre qu'un port réponde` | Attend qu'un port TCP réponde |
| `Attendre la fermeture` | Attend la fin du processus |

---

## 🖱️ Utilisation

Dans l'application, tu peux :

- Créer plusieurs **séquences** nommées
- Ajouter des étapes de différents types
- Tester une **étape individuellement**
- Lancer une **séquence complète** à la demande
- Réordonner les étapes **par drag & drop**
- Suivre la **progression d'une séquence en direct**
- Déclencher automatiquement une séquence **au démarrage de l'app**

> **Astuce** : les étapes sont repliées par défaut pour garder l'éditeur lisible. Clique sur une étape pour la déplier et la modifier.

---

## 🌐 Fonctionnement réseau

Au démarrage, chaque instance de l'application :

1. Expose une **API HTTP locale**
2. Diffuse sa présence sur le réseau local
3. Écoute les autres postes découverts
4. Récupère les **séquences distantes publiées**

**Ports par défaut :**

| Usage | Port |
|---|---|
| API HTTP locale | `8765` |
| Discovery UDP | `8766` |

> Pour que la découverte fonctionne entre plusieurs postes Windows, autorise l'application dans le **pare-feu Windows** sur le réseau privé.

---

## ⚡ Exemple rapide

**Séquence `hello` sur PC1 :**
1. Lancer Chrome
2. Appeler un webhook

**Séquence `stream-start` sur PC2 :**
1. Lancer OBS
2. Attendre 10 secondes
3. ➡️ Lancer la séquence `hello` sur PC1

---

## 📦 Installation

### Télécharger une version Windows

Les builds Windows sont disponibles via les **releases GitHub** :

👉 [`https://github.com/lfpoulain/py-network-luncher/releases`](https://github.com/lfpoulain/py-network-luncher/releases)

Deux formats disponibles :
- **Archive portable** (ZIP) — décompresse et lance directement
- **Installateur** (`PyNetworkLauncherSetup.exe`) — installe dans le menu Démarrer

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

Pour lancer l'application cachée dans la barre des tâches :

```powershell
python main.py --hidden
```

---

## ⚙️ Réglages du poste

Depuis l'onglet **Réglages**, tu peux configurer :

- 🏷️ Le **nom du poste** (visible sur le réseau)
- 🔌 Le **port API HTTP** local
- 📡 Le **port de discovery** UDP
- 🏠 L'**URL du serveur Home Assistant**
- 🔑 Le **token d'accès Home Assistant**
- 🪟 Le **lancement automatique avec Windows**
- 🙈 Le **démarrage caché** avec Windows
- 🚪 Le **comportement à la fermeture** (minimiser ou quitter)

> Le nom du poste est sauvegardé automatiquement. Les réglages réseau et Home Assistant sont appliqués via le bouton **Appliquer les réglages**.

---

## 🏠 Intégration Home Assistant

Configure l'URL et le token dans **Réglages**, puis ajoute une étape **Home Assistant** dans une séquence.

**Il suffit d'indiquer un `Entity ID` complet :**

```
light.salon
switch.prise_bureau
```

Le domaine (`light`, `switch`) est détecté automatiquement depuis l'ID.

**Actions disponibles :** `on` · `off`

---

## 🔨 Packaging Windows

Le dépôt contient une chaîne de packaging complète :

| Fichier | Rôle |
|---|---|
| `py-network-launcher.spec` | Génère l'exécutable avec PyInstaller |
| `installer\py-network-launcher.iss` | Génère l'installateur avec Inno Setup |
| `installer\build-installer.ps1` | Enchaîne les deux étapes |

### Pré-requis

- Python **3.11+**
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) avec `ISCC.exe` disponible

### Générer l'exécutable et l'installateur

```powershell
.\installer\build-installer.ps1
```

Avec un chemin Python ou Inno Setup personnalisé :

```powershell
.\installer\build-installer.ps1 `
  -Python ".\.venv\Scripts\python.exe" `
  -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

**Résultat :**

- Exécutable portable → `dist\Py Network Launcher\`
- Installateur Windows → `installer\dist\PyNetworkLauncherSetup.exe`

---

## 🤖 CI GitHub Actions

Le workflow `.github/workflows/windows-build.yml` se déclenche automatiquement à chaque `push` sur `main` ou `master`.

**Ce que fait le workflow :**

1. Installe Inno Setup sur un runner Windows
2. Construit l'exécutable avec PyInstaller
3. Génère l'installateur Inno Setup
4. Publie les artefacts du build
5. Crée une **pre-release CI** avec les deux fichiers

**Artefacts publiés :**

| Fichier | Format |
|---|---|
| `PyNetworkLauncher-portable.zip` | Archive portable |
| `PyNetworkLauncherSetup.exe` | Installateur Windows |

---

## 📄 Licence

Ce projet est distribué sous une **licence propriétaire non commerciale**.

Sans autorisation écrite préalable, il est interdit de :

- Utiliser le logiciel à des **fins commerciales**
- **Redistribuer** ou **republier** le projet
- **Reproduire** le projet, sauf une copie de sauvegarde strictement personnelle

Consulte le fichier [`LICENSE`](LICENSE) pour le texte complet.
