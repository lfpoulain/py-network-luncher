from __future__ import annotations

import argparse
from functools import partial

import flet as ft

from main_window import main as window_main
from runtime_paths import assets_dir


def main() -> int:
    parser = argparse.ArgumentParser(prog="py-network-launcher")
    parser.add_argument("--hidden", action="store_true")
    args = parser.parse_args()

    view = ft.AppView.FLET_APP_HIDDEN if args.hidden else ft.AppView.FLET_APP
    ft.run(partial(window_main, hidden=bool(args.hidden)), view=view, assets_dir=str(assets_dir()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
