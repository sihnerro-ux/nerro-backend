# ============================================================
# NERRO - Domain Models (models/domain.py)
# Purpose        : SQLAlchemy ORM tables for the whole platform - Road, Incident,
#                  Vehicle, Route, Alert, Prediction, Delivery, District, etc.
# TEAM NOTE      : Mirror any new backend model here, then expose it via a matching
#                  API route + (frontend) lib/types.ts interface.
# ============================================================
import enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    Enum, ForeignKey, func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class RoadType(str, enum.Enum):
    NATIONAL_HIGHWAY = "national_highway"
    STATE_HIGHWAY = "state_highway"
    DISTRICT_ROAD = "district_road"


class RoadStatus(str, enum.Enum):
    ACCESSIBLE = "accessible"
    RISKY = "risky"
    SEVERE = "severe"
    BLOCKED = "blocked"
    NO_DATA = "no_data"


class WaterType(str, enum.Enum):
    RIVER = "river"
    LAKE = "lake"
    POND = "pond"
    STREAM = "stream"


class IncidentType(str, enum.Enum):
    LANDSLIDE = "landslide"
    FLOOD = "flood"
    ROAD_DAMAGE = "road_damage"
    BRIDGE_DAMAGE = "bridge_damage"
    TRAFFIC = "traffic"
    OBSTRUCTION = "obstruction"
    OTHER = "other"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    MONITORING = "monitoring"


class CargoPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class VehicleStatus(str, enum.Enum):
    IDLE = "idle"
    EN_ROUTE = "en_route"
    DELAYED = "delayed"
    DIVERTED = "diverted"
    EMERGENCY = "emergency"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    FAILED = "failed"


class AlertType(str, enum.Enum):
    RISK = "risk"
    ROUTE = "route"
    INCIDENT = "incident"
    DELIVERY = "delivery"
    EMERGENCY = "emergency"


class AlertPriority(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class State(Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    code = Column(String(10), unique=True, nullable=False)
    capital = Column(String(150))
    latitude = Column(Float)
    longitude = Column(Float)

    districts = relationship("District", back_populates="state")
    roads = relationship("Road", back_populates="state")
    water_bodies = relationship("WaterBody", back_populates="state")
    incidents = relationship("Incident", back_populates="state")


# ---------------------------------------------------------------------------
# District
# ---------------------------------------------------------------------------
class District(Base):
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    population = Column(Integer)
    area_sq_km = Column(Float)

    state = relationship("State", back_populates="districts")
    roads = relationship("Road", back_populates="district")
    bridges = relationship("Bridge", back_populates="district")
    incidents = relationship("Incident", back_populates="district")
    weather_data = relationship("WeatherData", back_populates="district")
    hospitals = relationship("Hospital", back_populates="district")
    warehouses = relationship("Warehouse", back_populates="district")
    historical_disruptions = relationship("HistoricalDisruption", back_populates="district")


# ---------------------------------------------------------------------------
# Road
# ---------------------------------------------------------------------------
class Road(Base):
    __tablename__ = "roads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    road_type = Column(Enum(RoadType), nullable=False)
    start_point = Column(String(255))
    end_point = Column(String(255))
    length_km = Column(Float)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"))
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(Enum(RoadStatus), default=RoadStatus.NO_DATA)
    condition_score = Column(Float)
    weather_impact = Column(Float)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    state = relationship("State", back_populates="roads")
    district = relationship("District", back_populates="roads")
    bridges = relationship("Bridge", back_populates="road")
    incidents = relationship("Incident", back_populates="road")
    routes = relationship("Route", back_populates="road")
    risk_scores = relationship("RiskScore", back_populates="road")
    historical_disruptions = relationship("HistoricalDisruption", back_populates="road")


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------
class Bridge(Base):
    __tablename__ = "bridges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    road_id = Column(Integer, ForeignKey("roads.id"))
    district_id = Column(Integer, ForeignKey("districts.id"))
    latitude = Column(Float)
    longitude = Column(Float)
    length_meters = Column(Float)
    load_capacity = Column(Float)
    status = Column(Enum(RoadStatus), default=RoadStatus.NO_DATA)
    last_inspected = Column(DateTime(timezone=True))

    road = relationship("Road", back_populates="bridges")
    district = relationship("District", back_populates="bridges")


# ---------------------------------------------------------------------------
# Water Body
# ---------------------------------------------------------------------------
class WaterBody(Base):
    __tablename__ = "water_bodies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    water_type = Column(Enum(WaterType), nullable=False)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)

    state = relationship("State", back_populates="water_bodies")


# ---------------------------------------------------------------------------
# Incident
# ---------------------------------------------------------------------------
class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_type = Column(Enum(IncidentType), nullable=False)
    severity = Column(Enum(Severity), nullable=False, default=Severity.MEDIUM)
    latitude = Column(Float)
    longitude = Column(Float)
    road_id = Column(Integer, ForeignKey("roads.id"))
    district_id = Column(Integer, ForeignKey("districts.id"))
    state_id = Column(Integer, ForeignKey("states.id"))
    description = Column(Text)
    reported_by = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(IncidentStatus), default=IncidentStatus.ACTIVE)
    reported_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))

    road = relationship("Road", back_populates="incidents")
    district = relationship("District", back_populates="incidents")
    state = relationship("State", back_populates="incidents")
    reporter = relationship("User", foreign_keys=[reported_by])
    field_reports = relationship("FieldReport", back_populates="incident")


