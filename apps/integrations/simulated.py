"""Helpers for loading the bundled SIMULATED data files (mock providers only)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.utils.dateparse import parse_datetime

DATA_DIR = Path(__file__).resolve().parent / "simulated_data"


def load(name):
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def to_decimal(value):
    return None if value is None else Decimal(str(value))


def to_date(value):
    return date.fromisoformat(value) if value else None


def to_datetime(value):
    return parse_datetime(value) if value else None
