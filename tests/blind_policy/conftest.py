"""Lädt die HA-freien Dateien (const.py, policy.py) als synthetisches Paket.

Vermeidet den HA-Import-Pfad: policy.py nutzt ``from .const import ...``, was über
das synthetische Paket ``bbp_pure_pkg`` auf die geladene const.py auflöst — so
laufen die Pure-Logic-Tests ohne installiertes Home Assistant.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG_DIR = os.path.join(ROOT, "custom_components", "benni_blind_policy")

pkg_name = "bbp_pure_pkg"
pkg = types.ModuleType(pkg_name)
pkg.__path__ = [PKG_DIR]
sys.modules[pkg_name] = pkg


def _load(modname: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"{pkg_name}.{modname}", os.path.join(PKG_DIR, filename)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{pkg_name}.{modname}"] = mod
    spec.loader.exec_module(mod)
    return mod


const = _load("const", "const.py")
policy = _load("policy", "policy.py")

sys.modules["bbp_const"] = const
sys.modules["bbp_policy"] = policy
