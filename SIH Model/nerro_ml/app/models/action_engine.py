"""
NERRO ML — Action Intelligence Engine
Maps ML predictions (risk + delay) to actionable recommendations.
"""

from typing import Optional


# ── Action definitions ────────────────────────────────────────────

ACTIONS = {
    "CONTINUE": {
        "code": "CONTINUE",
        "label": "Continue normal operations",
        "icon": "🟢",
    },
    "MONITOR": {
        "code": "MONITOR",
        "label": "Monitor route and notify authorities",
        "icon": "🟡",
    },
    "REROUTE": {
        "code": "REROUTE",
        "label": "Suggest alternate route",
        "icon": "🔴",
    },
    "STOP_REROUTE": {
        "code": "STOP_REROUTE",
        "label": "Stop movement and reroute vehicles",
        "icon": "⛔",
    },
    "EMERGENCY": {
        "code": "EMERGENCY",
        "label": "Prioritize emergency accessibility route",
        "icon": "🚨",
    },
}


def recommend_action(
    risk_score: float,
    risk_level: str,
    predicted_delay_minutes: float = 0,
    active_incidents: int = 0,
) -> dict:
    """Produce a structured action recommendation.

    Logic:
        1. If risk_level is BLOCKED and there are active incidents → EMERGENCY
        2. If risk_level is BLOCKED → STOP_REROUTE
        3. If risk_level is HIGH → REROUTE
        4. If risk_level is MEDIUM or delay > 60 min → MONITOR
        5. Otherwise → CONTINUE
    """
    if risk_level == "BLOCKED" and active_incidents >= 2:
        action = ACTIONS["EMERGENCY"]
    elif risk_level == "BLOCKED":
        action = ACTIONS["STOP_REROUTE"]
    elif risk_level == "HIGH":
        action = ACTIONS["REROUTE"]
    elif risk_level == "MEDIUM" or predicted_delay_minutes > 60:
        action = ACTIONS["MONITOR"]
    else:
        action = ACTIONS["CONTINUE"]

    return {
        "action_code": action["code"],
        "action_label": action["label"],
        "action_icon": action["icon"],
    }


def build_full_prediction(
    route_id: str,
    risk_score: float,
    risk_level: str,
    predicted_delay_minutes: float,
    estimated_travel_minutes: float,
    active_incidents: int = 0,
    alternate_route: Optional[str] = None,
) -> dict:
    """Build the complete prediction response matching the blueprint JSON.

    Example output:
    {
        "route_id": "R101",
        "risk_score": 0.87,
        "risk_level": "HIGH",
        "predicted_delay_minutes": 45,
        "estimated_travel_minutes": 120,
        "recommended_action": "REROUTE",
        "action_label": "Suggest alternate route",
        "alternate_route": "R205"
    }
    """
    action = recommend_action(
        risk_score, risk_level, predicted_delay_minutes, active_incidents,
    )

    return {
        "route_id": route_id,
        "risk_score": round(risk_score, 4),
        "risk_level": risk_level,
        "predicted_delay_minutes": round(predicted_delay_minutes, 1),
        "estimated_travel_minutes": round(estimated_travel_minutes, 1),
        "recommended_action": action["action_code"],
        "action_label": action["action_label"],
        "alternate_route": alternate_route,
    }
