"""Move credentials from an installed pre-0.3 component into local HA secrets.

Run BEFORE replacing the old component. Default is a dry run. No values are
printed. This local migration does not establish vendor redistribution rights.
"""

import argparse
import ast
import json
import re
from datetime import datetime
from pathlib import Path


def migrate(config_dir: Path, apply: bool = False) -> None:
    config_dir = config_dir.resolve(strict=True)
    config = config_dir / "configuration.yaml"
    secrets = config_dir / "secrets.yaml"
    old = config_dir / "custom_components/tcl_smart_home/const.py"
    config_text = config.read_text(encoding="utf-8")
    secrets_text = secrets.read_text(encoding="utf-8") if secrets.exists() else ""
    if re.search(r"^tcl_smart_home\s*:", config_text, re.MULTILINE):
        raise ValueError(
            "TCL YAML configuration already exists; merge manually using the upgrade guide"
        )
    names = {
        "DOMESTIC_APP_SECRET": "tcl_ha_domestic_app_secret",
        "OVERSEAS_CLIENT_SECRET": "tcl_ha_overseas_client_secret",
    }
    values = {}
    for node in ast.parse(old.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    value = ast.literal_eval(node.value)
                    if isinstance(value, str) and value:
                        values[names[target.id]] = value
    if len(values) != 2:
        raise ValueError(
            "Expected pre-0.3 domestic and overseas credentials; nothing changed"
        )
    if any(
        re.search(r"^" + re.escape(key) + r"\s*:", secrets_text, re.MULTILINE)
        for key in values
    ):
        raise ValueError("Destination secret names already exist; nothing changed")
    if not apply:
        print(
            "Dry run passed. Use --apply to back up and update local configuration.yaml and secrets.yaml."
        )
        return
    backup = (
        config_dir
        / "tcl_credential_backups"
        / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    )
    backup.mkdir(parents=True, exist_ok=False)
    (backup / "configuration.yaml").write_bytes(config.read_bytes())
    if secrets.exists():
        (backup / "secrets.yaml").write_bytes(secrets.read_bytes())
    # Write secrets first: if interrupted, configuration still uses the old code.
    with secrets.open("a", encoding="utf-8") as destination:
        destination.write("\n# TCL application credentials: keep this file private.\n")
        for key, value in values.items():
            destination.write(f"{key}: {json.dumps(value)}\n")
    with config.open("a", encoding="utf-8") as destination:
        destination.write(
            "\ntcl_smart_home:\n  domestic_app_secret: !secret tcl_ha_domestic_app_secret\n  overseas_client_secret: !secret tcl_ha_overseas_client_secret\n"
        )
    print(
        "Local credentials migrated. Protect secrets.yaml and tcl_credential_backups. No credential values were printed."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    try:
        migrate(arguments.config_dir, arguments.apply)
    except (OSError, ValueError, SyntaxError):
        parser.exit(
            1,
            "Migration could not complete. Check the old component/configuration, or merge manually. Inspect local backups if any writes occurred. No credentials were printed.\n",
        )
