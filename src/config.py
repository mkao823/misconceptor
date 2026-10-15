"""Load YAML configs and resolve API keys from environment variables."""

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "configs"


def load_config(name: str) -> dict:
    """Load configs/<name>.yaml."""
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def get_api_key(provider: str) -> str:
    """Return the API key for a provider, read from the env var named in models.yaml."""
    providers = load_config("models")["providers"]
    env_var = providers[provider]["api_key_env"]
    key = os.environ.get(env_var)
    if not key:
        raise RuntimeError(f"Set the {env_var} environment variable (see .env.example).")
    return key
