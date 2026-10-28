import datetime as dt
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_script", ROOT / "scripts" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

SAMPLE = """# Changelog

## [Unreleased]

### Corrections

- Un bug corrigé.

## [0.1.0] - 2026-03-19

Première version.

[Unreleased]: https://example/compare/v0.1.0...HEAD
[0.1.0]: https://example/commits/v0.1.0
"""


def test_changelog_section_extraction() -> None:
    assert release.changelog_section(SAMPLE, "Unreleased") == "### Corrections\n\n- Un bug corrigé."
    assert release.changelog_section(SAMPLE, "0.1.0") == "Première version."
    assert release.changelog_section(SAMPLE, "9.9.9") is None


def test_bump_changelog_moves_unreleased_entries() -> None:
    bumped = release.bump_changelog(SAMPLE, "0.2.0", dt.date(2026, 11, 2))
    assert release.changelog_section(bumped, "Unreleased") == ""
    assert release.changelog_section(bumped, "0.2.0") == "### Corrections\n\n- Un bug corrigé."
    assert "## [0.2.0] - 2026-11-02" in bumped
    assert "[0.2.0]: https://github.com/lfpoulain/py-network-luncher/releases/tag/v0.2.0" in bumped
    assert "[0.1.0]: https://example/commits/v0.1.0" in bumped


def test_the_real_changelog_matches_the_current_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert release.changelog_section(text, release.current_version())


def test_tag_normalization() -> None:
    assert release.normalize_tag("v1.2.3") == "1.2.3"
    assert release.normalize_tag("refs/tags/v1.0.0-rc.1") == "1.0.0-rc.1"
