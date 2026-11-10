"""WhereUPark HTTP API consumed by the iOS/Android app."""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import model as model_mod
from . import service, store
from .config import CAMPUS_TZ, get_config
from .training import retrain

app = FastAPI(title="WhereUPark API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
                   allow_headers=["*"])

Permit = Literal["red", "yellow", "visitor"]
_model_lock = threading.Lock()
_model: model_mod.Forecaster | None = None


def current_model() -> model_mod.Forecaster | None:
    global _model
    with _model_lock:
        reg = model_mod.read_registry()
        if reg.get("current") and (_model is None or _model.version != reg["current"]):
            _model = model_mod.load_current()
        return _model


def require_admin(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("WHEREUPARK_ADMIN_KEY")
    if not expected:
        raise HTTPException(503, "Admin endpoints disabled: set WHEREUPARK_ADMIN_KEY")
    if x_api_key != expected:
        raise HTTPException(401, "Invalid API key")


def _site(site_id: str):
    try:
        return get_config().site(site_id)
    except KeyError:
        raise HTTPException(404, f"Unknown site: {site_id}")


def _parse_when(at: str | None) -> datetime:
    if not at:
        return datetime.now(timezone.utc)
    when = datetime.fromisoformat(at)
    return when.replace(tzinfo=CAMPUS_TZ) if when.tzinfo is None else when


# ---- public ----------------------------------------------------------------
@app.get("/health")
def health():
    m = current_model()
    return {"ok": True, "model_version": m.version if m else None}


@app.get("/meta")
def meta():
    cfg = get_config()
    return {"spot_types": cfg.spot_types, "permits": list(cfg.eligibility["permits"]),
            "timezone": str(CAMPUS_TZ)}


@app.get("/sites")
def list_sites(permit: Permit | None = None, ada: bool = False):
    cfg, now = get_config(), datetime.now(timezone.utc)
    return {"as_of": now.isoformat(),
            "sites": [service.site_status(cfg, s, now, permit, ada) for s in cfg.sites]}


@app.get("/sites/{site_id}")
def get_site(site_id: str, permit: Permit | None = None, ada: bool = False):
    return service.site_status(get_config(), _site(site_id), datetime.now(timezone.utc), permit, ada)


@app.get("/sites/{site_id}/forecast")
def get_forecast(site_id: str, hours: int = Query(12, ge=1, le=168),
                 step: int = Query(30, ge=15, le=120), start: str | None = None,
                 permit: Permit | None = None, ada: bool = False):
    if step % 15:
        raise HTTPException(422, "step must be a multiple of 15 minutes")
    return service.forecast_series(get_config(), current_model(), _site(site_id),
                                   _parse_when(start), hours, step, permit, ada)


@app.get("/recommendations")
def get_recommendations(permit: Permit, ada: bool = False, at: str | None = None):
    return service.recommendations(get_config(), current_model(), _parse_when(at), permit, ada)


@app.get("/model")
def model_info():
    reg = model_mod.read_registry()
    current = next((v for v in reg["versions"] if v["version"] == reg.get("current")), None)
    return {"current": current, "history": [
        {k: v[k] for k in ("version", "trained_at", "promoted")} for v in reg["versions"][-20:]]}


# ---- data feeds & admin ----------------------------------------------------
class Observation(BaseModel):
    ts: datetime
    site_id: str
    spot_type: Literal["red", "yellow", "visitor", "ada", "other"]
    occupied: int = Field(ge=0)
    capacity: int | None = Field(default=None, ge=0)
    source: Literal["parklio", "east_end_sensors", "manual_count", "import"] = "parklio"


@app.post("/observations", dependencies=[Depends(require_admin)])
def post_observations(rows: list[Observation]):
    for r in rows:
        _site(r.site_id)
        if r.ts.tzinfo is None:
            r.ts = r.ts.replace(tzinfo=CAMPUS_TZ)
    return {"stored": store.add_observations([r.model_dump() for r in rows])}


@app.post("/admin/retrain", dependencies=[Depends(require_admin)])
def post_retrain():
    return retrain()
