"""Initial training and periodic retraining.

Data blend:
  * Synthetic baseline (baseline.py) gives every site a starting pattern.
  * Real observations (store.py) are weighted REAL_WEIGHT times higher.
  * Per site, synthetic data fades out linearly as real history accumulates and
    disappears once that site has PHASE_OUT_WEEKS of real data.

Promotion gate: a retrained candidate replaces the current model only if its accuracy
on the holdout window (the most recent real data when there is enough, otherwise the
most recent synthetic week) is no worse than the current model's on the same window.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from . import store
from .baseline import generate_history
from .config import Config, get_config
from .model import Forecaster, load_current

log = logging.getLogger(__name__)

SYNTH_WEEKS = int(os.environ.get("WHEREUPARK_SYNTH_WEEKS", 12))
PHASE_OUT_WEEKS = float(os.environ.get("WHEREUPARK_PHASE_OUT_WEEKS", 8))
REAL_WEIGHT = float(os.environ.get("WHEREUPARK_REAL_WEIGHT", 3))
HOLDOUT_DAYS = 7
MIN_REAL_DAYS_FOR_REAL_HOLDOUT = 14
ACCURACY_TARGET = 0.95
PROMOTION_TOLERANCE = 0.002


def real_dataset(config: Config) -> pd.DataFrame:
    obs = store.load_observations()
    if obs.empty:
        return pd.DataFrame(columns=["ts", "site_id", "spot_type", "occupancy", "capacity"])
    known = {s.id for s in config.sites}
    obs = obs[obs.site_id.isin(known)].copy()
    obs["capacity"] = [
        c if pd.notna(c) else config.site(s).counts.get(t)
        for c, s, t in zip(obs.capacity, obs.site_id, obs.spot_type)
    ]
    obs = obs.dropna(subset=["capacity"])
    obs = obs[obs.capacity > 0]
    obs["occupancy"] = (obs.occupied / obs.capacity).clip(0, 1)
    obs["ts"] = obs.ts.dt.floor("15min")
    return (obs.groupby(["ts", "site_id", "spot_type"], as_index=False)
               .agg(occupancy=("occupancy", "mean"), capacity=("capacity", "max")))


def synthetic_dataset(config: Config, end: datetime) -> pd.DataFrame:
    end = end.replace(minute=0, second=0, microsecond=0)
    df = pd.DataFrame(generate_history(config.sites, end - timedelta(weeks=SYNTH_WEEKS), end))
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def build_dataset(config: Config, now: datetime) -> tuple[pd.DataFrame, dict]:
    real = real_dataset(config)
    synth = synthetic_dataset(config, now)
    real_days = (real.groupby("site_id").ts.apply(lambda s: s.dt.date.nunique()).to_dict()
                 if not real.empty else {})
    synth_w = {s.id: max(0.0, 1 - real_days.get(s.id, 0) / 7 / PHASE_OUT_WEEKS)
               for s in config.sites}
    synth["weight"] = synth.site_id.map(synth_w)
    synth = synth[synth.weight > 0]
    synth["origin"] = "synthetic"
    real = real.assign(weight=REAL_WEIGHT, origin="real")
    data = pd.concat([synth, real], ignore_index=True)
    info = {"real_days_by_site": real_days, "synthetic_weight_by_site": synth_w,
            "rows_synthetic": int(len(synth)), "rows_real": int(len(real))}
    return data, info


def split_holdout(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    real = data[data.origin == "real"]
    if not real.empty and real.ts.dt.date.nunique() >= MIN_REAL_DAYS_FOR_REAL_HOLDOUT:
        cutoff, basis = real.ts.max() - timedelta(days=HOLDOUT_DAYS), "real"
        test_mask = (data.origin == "real") & (data.ts > cutoff)
    else:
        cutoff, basis = data.ts.max() - timedelta(days=HOLDOUT_DAYS), "synthetic"
        test_mask = data.ts > cutoff
    return data[~test_mask], data[test_mask].reset_index(drop=True), basis


def retrain(config: Config | None = None, now: datetime | None = None) -> dict:
    config = config or get_config()
    now = now or datetime.now(timezone.utc)
    site_ids = [s.id for s in config.sites]
    data, info = build_dataset(config, now)
    train, test, basis = split_holdout(data)

    candidate = Forecaster.fit(train, site_ids, sample_weight=train.weight)
    cand_metrics = candidate.evaluate(test)
    current = load_current()
    cur_metrics = current.evaluate(test) if current and current.site_ids == site_ids else None

    promote = cur_metrics is None or (
        cand_metrics["accuracy"] >= cur_metrics["accuracy"] - PROMOTION_TOLERANCE)
    if promote:
        # Refit on all data (holdout included) so the deployed model sees the latest week.
        final = Forecaster.fit(data, site_ids, sample_weight=data.weight)
        final.version, final.trained_at = candidate.version, candidate.trained_at
    else:
        final = candidate
    final.metrics = {
        "holdout_basis": basis, "holdout": cand_metrics,
        "previous_model_on_holdout": cur_metrics,
        "meets_target": cand_metrics["accuracy"] >= ACCURACY_TARGET,
        "target": ACCURACY_TARGET, **info,
    }
    final.save(promote=promote)
    summary = {"version": final.version, "promoted": promote, "holdout_basis": basis,
               "accuracy": round(cand_metrics["accuracy"], 4),
               "previous_accuracy": round(cur_metrics["accuracy"], 4) if cur_metrics else None,
               "rows_real": info["rows_real"], "rows_synthetic": info["rows_synthetic"]}
    log.info("Retrain complete: %s", summary)
    return summary
