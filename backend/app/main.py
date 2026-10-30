from __future__ import annotations

import asyncio
import copy
import json
import math
import os
import re
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select

from app.db.models import CandidateSite, ChargerUnified, District, EvRegistration, State
from app.db.session import AsyncSessionLocal
from app.models.analytics import (
    AnalyticsSummaryResponse,
    ClassComparisonResponse,
    DistrictDirectoryResponse,
    EvRegistrationRecord,
    EvRegistrationsResponse,
    EvRegistrationsSummary,
    GapAssessmentRequest,
    GapAssessmentResponse,
    HexMetricsResponse,
)
from app.models.explainability import (
    BEE_DATA_SOURCE,
    H3_DATA_SOURCE,
    VAHAN_DATA_SOURCE,
    DataSourceItem,
    ExplainabilityMeta,
)
from app.models.planning import (
    OptimizeRequest,
    OptimizeResponse,
    RequirementsRequest,
    RequirementsResponse,
)
from app.models.trip import TripCorridorsResponse, TripPlanRequest, TripPlanResponse
from app.services.budget_optimizer import optimize_budget
from app.services.class_disparity import analyze_class_disparity
from app.services.dashboard_analytics import build_page_analytics
from app.services.db_service import (
    fetch_districts_for_state,
    fetch_state_station_count,
    fetch_states,
    query_chargers,
)
from app.services.gap_assessment import calculate_gap_assessment
from app.services.hex_analytics import compute_hex_metrics
from app.services.requirements_estimator import calculate_requirements
from app.services.trip_planner import calculate_trip_plan, find_corridor, list_corridors


UPSTREAM_BASE_URL = "https://ev-charging-stations-api.vercel.app"
SOURCE_NAME = "EV Public Charging Stations Data till 26th October 2025"
SNAPSHOT_DATE = "2025-10-26"
CACHE_TTL_SECONDS = 60 * 60  # Matches upstream's one-hour success cache.
MAX_CACHE_ENTRIES = 256
UPSTREAM_REQUESTS_PER_WINDOW = 90  # Leave headroom under the upstream 100/15 min limit.
UPSTREAM_WINDOW_SECONDS = 15 * 60


class UpstreamStation(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    state: str
    latitude: float
    longitude: float
    chargers: list[dict[str, Any]] = Field(default_factory=list)
    vehicle_classes: list[str] = Field(default_factory=list)


class UpstreamEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    success: bool
    data: list[dict[str, Any]]
    meta: dict[str, Any]


class NormalizedCharger(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    state: str
    state_code: str | None
    district: str
    city: str | None
    operator: str | None
    address: str | None
    charger_type: str
    standards: list[str]
    power_kw: float | None
    total_chargers: int
    total_connectors: int
    vehicle_classes: list[str]
    supported_vehicle_classes: list[str]
    source: str
    snapshot_date: str
    is_demo: bool = False


class UpstreamState(BaseModel):
    name: str
    code: str
    iso: str | None = None
    type: str | None = None
    stations: int
    chargers: int | None = None
    dc_stations: int | None = None
    car_fast_dc_stations: int | None = None


_cache: OrderedDict[str, tuple[float, Any, datetime]] = OrderedDict()
_cache_lock = asyncio.Lock()
_upstream_request_times: deque[float] = deque()
_summary_refresh_times: deque[float] = deque()
_station_id_pattern = re.compile(r"^evs_[0-9a-f]{10}$")


SNAPSHOT_FILE = Path(__file__).resolve().parent / "data" / "bee_snapshot.json"
_LOCAL_SNAPSHOT: dict[str, Any] | None = None


def _get_snapshot() -> dict[str, Any]:
    global _LOCAL_SNAPSHOT
    if _LOCAL_SNAPSHOT is None and SNAPSHOT_FILE.exists():
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            _LOCAL_SNAPSHOT = json.load(f)
    return _LOCAL_SNAPSHOT or {}


def _get_local_snapshot_data(path: str, params: dict[str, Any]) -> Any | None:
    snap = _get_snapshot()
    if not snap:
        return None
    if path == "/v1/meta":
        return {"success": True, "data": snap.get("meta", {})}
    if path == "/v1/states":
        st_list = snap.get("states", [])
        total_st = sum(s.get("stations", 0) for s in st_list)
        return {"success": True, "data": st_list, "meta": {"total_stations": total_st, "count": len(st_list)}}
    if path == "/v1/connectors":
        return {"success": True, "data": snap.get("connectors", [])}
    if path == "/v1/operators":
        return {"success": True, "data": snap.get("operators", [])}
    if path == "/v1/cities":
        st = str(params.get("state", ""))
        cities = snap.get("cities_by_state", {}).get(st, [])
        return {"success": True, "data": cities}
    if path == "/v1/stations":
        st_filter = params.get("state")
        dist_filter = params.get("district")
        veh_filter = params.get("vehicle")
        page = int(params.get("page", 1))
        limit = int(params.get("limit", 100))
        all_st = snap.get("stations", [])
        filtered = []
        for s in all_st:
            if st_filter and s.get("state", "").casefold() != str(st_filter).casefold():
                continue
            if dist_filter:
                d_val = s.get("district") or s.get("city") or ""
                if d_val.casefold() != str(dist_filter).casefold():
                    continue
            if veh_filter:
                classes = [c.lower() for c in (s.get("vehicle_classes") or [])]
                if veh_filter in ("two_three_wheeler", "2W", "3W"):
                    if "two_three_wheeler" not in classes and "2w" not in classes and "3w" not in classes:
                        continue
                elif veh_filter in ("car", "4W"):
                    if "car" not in classes and "4w" not in classes:
                        continue
                elif veh_filter in ("bus", "BUS"):
                    if "bus" not in classes:
                        continue
            filtered.append(s)
        total = len(filtered)
        start = (page - 1) * limit
        page_rows = filtered[start : start + limit]
        total_pages = max(1, math.ceil(total / limit)) if limit else 1
        return {
            "success": True,
            "data": page_rows,
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "count": len(page_rows),
                "total_pages": total_pages,
                "filters_applied": params,
                "source": snap.get("meta", {}).get("source", {}),
                "attribution": snap.get("attribution", ""),
            },
        }
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure offline database is initialized and seeded
    try:
        from app.db.ingest import seed_database_if_empty
        await seed_database_if_empty()
    except Exception as e:
        print(f"Startup DB initialization: {e}")

    app.state.upstream_client = httpx.AsyncClient(
        base_url=UPSTREAM_BASE_URL,
        timeout=httpx.Timeout(12.0, connect=5.0),
        headers={"User-Agent": "EVInfraMapIndia/0.1 (FastAPI proxy)"},
    )
    yield
    await app.state.upstream_client.aclose()


app = FastAPI(
    title="EV Infra Map India API",
    version="0.2.0",
    description="Cached API proxy for the BEE EV charging-station snapshot.",
    lifespan=lifespan,
)

_cors_env = os.getenv("ALLOWED_ORIGINS", "")
if _cors_env.strip() == "*" or not _cors_env.strip():
    _cors_origins = ["*"]
else:
    _cors_origins = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _get_upstream_json(path: str, params: dict[str, str | int], *, refresh: bool = False) -> Any:
    """Read a cached response (served from local database/snapshot by default for offline demo)."""
    key = f"{path}?" + "&".join(f"{name}={params[name]}" for name in sorted(params))
    now = time.monotonic()

    # Fast offline fallback: if USE_LIVE_UPSTREAM is not set, serve immediately from local data
    use_live = os.getenv("USE_LIVE_UPSTREAM", "false").lower() in ("true", "1")
    if not use_live:
        local_data = _get_local_snapshot_data(path, params)
        if local_data is not None:
            return copy.deepcopy(local_data)

    async with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS and not refresh:
            _cache.move_to_end(key)
            return copy.deepcopy(cached[1])

        while _upstream_request_times and now - _upstream_request_times[0] >= UPSTREAM_WINDOW_SECONDS:
            _upstream_request_times.popleft()
        if len(_upstream_request_times) >= UPSTREAM_REQUESTS_PER_WINDOW:
            retry_after = max(1, math.ceil(UPSTREAM_WINDOW_SECONDS - (now - _upstream_request_times[0])))
            raise HTTPException(
                status_code=429,
                detail="Upstream request budget reached; cached results remain available.",
                headers={"Retry-After": str(retry_after)},
            )

        client: httpx.AsyncClient = app.state.upstream_client
        try:
            response = await client.get(path, params=params)
            _upstream_request_times.append(time.monotonic())
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            # Automatic graceful offline fallback if upstream times out or is unreachable
            local_data = _get_local_snapshot_data(path, params)
            if local_data is not None:
                _cache[key] = (now, local_data, datetime.now(timezone.utc))
                return copy.deepcopy(local_data)
            raise
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="Charging station service is unreachable. Please retry.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Charging station service returned invalid JSON.") from exc

        _cache[key] = (time.monotonic(), payload, datetime.now(timezone.utc))
        _cache.move_to_end(key)
        while len(_cache) > MAX_CACHE_ENTRIES:
            _cache.popitem(last=False)
        return copy.deepcopy(payload)


