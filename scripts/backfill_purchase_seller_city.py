#!/usr/bin/env python3
"""CLI wrapper — deleguje do app.services.purchase_seller_city_backfill."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.purchase_seller_city_backfill import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
