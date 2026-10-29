"""Point d'entrée : arguments, journalisation, instance unique puis fenêtre Flet."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from functools import partial
from typing import Optional

from py_network_launcher import APP_NAME, __version__
from py_network_launcher.logs import get_logger, setup_logging
from py_network_launcher.paths import assets_dir, bundled_flet_client_dir, config_path, is_frozen, logs_dir
from py_network_launcher.windows import SingleInstanceLock

logger = get_logger()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="py-network-launcher", description=APP_NAME)
    parser.add_argument("--hidden", action="store_true", help="démarrer réduit dans la zone de notification")
    parser.add_argument("--web", type=int, metavar="PORT", help="(développement) servir l'interface dans un navigateur")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def _ask_running_instance_to_show() -> bool:
    """Demande à l'instance déjà lancée d'afficher sa fenêtre via son API locale."""
    try:
        data = json.loads(config_path().read_text(encoding="utf-8-sig"))
        port = int(data.get("settings", {}).get("api_port", 8765))
    except (OSError, ValueError, TypeError, AttributeError):
        port = 8765
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/show", data=b"{}", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=2):
            return True
    except OSError:
        return False


def _use_bundled_flet_client() -> None:
    """Exécutable : utilise le client Flet embarqué plutôt que de le télécharger depuis GitHub au premier lancement."""
    client = bundled_flet_client_dir()
    if is_frozen() and (client / "flet.exe").is_file():
        os.environ.setdefault("FLET_VIEW_PATH", str(client))


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(logs_dir())
    instance = SingleInstanceLock()
    if instance.already_running and args.web is None:
        if not args.hidden:
            _ask_running_instance_to_show()
        logger.info("Une instance est déjà en cours d'exécution, fermeture")
        return 0

    import flet as ft

    from py_network_launcher.ui.window import run_main_window

    logger.info(f"{APP_NAME} {__version__} (Python {sys.version.split()[0]})")
    target = partial(run_main_window, hidden=bool(args.hidden), web=args.web is not None)
    try:
        if args.web is not None:
            # Sert l'interface sans ouvrir de navigateur : on s'y connecte soi-même.
            os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")
            print(f"Interface disponible sur http://127.0.0.1:{args.web}", flush=True)
            ft.run(target, view=ft.AppView.WEB_BROWSER, port=args.web, assets_dir=str(assets_dir()))
        else:
            _use_bundled_flet_client()
            view = ft.AppView.FLET_APP_HIDDEN if args.hidden else ft.AppView.FLET_APP
            ft.run(target, view=view, assets_dir=str(assets_dir()))
    except Exception:
        logger.exception("Erreur fatale")
        raise
    finally:
        instance.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
