# Contribuer et publier

## Environnement

Python 3.11+ sous Windows (l'application cible Windows ; le cœur et les tests tournent aussi ailleurs).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

| Commande | Rôle |
|---|---|
| `python main.py` | Lance l'application (fenêtre Flet) |
| `python main.py --hidden` | Démarre réduit dans la zone de notification |
| `python -m pytest` | Tests |
| `python -m ruff check .` / `python -m ruff format .` | Lint / formatage |

Pour tester sans toucher à ta vraie configuration, pointe l'application vers un autre dossier de données :

```powershell
$env:PY_NETWORK_LAUNCHER_HOME = "$PWD\.dev-data"; python main.py
```

L'option `--web PORT` sert l'interface à un navigateur (développement uniquement, nécessite `pip install "flet-web==0.82.2" "fastapi<0.116"`).

## Organisation du code

```text
main.py                       point d'entrée (python main.py, PyInstaller)
src/py_network_launcher/
  app.py                      arguments, journalisation, instance unique, lancement de Flet
  models.py                   dataclasses de configuration (+ migration des anciens formats)
  storage.py                  lecture/écriture atomique du JSON, sauvegarde différée
  actions.py                  implémentation de chaque type d'étape
  executor.py                 exécution des séquences (threads, arrêt, sous-séquences)
  service.py                  API HTTP, découverte des postes, suivi des exécutions
  discovery.py / network.py   beacons UDP, broadcast multi-interfaces
  windows.py                  démarrage Windows, identifiant de session, mutex
  tray.py                     icône de la zone de notification
  logs.py                     journal mémoire + fichier tournant
  ui/                         interface Flet (une vue par onglet, carte d'étape, composants)
tests/                        tests pytest
installer/                    script Inno Setup
scripts/build.ps1             build Windows complet
scripts/release.py            préparation des versions
```

Règles de l'UI : les événements du service arrivent sur des threads de fond et passent par
`MainWindow.invalidate()`, qui regroupe les rafraîchissements sur la boucle Flet. Les contrôles en cours
d'édition ne sont jamais reconstruits pendant une exécution (les cartes d'étape se mettent à jour sur place).

## Build Windows

Prérequis : [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
.\scripts\build.ps1                    # installe les dépendances de build puis construit tout
.\scripts\build.ps1 -SkipInstaller     # sans Inno Setup
```

Résultat dans `dist\` : dossier de l'application, `PyNetworkLauncher-<version>-portable.zip`,
`PyNetworkLauncher-Setup-<version>.exe` et `SHA256SUMS.txt`.

## Intégration continue

| Workflow | Déclencheur | Rôle |
|---|---|---|
| `ci.yml` | push sur `main`, pull request | Ruff + pytest ; sur `main`, build complet publié en artefact (14 jours) |
| `release.yml` | tag `vX.Y.Z` | Vérifie tag/version/changelog, teste, construit et crée la release GitHub |

## Publier une version

1. Pendant le développement, ajoute chaque changement visible sous `## [Unreleased]` dans `CHANGELOG.md`.
2. Sur `main` à jour et propre :

   ```powershell
   python scripts/release.py prepare 0.2.0
   ```

   Le script met à jour `__version__`, transforme `[Unreleased]` en `[0.2.0] - <date>`, commite et crée le tag `v0.2.0`.
3. Publie :

   ```powershell
   git push origin main --follow-tags
   ```

   Le workflow `release.yml` construit et publie la release avec les notes du changelog.
   Un tag avec suffixe (`v0.3.0-rc.1`) produit une pré-version.

La version n'est définie qu'à un endroit : `src/py_network_launcher/__init__.py`. Le paquet Python, l'exécutable
(métadonnées Windows) et l'installateur la lisent depuis ce fichier.
