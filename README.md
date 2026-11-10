# WhereUPark

Real-time and forecast parking availability for the WashU Danforth campus: Simon Lot,
Snow Way Garage, DUC Garage, Millbrook Garage and East End Garage. This repo covers charter
deliverables 4 (forecasting model) and 5 (iOS & Android app, plus the backend data pipeline).

> **Status: placeholder data.** Spot counts are charter estimates and occupancy comes from a
> rule-based baseline until the site audit, camera install and East End integration are done.
> Every screen in the app labels the data "Simulated" until live feeds arrive.

```
config/sites.yaml          ← site capacities, spot-type mix, permit rules (edit this first)
backend/whereupark/        ← Python: baseline simulator, forecasting model, retraining, API
mobile/                    ← Expo / React Native app (one codebase → iOS + Android)
data_templates/            ← CSV templates for the real counts and usage figures
docs/screenshots/          ← app screenshots
```

## Placeholder assumptions

| Site | Spaces | Red | Yellow | Visitor | ADA | Unclassified |
|---|---|---|---|---|---|---|
| Simon Lot | 200 | 5% (10) | 90% (180) | — | 5% (10) | — |
| Snow Way Garage | 400 | 5% (20) | 65% (260) | 25% (100) | 5% (20) | — |
| DUC Garage | 400 | 5% (20) | 65% (260) | 25% (100) | 5% (20) | — |
| Millbrook Garage | 500 | 5% (25) | 65% (325) | 25% (125) | 5% (25) | — |
| East End Garage | ~1,000* | 5% (50) | 65% (650) | 25% (250) | from sensors | 5% (50) |

\*East End isn't in the charter cost table. 1,000 = the charter's ~2,300 garage total minus the other three garages.

**Occupancy baseline** (`backend/whereupark/baseline.py`):
- Mon–Fri 7 AM–5 PM: 90–98% full. Most empty spaces are red and yellow.
- 5 PM–7 PM: falls gradually to 40% total. Visitor spaces become the most open type.
- Overnight and weekends: held near 40% (team assumption, not yet specified).
- Morning ramp 5:30–7 AM from 40% up to the daytime level (team assumption).

**Permit rules** (`eligibility` in `sites.yaml`): red permit → red spaces only; yellow permit →
yellow spaces only; visitor → visitor spaces any time, plus yellow spaces 5 PM–7 AM on weekdays
and all day on weekends. Same rules year-round (school year and summer). An ADA placard adds ADA spaces.

## Run it

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m whereupark sites     # check the configured spot counts
python -m whereupark train     # initial training (~5 s)
python -m whereupark serve     # API on http://localhost:8000  (docs at /docs)
python -m pytest -q tests      # 28 tests
```

### Mobile app
```bash
cd mobile
npm install
npx expo start                 # press i (iOS simulator), a (Android emulator), or scan the QR code with Expo Go
```
Point the app at your backend with `EXPO_PUBLIC_API_URL`. Use `http://10.0.2.2:8000` on the
Android emulator, or your computer's LAN IP on a physical phone. Store builds go through EAS:
`npx eas-cli@latest build --platform all`. Bundle ID / package: `edu.wustl.whereupark`.

## Dropping in real data

**1. Real spot counts (from the site audit).** Give a site explicit `counts:` in
`config/sites.yaml`. These override the percentages and the site loses its "placeholder" flag:
```yaml
  - id: snow-way
    counts: { red: 22, yellow: 251, visitor: 108, ada: 19 }
```
`data_templates/site_counts_template.csv` is a per-level worksheet for collecting them.
Then run `python -m whereupark train`.

**2. Usage figures.** Fill in a CSV like `data_templates/usage_template.csv`
(`timestamp,site_id,spot_type,occupied[,capacity][,source]`, times in campus local time), then:
```bash
python -m whereupark ingest usage.csv --retrain
```

**3. Live feeds** (Parklio cameras, East End sensors) `POST /observations` with header
`X-API-Key: $WHEREUPARK_ADMIN_KEY`. A reading less than 15 minutes old replaces the simulated
value for that spot type, and the app badge changes to "Live".

## Forecasting model & retraining

- Gradient-boosted trees (`HistGradientBoostingRegressor`) predict the occupied fraction per
  site × spot type from day-of-week and time of day.
- **Accuracy** = 1 − capacity-weighted mean absolute error, the metric behind charter
  acceptance criterion 5 (> 95%).
- **Retraining** blends synthetic baseline data with real observations (real weighted 3×).
  Each site's synthetic data fades out linearly and is gone once that site has 8 weeks of real data.
- **Promotion gate:** a retrained model goes live only if it scores at least as well as the
  current model on the most recent 7 days of real data. If there are fewer than 14 days of real
  data, it uses synthetic data instead. Every version is kept in `backend/models/registry.json`.
- **Schedule:** `python -m whereupark schedule` retrains every Sunday at 3 AM campus time
  (`WHEREUPARK_RETRAIN_CRON` to change). Retraining can also be triggered with `POST /admin/retrain`.

Today's 99% accuracy only measures how well the model reproduces the placeholder rules. It
says nothing about real-world accuracy until it's validated against live data.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/sites?permit=&ada=` | All sites, current status, open spaces for the user's permit |
| GET | `/sites/{id}` | One site, by spot type |
| GET | `/sites/{id}/forecast?hours=12&step=30` | Forecast series |
| GET | `/recommendations?permit=&at=` | Sites ranked by open eligible spaces at a time |
| GET | `/model` | Current model version and metrics |
| POST | `/observations` | Ingest live readings (admin key) |
| POST | `/admin/retrain` | Retrain now (admin key) |

## Not yet included
Academic/event calendar features (charter 4b), EV and reserved spot types, the East End sensor
adapter and the Parklio API adapter (waiting on access and data-sharing agreements), auth for a
production deployment, and map view.
