"""Minimal PEP 517 backend so the project metadata has no network dependency.

The application is intended to run directly from source. The Hertz environment
does not need to build a wheel, but a backend is provided so metadata inspection
does not attempt to download setuptools.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


def _dist_info() -> str:
    return "equitylab_portable-0.1.0.dist-info"


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings=None) -> str:
    target = Path(metadata_directory, _dist_info())
    target.mkdir(parents=True, exist_ok=True)
    target.joinpath("METADATA").write_text(
        "Metadata-Version: 2.1\nName: equitylab-portable\nVersion: 0.1.0\n"
        "Requires-Python: >=3.10\n",
        encoding="utf-8",
    )
    target.joinpath("WHEEL").write_text(
        "Wheel-Version: 1.0\nGenerator: equitylab-build\nRoot-Is-Purelib: true\n"
        "Tag: py3-none-any\n",
        encoding="utf-8",
    )
    return target.name


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    name = "equitylab_portable-0.1.0-py3-none-any.whl"
    destination = Path(wheel_directory, name)
    root = Path(__file__).parent
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in root.joinpath("equitylab").glob("*.py"):
            archive.write(source, source.relative_to(root).as_posix())
        metadata = _dist_info()
        archive.writestr(
            f"{metadata}/METADATA",
            "Metadata-Version: 2.1\nName: equitylab-portable\nVersion: 0.1.0\n"
            "Requires-Python: >=3.10\n",
        )
        archive.writestr(
            f"{metadata}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: equitylab-build\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        archive.writestr(f"{metadata}/RECORD", "")
    return name


def build_sdist(sdist_directory: str, config_settings=None) -> str:
    raise RuntimeError("source distributions are not supported; run directly from source")
