# SPDX-FileCopyrightText: Copyright (c) 2026 provide.io llc
# SPDX-License-Identifier: Apache-2.0

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pytest import MonkeyPatch

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VERSION_FILE = _PROJECT_ROOT / "VERSION"


def test_version_file() -> None:
    assert _VERSION_FILE.read_text(encoding="utf-8").strip() == "0.1.0"


def test_package_version_sources_agree() -> None:
    import routedef

    version_file = _VERSION_FILE.read_text(encoding="utf-8").strip()

    assert isinstance(routedef.__all__, tuple)
    assert routedef.__version__ == version_file
    assert version("routedef") == version_file


def test_package_version_falls_back_to_version_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    import routedef.version as version_module

    package_names: list[str] = []
    version_file = tmp_path / "VERSION"
    version_file.write_text("9.8.7\n", encoding="utf-8")

    def missing_metadata(_package_name: str) -> str:
        package_names.append(_package_name)
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "_metadata_version", missing_metadata)
    monkeypatch.setattr(version_module, "_VERSION_FILE", version_file)

    assert version_module.load_version() == "9.8.7"
    assert package_names == ["routedef"]
