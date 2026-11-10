"""Import real usage figures from CSV.

Expected columns (header row required):
    timestamp,site_id,spot_type,occupied[,capacity][,source]

* timestamp: ISO-8601. Times with no offset are read as campus local time
  (America/Chicago), e.g. 2026-11-16 08:15
* site_id:   one of the ids in config/sites.yaml (simon-lot, snow-way, duc, millbrook, east-end)
* spot_type: red | yellow | visitor | ada | other
* occupied:  number of occupied spaces of that type at that time
* capacity:  optional. If omitted, the configured count for that site/spot type is used
* source:    optional. Defaults to "import"

See data_templates/usage_template.csv.
"""
from __future__ import annotations

import pandas as pd

from . import store
from .config import CAMPUS_TZ, SPOT_TYPE_ORDER, get_config


def import_csv(path: str) -> int:
    df = pd.read_csv(path)
    missing = {"timestamp", "site_id", "spot_type", "occupied"} - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    known = {s.id for s in get_config().sites}
    bad_sites = set(df.site_id) - known
    bad_types = set(df.spot_type) - set(SPOT_TYPE_ORDER)
    if bad_sites or bad_types:
        raise ValueError(f"Unknown site ids {sorted(bad_sites)} / spot types {sorted(bad_types)}")
    ts = pd.to_datetime(df.timestamp, format="ISO8601")
    ts = ts.dt.tz_localize(CAMPUS_TZ) if ts.dt.tz is None else ts
    rows = [
        {"ts": t.to_pydatetime(), "site_id": r.site_id, "spot_type": r.spot_type,
         "occupied": int(r.occupied),
         "capacity": int(r.capacity) if "capacity" in df and pd.notna(r.capacity) else None,
         "source": r.source if "source" in df and pd.notna(r.source) else "import"}
        for t, r in zip(ts, df.itertuples(index=False))
    ]
    return store.add_observations(rows)