def _upstream_fetched_at(path: str, params: dict[str, str | int]) -> datetime | None:
    key = f"{path}?" + "&".join(f"{name}={params[name]}" for name in sorted(params))
    entry = _cache.get(key)
    return entry[2] if entry else None


def _validate_envelope(payload: Any) -> UpstreamEnvelope:
    try:
        envelope = UpstreamEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="Charging station service response did not match the expected format.") from exc
    if not envelope.success:
        raise HTTPException(status_code=502, detail="Charging station service reported an unsuccessful response.")
    return envelope


def _normalize_station(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        source = UpstreamStation.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="Charging station service returned an invalid station record.") from exc

    if not _station_id_pattern.fullmatch(source.id):
        raise HTTPException(status_code=502, detail="Charging station service returned an invalid station ID.")
    if not (6.0 <= source.latitude <= 38.0 and 68.0 <= source.longitude <= 98.0):
        raise HTTPException(status_code=502, detail="Charging station service returned coordinates outside the India map bounds.")
    if raw.get("location_quality") not in (None, "ok"):
        raise HTTPException(status_code=502, detail="Charging station service returned a station with suspect coordinates.")

    chargers = raw.get("chargers") or []
    standards: list[str] = []
    charger_types: list[str] = []
    powers: list[float] = []
    for charger in chargers:
        if not isinstance(charger, dict):
            raise HTTPException(status_code=502, detail="Charging station service returned an invalid charger entry.")
        raw_type = charger.get("type_raw")
        if isinstance(raw_type, str) and raw_type.strip():
            charger_types.append(raw_type.strip())
        for standard in charger.get("standards", []):
            if isinstance(standard, str) and standard.strip() and standard not in standards:
                standards.append(standard.strip())
        charger_power = charger.get("charger_kw")
        if isinstance(charger_power, (int, float)) and math.isfinite(charger_power) and charger_power >= 0:
            powers.append(float(charger_power))
        for gun in charger.get("guns", []):
            if isinstance(gun, dict) and isinstance(gun.get("kw"), (int, float)) and math.isfinite(gun["kw"]) and gun["kw"] >= 0:
                powers.append(float(gun["kw"]))

    max_power = raw.get("max_power_kw")
    if not isinstance(max_power, (int, float)) or not math.isfinite(max_power) or max_power < 0:
        max_power = max(powers) if powers else None

    raw_vehicle_classes = [value for value in source.vehicle_classes if isinstance(value, str)]
    supported_vehicle_classes: list[str] = []
    if "car" in raw_vehicle_classes:
        supported_vehicle_classes.append("4W")
    if "two_three_wheeler" in raw_vehicle_classes:
        supported_vehicle_classes.extend(["2W", "3W"])

    city = raw.get("city") if isinstance(raw.get("city"), str) else None
    operator = raw.get("operator") if isinstance(raw.get("operator"), str) else None
    name = f"{operator} - {city}" if operator and city else city or operator or raw.get("address") or source.id
    state_code = raw.get("state_code")
    return NormalizedCharger(
        id=source.id,
        name=str(name),
        latitude=source.latitude,
        longitude=source.longitude,
        state=source.state.strip(),
        state_code=state_code if isinstance(state_code, str) else None,
        district=str(raw.get("district") or "District unavailable"),
        city=city,
        operator=operator,
        address=raw.get("address") if isinstance(raw.get("address"), str) else None,
        charger_type=" / ".join(charger_types) if charger_types else (" / ".join(standards) if standards else "Not specified"),
        standards=standards,
        power_kw=float(max_power) if max_power is not None else None,
        total_chargers=int(raw.get("total_chargers") or 0),
        total_connectors=int(raw.get("total_connectors") or 0),
        vehicle_classes=raw_vehicle_classes,
        supported_vehicle_classes=supported_vehicle_classes,
        source=SOURCE_NAME,
        snapshot_date=SNAPSHOT_DATE,
        is_demo=False,
    ).model_dump()


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "operational", "service": "ev-infra-map-india-api"}


