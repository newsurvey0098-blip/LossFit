"""Load project-local environment files with safe, documented precedence."""
import os
from pathlib import Path
from collections.abc import MutableMapping

from dotenv import dotenv_values


def load_project_environment(project_root: Path, environ: MutableMapping[str, str] | None = None) -> None:
    """Load developer overrides before the shared template, without replacing OS env.

    `.env.local` is intended for ignored, machine-specific settings. It is skipped
    in production so local credentials cannot leak into a production process.
    Existing process environment variables always take precedence.
    """
    root = Path(project_root)
    target = os.environ if environ is None else environ
    base_path = root / ".env"
    base_values = dotenv_values(base_path)
    environment = target.get("ENVIRONMENT") or base_values.get("ENVIRONMENT") or "development"
    files = [root / ".env.local"] if environment.lower() != "production" else []
    files.append(base_path)
    for path in files:
        for name, value in dotenv_values(path).items():
            if value is not None and name not in target:
                target[name] = value
