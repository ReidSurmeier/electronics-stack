"""Behavioral contracts for offline-first LCSC lookup."""

from __future__ import annotations

import sqlite3
import sys
import urllib.request
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lcsc_client import LcscClient


def _create_fixture_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE manufacturers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE components (
            lcsc INTEGER PRIMARY KEY,
            mfr TEXT,
            manufacturer_id INTEGER,
            package TEXT,
            basic INTEGER,
            preferred INTEGER,
            stock INTEGER,
            price TEXT,
            datasheet TEXT,
            description TEXT
        );
        INSERT INTO manufacturers (id, name)
        VALUES (1, 'STMicroelectronics');
        INSERT INTO components (
            lcsc, mfr, manufacturer_id, package, basic, preferred,
            stock, price, datasheet, description
        ) VALUES (
            8734, 'STM32F103C8T6', 1, 'LQFP-48', 1, 0,
            42, '[{"qFrom": 1, "price": 2.5}]',
            'https://example.invalid/datasheet.pdf', 'MCU'
        );
        """
    )
    connection.commit()
    connection.close()


def test_missing_cache_fails_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def reject_network(*args: object, **kwargs: object) -> object:
        calls.append(str(args[0]) if args else "unknown")
        raise AssertionError("offline lookup attempted a download")

    monkeypatch.setattr(urllib.request, "urlopen", reject_network)

    with pytest.raises(RuntimeError, match="refresh"):
        LcscClient.from_env(db_path=tmp_path / "missing.sqlite3")

    assert calls == []


def test_local_database_supports_keyword_and_id_lookup(tmp_path: Path) -> None:
    database = tmp_path / "cache.sqlite3"
    _create_fixture_database(database)

    with LcscClient.from_env(db_path=database) as client:
        matches = client.keyword_search("STM32F103", limit=3)
        by_id = client.lookup_lcsc_id("C8734")

    assert matches[0]["mpn"] == "STM32F103C8T6"
    assert matches[0]["stock"] == 42
    assert matches[0]["price_tiers"] == [{"qty": 1, "price_usd": 2.5}]
    assert by_id == matches[0]