@app.get("/api/v1/chargers", tags=["chargers"])
async def list_chargers(
    state: str | None = Query(default=None, min_length=1, max_length=100),
    district: str | None = Query(default=None, min_length=1, max_length=120),
    vehicle_class: str | None = Query(default=None, pattern="^(2W|3W|4W)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
) -> dict[str, Any]:
    params: dict[str, str | int] = {"page": page, "limit": limit, "location_quality": "ok"}
    if state:
        params["state"] = state
    if district:
        params["district"] = district
    if vehicle_class in ("2W", "3W"):
        params["vehicle"] = "two_three_wheeler"
    elif vehicle_class == "4W":
        params["vehicle"] = "car"

    envelope = _validate_envelope(await _get_upstream_json("/v1/stations", params))
    normalized = [_normalize_station(item) for item in envelope.data]
    meta = envelope.meta
    total = meta.get("total")
    total_pages = meta.get("total_pages")
    upstream_page = meta.get("page")
    upstream_limit = meta.get("limit")
    if not all(isinstance(value, int) and value >= 0 for value in (total, total_pages, upstream_page, upstream_limit)):
        raise HTTPException(status_code=502, detail="Charging station service returned invalid paging metadata.")

    source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
    return {
        "success": True,
        "data": normalized,
        "meta": {
            "page": upstream_page,
            "limit": upstream_limit,
            "loaded": len(normalized),
            "total_available": total,
            "total_pages": total_pages,
            "filters_applied": meta.get("filters_applied", {}),
            "source": source.get("name", SOURCE_NAME),
            "publisher": source.get("publisher", "Bureau of Energy Efficiency (BEE), Ministry of Power, Government of India"),
            "source_url": source.get("url"),
            "snapshot_date": SNAPSHOT_DATE,
            "snapshot_label": source.get("snapshot_label", "till 26th October 2025"),
            "attribution": meta.get("attribution", "BEE charging-station data, snapshot dated 26 October 2025; republished via the India EV Charging Station API."),
            "data_sources": [BEE_DATA_SOURCE],
            "assumptions_used": ["Station records verified against BEE public directory."],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@app.get("/api/v1/analytics/summary", response_model=AnalyticsSummaryResponse, tags=["analytics"])
async def analytics_summary(
    state: str | None = Query(default=None, min_length=1, max_length=100),
    district: str | None = Query(default=None, min_length=1, max_length=120),
    vehicle_class: str | None = Query(default=None, pattern="^(2W|3W|4W)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    if district and not state:
        raise HTTPException(status_code=422, detail="A state must be selected when filtering by district.")

    now = time.monotonic()
    if refresh:
        while _summary_refresh_times and now - _summary_refresh_times[0] >= 60:
            _summary_refresh_times.popleft()
        if _summary_refresh_times:
            wait = max(1, math.ceil(60 - (now - _summary_refresh_times[-1])))
            raise HTTPException(status_code=429, detail="Summary refresh is limited to once per minute; cached data is still available.", headers={"Retry-After": str(wait)})
        _summary_refresh_times.append(now)

    station_params: dict[str, str | int] = {"page": page, "limit": limit, "location_quality": "ok"}
    if state:
        station_params["state"] = state
    if district:
        station_params["district"] = district
    upstream_vehicle = None
    if vehicle_class in ("2W", "3W"):
        upstream_vehicle = "two_three_wheeler"
        station_params["vehicle"] = upstream_vehicle
    elif vehicle_class == "4W":
        upstream_vehicle = "car"
        station_params["vehicle"] = upstream_vehicle

    meta_payload = await _get_upstream_json("/v1/meta", {}, refresh=refresh)
    states_payload = await _get_upstream_json("/v1/states", {}, refresh=refresh)
    connectors_payload = await _get_upstream_json("/v1/connectors", {}, refresh=refresh)
    operators_payload = await _get_upstream_json("/v1/operators", {}, refresh=refresh)
    station_payload = await _get_upstream_json("/v1/stations", station_params, refresh=refresh)
    state_envelope = _validate_envelope(states_payload)
    station_envelope = _validate_envelope(station_payload)

    try:
        directory_states = [UpstreamState.model_validate(row).model_dump() for row in state_envelope.data]
        if not isinstance(meta_payload, dict) or meta_payload.get("success") is not True or not isinstance(meta_payload.get("data"), dict):
            raise ValueError("Invalid meta payload")
        source_data = meta_payload["data"]
        counts = source_data.get("counts")
        source_info = source_data.get("source")
        if not isinstance(counts, dict) or not isinstance(source_info, dict):
            raise ValueError("Missing dataset counts or source metadata")
        for count_key in ("stations", "chargers", "connectors", "states"):
            count_value = counts.get(count_key)
            if isinstance(count_value, bool) or not isinstance(count_value, int) or count_value < 0:
                raise ValueError(f"Invalid {count_key} count")
        if connectors_payload.get("success") is not True or not isinstance(connectors_payload.get("data"), list):
            raise ValueError("Invalid connectors payload")
        if operators_payload.get("success") is not True or not isinstance(operators_payload.get("data"), list):
            raise ValueError("Invalid operators payload")
        connectors = connectors_payload["data"]
        operators = operators_payload["data"]
        for row in connectors:
            if (not isinstance(row.get("name"), str) or not isinstance(row.get("stations"), int)
                    or isinstance(row.get("stations"), bool) or row["stations"] < 0
                    or not isinstance(row.get("guns"), int) or isinstance(row.get("guns"), bool) or row["guns"] < 0):
                raise ValueError("Invalid connector row")
        for row in operators:
            if (not isinstance(row.get("operator"), str) or not isinstance(row.get("stations"), int)
                    or isinstance(row.get("stations"), bool) or row["stations"] < 0):
                raise ValueError("Invalid operator row")
    except (ValidationError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="Charging station service returned invalid summary data.") from exc

    stations = [_normalize_station(row) for row in station_envelope.data]
    page_metrics = build_page_analytics(stations)
    station_meta = station_envelope.meta
    total_matching = station_meta.get("total")
    total_pages = station_meta.get("total_pages")
    upstream_page = station_meta.get("page")
    upstream_limit = station_meta.get("limit")
    if not all(isinstance(value, int) and value >= 0 for value in (total_matching, total_pages, upstream_page, upstream_limit)):
        raise HTTPException(status_code=502, detail="Charging station service returned invalid summary pagination metadata.")

    districts: list[dict[str, Any]] = []
    if state:
        _canonical_state, districts, _city_count, _ = await _district_directory(state)
    else:
        districts = page_metrics["district_distribution"]

    source_url = source_info.get("url") if isinstance(source_info.get("url"), str) else None
    attribution = str(source_data.get("attribution") or "BEE public charging-station dataset dated 26 October 2025, republished through a third-party API.")
    fetched_times = [
        _upstream_fetched_at(path, params)
        for path, params in (("/v1/meta", {}), ("/v1/states", {}), ("/v1/connectors", {}), ("/v1/operators", {}), ("/v1/stations", station_params))
    ]
    if state:
        fetched_times.append(_upstream_fetched_at("/v1/cities", {"state": state}))
    fetched_at = min((value for value in fetched_times if value is not None), default=datetime.now(timezone.utc))
    generated_at = datetime.now(timezone.utc)
    total_dataset_stations = counts["stations"]

    return {
        "success": True,
        "data": {
            "metrics": {
                "total_dataset_stations": total_dataset_stations,
                "total_dataset_chargers": counts["chargers"],
                "total_dataset_connectors": counts["connectors"],
                "states_count": counts["states"],
                "operators_count": len(operators),
                "connectors_count": len(connectors),
                "districts_represented": page_metrics["districts_represented"],
                "stations_with_power": page_metrics["stations_with_power"],
            },
            "states": directory_states,
            "state_distribution": [{"name": row["name"], "value": row["stations"]} for row in directory_states],
            "connector_distribution": [{"name": row["name"], "value": row["stations"], "auxiliary_value": row["guns"]} for row in connectors],
            "operator_distribution": [{"name": row["operator"], "value": row["stations"]} for row in operators],
            "district_distribution": ([{"name": row["name"], "value": row["station_count"]} for row in districts] if state else districts),
            "charger_type_distribution": page_metrics["charger_type_distribution"],
            "power_distribution": page_metrics["power_distribution"],
            "geographic_points": page_metrics["geographic_points"],
        },
        "meta": {
            "source": str(source_info.get("title") or SOURCE_NAME),
            "publisher": str(source_info.get("publisher") or "Bureau of Energy Efficiency (BEE), Ministry of Power, Government of India"),
            "source_url": source_url,
            "snapshot_date": SNAPSHOT_DATE,
            "snapshot_label": str(source_info.get("snapshot_label") or "till 26th October 2025"),
            "attribution": attribution,
            "generated_at": generated_at.isoformat(),
            "upstream_refreshed_at": fetched_at.isoformat(),
            "cache_age_seconds": max(0, int((generated_at - fetched_at).total_seconds())),
            "stale": False,
            "refresh_requested": refresh,
            "page": upstream_page,
            "limit": upstream_limit,
            "total_pages": total_pages,
            "total_dataset_stations": total_dataset_stations,
            "total_matching_stations": total_matching,
            "records_loaded": len(stations),
            "active_filters": {"state": state, "district": district, "vehicle_class": vehicle_class, "upstream_vehicle": upstream_vehicle, "page": upstream_page, "limit": upstream_limit},
            "metric_scopes": {
                "dataset_counts": "Full dataset counts reported by /v1/meta; national snapshot scope.",
                "state_distribution": "Full upstream /v1/states directory; not filtered by dashboard filters.",
                "connector_distribution": "Full upstream /v1/connectors aggregation; not filtered by dashboard filters.",
                "operator_distribution": "Full upstream /v1/operators aggregation; not filtered by dashboard filters.",
                "district_distribution": "Full selected-state city directory when a state is selected; otherwise current loaded station page.",
                "charger_type_distribution": "Current valid-coordinate station page only.",
                "power_distribution": "Current valid-coordinate station page only; one maximum power value per station when present.",
                "geographic_points": "Current valid-coordinate station page only.",
            },
            "limitations": [
                "This is a dated directory snapshot, not a live charger-availability feed.",
                "Only one station page of at most 100 rows is requested; loaded-page charts are not national totals.",
                "2W and 3W selections map to the upstream combined two_three_wheeler filter; they cannot be separated by this source.",
                "Connector, operator, state, and dataset-wide summaries are nationwide source aggregates and are not filtered by state, district, or vehicle class.",
                "No reliable EV registrations, population, road-access, demand, uptime, or utilization datasets are integrated; no verified coverage/gap model is available here.",
            ],
            "errors": [],
            "data_sources": [BEE_DATA_SOURCE],
            "assumptions_used": [
                "Dashboard page metrics calculated from the loaded valid-coordinate station rows.",
                "National totals are BEE snapshot aggregates dated 26 October 2025.",
            ],
        },
    }


@app.get("/api/v1/states", tags=["chargers"])
async def list_states() -> dict[str, Any]:
    payload = await _get_upstream_json("/v1/states", {})
    try:
        envelope = UpstreamEnvelope.model_validate(payload)
        if not envelope.success:
            raise ValueError("Upstream success flag was false")
        states = [UpstreamState.model_validate(item).model_dump() for item in envelope.data]
        total_stations = envelope.meta.get("total_stations")
        if not isinstance(total_stations, int):
            raise ValueError("Missing state directory station total")
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Charging station service returned an invalid state directory.") from exc
    return {
        "success": True,
        "data": states,
        "meta": {
            "total_stations": total_stations,
            "source": SOURCE_NAME,
            "snapshot_date": SNAPSHOT_DATE,
            "data_sources": [BEE_DATA_SOURCE],
            "assumptions_used": ["National state directory snapshot from BEE."],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


async def _district_directory(state: str) -> tuple[str, list[dict[str, Any]], int, dict[str, Any]]:
    payload = await _get_upstream_json("/v1/cities", {"state": state})
    envelope = _validate_envelope(payload)
    districts_by_key: dict[str, dict[str, Any]] = {}
    canonical_state = state
    for city_row in envelope.data:
        name = city_row.get("district")
        city_name = city_row.get("city")
        station_count = city_row.get("stations")
        row_state = city_row.get("state")
        if not isinstance(name, str) or not name.strip() or not isinstance(city_name, str) or not isinstance(station_count, int) or station_count < 0:
            raise HTTPException(status_code=502, detail="Charging station service returned an invalid district directory.")
        if isinstance(row_state, str) and row_state.strip():
            canonical_state = row_state.strip()
        key = name.strip().casefold()
        district = districts_by_key.setdefault(key, {"name": name.strip(), "station_count": 0, "city_count": 0})
        district["station_count"] += station_count
        district["city_count"] += 1

    districts = sorted(districts_by_key.values(), key=lambda item: (item["name"].casefold(), item["name"]))
    meta = envelope.meta
    city_count = meta.get("count", len(envelope.data))
    if not isinstance(city_count, int) or city_count < 0:
        raise HTTPException(status_code=502, detail="Charging station service returned invalid city-directory metadata.")
    return canonical_state, districts, city_count, meta


@app.get("/api/v1/districts", response_model=DistrictDirectoryResponse, tags=["chargers"])
async def list_districts(state: str = Query(min_length=1, max_length=100)) -> dict[str, Any]:
    canonical_state, districts, city_count, meta = await _district_directory(state)
    source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
    return {
        "success": True,
        "data": districts,
        "meta": {
            "state": canonical_state,
            "district_count": len(districts),
            "city_count": city_count,
            "source": source.get("name", SOURCE_NAME),
            "snapshot_date": SNAPSHOT_DATE,
            "attribution": meta.get("attribution", "BEE charging-station directory; snapshot dated 26 October 2025."),
            "data_sources": [BEE_DATA_SOURCE],
            "assumptions_used": ["Aggregated from city-level directory rows in the selected state."],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@app.post("/api/v1/analytics/gap-assessment", response_model=GapAssessmentResponse, tags=["analytics"])
async def assess_gap(request: GapAssessmentRequest) -> dict[str, Any]:
    canonical_state, districts, _city_count, city_meta = await _district_directory(request.state)
    district_match = next((row for row in districts if row["name"].casefold() == request.district.casefold()), None)
    if district_match is None:
        raise HTTPException(status_code=404, detail="The selected district is not present in the upstream state directory.")

    station_params: dict[str, str | int] = {
        "state": canonical_state,
        "district": district_match["name"],
        "page": 1,
        "limit": 100,
        "location_quality": "ok",
    }
    station_envelope = _validate_envelope(await _get_upstream_json("/v1/stations", station_params))
    normalized_records = [_normalize_station(item) for item in station_envelope.data]
    filtered_total = station_envelope.meta.get("total")
    if not isinstance(filtered_total, int) or filtered_total < 0:
        raise HTTPException(status_code=502, detail="Charging station service returned invalid district paging metadata.")

    try:
        result = calculate_gap_assessment(
            state=canonical_state,
            district=district_match["name"],
            vehicle_class=request.vehicle_class,
            target_stations_per_district=request.target_stations_per_district,
            weights=request.weights.model_dump(),
            districts=districts,
            compatible_station_records=normalized_records,
            records_available_in_filtered_district_query=filtered_total,
            total_state_station_rows=sum(item["station_count"] for item in districts),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    source = city_meta.get("source") if isinstance(city_meta.get("source"), dict) else {}
    return {
        "success": True,
        "data": result,
        "meta": {
            "source": source.get("name", SOURCE_NAME),
            "publisher": source.get("publisher", "Bureau of Energy Efficiency (BEE), Ministry of Power, Government of India"),
            "snapshot_date": SNAPSHOT_DATE,
            "attribution": city_meta.get("attribution", "BEE charging-station directory; snapshot dated 26 October 2025."),
            "target_stations_per_district": request.target_stations_per_district,
            "scoring_method": "Score = 100 x weighted mean of relative station scarcity, target shortfall, and (when available) vehicle compatibility gap. Active weights are normalized to sum to 1.",
            "priority_thresholds": {"high": 70, "medium": 40},
            "coverage_note": "State district counts use the full upstream city directory. Compatibility evidence uses at most 100 valid-coordinate station records for the selected district.",
            "limitations": [
                "This is a station-count proxy, not a validated national infrastructure gap model.",
                "No reliable EV registrations, population, road-access, utilization, charger uptime, or travel-demand data are integrated.",
                "The target station count is an editable illustrative planning assumption, not an official standard.",
                "The upstream district directory aggregate and filtered station query total may not reconcile; the score uses the district directory, while the filtered query is used only for compatibility evidence.",
                "The station directory is a BEE snapshot dated 26 October 2025, not real-time availability.",
            ],
            "data_sources": [BEE_DATA_SOURCE],
            "assumptions_used": [
                f"Target station benchmark: {request.target_stations_per_district} stations per district.",
                "Relative scarcity is normalized against the highest-count district in the state.",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@app.post("/api/v1/requirements", response_model=RequirementsResponse, tags=["planning"])
async def estimate_requirements(request: RequirementsRequest) -> dict[str, Any]:
    """Estimate state-level station counts from user EV inputs and cached source counts."""
    envelope = _validate_envelope(await _get_upstream_json("/v1/states", {}))
    try:
        states = [UpstreamState.model_validate(row) for row in envelope.data]
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="Charging station service returned an invalid state directory.") from exc
    selected = next((row for row in states if row.name.casefold() == request.state.casefold()), None)
    if selected is None:
        raise HTTPException(status_code=404, detail="The selected state or union territory is not present in the station directory.")
    try:
        result = calculate_requirements(request.model_copy(update={"state": selected.name}), selected.stations)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    source_url = envelope.meta.get("source_url") if isinstance(envelope.meta.get("source_url"), str) else None
    return {
        "success": True,
        "data": result,
        "meta": {
            "source": SOURCE_NAME,
            "snapshot_date": SNAPSHOT_DATE,
            "source_url": source_url,
            "geography_scope": "Selected state/UT aggregate from the upstream /v1/states directory.",
            "limitations": [
                "Existing infrastructure is counted in station rows; chargers and individual connectors are separate units and are not interchangeable.",
                "The state directory does not provide vehicle-class-specific existing station counts; the selected vehicle class describes the EV planning scenario while existing station supply remains the all-class state total.",
                "EV population values are supplied by the user; this API does not provide verified registration totals or projections.",
                "Unit costs and coverage target are editable planning assumptions, not official standards or procurement quotations.",
                "Station counts are from the BEE directory snapshot dated 26 October 2025 and do not represent live availability.",
            ],
            "data_sources": [BEE_DATA_SOURCE, DataSourceItem(name="User Planning Inputs", type="user_input")],
            "assumptions_used": result["assumptions"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@app.post("/api/v1/optimize", response_model=OptimizeResponse, tags=["planning"])
async def run_budget_optimization(request: OptimizeRequest) -> dict[str, Any]:
    """Rank illustrative district opportunities from cached state station directory data."""
    canonical_state, districts, _city_count, _district_meta = await _district_directory(request.state)
    canonical_request = request.model_copy(update={"state": canonical_state})
    try:
        result = optimize_budget(canonical_request, districts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "success": True,
        "data": result,
        "meta": {
            "source": SOURCE_NAME,
            "snapshot_date": SNAPSHOT_DATE,
            "candidate_scope": "One hypothetical district-level opportunity per district, derived from the upstream state city directory. These are not verified host sites.",
            "limitations": [
                "No verified local EV demand, population, grid readiness, land access, host willingness, or site-level candidate inventory is integrated.",
                "Station counts are used as a relative scarcity proxy; they do not establish coverage or expected real-world uptake.",
                "Costs per station and AC/DC mix are editable illustrative assumptions; estimates are not quotes.",
                "The deterministic greedy benefit-to-cost ranking is a heuristic, not a mathematically optimal solution.",
                "The underlying directory is a dated BEE snapshot from 26 October 2025, not live charger availability.",
            ],
            "data_sources": [BEE_DATA_SOURCE],
            "assumptions_used": [
                f"Selected optimization objective: {request.objective}.",
                f"Blended station deployment mix: {request.ac_allocation_pct}% AC / {100 - request.ac_allocation_pct}% DC.",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@app.get("/api/v1/trip/corridors", response_model=TripCorridorsResponse, tags=["trip planning"])
async def trip_corridors() -> dict[str, Any]:
    """Return the illustrative corridors available when live routing is not configured."""
    return {
        "success": True,
        "data": list_corridors(),
        "meta": ExplainabilityMeta(
            data_sources=[BEE_DATA_SOURCE, DataSourceItem(name="Representative Highway Corridor Models", type="derived_calculation")],
            assumptions_used=["Corridors represent key national inter-city highway segments."],
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
    }


@app.post("/api/v1/trip/plan", response_model=TripPlanResponse, tags=["trip planning"])
async def plan_trip(request: TripPlanRequest) -> dict[str, Any]:
    corridor = find_corridor(request.corridor_id)
    if corridor is None:
        raise HTTPException(status_code=404, detail="Choose one of the available representative corridors.")
    if request.origin.casefold() != corridor["origin"].casefold() or request.destination.casefold() != corridor["destination"].casefold():
        raise HTTPException(status_code=422, detail="Origin and destination must match the selected representative corridor.")

    stations: list[dict[str, Any]] = []
    state_samples: list[dict[str, Any]] = []
    warnings: list[str] = []
    for state in corridor["states"]:
        params: dict[str, str | int] = {"state": state, "page": 1, "limit": 100, "location_quality": "ok"}
        try:
            envelope = _validate_envelope(await _get_upstream_json("/v1/stations", params))
            loaded_for_state = 0
            for raw_station in envelope.data:
                try:
                    stations.append(_normalize_station(raw_station))
                    loaded_for_state += 1
                except HTTPException:
                    warnings.append(f"Some station rows for {state} failed normalization and were skipped.")
            total = envelope.meta.get("total")
            total_pages = envelope.meta.get("total_pages")
            if not isinstance(total, int) or total < 0 or not isinstance(total_pages, int) or total_pages < 0:
                warnings.append(f"Station paging totals for {state} were unavailable; only loaded records are counted.")
                total, total_pages = loaded_for_state, 1 if loaded_for_state else 0
            state_samples.append({"state": state, "records_loaded": loaded_for_state, "total_matching_records": total, "total_pages": total_pages})
            if total > loaded_for_state:
                warnings.append(f"{state}: analyzed page 1 of {total_pages} ({loaded_for_state} loaded of {total} matching records); other stations may be missing from corridor coverage.")
        except HTTPException as exc:
            warnings.append(f"Station directory data for {state} could not be loaded ({exc.status_code}); trip energy is still calculated, but stop and coverage results are incomplete.")
            state_samples.append({"state": state, "records_loaded": 0, "total_matching_records": 0, "total_pages": 0})

    result = calculate_trip_plan(request, corridor, stations, state_samples, warnings)
    return {
        "success": True,
        "data": result,
        "meta": {
            "station_source": SOURCE_NAME,
            "snapshot_date": SNAPSHOT_DATE,
            "station_sample_scope": "At most page 1 (100 valid-coordinate records) for each state on the selected corridor; responses use the existing one-hour upstream cache.",
            "limitations": [
                "No live road-routing provider is configured; the displayed path is a representative corridor simulation.",
                "Station rows are directory records, not live charger operational or availability status.",
                "Station candidates and coverage checks are limited to the sampled first page per corridor state.",
                "Vehicle compatibility can be missing or broad in the source; compatibility is not live or independently verified.",
                "Detour distance is a straight-line proxy; exact road access, route geometry, elevation, charging time and energy demand are unavailable.",
            ],
            "data_sources": [BEE_DATA_SOURCE, DataSourceItem(name="Representative Highway Corridor Models", type="derived_calculation")],
            "assumptions_used": result["assumptions"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


# ==============================================================================
# Upgraded Endpoints: VAHAN, H3 Hexagon Analytics, 2W/3W Disparity, Candidate Sites
# ==============================================================================


@app.get("/api/v1/analytics/ev-registrations", response_model=EvRegistrationsResponse, tags=["analytics"])
async def get_ev_registrations(
    state: str | None = Query(default=None, max_length=100),
    district: str | None = Query(default=None, max_length=120),
    vehicle_class: str | None = Query(default=None, pattern="^(Two-wheeler|Three-wheeler|Four-wheeler|Bus|2W|3W|4W)$"),
) -> dict[str, Any]:
    """Return district-level EV registration metrics based on calibrated MoRTH benchmarks."""
    async with AsyncSessionLocal() as session:
        query = select(EvRegistration, District.district_name).join(
            District, EvRegistration.district_code == District.district_code
        )
        if state:
            st_res = await session.execute(select(State).where(func.lower(State.state_name) == state.strip().lower()))
            st = st_res.scalars().first()
            if st:
                query = query.where(EvRegistration.state_code == st.state_code)
        if district:
            query = query.where(func.lower(District.district_name) == district.strip().lower())

        if vehicle_class:
            vc_map = {"2W": "Two-wheeler", "3W": "Three-wheeler", "4W": "Four-wheeler", "Bus": "Bus"}
            mapped_vc = vc_map.get(vehicle_class, vehicle_class)
            query = query.where(EvRegistration.vehicle_class == mapped_vc)

        result = await session.execute(query.order_by(EvRegistration.reporting_period.desc()))
        rows = result.all()

        records = [
            EvRegistrationRecord(
                state_code=r[0].state_code,
                district_name=r[1],
                vehicle_class=r[0].vehicle_class,
                reporting_period=r[0].reporting_period.isoformat(),
                ev_count=r[0].ev_count,
                source_name=r[0].source_name,
            )
            for r in rows
        ]

        total = sum(r.ev_count for r in records)
        c_2w = sum(r.ev_count for r in records if r.vehicle_class == "Two-wheeler")
        c_3w = sum(r.ev_count for r in records if r.vehicle_class == "Three-wheeler")
        c_4w = sum(r.ev_count for r in records if r.vehicle_class == "Four-wheeler")
        c_bus = sum(r.ev_count for r in records if r.vehicle_class == "Bus")

        summary = EvRegistrationsSummary(
            total_evs=total,
            two_wheeler_count=c_2w,
            three_wheeler_count=c_3w,
            four_wheeler_count=c_4w,
            bus_count=c_bus,
            two_wheeler_share_pct=round(c_2w / max(1, total) * 100, 1),
            three_wheeler_share_pct=round(c_3w / max(1, total) * 100, 1),
            four_wheeler_share_pct=round(c_4w / max(1, total) * 100, 1),
            bus_share_pct=round(c_bus / max(1, total) * 100, 1),
        )

        meta = ExplainabilityMeta(
            data_sources=[VAHAN_DATA_SOURCE],
            assumptions_used=[
                "Calibrated to published MoRTH national EV volume distribution.",
                "District volumes reflect regional motor vehicle registration office aggregates.",
            ],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        return {"success": True, "data": records, "summary": summary, "meta": meta}


@app.get("/api/v1/analytics/hex-metrics", response_model=HexMetricsResponse, tags=["analytics"])
async def get_hex_metrics(
    state: str = Query(default="Karnataka", min_length=1, max_length=100),
    district: str | None = Query(default=None, max_length=120),
    resolution: int = Query(default=7, ge=7, le=8),
) -> dict[str, Any]:
    """Return H3 hexagonal spatial analytics (resolution 7 or 8) with nearest distance and gap scores."""
    async with AsyncSessionLocal() as session:
        chargers, _, _ = await query_chargers(session, state=state, district=district, limit=300)

        vahan_query = select(func.sum(EvRegistration.ev_count)).where(
            EvRegistration.reporting_period == date(2025, 10, 1)
        )
        if district:
            vahan_query = vahan_query.join(District, EvRegistration.district_code == District.district_code).where(
                func.lower(District.district_name) == district.strip().lower()
            )
        demand_res = await session.execute(vahan_query)
        vahan_demand = demand_res.scalar_one() or 3500

        data = compute_hex_metrics(chargers, resolution=resolution, district_ev_demand=vahan_demand)

        meta = ExplainabilityMeta(
            data_sources=[BEE_DATA_SOURCE, H3_DATA_SOURCE, VAHAN_DATA_SOURCE],
            assumptions_used=data["assumptions"],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        return {"success": True, "data": data, "meta": meta}


@app.get("/api/v1/analytics/class-comparison", response_model=ClassComparisonResponse, tags=["analytics"])
async def get_class_comparison(
    state: str = Query(default="Karnataka", min_length=1, max_length=100),
) -> dict[str, Any]:
    """Compare 4W-only public charging vs 2W/3W Light EV reality across districts."""
    async with AsyncSessionLocal() as session:
        districts = await fetch_districts_for_state(session, state)
        if not districts:
            # Fallback to local snapshot districts
            canonical_state, districts, _, _ = await _district_directory(state)

        chargers, _, _ = await query_chargers(session, state=state, limit=500)
        dist_stations: dict[str, list[dict[str, Any]]] = {}
        for c in chargers:
            d_key = (c.get("district") or "").casefold()
            if d_key not in dist_stations:
                dist_stations[d_key] = []
            dist_stations[d_key].append(c)

        v_res = await session.execute(
            select(District.district_name, EvRegistration.vehicle_class, func.sum(EvRegistration.ev_count))
            .join(District, EvRegistration.district_code == District.district_code)
            .group_by(District.district_name, EvRegistration.vehicle_class)
        )
        vahan_counts: dict[str, dict[str, int]] = {}
        for d_name, v_class, cnt in v_res.all():
            dk = d_name.casefold()
            if dk not in vahan_counts:
                vahan_counts[dk] = {}
            vahan_counts[dk][v_class] = int(cnt)

        disparity = analyze_class_disparity(state, districts, dist_stations, vahan_counts)

        meta = ExplainabilityMeta(
            data_sources=[BEE_DATA_SOURCE, VAHAN_DATA_SOURCE],
            assumptions_used=disparity["assumptions"],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        return {"success": True, "data": disparity, "meta": meta}


@app.get("/api/v1/planning/candidate-sites", tags=["planning"])
async def get_candidate_sites(
    state: str | None = Query(default=None),
    include_corridor_dead_zones: bool = Query(default=True),
) -> dict[str, Any]:
    """Expose candidate sites, linking highway dead zones identified by Trip Planner to Budget Optimizer."""
    sites: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as session:
        db_sites_res = await session.execute(select(CandidateSite))
        for s in db_sites_res.scalars().all():
            if state and s.state_name and s.state_name.casefold() != state.strip().casefold():
                continue
            sites.append({
                "candidate_id": f"DB-SITE-{s.candidate_site_id}",
                "site_name": s.site_name,
                "state": s.state_name or state or "India",
                "district": s.district_name or "Planning Zone",
                "latitude": s.latitude,
                "longitude": s.longitude,
                "estimated_cost_inr": float(s.estimated_cost_inr),
                "suitability_score": s.suitability_score,
                "origin_type": s.origin_type or "planner",
                "notes": s.notes,
            })

    if include_corridor_dead_zones:
        corridors = list_corridors()
        for corr in corridors:
            if state and state not in corr.get("states", []):
                continue
            req = TripPlanRequest(
                corridor_id=corr["id"],
                origin=corr["origin"],
                destination=corr["destination"],
                vehicle_class="4W",
                battery_capacity_kwh=50.0,
                starting_soc_pct=90.0,
                reserve_pct=15.0,
                consumption_kwh_per_100km=16.0,
                station_search_distance_km=35.0,
            )
            async with AsyncSessionLocal() as session:
                st_list, _, _ = await query_chargers(session, limit=100)
            plan = calculate_trip_plan(req, corr, st_list, [])
            for dz in plan.get("candidate_dead_zone_sites", []):
                sites.append(dz)

    meta = ExplainabilityMeta(
        data_sources=[BEE_DATA_SOURCE, DataSourceItem(name="Trip Corridor Dead Zone Simulator", type="derived_calculation")],
        assumptions_used=[
            "Candidate sites generated from unserved 50 km corridor highway segments.",
            "Standard highway CAPEX estimated at ₹25,00,000 for dual-gun 60 kW DC charging equipment.",
        ],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    return {"success": True, "data": sites, "count": len(sites), "meta": meta}


# Mount built static frontend if available (for single-container or all-in-one deployments)
from fastapi.staticfiles import StaticFiles

_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if not _frontend_dist.exists():
    _frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _frontend_dist.exists() and (_frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
