# EV Infra Map India backend

FastAPI proxy for the India EV Charging Station API. It caches successful
upstream pages and the state directory for one hour, matching the upstream
cache period, and limits this backend process to 90 uncached requests per
15 minutes to leave headroom under the upstream's 100-request limit.

## Run locally

From the `backend/` directory, install dependencies and start the development server:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The health endpoint is available at `http://127.0.0.1:8000/health`. CORS permits the local frontend origin `http://localhost:5173`.

## Charger API

- `GET /api/v1/chargers?state=Karnataka&district=Pune&page=1&limit=100`
- `GET /api/v1/states` returns the upstream state/UT directory for the map filter.
- `GET /api/v1/districts?state=Karnataka` returns district station counts from the upstream city directory.
- `POST /api/v1/analytics/gap-assessment` calculates a reproducible district station-scarcity proxy.
- `GET /api/v1/analytics/summary` returns validated snapshot counts, state/connector/operator aggregates, and analytics calculated from one filtered station page.
- `POST /api/v1/requirements` estimates state-level station need from user-entered EV population and planning assumptions.
- `POST /api/v1/optimize` ranks illustrative district opportunity packages under a budget limit.
- `GET /api/v1/trip/corridors` lists representative corridors for the trip simulation.
- `POST /api/v1/trip/plan` estimates journey energy and nearby sampled station stops.

`limit` is restricted to 1-100. Each charger response reports page records
loaded separately from `total_available`; it does not download the complete
directory automatically. The upstream BEE dataset is a snapshot dated
26 October 2025, not a real-time availability feed. Upstream errors, including
rate limits and invalid state/district filters, are returned as HTTP errors
with a useful detail message.

## Decision dashboard and gap assessment

The decision dashboard consumes `/api/v1/analytics/summary`. That endpoint
combines `/v1/meta`, `/v1/states`, `/v1/connectors`, `/v1/operators`, and one
filtered `/v1/stations` page. Optional state, district, and vehicle class
filters are sent to the upstream station API. Its 2W and 3W classes are exposed
as separate UI choices, but both map to the upstream combined
`two_three_wheeler` filter. The endpoint caches successful upstream responses
for one hour, limits refresh requests to once per minute, and still enforces
the process-wide 90-request/15-minute cap.

National station, state, connector, and operator summaries are source-provided
and remain nationwide, even when station filters are active. Charger-type,
power, and coordinate visualizations are calculated by the backend from only
the returned page of at most 100 valid-coordinate station records. The response
reports those scopes separately from the total matching query count and the
full snapshot count; the loaded page is never presented as a national total.
This dated 26 October 2025 directory snapshot is not a live availability feed.

The gap endpoint uses the state's cached `/v1/cities` directory, aggregated by
district, plus at most the first 100 valid-coordinate station rows for the
selected district. The score is:

```text
100 x weighted mean of:
  relative station scarcity = 1 - district rows / highest district rows in state
  target shortfall = max(0, (illustrative target - district rows) / target)
  vehicle compatibility gap = 1 - compatible known rows / known rows (when selected and available)
```

Weights are validated, omitted factors are removed, and active weights are
renormalized to 100%. The default illustrative target is 25 directory rows per
district; it is not an official standard. Priority labels are High (70+),
Medium (40-69), and Monitor (below 40). This is a station-count proxy, not a
validated national gap model; it does not include EV registrations, population,
road access, usage, charger uptime, or live availability.

## Charger requirement estimator

`POST /api/v1/requirements` requires user-provided current/projected EV counts,
planning horizon, target EVs per station, target population coverage, vehicle
class, AC allocation, and editable AC/DC costs. Existing state infrastructure
comes from cached upstream state station rows. Its unit is **station**, not
charger, gun, or connector. The target coverage percentage is applied to the
projected EV count before the ratio calculation:

```text
covered projected EVs = ceil(projected EVs x target coverage / 100)
required stations = ceil(covered projected EVs / target EVs per station)
additional stations = max(0, required stations - existing station rows)
```

Whole additional stations are allocated to AC/DC using the selected mix and
rounded to the nearest AC station; DC receives the remainder. This is a
planning estimate, not an official EV projection or infrastructure standard.
The current-capacity percentage is a capped station-count ratio against the
user-entered current population, not geographic or service coverage.
State station totals are not broken down by vehicle class in the source, so a
selected class is a planning scenario while the existing total remains
all-class.

## Budget optimizer

`POST /api/v1/optimize` reads the cached `/v1/cities?state=...` directory and
creates one hypothetical opportunity per district. These are district-level
areas, not verified host sites. A deterministic greedy procedure ranks them
by weighted relative benefit per estimated station-package cost. Coverage is
the one-area-per-package contribution; relative gap reduction compares a
district's station rows with the highest-count district in the state; equity
uses inverse station rows. The selected AC/DC package type follows the
requested mix, and recommendations stop before exceeding the INR budget. This
is a transparent heuristic, not a mathematically optimal solution. No demand,
grid readiness, land access, host-site, or site-specific cost dataset is
integrated.

## Trip planner

No road-routing provider is configured. `GET /api/v1/trip/corridors` returns a
small set of illustrative polylines; their estimated distance is the geometry
length multiplied by a corridor-specific road-distance factor. These are not
turn-by-turn roads or road distances. `POST /api/v1/trip/plan` calculates
energy from the selected corridor estimate and user-provided consumption,
battery capacity, starting SoC, and reserve.

```text
journey energy = route distance x consumption / 100
available battery energy = capacity x starting SoC / 100
reserve energy = capacity x reserve percentage / 100
```

For charging candidates, the service requests only page 1 (up to 100 valid
coordinate station records) for each state on the selected corridor, using the
existing one-hour upstream cache. It projects records onto the corridor,
filters by a configurable straight-line radius, and bins sampled records into
50 km segments. A missing sample in a segment is not proof there are no
stations because the pages are capped. Suggested stops must be reachable while
maintaining the reserve, and the estimate assumes a charge back to 100% at each
stop. Compatibility, station access, live availability, charging time, exact
road detour, elevation, traffic, and vehicle-specific consumption are not
verified. An infeasible plan does not display a fabricated arrival SoC.

Run all backend calculation and request-validation tests from `backend/`:

```bash
python -m unittest discover -s tests -v
```

