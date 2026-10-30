from __future__ import annotations

from typing import Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import State, District, ChargerUnified


async def fetch_states(session: AsyncSession) -> list[dict[str, Any]]:
    query = select(State).order_by(State.stations_count.desc())
    result = await session.execute(query)
    rows = result.scalars().all()
    return [
        {
            "name": row.state_name,
            "code": row.state_code,
            "stations": row.stations_count,
            "chargers": row.chargers_count,
            "dc_stations": row.dc_stations_count,
        }
        for row in rows
    ]


async def fetch_districts_for_state(session: AsyncSession, state_name: str) -> list[dict[str, Any]]:
    # Find matching state
    st_res = await session.execute(
        select(State).where(func.lower(State.state_name) == state_name.strip().lower())
    )
    st = st_res.scalars().first()
    if not st:
        return []

    dist_res = await session.execute(
        select(District)
        .where(District.state_code == st.state_code)
        .order_by(District.station_count.desc(), District.district_name.asc())
    )
    districts = dist_res.scalars().all()
    return [
        {
            "name": d.district_name,
            "station_count": d.station_count,
            "city_count": d.city_count,
        }
        for d in districts
    ]


async def fetch_state_station_count(session: AsyncSession, state_name: str) -> int:
    st_res = await session.execute(
        select(State).where(func.lower(State.state_name) == state_name.strip().lower())
    )
    st = st_res.scalars().first()
    if st:
        return st.stations_count

    # Fallback to count from unified chargers
    count_res = await session.execute(
        select(func.count(ChargerUnified.charger_id)).where(
            func.lower(ChargerUnified.state_name) == state_name.strip().lower()
        )
    )
    return count_res.scalar_one() or 0


async def query_chargers(
    session: AsyncSession,
    *,
    state: str | None = None,
    district: str | None = None,
    vehicle_class: str | None = None,
    page: int = 1,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int, int]:
    """Query chargers from DB with filtering and pagination."""
    # Total available across all database
    total_avail_res = await session.execute(select(func.count(ChargerUnified.charger_id)))
    total_available = total_avail_res.scalar_one()

    conditions = []
    if state and state.strip():
        conditions.append(func.lower(ChargerUnified.state_name) == state.strip().lower())
    if district and district.strip():
        conditions.append(func.lower(ChargerUnified.district_name) == district.strip().lower())

    base_query = select(ChargerUnified)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    result = await session.execute(base_query)
    all_matching = result.scalars().all()

    # In-memory class filter for JSON fields to ensure 100% dialect independence (SQLite & Postgres)
    filtered = []
    target_class = vehicle_class.strip().upper() if vehicle_class else None
    for row in all_matching:
        if target_class:
            supp = [s.upper() for s in (row.supported_vehicle_classes or [])]
            raw = [r.lower() for r in (row.vehicle_classes or [])]
            match = False
            if target_class in ("2W", "3W"):
                match = (target_class in supp) or ("two_three_wheeler" in raw)
            elif target_class == "4W":
                match = ("4W" in supp) or ("car" in raw)
            elif target_class == "BUS":
                match = ("BUS" in supp) or ("bus" in raw)
            if not match:
                continue
        filtered.append(row)

    total_matching = len(filtered)
    # Pagination
    start = (page - 1) * limit
    page_rows = filtered[start : start + limit]

    data = [
        {
            "id": row.source_id or f"evs_{row.charger_id}",
            "name": row.station_name,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "state": row.state_name,
            "state_code": None,
            "district": row.district_name,
            "city": row.city_name,
            "operator": row.operator,
            "address": row.address,
            "charger_type": row.charger_type,
            "standards": row.standards or [],
            "power_kw": row.power_kw,
            "total_chargers": row.total_chargers,
            "total_connectors": row.total_connectors,
            "vehicle_classes": row.vehicle_classes or [],
            "supported_vehicle_classes": row.supported_vehicle_classes or [],
            "source": row.source_name,
            "snapshot_date": "2025-10-26",
            "is_demo": False,
        }
        for row in page_rows
    ]

    return data, total_matching, total_available

