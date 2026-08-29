# ============================================================
# NERRO - Alert Service (services/alert_service.py)
# Purpose        : Creates/queues/delivers alerts (weather, incident, system)
#                  with severity thresholds and broadcasts to WebSocket clients.
# Consumed by    : /api/alerts endpoints + realtime /ws channel
# TEAM NOTE      : Extend push targets here (email/SMS) and mirror messages to
#                  connectWebSocket subscribers on the frontend.
# ============================================================
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.domain import (
    Alert,
    AlertPriority,
    AlertType,
    Vehicle,
    VehicleStatus,
)

HIGH_THRESHOLD = 70
CRITICAL_THRESHOLD = 90


class AlertService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()

    def close(self):
        self.db.close()

    def create_alert(
        self,
        alert_type: AlertType,
        priority: AlertPriority,
        title: str,
        message: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        road_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
    ) -> Alert:
        alert = Alert(
            alert_type=alert_type,
            priority=priority,
            title=title,
            message=message,
            latitude=latitude,
            longitude=longitude,
            road_id=road_id,
            vehicle_id=vehicle_id,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def check_risk_threshold(
        self,
        risk_score: float,
        road_id: Optional[int] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        road_name: str = "Unknown Road",
    ) -> Optional[Alert]:
        if risk_score >= CRITICAL_THRESHOLD:
            alert = self.create_alert(
                alert_type=AlertType.RISK,
                priority=AlertPriority.CRITICAL,
                title=f"CRITICAL Risk on {road_name}",
                message=(
                    f"Risk score {risk_score}/100 on {road_name}. "
                    f"Immediate danger. All vehicles must avoid this route. "
                    f"Emergency protocols activated."
                ),
                latitude=latitude,
                longitude=longitude,
                road_id=road_id,
            )
            return alert

        if risk_score >= HIGH_THRESHOLD:
            alert = self.create_alert(
                alert_type=AlertType.RISK,
                priority=AlertPriority.HIGH,
                title=f"High Risk Alert - {road_name}",
                message=(
                    f"Risk score {risk_score}/100 on {road_name}. "
                    f"Significant danger. Recommend immediate diversion. "
                    f"Monitoring conditions."
                ),
                latitude=latitude,
                longitude=longitude,
                road_id=road_id,
            )
            return alert

        return None

    def notify_vehicle_risk_zone(
        self,
        vehicle_id: int,
        risk_score: float,
        risk_factors: list[str],
    ) -> Optional[Alert]:
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            return None

        if risk_score >= CRITICAL_THRESHOLD:
            priority = AlertPriority.CRITICAL
            action = "STOP IMMEDIATELY and await reroute instructions"
            if vehicle.status != VehicleStatus.EMERGENCY:
                vehicle.status = VehicleStatus.EMERGENCY
        elif risk_score >= HIGH_THRESHOLD:
            priority = AlertPriority.HIGH
            action = "Begin controlled diversion to nearest safe route"
            if vehicle.status == VehicleStatus.EN_ROUTE:
                vehicle.status = VehicleStatus.DIVERTED
        else:
            return None

        factors_text = "; ".join(risk_factors) if risk_factors else "Multiple risk factors detected"
        title = f"Vehicle {vehicle.vehicle_number} entered risk zone"
        message = (
            f"Vehicle {vehicle.vehicle_number} (Driver: {vehicle.driver_name}) "
            f"is in a high-risk zone. Risk score: {risk_score}/100. "
            f"Factors: {factors_text}. "
            f"Required action: {action}"
        )

        alert = self.create_alert(
            alert_type=AlertType.EMERGENCY,
            priority=priority,
            title=title,
            message=message,
            latitude=vehicle.latitude,
            longitude=vehicle.longitude,
            vehicle_id=vehicle_id,
        )
        self.db.commit()
        return alert

    def generate_route_alert(
        self,
        route_name: str,
        origin: str,
        destination: str,
        risk_score: float,
        recommended_action: str,
        alternative_available: bool = True,
        road_id: Optional[int] = None,
    ) -> Optional[Alert]:
        if risk_score < HIGH_THRESHOLD:
            return None

        priority = (
            AlertPriority.CRITICAL if risk_score >= CRITICAL_THRESHOLD
            else AlertPriority.HIGH
        )

        alt_text = (
            "An alternative route is available and recommended."
            if alternative_available
            else "No safe alternative route currently available."
        )

        alert = self.create_alert(
            alert_type=AlertType.ROUTE,
            priority=priority,
            title=f"Route Alert: {route_name} ({origin} → {destination})",
            message=(
                f"Route {route_name} from {origin} to {destination} "
                f"has elevated risk (score: {risk_score}/100). "
                f"Action: {recommended_action}. {alt_text}"
            ),
            road_id=road_id,
        )
        return alert


alert_service = AlertService()
