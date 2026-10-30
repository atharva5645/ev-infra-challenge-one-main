import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any
from sqlalchemy import select, func
from datetime import date
from app.db.session import engine, AsyncSessionLocal, Base
from app.db.models import (
    State, District, ChargerSourceRecord, ChargerUnified, Assumption, EvRegistration
)

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "bee_snapshot.json"
VAHAN_PATH = Path(__file__).resolve().parent.parent / "data" / "vahan_registrations.json"


def _make_district_code(state_code: str, district_name: str) -> str:
    h = hashlib.md5(f"{state_code}:{district_name.casefold()}".encode("utf-8")).hexdigest()[:8].upper()
    slug = "".join(ch for ch in district_name if ch.isalnum()).upper()[:8]
    return f"{state_code}-{slug}-{h}"


def _normalize_classes(classes_raw: list[str]) -> list[str]:
    result = []
    for c in classes_raw:
        if c == "two_three_wheeler":
            if "2W" not in result:
                result.append("2W")
            if "3W" not in result:
                result.append("3W")
        elif c in ("car", "4W") and "4W" not in result:
            result.append("4W")
        elif c == "bus" and "Bus" not in result:
            result.append("Bus")
    return sorted(result)


def _classify_type(currents: list[str], max_kw: float | None) -> str:
    if "DC" in currents:
        return "DC fast"
    return "AC"


