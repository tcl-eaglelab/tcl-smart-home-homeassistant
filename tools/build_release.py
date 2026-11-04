"""Build source/manual ZIPs from reviewed paths, without local HA data.

Usage: python tools/build_release.py --output /path/to/release
The output directory must be outside the source tree. This tool does not publish.
"""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT_FILES = {
    "README.md",
    "README_zh-CN.md",
    "LICENSE",
    "SECURITY.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "hacs.json",
    "pyproject.toml",
    "requirements-test.txt",
    ".gitignore",
}
ROOT_DIRS = {"custom_components", "docs", "tests", "tools", ".github"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".git", ".venv", "venv"}
EXTENSIONS = {
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".toml",
    ".csv",
    ".js",
    ".png",
}


def build(source: Path, output: Path) -> list[dict]:
    source, output = source.resolve(), output.resolve()
    if output.is_relative_to(source):
        raise ValueError("Release output must be outside the source tree")
    component = source / "custom_components/tcl_smart_home"
    version = json.loads((component / "manifest.json").read_text(encoding="utf-8"))[
        "version"
    ]
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[a-zA-Z0-9.-]+)?", version):
        raise ValueError("Invalid release version")
    files = []
    for file in sorted(source.rglob("*")):
        relative = file.relative_to(source)
        if any(
            p in SKIP_DIRS or p.startswith("pytest-cache-files-")
            for p in relative.parts
        ):
            continue
        if file.is_symlink():
            raise ValueError("Symlinks are not allowed in releases")
        if not file.is_file():
            continue
        if relative.as_posix() not in ROOT_FILES and (
            relative.parts[0] not in ROOT_DIRS or file.suffix not in EXTENSIONS
        ):
            raise ValueError(f"Unreviewed release path: {relative}")
        if file.name.lower() in {"secrets.yaml", "configuration.yaml", "auth", ".env"}:
            raise ValueError("Private configuration must not be packaged")
        files.append(file)
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    for kind in ("manual-install", "source"):
        archive = output / f"TCL-Smart-Home-{version}-{kind}.zip"
        expected = {}
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
            for file in files:
                relative = file.relative_to(source).as_posix()
                if kind == "manual-install" and not (
                    file.is_relative_to(component)
                    or relative.startswith("docs/")
                    or relative
                    in {
                        "README.md",
                        "README_zh-CN.md",
                        "LICENSE",
                        "SECURITY.md",
                        "tools/migrate_credentials.py",
                    }
                ):
                    continue
                name = (
                    "tcl-smart-home-unified-homeassistant/" if kind == "source" else ""
                ) + relative
                # Stable timestamps and permissions make equal input reproducible.
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                data = file.read_bytes()
                package.writestr(info, data)
                expected[name] = data
        with zipfile.ZipFile(archive) as package:
            if package.testzip() is not None or any(
                package.read(name) != data for name, data in expected.items()
            ):
                raise ValueError("Archive verification failed")
        checks.append(
            {
                "file": archive.name,
                "files": len(expected),
                "crc_ok": True,
                "source_bytes_match": True,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
        )
    (output / "SHA256SUMS.txt").write_text(
        "\n".join(f"{item['sha256']}  {item['file']}" for item in checks) + "\n",
        encoding="utf-8",
    )
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], args.output)))
