"""Load site configuration (config/sites.yaml) and derive spot counts and eligibility."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

CAMPUS_TZ = ZoneInfo("America/Chicago")
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(os.environ.get("WHEREUPARK_SITES", REPO_ROOT / "config" / "sites.yaml"))
SPOT_TYPE_ORDER = ["red", "yellow", "visitor", "ada", "other"]


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    kind: str
    levels: int
    capacity: int
    counts: dict[str, int]          # spot_type -> number of spaces (sums to capacity)
    data_source: str
    location: dict[str, float] = field(default_factory=dict)
    counts_are_placeholder: bool = True

    @property
    def spot_types(self) -> list[str]:
        return [t for t in SPOT_TYPE_ORDER if self.counts.get(t, 0) > 0]


def allocate_counts(capacity: int, mix: dict[str, float]) -> dict[str, int]:
    """Split `capacity` by `mix` fractions using largest-remainder rounding.

    If the fractions sum to less than 1, the remainder becomes "other".
    """
    mix = dict(mix)
    total = sum(mix.values())
    if total > 1.0 + 1e-9:
        raise ValueError(f"Spot mix sums to {total:.3f} (> 1.0): {mix}")
    if total < 1.0 - 1e-9:
        mix["other"] = mix.get("other", 0.0) + (1.0 - total)
    raw = {t: capacity * f for t, f in mix.items()}
    counts = {t: math.floor(v) for t, v in raw.items()}
    leftover = capacity - sum(counts.values())
    for t in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[:leftover]:
        counts[t] += 1
    return {t: counts[t] for t in SPOT_TYPE_ORDER if counts.get(t, 0) > 0}


@dataclass(frozen=True)
class Config:
    spot_types: dict[str, dict]
    sites: list[Site]
    eligibility: dict

    def site(self, site_id: str) -> Site:
        for s in self.sites:
            if s.id == site_id:
                return s
        raise KeyError(site_id)

    # ---- eligibility -------------------------------------------------------
    def is_free_hours(self, when: datetime) -> bool:
        """True all weekend (if configured) or inside the daily window (may wrap midnight)."""
        window = self.eligibility.get("free_hours")
        if not window:
            return False
        local = when.astimezone(CAMPUS_TZ)
        if local.weekday() >= 5 and window.get("weekends") == "all_day":
            return True
        start, end = (time(*(int(x) for x in window[k].split(":"))) for k in ("start", "end"))
        now = local.time()
        return start <= now < end if start <= end else (now >= start or now < end)

    def eligible_types(self, permit: str, when: datetime, ada_placard: bool = False) -> list[str]:
        rules = self.eligibility["permits"].get(permit)
        if rules is None:
            raise KeyError(f"Unknown permit type: {permit}")
        types = list(rules.get("always", []))
        if self.is_free_hours(when):
            for t in rules.get("during_free_hours", []):
                if t not in types:
                    types.append(t)
        if ada_placard:
            types += [t for t in self.eligibility.get("ada_placard_adds", []) if t not in types]
        return types


def load_config(path: Path | str = CONFIG_PATH) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    mixes = raw.get("mixes", {})
    sites = []
    for s in raw["sites"]:
        if "counts" in s:
            counts = {t: int(n) for t, n in s["counts"].items() if int(n) > 0}
            capacity = sum(counts.values())
            if "capacity" in s and int(s["capacity"]) != capacity:
                raise ValueError(
                    f"{s['id']}: explicit counts sum to {capacity}, capacity says {s['capacity']}"
                )
            placeholder = False
        else:
            mix = s["mix"]
            mix = mixes[mix] if isinstance(mix, str) else mix
            capacity = int(s["capacity"])
            counts = allocate_counts(capacity, mix)
            placeholder = True
        sites.append(
            Site(
                id=s["id"],
                name=s["name"],
                kind=s.get("kind", "garage"),
                levels=int(s.get("levels", 0)),
                capacity=capacity,
                counts=counts,
                data_source=s.get("data_source", "unknown"),
                location=s.get("location", {}),
                counts_are_placeholder=placeholder,
            )
        )
    return Config(spot_types=raw["spot_types"], sites=sites, eligibility=raw["eligibility"])


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()
