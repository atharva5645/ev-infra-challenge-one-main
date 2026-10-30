from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import JSON
from app.db.session import Base


class State(Base):
    __tablename__ = "states"

    state_code = Column(String(16), primary_key=True)
    state_name = Column(String(100), nullable=False, unique=True)
    stations_count = Column(Integer, default=0)
    chargers_count = Column(Integer, default=0)
    dc_stations_count = Column(Integer, default=0)


class District(Base):
    __tablename__ = "districts"

    district_code = Column(String(32), primary_key=True)
    state_code = Column(String(16), ForeignKey("states.state_code"), nullable=False)
    district_name = Column(String(120), nullable=False)
    station_count = Column(Integer, default=0)
    city_count = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("state_code", "district_name", name="uq_state_district"),)


class ChargerSourceRecord(Base):
    __tablename__ = "charger_source_records"

    source_record_id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(120), nullable=False)
    source_record_key = Column(String(160), nullable=False)
    station_name = Column(String(200), nullable=False)
    district_code = Column(String(32), ForeignKey("districts.district_code"), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    charger_type = Column(String(40), nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    raw_attributes = Column(JSON, default=dict)

    __table_args__ = (UniqueConstraint("source_name", "source_record_key", name="uq_source_key"),)


class ChargerUnified(Base):
    __tablename__ = "chargers_unified"

    charger_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(64), unique=True, nullable=True)  # e.g. evs_xxxx
    station_name = Column(String(200), nullable=False)
    district_code = Column(String(32), ForeignKey("districts.district_code"), nullable=True)
    state_name = Column(String(100), nullable=True)
    district_name = Column(String(120), nullable=True)
    city_name = Column(String(120), nullable=True)
    operator = Column(String(120), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    charger_type = Column(String(40), nullable=False)
    standards = Column(JSON, default=list)
    power_kw = Column(Float, nullable=True)
    total_chargers = Column(Integer, default=1)
    total_connectors = Column(Integer, default=1)
    vehicle_classes = Column(JSON, default=list)
    supported_vehicle_classes = Column(JSON, default=list)
    source_name = Column(String(120), nullable=False)
    source_record_id = Column(Integer, ForeignKey("charger_source_records.source_record_id"), nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.90)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EvRegistration(Base):
    __tablename__ = "ev_registrations"

    registration_id = Column(Integer, primary_key=True, autoincrement=True)
    state_code = Column(String(16), ForeignKey("states.state_code"), nullable=True)
    district_code = Column(String(32), ForeignKey("districts.district_code"), nullable=False)
    vehicle_class = Column(String(60), nullable=False)  # 'Two-wheeler', 'Three-wheeler', 'Four-wheeler', 'Bus'
    reporting_period = Column(Date, nullable=False)
    ev_count = Column(Integer, nullable=False)
    source_name = Column(String(120), nullable=False)

    __table_args__ = (UniqueConstraint("district_code", "vehicle_class", "reporting_period", name="uq_district_class_period"),)


class HexMetric(Base):
    __tablename__ = "hex_metrics"

    hex_metric_id = Column(Integer, primary_key=True, autoincrement=True)
    cell_id = Column(String(32), nullable=False)
    resolution = Column(Integer, default=7)
    state_name = Column(String(100), nullable=True)
    district_name = Column(String(120), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    reporting_period = Column(Date, nullable=False)
    ev_demand = Column(Integer, nullable=False, default=0)
    charger_count = Column(Integer, nullable=False, default=0)
    distance_to_nearest_charger_km = Column(Float, nullable=True)
    coverage = Column(Float, nullable=False, default=0.0)
    gap_score = Column(Float, nullable=False, default=0.0)

    __table_args__ = (UniqueConstraint("cell_id", "reporting_period", name="uq_cell_period"),)


class CandidateSite(Base):
    __tablename__ = "candidate_sites"

    candidate_site_id = Column(Integer, primary_key=True, autoincrement=True)
    site_name = Column(String(200), nullable=False)
    state_name = Column(String(100), nullable=True)
    district_code = Column(String(32), ForeignKey("districts.district_code"), nullable=True)
    district_name = Column(String(120), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    estimated_cost_inr = Column(Numeric(14, 2), nullable=False)
    suitability_score = Column(Float, nullable=False)
    origin_type = Column(String(60), default="planner")  # 'trip_dead_zone', 'spatial_hex_gap', 'planner'
    notes = Column(Text, nullable=True)


class Assumption(Base):
    __tablename__ = "assumptions"

    assumption_id = Column(Integer, primary_key=True, autoincrement=True)
    parameter_name = Column(String(120), nullable=False, unique=True)
    parameter_value = Column(Float, nullable=False)
    units = Column(String(60), nullable=False)
    description = Column(Text, nullable=False)
    source = Column(String(240), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OptimizerRun(Base):
    __tablename__ = "optimizer_runs"

    optimizer_run_id = Column(Integer, primary_key=True, autoincrement=True)
    run_name = Column(String(160), nullable=False)
    budget_inr = Column(Numeric(16, 2), nullable=False)
    objective = Column(String(240), nullable=False)
    recommended_sites = Column(JSON, default=list)
    estimated_new_chargers = Column(Integer, nullable=False)
    estimated_coverage_gain = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
