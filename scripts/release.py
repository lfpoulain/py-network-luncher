"""Outils de release (bibliothèque standard uniquement).

    python scripts/release.py prepare 0.2.0   # version + CHANGELOG + commit + tag v0.2.0
    python scripts/release.py check v0.2.0    # vérifie tag / version / changelog (utilisé par la CI)
    python scripts/release.py notes v0.2.0    # affiche la section du CHANGELOG pour cette version

Après `prepare`, publier avec : git push origin main --follow-tags
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src" / "py_network_launcher" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
REPO_URL = "https://github.com/lfpoulain/py-network-luncher"

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
VERSION_LINE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
SECTION = re.compile(r"^## \[(?P<version>[^\]]+)\][^\n]*\n(?P<body>.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", re.MULTILINE | re.DOTALL)


class ReleaseError(RuntimeError):
    pass


def current_version() -> str:
    match = VERSION_LINE.search(INIT_FILE.read_text(encoding="utf-8"))
    if match is None:
        raise ReleaseError(f"__version__ introuvable dans {INIT_FILE}")
    return match.group(1)


def changelog_section(text: str, version: str) -> str | None:
    for match in SECTION.finditer(text):
        if match.group("version") == version:
            return match.group("body").strip()
    return None


def bump_changelog(text: str, version: str, today: dt.date) -> str:
    unreleased = changelog_section(text, "Unreleased")
    if not unreleased:
        raise ReleaseError("La section [Unreleased] du CHANGELOG est vide : rien à publier.")
    text = re.sub(r"^## \[Unreleased\][^\n]*\n", f"## [Unreleased]\n\n## [{version}] - {today.isoformat()}\n", text, count=1, flags=re.MULTILINE)
    links = f"[Unreleased]: {REPO_URL}/compare/v{version}...HEAD\n[{version}]: {REPO_URL}/releases/tag/v{version}\n"
    if re.search(r"^\[Unreleased\]: .*$", text, flags=re.MULTILINE):
        text = re.sub(r"^\[Unreleased\]: .*\n?", links, text, count=1, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + "\n\n" + links
    return text


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)} : {result.stderr.strip()}")
    return result.stdout.strip()


def normalize_tag(tag: str) -> str:
    version = tag.removeprefix("refs/tags/").removeprefix("v")
    if not SEMVER.match(version):
        raise ReleaseError(f"« {tag} » n'est pas une version valide (attendu vX.Y.Z)")
    return version


def cmd_check(tag: str) -> None:
    version = normalize_tag(tag)
    if current_version() != version:
        raise ReleaseError(f"Le tag {tag} ne correspond pas à __version__ = {current_version()}")
    if not changelog_section(CHANGELOG.read_text(encoding="utf-8"), version):
        raise ReleaseError(f"Aucune section [{version}] dans CHANGELOG.md")
    print(f"OK : version {version}")


def cmd_notes(tag: str, output: str | None) -> None:
    version = normalize_tag(tag)
    body = changelog_section(CHANGELOG.read_text(encoding="utf-8"), version)
    if not body:
        raise ReleaseError(f"Aucune section [{version}] dans CHANGELOG.md")
    notes = (
        f"{body}\n\n---\n\n"
        "**Installation** : télécharge `PyNetworkLauncher-Setup-*.exe` (installateur) "
        "ou `PyNetworkLauncher-*-portable.zip` (sans installation). "
        "Les sommes SHA-256 sont dans `SHA256SUMS.txt`.\n"
    )
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(notes, encoding="utf-8")
    else:
        sys.stdout.write(notes)


def cmd_prepare(version: str, *, allow_dirty: bool) -> None:
    version = normalize_tag(version)
    previous = current_version()
    if version == previous:
        raise ReleaseError(f"La version {version} est déjà la version courante")
    if not allow_dirty and git("status", "--porcelain"):
        raise ReleaseError("Le dépôt contient des modifications non commitées (utilise --allow-dirty pour forcer)")
    if git("tag", "--list", f"v{version}"):
        raise ReleaseError(f"Le tag v{version} existe déjà")

    CHANGELOG.write_text(bump_changelog(CHANGELOG.read_text(encoding="utf-8"), version, dt.date.today()), encoding="utf-8")
    INIT_FILE.write_text(VERSION_LINE.sub(f'__version__ = "{version}"', INIT_FILE.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    git("add", str(CHANGELOG), str(INIT_FILE))
    git("commit", "-m", f"Release v{version}")
    git("tag", "-a", f"v{version}", "-m", f"Py Network Launcher v{version}")
    print(f"Version {version} prête (commit + tag v{version}).")
    print("Publie-la avec :  git push origin main --follow-tags")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="prépare une nouvelle version (commit + tag)")
    prepare.add_argument("version")
    prepare.add_argument("--allow-dirty", action="store_true")
    commands.add_parser("check", help="vérifie la cohérence d'un tag").add_argument("tag")
    notes = commands.add_parser("notes", help="extrait les notes de version du CHANGELOG")
    notes.add_argument("tag")
    notes.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            cmd_prepare(args.version, allow_dirty=args.allow_dirty)
        elif args.command == "check":
            cmd_check(args.tag)
        else:
            cmd_notes(args.tag, args.output)
    except ReleaseError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
