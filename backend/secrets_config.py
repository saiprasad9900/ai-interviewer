"""
secrets_config.py — Load GROQ_API_KEY from env, .env, TOML, or Streamlit secrets.

Streamlit Community Cloud stores secrets in st.secrets; they are not always
in os.environ before the embedded FastAPI thread starts. This module copies
them into os.environ so Groq is used instead of demo mode.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_PLACEHOLDER_KEYS = {
    "",
    "your-groq-api-key",
    "your-groq-api-key-here",
    "your_groq_api_key_here",
    "sk-your-key-here",
    "changeme",
    "xxx",
}

_ROOT = Path(__file__).resolve().parent.parent


def _is_valid_groq_key(key: str) -> bool:
    k = (key or "").strip()
    if k.lower() in _PLACEHOLDER_KEYS:
        return False
    # Groq keys typically start with gsk_
    return len(k) >= 20 and (k.startswith("gsk_") or k.startswith("gsk-"))


def _set_key(key: str) -> str:
    key = key.strip()
    if _is_valid_groq_key(key):
        os.environ["GROQ_API_KEY"] = key
        return key
    return ""


def _flatten_secrets(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.extend(_flatten_secrets(v, p))
    else:
        out.append((prefix, str(obj)))
    return out


def _from_streamlit_secrets() -> str:
    try:
        import streamlit as st
    except ImportError:
        return ""

    try:
        secrets = st.secrets
    except Exception:
        return ""

    # Direct keys (Streamlit Cloud dashboard / secrets.toml)
    for name in (
        "GROQ_API_KEY",
        "groq_api_key",
        "GROQ_APIKEY",
        "groq_apikey",
    ):
        try:
            val = secrets[name]
            if isinstance(val, str):
                found = _set_key(val)
                if found:
                    return found
        except (KeyError, TypeError, AttributeError):
            pass

    # Nested: [groq] api_key = "..."
    try:
        groq = secrets["groq"]
        if isinstance(groq, dict):
            for sub in ("api_key", "apikey", "GROQ_API_KEY", "key"):
                if sub in groq:
                    found = _set_key(str(groq[sub]))
                    if found:
                        return found
    except (KeyError, TypeError, AttributeError):
        pass

    # Any secret key containing groq + key
    for path, value in _flatten_secrets(dict(secrets)):
        low = path.lower()
        if "groq" in low and ("key" in low or "api" in low):
            found = _set_key(value)
            if found:
                return found

    return ""


def _from_toml_files() -> str:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return ""

    candidates = [
        _ROOT / ".streamlit" / "secrets.toml",
        Path(os.getenv("STREAMLIT_SECRETS", "")),
    ]
    home = Path.home() / ".streamlit" / "secrets.toml"
    if home.exists():
        candidates.append(home)

    for path in candidates:
        if not path or not Path(path).is_file():
            continue
        try:
            data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        if "GROQ_API_KEY" in data:
            found = _set_key(str(data["GROQ_API_KEY"]))
            if found:
                return found
        groq = data.get("groq") or data.get("GROQ")
        if isinstance(groq, dict):
            for sub in ("api_key", "GROQ_API_KEY", "key"):
                if sub in groq:
                    found = _set_key(str(groq[sub]))
                    if found:
                        return found
    return ""


def bootstrap_groq_api_key() -> str:
    """
    Resolve GROQ_API_KEY and set os.environ. Safe to call multiple times.
    Returns the key string, or empty if not configured.
    """
    existing = os.getenv("GROQ_API_KEY", "").strip()
    if _is_valid_groq_key(existing):
        return existing

    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    existing = os.getenv("GROQ_API_KEY", "").strip()
    if _is_valid_groq_key(existing):
        return existing

    for loader in (_from_streamlit_secrets, _from_toml_files):
        found = loader()
        if found:
            return found

    return os.getenv("GROQ_API_KEY", "").strip()


def get_groq_api_key() -> str:
    return bootstrap_groq_api_key()


def groq_configured() -> bool:
    return _is_valid_groq_key(get_groq_api_key())
