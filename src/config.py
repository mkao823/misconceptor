"""Load YAML configs, resolve API keys from environment variables, resolve model names.

Paths are anchored at the repo root so every script and test can import this
module without caring about the working directory.
"""

import hashlib
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "configs"
PROMPT_DIR = CONFIG_DIR / "prompts"
TAXONOMY_PATH = REPO_ROOT / "taxonomy" / "recursion_bigO.yaml"
ANNOTATION_SHEET = REPO_ROOT / "annotation" / "pilot_sheet.csv"
RESULTS_DIR = REPO_ROOT / "results"

# Used for providers that do not check the key (Ollama). The OpenAI SDK refuses
# an empty key, so a placeholder is required even when the server ignores it.
PLACEHOLDER_API_KEY = "no-key-needed"


def load_dotenv(path: Path | None = None) -> None:
    """Export KEY=value lines from .env (gitignored) without overriding existing env vars."""
    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(name: str) -> dict:
    """Load configs/<name>.yaml."""
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)


def get_api_key(provider: str, providers: dict | None = None) -> str:
    """Return the API key for a provider, read from the env var named in models.yaml.

    Providers with ``api_key_required: false`` fall back to a placeholder when the
    variable is unset or empty (any value is accepted by Ollama).
    """
    providers = providers if providers is not None else load_config("models")["providers"]
    if provider not in providers:
        raise KeyError(f"Unknown provider {provider!r}; known: {sorted(providers)}")
    pcfg = providers[provider]
    env_var = pcfg["api_key_env"]
    load_dotenv()
    key = os.environ.get(env_var)
    if key:
        return key
    if pcfg.get("api_key_required", True) is False:
        return PLACEHOLDER_API_KEY
    raise RuntimeError(f"Set the {env_var} environment variable (see .env.example).")


def resolve_model(spec: str | None = None, models_cfg: dict | None = None) -> tuple[str, str]:
    """Map ``provider/model`` or a bare ``model`` to ``(provider, model)``.

    A bare name is looked up in each provider's ``models`` list; if no provider
    lists it, ``default_provider`` is used. ``None`` means ``default_model``.
    """
    cfg = models_cfg if models_cfg is not None else load_config("models")
    providers = cfg["providers"]
    spec = spec or cfg["default_model"]
    if spec is None or str(spec).upper() == "TODO":
        raise RuntimeError("configs/models.yaml: default_model is not set")
    head, sep, tail = str(spec).partition("/")
    if sep and head in providers:
        return head, tail
    for name, pcfg in providers.items():
        if spec in (pcfg.get("models") or []):
            return name, spec
    default_provider = cfg.get("default_provider")
    if not default_provider:
        raise RuntimeError(f"No provider lists model {spec!r} and default_provider is unset")
    return default_provider, spec


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
