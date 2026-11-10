"""Placeholder occupancy profile: the starting-case assumptions, written as a simulator.

These assumptions give the forecasting model its initial training data and supply the
"current" reading for any site that has no live camera or sensor feed yet. Replace or
retire them as real usage data arrives (see training.py for how they are phased out).

Assumptions (from the project team, Nov 2026):
  * Mon-Fri 07:00-17:00: every site is 90-98% full. Most of the empty spaces are
    red- and yellow-permit spaces.
  * After 17:00 on weekdays, total occupancy falls gradually to 40% by 19:00. At that
    point visitor spaces are the most open spot type.
Gaps filled by the engineering team (adjust as needed):
  * Overnight (after 19:00 until the morning ramp) and all weekend: hold near 40%.
  * Morning ramp: rise from 40% at 05:30 to the daytime level by 07:00.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

import numpy as np

from .config import CAMPUS_TZ, Site

NIGHT_LEVEL = 0.40
DAY_MIN, DAY_MAX = 0.90, 0.98
MORNING_RAMP = (5.5, 7.0)     # hours
EVENING_RAMP = (17.0, 19.0)

# Relative tendency of each spot type to be the one left empty.
# Daytime: empties concentrate in red and yellow. Evening/night: in visitor.
DAY_VACANCY_WEIGHT = {"red": 3.0, "yellow": 1.0, "visitor": 0.15, "ada": 1.0, "other": 1.0}
NIGHT_VACANCY_WEIGHT = {"red": 0.6, "yellow": 0.6, "visitor": 4.0, "ada": 1.0, "other": 1.0}
MAX_VACANCY = 0.97            # no spot type ever reads as completely empty


def _seeded_uniform(*key) -> float:
    digest = hashlib.blake2b("|".join(map(str, key)).encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") / 2**64


def _smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _day_level(site_id: str, d: date, hour: float) -> float:
    """Daytime occupancy: a per-site, per-day base within 90-98% plus a gentle midday peak."""
    base = DAY_MIN + 0.75 * (DAY_MAX - DAY_MIN) * _seeded_uniform("day", site_id, d)
    peak = 0.02 * np.sin(np.pi * (hour - 7.0) / 10.0)   # max around 12:00
    wiggle = 0.006 * (_seeded_uniform("wig", site_id, d, int(hour * 4)) - 0.5)
    return float(np.clip(base + peak + wiggle, DAY_MIN, DAY_MAX))


def total_occupancy(site_id: str, when: datetime) -> tuple[float, float]:
    """Return (occupied fraction, night blend 0..1) for a site at a local time."""
    local = when.astimezone(CAMPUS_TZ)
    d, h = local.date(), local.hour + local.minute / 60
    night_noise = 0.015 * (_seeded_uniform("night", site_id, d, int(h * 4)) - 0.5)
    night = NIGHT_LEVEL + night_noise

    if local.weekday() >= 5:                       # weekend
        return night, 1.0
    if h < MORNING_RAMP[0] or h >= EVENING_RAMP[1]:
        return night, 1.0
    if h < MORNING_RAMP[1]:
        p = _smoothstep((h - MORNING_RAMP[0]) / (MORNING_RAMP[1] - MORNING_RAMP[0]))
        return night + p * (_day_level(site_id, d, 7.0) - night), 1.0 - p
    if h < EVENING_RAMP[0]:
        return _day_level(site_id, d, h), 0.0
    p = _smoothstep((h - EVENING_RAMP[0]) / (EVENING_RAMP[1] - EVENING_RAMP[0]))
    return _day_level(site_id, d, 17.0) + p * (night - _day_level(site_id, d, 17.0)), p


def allocate_vacancies(counts: dict[str, int], empty: float, night_blend: float) -> dict[str, float]:
    """Distribute `empty` spaces across spot types by weight, respecting per-type caps."""
    weights = {
        t: (1 - night_blend) * DAY_VACANCY_WEIGHT.get(t, 1.0)
        + night_blend * NIGHT_VACANCY_WEIGHT.get(t, 1.0)
        for t in counts
    }
    caps = {t: MAX_VACANCY * n for t, n in counts.items()}
    vacant = {t: 0.0 for t in counts}
    remaining = min(empty, sum(caps.values()))
    active = {t for t in counts if caps[t] > 0}
    while remaining > 1e-9 and active:
        denom = sum(counts[t] * weights[t] for t in active)
        spill = 0.0
        for t in list(active):
            share = remaining * counts[t] * weights[t] / denom
            room = caps[t] - vacant[t]
            if share >= room:
                vacant[t] = caps[t]
                spill += share - room
                active.discard(t)
            else:
                vacant[t] += share
        remaining = spill
    return vacant


def occupancy_by_type(site: Site, when: datetime) -> dict[str, float]:
    """Occupied fraction (0..1) for each spot type at `site` at time `when`."""
    occ, blend = total_occupancy(site.id, when)
    vacant = allocate_vacancies(site.counts, site.capacity * (1 - occ), blend)
    return {t: 1.0 - vacant[t] / n for t, n in site.counts.items()}


def generate_history(sites: list[Site], start: datetime, end: datetime,
                     step_minutes: int = 15) -> list[dict]:
    """Synthetic observations (one row per site x spot type x timestamp)."""
    rows = []
    t = start
    step = timedelta(minutes=step_minutes)
    while t < end:
        for site in sites:
            for spot_type, frac in occupancy_by_type(site, t).items():
                rows.append({"ts": t, "site_id": site.id, "spot_type": spot_type,
                             "occupancy": frac, "capacity": site.counts[spot_type]})
        t += step
    return rows
