# Changelog

Toutes les évolutions notables de Py Network Launcher sont listées ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions selon [SemVer](https://semver.org/lang/fr/).

## [Unreleased]

### Corrections

- L'application n'éteint plus le HDR et n'assombrit plus les écrans externes sous Windows pendant qu'elle tourne (correctif Flet 1.0.4).
- Plus de bref affichage de la fenêtre dans le coin de l'écran au démarrage réduit dans la zone de notification.
- Un champ en cours de saisie ne perd plus le focus quand un élément voisin apparaît ou disparaît.
- La sortie d'une commande shell est refermée après lecture (fuite de ressource à chaque exécution).

### Technique

- Passage de Flet 0.82.2 à 1.0.5.
- Le client Flet (`flet.exe`), qui n'est plus fourni par le paquet `flet-desktop`, est téléchargé une fois au build, vérifié (SHA-256) et embarqué : l'application installée fonctionne toujours hors ligne dès le premier lancement.
- Extra `web` pour le mode `--web` de développement (`pip install -e ".[web]"`).

## [0.2.0] - 2026-10-28

### Nouveautés

- Nouvelle interface : navigation latérale, barre d'état réseau (postes en ligne, erreurs de port), notifications avec action « Annuler ».
- Réordonnancement des étapes par glisser-déposer natif, menu par étape (monter, descendre, dupliquer, désactiver, supprimer), « Tout déplier / replier ».
- Étapes désactivables et option « Continuer si elle échoue ».
- Duplication de séquence ; confirmation avant suppression (avec la liste des séquences qui l'appellent).
- Suivi d'exécution conservé après la fin : étape en échec en rouge avec la raison, statut « réussie / échouée / arrêtée » sur la séquence.
- Test d'une étape seule avec retour de résultat.
- Onglet « Postes » : lancement direct des séquences d'un autre poste, état « API injoignable » quand le pare-feu bloque.
- Menu de la zone de notification : afficher la fenêtre (double-clic), lancer ou arrêter une séquence ; notification si une séquence échoue fenêtre masquée.
- Home Assistant : toutes les entités compatibles turn_on / turn_off (scènes, scripts, prises…), action « Basculer », bouton « Tester la connexion ».
- Étape « Séquence distante » : attend que le poste réapparaisse (pratique après un Wake-on-LAN).
- Commande shell : console masquée par défaut, sortie de la commande reprise dans le message d'erreur.
- Journal en couleurs, filtre « erreurs seulement », fichier de log tournant dans `%APPDATA%\PyNetworkLauncher\logs`.
- Instance unique : relancer l'application ré-affiche la fenêtre existante.
- Les URL saisies sans schéma sont complétées (`homeassistant.local:8123` → `http://homeassistant.local:8123`).

### Corrections

- Un port API ou de découverte déjà utilisé n'empêche plus l'application de démarrer : l'erreur est affichée et les ports peuvent être corrigés à chaud.
- Deux applications ne peuvent plus écouter silencieusement le même port API (bind exclusif sous Windows).
- Lancer une séquence déjà en cours ne crée plus d'exécution en double qui mélangeait l'affichage et le bouton Stop.
- Les arguments entre guillemets (chemins avec espaces) sont transmis tels quels ; les guillemets autour du programme (« Copier en tant que chemin ») et les `%VARIABLES%` sont gérés.
- Le dossier de travail d'une application est par défaut son propre dossier (corrige OBS & co.).
- Raccourcis `.lnk`, documents et applications demandant les droits administrateur (UAC) peuvent être lancés.
- Une boucle entre séquences locales (A → B → A) est détectée au lieu de planter ; l'échec d'une sous-séquence arrête désormais la séquence appelante.
- Glisser une étape vers le bas la plaçait une position trop haut.
- La saisie n'est plus interrompue (perte du focus) quand une séquence tourne ou qu'un poste apparaît.
- La configuration n'est plus réécrite à chaque frappe (sauvegarde groupée).
- Une configuration illisible est mise de côté (`config.illisible-*.json`) au lieu d'être écrasée, et un fichier momentanément verrouillé (antivirus, sauvegarde) n'est jamais remplacé ; un fichier enregistré avec BOM UTF-8 est accepté.
- « Une fois par session » se déclenche bien après un arrêt/rallumage avec le démarrage rapide de Windows, et n'est plus faussé au-delà de 49 jours d'uptime.
- Les postes déconnectés disparaissent de la liste ; un paquet de découverte malformé ne coupe plus la découverte.
- La découverte fonctionne avec plusieurs cartes réseau (VPN, Hyper-V, WSL…).
- Le renommage du poste est diffusé immédiatement, sans redémarrer le service.
- L'entrée de démarrage Windows est corrigée automatiquement si l'application a été déplacée ou mise à jour.
- Un nouveau poste voit ses séquences tout de suite (plus d'attente de 5 s).
- Les étapes ajoutées s'ouvrent directement en édition.

### Technique

- Code réorganisé en paquet `py_network_launcher` (UI découpée par vue), suite de tests pytest, lint/format Ruff.
- Configuration déplacée dans `%APPDATA%\PyNetworkLauncher\config.json` (migration automatique de `%USERPROFILE%\py-network-launcher.json`).
- Build unique `scripts/build.ps1` (exe versionné, archive portable, installateur, SHA-256) ; CI sur chaque push/PR ; release automatique sur tag `vX.Y.Z`.
- L'installateur ferme l'application avant mise à jour, la relance sans droits administrateur et nettoie l'entrée de démarrage à la désinstallation.

## [0.1.0] - 2026-03-19

Première version : séquences locales et distantes, découverte LAN, API HTTP, étapes application / shell / page web /
webhook / Wake-on-LAN / délai / séquence locale / séquence distante / Home Assistant, zone de notification,
démarrage avec Windows, installateur Inno Setup.

[Unreleased]: https://github.com/lfpoulain/py-network-luncher/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/lfpoulain/py-network-luncher/releases/tag/v0.2.0
[0.1.0]: https://github.com/lfpoulain/py-network-luncher/tree/3fb7792
