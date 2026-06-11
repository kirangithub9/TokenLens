"""
Auto-discovers all provider wrappers in this package at import time.

Each wrapper file must define:
  PROVIDER_MODULE: str            — substring matched against type(client).__module__
  wrap_<filename>(client, tl)     — factory that returns a wrapped client

To add a new provider:
  1. Create wrappers/<provider>.py with PROVIDER_MODULE + wrap_<provider>()
  2. Add the provider package to pyproject.toml dependencies
  3. pip install -e .  (or release a new version)
"""

import importlib
from pathlib import Path

REGISTRY: dict[str, object] = {}


def _discover() -> None:
    for path in Path(__file__).parent.glob("*.py"):
        if path.stem.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f".{path.stem}", package=__name__)
            provider = getattr(mod, "PROVIDER_MODULE", None)
            fn = getattr(mod, f"wrap_{path.stem}", None)
            if provider and fn:
                REGISTRY[provider] = fn
        except ImportError:
            pass


_discover()
