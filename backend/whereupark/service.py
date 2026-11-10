"""Business logic shared by the API: current status, forecasts, recommendations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from . import store
from .baseline import occupancy_by_type
from .config import Config, Site
from .model import Forecaster

LIVE_MAX_AGE = timedelta(minutes=15)


def _counts(site: Site, fractions: dict[str, float]) -> dict[str, dict]:
    out = {}
    for t, cap in site.counts.items():
        occ = int(round(fractions[t] * cap))
        out[t] = {"capacity": cap, "occupied": occ, "open": cap - occ}
    return out


def current_by_type(site: Site, now: datetime) -> tuple[dict[str, dict], str]:
    """Live readings where fresh; simulated baseline for anything else.

    Returns (by_type, source), where source is "live", "simulated" or "mixed".
    """
    simulated = _counts(site, occupancy_by_type(site, now))
    live = store.latest_observations(site.id, since=now - LIVE_MAX_AGE)
    sources = set()
    by_type = {}
    for t, sim in simulated.items():
        row = live[live.spot_type == t] if not live.empty else live
        if row is not None and not row.empty:
            r = row.iloc[-1]
            cap = int(r.capacity) if pd.notna(r.capacity) and r.capacity > 0 else sim["capacity"]
            occ = min(int(r.occupied), cap)
            by_type[t] = {"capacity": cap, "occupied": occ, "open": cap - occ, "source": "live"}
            sources.add("live")
        else:
            by_type[t] = {**sim, "source": "simulated"}
            sources.add("simulated")
    source = sources.pop() if len(sources) == 1 else "mixed"
    return by_type, source


def summarize(config: Config, site: Site, by_type: dict[str, dict], when: datetime,
              permit: str | None, ada: bool) -> dict:
    cap = sum(v["capacity"] for v in by_type.values())
    occ = sum(v["occupied"] for v in by_type.values())
    out = {"capacity": cap, "occupied": occ, "open": cap - occ,
           "percent_full": round(100 * occ / cap, 1) if cap else 0.0}
    if permit:
        eligible = [t for t in config.eligible_types(permit, when, ada) if t in by_type]
        e_cap = sum(by_type[t]["capacity"] for t in eligible)
        e_open = sum(by_type[t]["open"] for t in eligible)
        out.update({"eligible_types": eligible, "eligible_open": e_open,
                    "eligible_percent_full": round(100 * (1 - e_open / e_cap), 1) if e_cap else None})
    return out


def site_meta(site: Site) -> dict:
    return {"id": site.id, "name": site.name, "kind": site.kind, "levels": site.levels,
            "capacity": site.capacity, "counts": site.counts, "data_source": site.data_source,
            "location": site.location, "counts_are_placeholder": site.counts_are_placeholder}


def site_status(config: Config, site: Site, now: datetime, permit: str | None, ada: bool) -> dict:
    by_type, source = current_by_type(site, now)
    return {**site_meta(site), "as_of": now.isoformat(), "source": source, "by_type": by_type,
            "summary": summarize(config, site, by_type, now, permit, ada)}


def forecast_series(config: Config, model: Forecaster | None, site: Site, start: datetime,
                    hours: int, step_minutes: int, permit: str | None, ada: bool) -> dict:
    start = start.replace(second=0, microsecond=0)
    start -= timedelta(minutes=start.minute % step_minutes)
    times = [start + timedelta(minutes=step_minutes * i)
             for i in range(1, hours * 60 // step_minutes + 1)]
    if model is not None:
        points, basis = model.forecast(config, site.id, times), f"model:{model.version}"
    else:
        points = [{"ts": t.isoformat(), "by_type": _counts(site, occupancy_by_type(site, t))}
                  for t in times]
        basis = "baseline"
    for p, t in zip(points, times):
        p["summary"] = summarize(config, site, p["by_type"], t, permit, ada)
    return {"site_id": site.id, "basis": basis, "step_minutes": step_minutes, "points": points}


def recommendations(config: Config, model: Forecaster | None, when: datetime,
                    permit: str, ada: bool) -> dict:
    now = datetime.now(timezone.utc)
    use_current = abs((when - now).total_seconds()) <= 600
    results = []
    for site in config.sites:
        if use_current:
            by_type, source = current_by_type(site, when)
        elif model is not None:
            by_type, source = model.forecast(config, site.id, [when])[0]["by_type"], "forecast"
        else:
            by_type, source = _counts(site, occupancy_by_type(site, when)), "baseline"
        results.append({"site_id": site.id, "name": site.name, "source": source,
                        "summary": summarize(config, site, by_type, when, permit, ada)})
    results.sort(key=lambda r: r["summary"]["eligible_open"], reverse=True)
    return {"at": when.isoformat(), "permit": permit, "ada_placard": ada,
            "free_hours": config.is_free_hours(when), "sites": results}
