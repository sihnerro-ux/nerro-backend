# ============================================================
# NERRO - Risk Fusion Engine (services/risk_engine.py)
# Purpose        : Core AI risk-scoring engine. Combines rainfall, slope,
#                  historical incidents, road condition and weather into a
#                  0-1 risk score + level for a location or road.
# Consumed by    : /api/predictions/predict, /api/roads/{id}/intelligence
# TEAM NOTE      : *** ML INTEGRATION POINT ***
#                  `evaluate()` currently uses a weighted heuristic formula
#                  (RiskFusionEngine.WEIGHTS). Replace the scoring logic here
#                  with your trained model's inference call and map its output
#                  to the existing RiskResult shape so the API/frontend need
#                  no changes.
# ============================================================
import json
from typing import Optional
from datetime import datetime, timezone


class RiskFusionEngine:
    WEIGHTS = {
        "rainfall": 28,
        "slope": 21,
        "historical_incidents": 19,
        "current_incidents": 14,
        "road_condition": 5,
        "wind": 8,
        "visibility": 5,
    }

    def calculate_road_risk(
        self,
        road_data: dict,
        weather: Optional[dict] = None,
        incidents: Optional[list[dict]] = None,
        history: Optional[list[dict]] = None,
    ) -> dict:
        factors: list[dict] = []
        total_weight = sum(self.WEIGHTS.values())

        rainfall_score = self._score_rainfall(weather)
        factors.append({
            "name": "rainfall",
            "weight": self.WEIGHTS["rainfall"],
            "score": rainfall_score,
            "contribution": round(rainfall_score * self.WEIGHTS["rainfall"] / total_weight, 2),
            "detail": self._rainfall_detail(weather),
        })

        slope_score = self._score_slope(road_data)
        factors.append({
            "name": "slope",
            "weight": self.WEIGHTS["slope"],
            "score": slope_score,
            "contribution": round(slope_score * self.WEIGHTS["slope"] / total_weight, 2),
            "detail": self._slope_detail(road_data),
        })

        hist_score = self._score_historical(history)
        factors.append({
            "name": "historical_incidents",
            "weight": self.WEIGHTS["historical_incidents"],
            "score": hist_score,
            "contribution": round(hist_score * self.WEIGHTS["historical_incidents"] / total_weight, 2),
            "detail": self._historical_detail(history),
        })

        curr_score = self._score_current_incidents(incidents)
        factors.append({
            "name": "current_incidents",
            "weight": self.WEIGHTS["current_incidents"],
            "score": curr_score,
            "contribution": round(curr_score * self.WEIGHTS["current_incidents"] / total_weight, 2),
            "detail": self._current_incidents_detail(incidents),
        })

        road_cond_score = self._score_road_condition(road_data)
        factors.append({
            "name": "road_condition",
            "weight": self.WEIGHTS["road_condition"],
            "score": road_cond_score,
            "contribution": round(road_cond_score * self.WEIGHTS["road_condition"] / total_weight, 2),
            "detail": self._road_condition_detail(road_data),
        })

        wind_score = self._score_wind(weather)
        factors.append({
            "name": "wind",
            "weight": self.WEIGHTS["wind"],
            "score": wind_score,
            "contribution": round(wind_score * self.WEIGHTS["wind"] / total_weight, 2),
            "detail": self._wind_detail(weather),
        })

        visibility_score = self._score_visibility(weather)
        factors.append({
            "name": "visibility",
            "weight": self.WEIGHTS["visibility"],
            "score": visibility_score,
            "contribution": round(visibility_score * self.WEIGHTS["visibility"] / total_weight, 2),
            "detail": self._visibility_detail(weather),
        })

        weighted_sum = sum(f["contribution"] for f in factors)
        overall = min(round(weighted_sum, 1), 100)

        if overall >= 80:
            risk_level = "critical"
            recommendation = "AVOID this route. Immediate danger to vehicles."
        elif overall >= 60:
            risk_level = "high"
            recommendation = "Proceed with extreme caution. Consider alternative route."
        elif overall >= 40:
            risk_level = "moderate"
            recommendation = "Elevated risk. Monitor conditions continuously."
        elif overall >= 20:
            risk_level = "low"
            recommendation = "Generally safe. Normal driving precautions."
        else:
            risk_level = "minimal"
            recommendation = "Favorable conditions. Safe to proceed."

        return {
            "overall_risk": overall,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "factors": factors,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": "nerro-risk-v1",
        }

    def calculate_route_risk(self, route_data: dict) -> dict:
        segments = route_data.get("segments", [])
        if not segments:
            return self.calculate_road_risk(route_data)

        segment_risks = []
        for seg in segments:
            seg_risk = self.calculate_road_risk(
                road_data=seg,
                weather=route_data.get("weather"),
                incidents=route_data.get("incidents"),
                history=route_data.get("history"),
            )
            segment_risks.append({
                "segment_id": seg.get("id"),
                "segment_name": seg.get("name", "Unknown"),
                **seg_risk,
            })

        max_risk = max(s["overall_risk"] for s in segment_risks)
        avg_risk = round(
            sum(s["overall_risk"] for s in segment_risks) / len(segment_risks), 1
        )

        critical_segments = [
            s for s in segment_risks if s["risk_level"] in ("critical", "high")
        ]

        if max_risk >= 80:
            route_level = "critical"
        elif max_risk >= 60:
            route_level = "high"
        elif avg_risk >= 35:
            route_level = "moderate"
        else:
            route_level = "low"

        return {
            "overall_risk": max_risk,
            "average_risk": avg_risk,
            "route_risk_level": route_level,
            "total_segments": len(segments),
            "critical_segments_count": len(critical_segments),
            "segment_details": segment_risks,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": "nerro-risk-v1",
        }

    def calculate_overall_risk(self, factors: dict) -> dict:
        total = 0
        count = 0
        breakdown = []

        for name, value in factors.items():
            if value is None:
                continue
            if isinstance(value, (int, float)):
                total += min(max(float(value), 0), 100)
                count += 1
                breakdown.append({"factor": name, "value": float(value)})

        overall = round(total / count, 1) if count > 0 else 0.0

        if overall >= 80:
            level = "critical"
        elif overall >= 60:
            level = "high"
        elif overall >= 40:
            level = "moderate"
        elif overall >= 20:
            level = "low"
        else:
            level = "minimal"

        return {
            "overall_risk": overall,
            "risk_level": level,
            "factor_count": count,
            "breakdown": breakdown,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }

    # -- scoring helpers --

    def _score_rainfall(self, weather: Optional[dict]) -> float:
        if not weather:
            return 0.0
        rain = weather.get("rain_mm", 0) or weather.get("precipitation_mm", 0) or 0
        snow = weather.get("snowfall_cm", 0) or 0
        effective = rain + (snow * 5)
        if effective > 80:
            return 1.0
        if effective > 50:
            return 0.85
        if effective > 30:
            return 0.65
        if effective > 15:
            return 0.45
        if effective > 5:
            return 0.25
        if effective > 0:
            return 0.10
        return 0.0

    def _score_slope(self, road_data: dict) -> float:
        slope = road_data.get("slope_percent") or road_data.get("elevation_change")
        if slope is None:
            road_type = (road_data.get("road_type") or "").lower()
            if "highway" in road_type:
                return 0.15
            if "district" in road_type:
                return 0.40
            return 0.30
        if slope > 15:
            return 1.0
        if slope > 10:
            return 0.75
        if slope > 6:
            return 0.50
        if slope > 3:
            return 0.25
        return 0.10

    def _score_historical(self, history: Optional[list[dict]]) -> float:
        if not history:
            return 0.20
        count = len(history)
        critical_count = sum(
            1 for h in history
            if (h.get("severity") or "").lower() in ("high", "critical")
        )
        score = min(count * 0.10, 0.60) + min(critical_count * 0.15, 0.40)
        return min(score, 1.0)

    def _score_current_incidents(self, incidents: Optional[list[dict]]) -> float:
        if not incidents:
            return 0.0
        active = [i for i in incidents if (i.get("status") or "").lower() != "resolved"]
        if not active:
            return 0.0
        severity_map = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
        max_sev = 0.0
        for inc in active:
            sev = (inc.get("severity") or "medium").lower()
            max_sev = max(max_sev, severity_map.get(sev, 0.5))
        count_bonus = min(len(active) * 0.10, 0.30)
        return min(max_sev + count_bonus, 1.0)

    def _score_road_condition(self, road_data: dict) -> float:
        score = road_data.get("condition_score")
        if score is not None:
            return min(max(float(score), 0), 1.0)
        status = (road_data.get("status") or "").lower()
        status_map = {
            "blocked": 1.0,
            "severe": 0.85,
            "risky": 0.55,
            "accessible": 0.15,
        }
        return status_map.get(status, 0.30)

    def _score_wind(self, weather: Optional[dict]) -> float:
        if not weather:
            return 0.0
        wind = weather.get("wind_speed_kmh", 0) or 0
        gusts = weather.get("wind_gusts_kmh", 0) or 0
        effective = max(wind, gusts)
        if effective > 80:
            return 1.0
        if effective > 60:
            return 0.80
        if effective > 40:
            return 0.50
        if effective > 25:
            return 0.25
        return 0.0

    def _score_visibility(self, weather: Optional[dict]) -> float:
        if not weather:
            return 0.10
        if weather.get("snowfall_cm", 0) or 0 > 5:
            return 0.90
        rain = weather.get("rain_mm", 0) or weather.get("precipitation_mm", 0) or 0
        if rain > 50:
            return 0.70
        if rain > 20:
            return 0.40
        humidity = weather.get("humidity_percent", 0) or 0
        if humidity > 95:
            return 0.30
        return 0.05

    # -- detail helpers --

    def _rainfall_detail(self, weather: Optional[dict]) -> str:
        if not weather:
            return "No weather data available"
        rain = weather.get("rain_mm", 0) or weather.get("precipitation_mm", 0) or 0
        snow = weather.get("snowfall_cm", 0) or 0
        parts = []
        if rain > 0:
            parts.append(f"{rain}mm rain")
        if snow > 0:
            parts.append(f"{snow}cm snow")
        return ", ".join(parts) if parts else "No precipitation"

    def _slope_detail(self, road_data: dict) -> str:
        slope = road_data.get("slope_percent")
        if slope is not None:
            return f"{slope}% gradient"
        road_type = road_data.get("road_type", "unknown")
        return f"Estimated from road type: {road_type}"

    def _historical_detail(self, history: Optional[list[dict]]) -> str:
        if not history:
            return "No historical data"
        types = set()
        for h in history:
            t = h.get("disruption_type") or h.get("type") or "unknown"
            types.add(t)
        return f"{len(history)} past disruptions ({', '.join(types)})"

    def _current_incidents_detail(self, incidents: Optional[list[dict]]) -> str:
        if not incidents:
            return "No active incidents"
        active = [i for i in incidents if (i.get("status") or "").lower() != "resolved"]
        if not active:
            return "No active incidents"
        types = set()
        for i in active:
            t = i.get("incident_type") or "unknown"
            types.add(t)
        return f"{len(active)} active incidents ({', '.join(types)})"

    def _road_condition_detail(self, road_data: dict) -> str:
        score = road_data.get("condition_score")
        status = road_data.get("status", "unknown")
        if score is not None:
            return f"Condition score: {score}, status: {status}"
        return f"Status: {status}"

    def _wind_detail(self, weather: Optional[dict]) -> str:
        if not weather:
            return "No wind data"
        wind = weather.get("wind_speed_kmh", 0) or 0
        gusts = weather.get("wind_gusts_kmh", 0) or 0
        return f"Wind {wind} km/h, gusts {gusts} km/h"

    def _visibility_detail(self, weather: Optional[dict]) -> str:
        if not weather:
            return "No visibility data"
        rain = weather.get("rain_mm", 0) or weather.get("precipitation_mm", 0) or 0
        snow = weather.get("snowfall_cm", 0) or 0
        humidity = weather.get("humidity_percent", 0) or 0
        if snow > 5:
            return "Severely reduced due to snowfall"
        if rain > 50:
            return "Reduced due to heavy rain"
        if humidity > 95:
            return "Possible fog - reduced visibility"
        return "Good visibility"


risk_engine = RiskFusionEngine()
