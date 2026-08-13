"""About-column file-guess consent. Off by default. No file reads here."""

from __future__ import annotations

from pathlib import Path

ACPT_HELP = """\
About-column consent (acpt)

Default: OFF. The About column shows a README excerpt, or —.
Get Gited does not read other project files to guess what a repo is.

Granting consent allows reading only public manifests:
  - pyproject.toml  [project].description
  - package.json    "description"
  - Cargo.toml      [package].description
  - well-known markers (Python / Node / Rust / Go / …)

Never used for this column: .env, credentials, source code, git history.

  gg acpt            show whether consent is granted
  gg acpt --on       grant (writes Get Gited config)
  gg acpt --off      revoke
  gg acpt -h
  gg acpt --help     this text
"""


def format_acpt_status(*, granted: bool, config_path: Path) -> str:
    state = "granted" if granted else "off (default)"
    return "\n".join(
        [
            ACPT_HELP.rstrip(),
            "",
            f"Current: {state}",
            f"Config:  {config_path}",
        ]
    )
