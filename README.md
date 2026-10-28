<p align="center">
  <img src="assets/logo_128.png" width="96" alt="Logo Py Network Launcher"/>
</p>

<h1 align="center">Py Network Launcher</h1>

<p align="center">
  <strong>Enchaîne des actions sur plusieurs PC Windows d'un même réseau, en un clic.</strong><br/>
  Lancer OBS sur le PC de stream, réveiller le PC de jeu, allumer la lumière Home Assistant… tout dans une seule séquence.
</p>

<p align="center">
  <a href="https://github.com/lfpoulain/py-network-luncher/releases/latest"><img src="https://img.shields.io/github/v/release/lfpoulain/py-network-luncher?label=t%C3%A9l%C3%A9charger&logo=windows" alt="Dernière version"/></a>
  <a href="https://github.com/lfpoulain/py-network-luncher/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/lfpoulain/py-network-luncher/ci.yml?branch=main&label=CI&logo=github" alt="CI"/></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/licence-non%20commerciale-lightgrey" alt="Licence non commerciale"/>
</p>

---

## Sommaire

- [Installation](#installation)
- [Prise en main](#prise-en-main)
- [Les étapes disponibles](#les-étapes-disponibles)
- [Plusieurs postes sur le réseau](#plusieurs-postes-sur-le-réseau)
- [Home Assistant](#home-assistant)
- [Réglages et fichiers](#réglages-et-fichiers)
- [Dépannage](#dépannage)
- [Développement](#développement)
- [Licence](#licence)

## Installation

Télécharge la [dernière version](https://github.com/lfpoulain/py-network-luncher/releases/latest) :

| Fichier | Pour qui |
|---|---|
| `PyNetworkLauncher-Setup-x.y.z.exe` | Installation classique (menu Démarrer, règles de pare-feu, désinstallation propre) |
| `PyNetworkLauncher-x.y.z-portable.zip` | Sans installation : décompresse et lance `Py Network Launcher.exe` |

L'installateur ajoute les règles de pare-feu nécessaires sur les réseaux privés. Avec la version portable,
accepte l'invite du pare-feu Windows au premier lancement (réseaux **privés**).

## Prise en main

1. **Crée une séquence** (bouton `+`), donne-lui un nom.
2. **Ajoute des étapes** avec « Ajouter une étape ». Chaque étape s'ouvre pour être réglée ; le bouton ▶ d'une étape la teste seule.
3. **Réordonne** les étapes par glisser-déposer (poignée ⋮⋮) ou via leur menu.
4. **Lance** la séquence : l'étape en cours s'entoure d'orange, les étapes réussies passent au vert, une étape en échec passe au rouge avec la raison.

Une séquence peut aussi démarrer **automatiquement** :

| Déclenchement | Comportement |
|---|---|
| Manuel uniquement | Seulement quand tu cliques sur Lancer (ou depuis un autre poste) |
| À chaque démarrage de l'application | À chaque ouverture de l'application |
| Une fois par session Windows | Au premier lancement de l'application après l'ouverture de session, pas aux relances suivantes |

Chaque étape peut être **désactivée** temporairement ou marquée **« Continuer si elle échoue »** (par exemple un
webhook facultatif qui ne doit pas bloquer le reste).

L'icône de la zone de notification permet d'afficher la fenêtre (double-clic) et de lancer ou arrêter une séquence
sans ouvrir l'interface.

## Les étapes disponibles

| Étape | Ce qu'elle fait |
|---|---|
| **Lancer une application** | Exécutable, raccourci `.lnk` ou fichier quelconque, avec arguments et dossier de travail. Gère les chemins entre guillemets, les `%VARIABLES%` et l'élévation UAC. |
| **Commande shell** | Ligne `cmd.exe` (pipes, `&&`, redirections), console masquée par défaut. |
| **Ouvrir une page web** | Ouvre une URL dans le navigateur par défaut. |
| **Appeler un webhook** | Requête HTTP `GET/POST/PUT/PATCH/DELETE` avec headers JSON et corps. |
| **Wake-on-LAN** | Réveille un PC à partir de son adresse MAC. |
| **Délai** | Attend quelques secondes. |
| **Séquence locale** | Exécute une autre séquence de ce poste, puis continue (les boucles sont détectées). |
| **Séquence distante** | Déclenche une séquence sur un autre poste ; attend qu'il apparaisse s'il vient d'être réveillé. |
| **Home Assistant** | Allume, éteint ou bascule une entité (`light.*`, `switch.*`, `scene.*`, `script.*`…). |

Pour **Lancer une application** et **Commande shell**, l'étape peut ensuite attendre :

| Attente | Validation |
|---|---|
| Ne pas attendre | Passe immédiatement à la suite |
| Vérifier que l'application s'ouvre | Échec si le processus se ferme dans la seconde |
| Vérifier qu'elle reste ouverte pendant le délai | Échec si le processus se ferme avant la durée indiquée |
| Attendre qu'un port TCP réponde | Utile pour un serveur (OBS WebSocket, API locale…) |
| Attendre la fin du processus | Échec si le code de sortie n'est pas 0 |

## Plusieurs postes sur le réseau

Chaque instance de l'application :

- s'annonce sur le réseau local (UDP **8766**) et découvre les autres postes ;
- expose ses séquences via une petite API HTTP (TCP **8765**).

L'onglet **Postes** liste les machines trouvées et permet de lancer leurs séquences. Dans une séquence, l'étape
**Séquence distante** fait la même chose automatiquement.

Exemple de setup double PC :

```text
PC Stream  ─ séquence « Live »
  1. Wake-on-LAN           → réveille le PC Jeu
  2. Séquence distante     → « Mode jeu » sur PC Jeu (attend jusqu'à 60 s qu'il soit en ligne)
  3. Lancer une application → OBS, attendre le port 4455
  4. Home Assistant        → allumer light.bureau
```

> ⚠️ L'API n'a pas d'authentification : n'importe quel appareil du réseau local peut lancer les séquences publiées.
> Utilise l'application sur un réseau de confiance.

## Home Assistant

Dans **Réglages → Home Assistant**, renseigne l'URL (ex. `http://homeassistant.local:8123`) et un
**jeton d'accès longue durée** (profil Home Assistant → Sécurité), puis clique sur **Tester la connexion**.
L'étape Home Assistant n'a ensuite besoin que de l'Entity ID complet, par exemple `light.salon`.

## Réglages et fichiers

| Élément | Emplacement |
|---|---|
| Configuration | `%APPDATA%\PyNetworkLauncher\config.json` |
| Journaux | `%APPDATA%\PyNetworkLauncher\logs\` |
| Démarrage avec Windows | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |

Depuis la version 0.2, l'ancien fichier `%USERPROFILE%\py-network-launcher.json` est migré automatiquement.
Si la configuration devient illisible, elle est conservée sous `config.illisible-<date>.json` et une configuration
vierge est chargée.

Options en ligne de commande : `--hidden` (démarrage réduit dans la zone de notification), `--version`.

## Dépannage

| Symptôme | Piste |
|---|---|
| Un poste n'apparaît pas | Réseau Windows en mode **Privé**, pare-feu autorisé, même port de découverte des deux côtés. |
| « API injoignable » sur un poste | Le poste est vu mais le port TCP est bloqué par son pare-feu. |
| « Port … indisponible » en bas de la fenêtre | Un autre programme utilise ce port : change-le dans Réglages puis **Appliquer**. |
| Une étape échoue | Survole l'icône rouge de l'étape ou ouvre l'onglet **Journal** (filtre « Erreurs seulement »). |

## Développement

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python main.py            # lance l'application
python -m pytest          # tests
python -m ruff check .    # lint
```

Structure du code, build Windows et processus de release : voir [CONTRIBUTING.md](CONTRIBUTING.md).
Historique des versions : [CHANGELOG.md](CHANGELOG.md).

## Licence

Logiciel distribué sous **licence propriétaire non commerciale** : usage personnel, éducatif ou interne non
commercial autorisé ; redistribution, republication et usage commercial interdits sans autorisation écrite.
Texte complet : [LICENSE](LICENSE).
