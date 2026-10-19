"""Regression tests for renamed product metadata and its API surface."""
from pathlib import Path

from app.main import app
from app.memory.models import Vault

ROOT = Path(__file__).resolve().parents[1]


def test_product_name():
    assert app.title == "TMC — Total Memory Core v1.0.0"


def test_default_vault_owner_is_generic():
    vault = Vault(display_name="Example")
    assert vault.owner_label == "Local Operator"


def test_public_source_license():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License")
    assert "Permission is hereby granted, free of charge" in text
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in text


def test_package_identifiers_unchanged():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "tmc"' in text
    assert 'version = "1.0.0"' in text
