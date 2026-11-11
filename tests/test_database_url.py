import os
import sys
import pytest
from config import clean_database_url


def test_clean_database_url_none():
    assert clean_database_url(None) is None
    assert clean_database_url("") is None
    assert clean_database_url("   ") is None
    assert clean_database_url("none") is None
    assert clean_database_url("null") is None
    assert clean_database_url("undefined") is None


def test_clean_database_url_sqlite():
    res = clean_database_url("sqlite:///instance/money_tracker.db")
    assert res == "sqlite:///instance/money_tracker.db"


def test_clean_database_url_quoted():
    res = clean_database_url('"sqlite:///instance/money_tracker.db"')
    assert res == "sqlite:///instance/money_tracker.db"


def test_clean_database_url_postgresql_psycopg_neon_ssl():
    url = "postgresql+psycopg://user:password@ep-sample-1234.us-east-2.aws.neon.tech/neondb"
    res = clean_database_url(url)
    assert res is not None
    assert "sslmode=require" in res
    assert "ep-sample-1234.us-east-2.aws.neon.tech" in res


def test_clean_database_url_legacy_postgres():
    url = "postgres://user:password@localhost:5432/testdb"
    res = clean_database_url(url)
    assert res is not None
    assert not res.startswith("postgres://")
    assert res.startswith("postgresql")


def test_clean_database_url_fallback_when_psycopg_missing(monkeypatch):
    """When psycopg module is missing, clean_database_url should fall back to psycopg2 or pg8000."""
    monkeypatch.setitem(sys.modules, "psycopg", None)
    url = "postgresql+psycopg://user:password@localhost:5432/testdb"
    res = clean_database_url(url)
    assert res is not None
    assert "postgresql+" in res
    assert not res.startswith("postgresql+psycopg://")


def test_clean_database_url_fallback_when_both_missing(monkeypatch):
    """When both psycopg and psycopg2 are missing, fallback to pg8000."""
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    url = "postgresql://user:password@localhost:5432/testdb"
    res = clean_database_url(url)
    assert res is not None
    assert res.startswith("postgresql+pg8000://")

