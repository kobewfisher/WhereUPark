"""Tests that pin the placeholder assumptions and the train/serve pipeline."""
from datetime import datetime, timedelta

import pytest

from whereupark.baseline import occupancy_by_type
from whereupark.config import CAMPUS_TZ, allocate_counts, load_config, CONFIG_PATH

CFG = load_config(CONFIG_PATH)
WED = datetime(2026, 11, 11, tzinfo=CAMPUS_TZ)   # a Wednesday
SAT = datetime(2026, 11, 14, tzinfo=CAMPUS_TZ)


def at(day, h, m=0):
    return day.replace(hour=h, minute=m)


def totals(site, when):
    occ = occupancy_by_type(site, when)
    empty = {t: (1 - occ[t]) * n for t, n in site.counts.items()}
    return 1 - sum(empty.values()) / site.capacity, empty


# ---- spot structure ---------------------------------------------------------
def test_counts_sum_to_capacity():
    for s in CFG.sites:
        assert sum(s.counts.values()) == s.capacity


def test_garage_mix():
    for sid in ("snow-way", "duc", "millbrook"):
        s = CFG.site(sid)
        assert s.counts == allocate_counts(s.capacity, {"red": .05, "yellow": .65, "visitor": .25, "ada": .05})
    assert CFG.site("snow-way").counts == {"red": 20, "yellow": 260, "visitor": 100, "ada": 20}


def test_east_end_has_no_ada_placeholder():
    ee = CFG.site("east-end")
    assert "ada" not in ee.counts
    assert ee.counts["red"] == 50 and ee.counts["yellow"] == 650 and ee.counts["visitor"] == 250


def test_simon_lot_mix():
    assert CFG.site("simon-lot").counts == {"red": 10, "yellow": 180, "ada": 10}


# ---- occupancy assumptions --------------------------------------------------
@pytest.mark.parametrize("site", CFG.sites, ids=lambda s: s.id)
def test_weekday_daytime_90_to_98(site):
    for d in range(5):
        for h in range(7, 17):
            for m in (0, 30):
                total, _ = totals(site, at(WED - timedelta(days=2) + timedelta(days=d), h, m))
                assert 0.895 <= total <= 0.985, (site.id, d, h, m, total)


@pytest.mark.parametrize("site", CFG.sites, ids=lambda s: s.id)
def test_daytime_empties_mostly_red_and_yellow(site):
    _, empty = totals(site, at(WED, 11))
    assert (empty.get("red", 0) + empty.get("yellow", 0)) / sum(empty.values()) > 0.8


@pytest.mark.parametrize("site", CFG.sites, ids=lambda s: s.id)
def test_evening_decline_to_40(site):
    seq = [totals(site, at(WED, 17, 0))[0], totals(site, at(WED, 17, 30))[0],
           totals(site, at(WED, 18, 0))[0], totals(site, at(WED, 18, 30))[0]]
    assert all(a > b for a, b in zip(seq, seq[1:])), seq   # gradual, monotonic
    assert abs(totals(site, at(WED, 19))[0] - 0.40) < 0.02


@pytest.mark.parametrize("sid", ["snow-way", "duc", "millbrook", "east-end"])
def test_evening_visitor_most_open(sid):
    site = CFG.site(sid)
    occ = occupancy_by_type(site, at(WED, 19, 30))
    assert min(occ, key=occ.get) == "visitor"


def test_weekend_low():
    for s in CFG.sites:
        assert abs(totals(s, at(SAT, 12))[0] - 0.40) < 0.02


# ---- eligibility ------------------------------------------------------------
def test_permits_only_their_own_type():
    for when in (at(WED, 12), at(WED, 18), at(WED, 3), at(SAT, 12)):
        assert CFG.eligible_types("red", when) == ["red"]
        assert CFG.eligible_types("yellow", when) == ["yellow"]


@pytest.mark.parametrize("h,m,yellow_ok", [
    (6, 59, True), (7, 0, False), (12, 0, False), (16, 59, False),
    (17, 0, True), (23, 30, True), (0, 0, True), (3, 0, True)])
def test_visitor_yellow_weekdays_5pm_to_7am(h, m, yellow_ok):
    types = CFG.eligible_types("visitor", at(WED, h, m))
    assert types[0] == "visitor" and ("yellow" in types) == yellow_ok, (h, m, types)
    assert "red" not in types


@pytest.mark.parametrize("day", [SAT, SAT + timedelta(days=1)], ids=["sat", "sun"])
@pytest.mark.parametrize("h", [0, 7, 12, 16, 20])
def test_visitor_yellow_all_weekend(day, h):
    types = CFG.eligible_types("visitor", at(day, h))
    assert "yellow" in types and "red" not in types


