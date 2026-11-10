"""Forecasting model: predicts the occupied fraction per site x spot type x time.

Accuracy metric (charter acceptance criterion 5, target > 95%):
    accuracy = 1 - capacity-weighted mean absolute error of the occupied fraction
That is, the share of spaces whose state the forecast gets right on average.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .config import CAMPUS_TZ, REPO_ROOT, SPOT_TYPE_ORDER, Config

MODEL_DIR = Path(os.environ.get("WHEREUPARK_MODELS", REPO_ROOT / "backend" / "models"))
REGISTRY = MODEL_DIR / "registry.json"
FEATURES = ["site_id", "spot_type", "dow", "minute_of_day", "is_weekend"]


def make_features(df: pd.DataFrame, site_ids: list[str]) -> pd.DataFrame:
    """df needs columns ts (tz-aware), site_id, spot_type."""
    local = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(CAMPUS_TZ)
    return pd.DataFrame({
        "site_id": pd.Categorical(df["site_id"], categories=site_ids),
        "spot_type": pd.Categorical(df["spot_type"], categories=SPOT_TYPE_ORDER),
        "dow": local.dt.weekday.to_numpy(),
        "minute_of_day": (local.dt.hour * 60 + local.dt.minute).to_numpy(),
        "is_weekend": (local.dt.weekday >= 5).astype(int).to_numpy(),
    })


def accuracy(y_true, y_pred, capacity) -> float:
    w = np.asarray(capacity, dtype=float)
    return float(1 - np.sum(w * np.abs(np.asarray(y_true) - np.asarray(y_pred))) / np.sum(w))


@dataclass
class Forecaster:
    model: HistGradientBoostingRegressor
    site_ids: list[str]
    version: str
    trained_at: str
    metrics: dict

    @classmethod
    def fit(cls, train: pd.DataFrame, site_ids: list[str], sample_weight=None) -> "Forecaster":
        model = HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.08, max_leaf_nodes=63,
            categorical_features="from_dtype", random_state=0,
        )
        model.fit(make_features(train, site_ids), train["occupancy"], sample_weight=sample_weight)
        now = datetime.now(timezone.utc)
        return cls(model, site_ids, now.strftime("%Y%m%dT%H%M%SZ"), now.isoformat(), {})

    def predict_frame(self, df: pd.DataFrame) -> np.ndarray:
        return np.clip(self.model.predict(make_features(df, self.site_ids)), 0.0, 1.0)

    def evaluate(self, test: pd.DataFrame) -> dict:
        pred = self.predict_frame(test)
        out = {"accuracy": accuracy(test["occupancy"], pred, test["capacity"]),
               "rows": int(len(test)), "by_site": {}}
        for site_id, idx in test.groupby("site_id", observed=True).groups.items():
            sub = test.loc[idx]
            out["by_site"][site_id] = accuracy(sub["occupancy"], pred[test.index.get_indexer(idx)],
                                               sub["capacity"])
        return out

    def forecast(self, config: Config, site_id: str, times: list[datetime]) -> list[dict]:
        """Per-timestamp forecast with occupied/open counts per spot type."""
        site = config.site(site_id)
        grid = pd.DataFrame(
            [{"ts": t, "site_id": site_id, "spot_type": st} for t in times for st in site.spot_types]
        )
        grid["occupancy"] = self.predict_frame(grid)
        out = []
        for t, g in grid.groupby("ts", sort=True):
            by_type = {}
            for _, r in g.iterrows():
                cap = site.counts[r.spot_type]
                occ = int(round(r.occupancy * cap))
                by_type[r.spot_type] = {"capacity": cap, "occupied": occ, "open": cap - occ}
            out.append({"ts": t.isoformat(), "by_type": by_type})
        return out

    # ---- persistence / registry --------------------------------------------
    def save(self, promote: bool) -> Path:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        path = MODEL_DIR / f"forecaster_{self.version}.joblib"
        joblib.dump(self, path)
        reg = read_registry()
        reg["versions"].append({"version": self.version, "trained_at": self.trained_at,
                                "metrics": self.metrics, "promoted": promote})
        if promote:
            reg["current"] = self.version
        REGISTRY.write_text(json.dumps(reg, indent=2))
        return path


def read_registry() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())
    return {"current": None, "versions": []}


def load_current() -> Forecaster | None:
    version = read_registry().get("current")
    if not version:
        return None
    return joblib.load(MODEL_DIR / f"forecaster_{version}.joblib")