# ---------------------------------------------------------------------------
# Weather Data
# ---------------------------------------------------------------------------
class WeatherData(Base):
    __tablename__ = "weather_data"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    temperature = Column(Float)
    humidity = Column(Float)
    rainfall_mm = Column(Float)
    wind_speed = Column(Float)
    wind_direction = Column(String(10))
    weather_condition = Column(String(100))
    forecast_hours = Column(Integer)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    district = relationship("District", back_populates="weather_data")


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------
class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_number = Column(String(50), unique=True, index=True, nullable=False)
    vehicle_type = Column(String(50))
    driver_name = Column(String(255))
    driver_phone = Column(String(20))
    cargo_type = Column(String(100))
    cargo_priority = Column(Enum(CargoPriority), default=CargoPriority.MEDIUM)
    origin = Column(String(255))
    destination = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    speed = Column(Float)
    heading = Column(Float)
    status = Column(Enum(VehicleStatus), default=VehicleStatus.IDLE)
    route_id = Column(Integer, ForeignKey("routes.id"))
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    route = relationship("Route", back_populates="vehicles")
    deliveries = relationship("Delivery", back_populates="vehicle")
    alerts = relationship("Alert", back_populates="vehicle")


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    commodity = Column(String(255))
    priority = Column(Enum(CargoPriority), default=CargoPriority.MEDIUM)
    origin = Column(String(255))
    destination = Column(String(255))
    origin_lat = Column(Float)
    origin_lon = Column(Float)
    dest_lat = Column(Float)
    dest_lon = Column(Float)
    status = Column(Enum(DeliveryStatus), default=DeliveryStatus.PENDING)
    estimated_arrival = Column(DateTime(timezone=True))
    actual_arrival = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="deliveries")


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    origin = Column(String(255))
    destination = Column(String(255))
    origin_lat = Column(Float)
    origin_lon = Column(Float)
    dest_lat = Column(Float)
    dest_lon = Column(Float)
    distance_km = Column(Float)
    estimated_time_hours = Column(Float)
    risk_score = Column(Float)
    status = Column(String(50))
    road_id = Column(Integer, ForeignKey("roads.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    road = relationship("Road", back_populates="routes")
    vehicles = relationship("Vehicle", back_populates="route")
    alternatives = relationship("RouteAlternative", back_populates="route")


# ---------------------------------------------------------------------------
# Route Alternative
# ---------------------------------------------------------------------------
class RouteAlternative(Base):
    __tablename__ = "route_alternatives"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    alternative_name = Column(String(255))
    distance_km = Column(Float)
    estimated_time_hours = Column(Float)
    risk_score = Column(Float)
    recommended = Column(Boolean, default=False)
    reason = Column(Text)

    route = relationship("Route", back_populates="alternatives")


# ---------------------------------------------------------------------------
# Risk Score
# ---------------------------------------------------------------------------
class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    road_id = Column(Integer, ForeignKey("roads.id"), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    overall_risk = Column(Float)
    flood_risk = Column(Float)
    landslide_risk = Column(Float)
    road_disruption_risk = Column(Float)
    travel_delay_risk = Column(Float)
    factors_json = Column(Text)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())

    road = relationship("Road", back_populates="risk_scores")


# ---------------------------------------------------------------------------
# AI Prediction
# ---------------------------------------------------------------------------
class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    prediction_type = Column(String(100), nullable=False)
    risk_score = Column(Float)
    prediction_window = Column(String(50))
    factors_json = Column(Text)
    model_version = Column(String(50))
    predicted_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    priority = Column(Enum(AlertPriority), nullable=False, default=AlertPriority.INFO)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    road_id = Column(Integer, ForeignKey("roads.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    road = relationship("Road")
    vehicle = relationship("Vehicle", back_populates="alerts")


# ---------------------------------------------------------------------------
# Hospital
# ---------------------------------------------------------------------------
class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"))
    latitude = Column(Float)
    longitude = Column(Float)
    bed_count = Column(Integer)
    has_emergency = Column(Boolean, default=False)
    phone = Column(String(20))

    district = relationship("District", back_populates="hospitals")


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------
class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"))
    latitude = Column(Float)
    longitude = Column(Float)
    capacity = Column(Float)
    storage_type = Column(String(100))
    contact_phone = Column(String(20))

    district = relationship("District", back_populates="warehouses")


# ---------------------------------------------------------------------------
# Historical Disruption
# ---------------------------------------------------------------------------
class HistoricalDisruption(Base):
    __tablename__ = "historical_disruptions"

    id = Column(Integer, primary_key=True, index=True)
    road_id = Column(Integer, ForeignKey("roads.id"))
    district_id = Column(Integer, ForeignKey("districts.id"))
    disruption_type = Column(String(100))
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    cause = Column(String(255))
    severity = Column(Enum(Severity), nullable=False)
    notes = Column(Text)

    road = relationship("Road", back_populates="historical_disruptions")
    district = relationship("District", back_populates="historical_disruptions")


# ---------------------------------------------------------------------------
# Field Report
# ---------------------------------------------------------------------------
class FieldReport(Base):
    __tablename__ = "field_reports"

    id = Column(Integer, primary_key=True, index=True)
    officer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    incident_type = Column(Enum(IncidentType))
    severity = Column(Enum(Severity))
    latitude = Column(Float)
    longitude = Column(Float)
    description = Column(Text)
    photo_url = Column(String(500))
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    officer = relationship("User")
    incident = relationship("Incident", back_populates="field_reports")