async def ingest_snapshot(drop_tables: bool = False):
    async with engine.begin() as conn:
        if drop_tables:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    if not SNAPSHOT_PATH.exists():
        print(f"Snapshot not found at {SNAPSHOT_PATH}")
        return

    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        res = await session.execute(select(func.count(State.state_code)))
        if res.scalar_one() > 0:
            print("Database already contains state records; skipping duplicate ingestion.")
            return

        print("Ingesting states...")
        state_map = {}  # name -> code
        for s in data.get("states", []):
            code = s.get("code") or s.get("name")[:2].upper()
            state_map[s["name"].casefold()] = code
            state = State(
                state_code=code,
                state_name=s["name"],
                stations_count=s.get("stations", 0),
                chargers_count=s.get("chargers", 0),
                dc_stations_count=s.get("dc_stations", 0),
            )
            session.add(state)
        await session.flush()

        print("Ingesting districts...")
        district_map = {}  # (state_code, district_name.casefold()) -> district_code
        for state_name, cities in data.get("cities_by_state", {}).items():
            st_code = state_map.get(state_name.casefold(), state_name[:2].upper())
            # Aggregate by district (case-insensitively to normalize mixed casing in BEE data)
            district_totals: dict[str, dict[str, Any]] = {}
            for c in cities:
                raw_d = c.get("district") or c.get("city") or "General"
                canonical_name = raw_d.strip().title()
                norm_key = canonical_name.casefold()
                if norm_key not in district_totals:
                    district_totals[norm_key] = {"name": canonical_name, "station_count": 0, "city_count": 0}
                district_totals[norm_key]["station_count"] += c.get("stations", 0)
                district_totals[norm_key]["city_count"] += 1

            for norm_key, info in district_totals.items():
                d_name = info["name"]
                d_code = _make_district_code(st_code, d_name)
                district_map[(st_code, norm_key)] = d_code
                district = District(
                    district_code=d_code,
                    state_code=st_code,
                    district_name=d_name,
                    station_count=info["station_count"],
                    city_count=info["city_count"],
                )
                session.add(district)
        await session.flush()

        print("Ingesting charging stations...")
        source_name = "EV Public Charging Stations Data till 26th October 2025"
        stations = data.get("stations", [])
        for st in stations:
            st_id = st.get("id")
            s_name = st.get("state", "")
            st_code = state_map.get(s_name.casefold(), s_name[:2].upper() if s_name else "IN")
            d_name = st.get("district") or st.get("city") or "General"
            d_code = district_map.get((st_code, d_name.casefold()))

            # Create district on the fly if not yet recorded
            if not d_code:
                d_code = _make_district_code(st_code, d_name)
                district_map[(st_code, d_name.casefold())] = d_code
                new_district = District(
                    district_code=d_code,
                    state_code=st_code,
                    district_name=d_name,
                    station_count=1,
                    city_count=1,
                )
                session.add(new_district)
                await session.flush()

            lat = float(st["latitude"]) if st.get("latitude") is not None else None
            lon = float(st["longitude"]) if st.get("longitude") is not None else None
            currents = st.get("currents") or []
            max_kw = st.get("max_power_kw")
            ch_type = _classify_type(currents, max_kw)
            raw_classes = st.get("vehicle_classes") or []
            supp_classes = _normalize_classes(raw_classes)

            source_rec = ChargerSourceRecord(
                source_name=source_name,
                source_record_key=st_id,
                station_name=st.get("address") or f"Station {st_id}",
                district_code=d_code,
                latitude=lat,
                longitude=lon,
                charger_type=ch_type,
                raw_attributes=st,
            )
            session.add(source_rec)
            await session.flush()

            if lat is not None and lon is not None:
                unified = ChargerUnified(
                    source_id=st_id,
                    station_name=st.get("address") or f"Station {st_id}",
                    district_code=d_code,
                    state_name=s_name,
                    district_name=d_name,
                    city_name=st.get("city"),
                    operator=st.get("operator"),
                    address=st.get("address"),
                    latitude=lat,
                    longitude=lon,
                    charger_type=ch_type,
                    standards=st.get("standards") or [],
                    power_kw=max_kw,
                    total_chargers=st.get("total_chargers", 1),
                    total_connectors=st.get("total_connectors", 1),
                    vehicle_classes=raw_classes,
                    supported_vehicle_classes=supp_classes,
                    source_name=source_name,
                    source_record_id=source_rec.source_record_id,
                    confidence_score=0.92,
                )
                session.add(unified)

        # Ingest baseline assumptions
        assumptions_data = [
            ("planning_horizon_years", 5, "years", "Planning horizon used for EV infrastructure planning.", "BEE / NITI Aayog Planning Guidelines"),
            ("target_chargers_per_1000_evs", 2.5, "chargers per 1000 EVs", "Illustrative planning target; not an official standard.", "NITI Aayog Handbook on EV Charging Infrastructure"),
            ("default_site_cost_inr", 2000000, "INR per site", "Estimated standard public charging station installation CAPEX.", "Industry average / BEE benchmark"),
            ("minimum_confidence_score", 0.70, "score from 0 to 1", "Confidence threshold for geo-coordinates and connector standards.", "EV Infra Map Data Quality Standard"),
        ]
        for p_name, p_val, units, desc, src in assumptions_data:
            session.add(Assumption(
                parameter_name=p_name,
                parameter_value=p_val,
                units=units,
                description=desc,
                source=src,
            ))

        # Ingest VAHAN registration records
        if VAHAN_PATH.exists():
            print("Ingesting calibrated VAHAN registration data...")
            with open(VAHAN_PATH, "r", encoding="utf-8") as vf:
                vahan_data = json.load(vf)
            v_records = vahan_data.get("records", [])
            for vr in v_records:
                st_code = vr.get("state_code")
                dist_name = vr.get("district_name")
                d_code = district_map.get((st_code, dist_name.casefold()))
                if not d_code:
                    d_code = _make_district_code(st_code, dist_name)
                    district_map[(st_code, dist_name.casefold())] = d_code
                    new_dist = District(
                        district_code=d_code,
                        state_code=st_code,
                        district_name=dist_name,
                        station_count=0,
                        city_count=1,
                    )
                    session.add(new_dist)
                    await session.flush()

                # Parse date
                p_parts = [int(x) for x in vr["reporting_period"].split("-")]
                rep_date = date(p_parts[0], p_parts[1], p_parts[2])
                session.add(EvRegistration(
                    state_code=st_code,
                    district_code=d_code,
                    vehicle_class=vr["vehicle_class"],
                    reporting_period=rep_date,
                    ev_count=vr["ev_count"],
                    source_name=vr["source_name"],
                ))
            print(f"Successfully staged {len(v_records)} VAHAN registration rows.")

        await session.commit()
        print(f"Successfully ingested {len(stations)} stations into database!")


async def seed_database_if_empty():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(func.count(State.state_code)))
        if res.scalar_one() == 0:
            print("Database empty. Initializing and seeding...")
            await ingest_snapshot()


if __name__ == "__main__":
    asyncio.run(ingest_snapshot(drop_tables=True))