def test_rules_hold_in_summer():
    july_wed, july_sat = datetime(2027, 7, 14, tzinfo=CAMPUS_TZ), datetime(2027, 7, 17, tzinfo=CAMPUS_TZ)
    assert CFG.eligible_types("visitor", at(july_wed, 10)) == ["visitor"]
    assert "yellow" in CFG.eligible_types("visitor", at(july_wed, 18))
    assert "yellow" in CFG.eligible_types("visitor", at(july_sat, 10))
    assert CFG.eligible_types("visitor", at(july_sat, 10)).count("red") == 0


def test_ada_placard_adds_ada():
    assert CFG.eligible_types("yellow", at(WED, 12), ada_placard=True) == ["yellow", "ada"]


# ---- pipeline: ingest real data, retrain, serve ------------------------------
@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    import whereupark.model as m
    import whereupark.store as st
    import whereupark.training as tr
    monkeypatch.setattr(st, "DB_PATH", tmp_path / "db.sqlite3")
    monkeypatch.setattr(m, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(m, "REGISTRY", tmp_path / "models" / "registry.json")
    monkeypatch.setattr(tr, "SYNTH_WEEKS", 3)
    yield tmp_path


def test_retrain_and_phase_out(isolated, tmp_path):
    from whereupark import store
    from whereupark.training import retrain
    first = retrain(CFG)
    assert first["promoted"] and first["accuracy"] > 0.95

    # 15 days of "real" Snow Way data that is 10 points emptier than the baseline.
    site, rows = CFG.site("snow-way"), []
    start = datetime(2026, 10, 20, tzinfo=CAMPUS_TZ)
    for i in range(15 * 24 * 4):
        t = start + timedelta(minutes=15 * i)
        for st, frac in occupancy_by_type(site, t).items():
            n = site.counts[st]
            rows.append({"ts": t, "site_id": site.id, "spot_type": st,
                         "occupied": round(max(0, frac - 0.10) * n), "source": "manual_count"})
    store.add_observations(rows)
    second = retrain(CFG, now=datetime(2026, 11, 4, tzinfo=CAMPUS_TZ))
    assert second["holdout_basis"] == "real"
    assert second["rows_real"] > 0
    import whereupark.model as m
    reg = m.read_registry()
    info = reg["versions"][-1]["metrics"]
    assert info["synthetic_weight_by_site"]["snow-way"] < 1.0
    assert info["synthetic_weight_by_site"]["duc"] == 1.0


def test_api_endpoints(isolated, monkeypatch):
    from fastapi.testclient import TestClient
    from whereupark.api import app
    from whereupark.training import retrain
    retrain(CFG)
    monkeypatch.setenv("WHEREUPARK_ADMIN_KEY", "k")
    c = TestClient(app)
    sites = c.get("/sites", params={"permit": "yellow"}).json()["sites"]
    assert {s["id"] for s in sites} == {s.id for s in CFG.sites}
    assert all(s["source"] == "simulated" for s in sites)

    fc = c.get("/sites/duc/forecast", params={"hours": 6, "step": 30}).json()
    assert fc["basis"].startswith("model:") and len(fc["points"]) == 12

    rec = c.get("/recommendations", params={"permit": "visitor",
                                           "at": "2026-11-11T18:30:00"}).json()
    assert rec["free_hours"] is True and "yellow" in rec["sites"][0]["summary"]["eligible_types"]

    assert c.post("/observations", json=[]).status_code == 401
    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()
    r = c.post("/observations", headers={"X-API-Key": "k"}, json=[
        {"ts": now, "site_id": "duc", "spot_type": t, "occupied": 1, "source": "parklio"}
        for t in CFG.site("duc").counts])
    assert r.json() == {"stored": 4}
    duc = c.get("/sites/duc").json()
    assert duc["source"] == "live" and duc["summary"]["occupied"] == 4


def test_live_reading_freshness_across_timezones(isolated):
    """A reading sent in Chicago local time must still count as fresh."""
    from datetime import timezone
    from whereupark import store
    from whereupark.service import current_by_type
    now = datetime.now(timezone.utc)
    store.add_observations([{"ts": (now - timedelta(minutes=5)).astimezone(CAMPUS_TZ),
                             "site_id": "simon-lot", "spot_type": "yellow", "occupied": 7}])
    store.add_observations([{"ts": now - timedelta(hours=2), "site_id": "simon-lot",
                             "spot_type": "red", "occupied": 1}])
    by_type, source = current_by_type(CFG.site("simon-lot"), now)
    assert by_type["yellow"] == {"capacity": 180, "occupied": 7, "open": 173, "source": "live"}
    assert by_type["red"]["source"] == "simulated"     # 2 h old reading is stale
    assert source == "mixed"
