import json
from pathlib import Path

import pytest

from py_network_launcher.models import AppConfig, LaunchSequence
from py_network_launcher.storage import ConfigStore


def test_save_and_load(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json", legacy_path=None)
    config = AppConfig(sequences=[LaunchSequence(name="Démo")])
    store.save(config)
    assert ConfigStore(tmp_path / "config.json", legacy_path=None).load().sequences[0].name == "Démo"
    assert list(tmp_path.glob("*.tmp")) == []


def test_missing_file_gives_empty_config(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json", legacy_path=None)
    assert store.load().sequences == []
    assert store.load_warning is None


def test_unreadable_file_is_kept_aside_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{ pas du json", encoding="utf-8")
    store = ConfigStore(path, legacy_path=None)
    config = store.load()
    assert config.sequences == []
    assert store.load_warning
    backups = list(tmp_path.glob("config.illisible-*.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{ pas du json"


def test_legacy_file_is_migrated(tmp_path: Path) -> None:
    legacy = tmp_path / "home" / "py-network-launcher.json"
    legacy.parent.mkdir()
    legacy.write_text(json.dumps({"version": 1, "sequences": [{"name": "Ancienne", "run_once_on_boot": True}]}), encoding="utf-8")
    path = tmp_path / "appdata" / "config.json"
    config = ConfigStore(path, legacy_path=legacy).load()
    assert config.sequences[0].name == "Ancienne"
    assert path.exists()
    assert not legacy.exists()


def test_save_soon_is_debounced_and_flushed(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    store = ConfigStore(path, legacy_path=None)
    config = AppConfig(sequences=[LaunchSequence(name="v1")])
    store.save_soon(config, delay_s=30)
    config.sequences[0].name = "v2"
    store.save_soon(config, delay_s=30)
    assert not path.exists()
    store.flush()
    assert json.loads(path.read_text(encoding="utf-8"))["sequences"][0]["name"] == "v2"


def test_file_saved_with_utf8_bom_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"sequences": [{"name": "Édité à la main"}]}).encode("utf-8"))
    store = ConfigStore(path, legacy_path=None)
    assert store.load().sequences[0].name == "Édité à la main"
    assert store.load_warning is None


def test_locked_file_is_never_overwritten(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"sequences": [{"name": "Précieuse"}]}', encoding="utf-8")
    store = ConfigStore(path, legacy_path=None)

    def locked(self):
        raise PermissionError(13, "fichier verrouillé")

    monkeypatch.setattr(Path, "read_bytes", locked)
    monkeypatch.setattr("py_network_launcher.storage.time.sleep", lambda _s: None)
    assert store.load().sequences == []
    assert store.read_only and store.load_warning
    monkeypatch.undo()
    with pytest.raises(RuntimeError):
        store.save(AppConfig())
    assert "Précieuse" in path.read_text(encoding="utf-8")
