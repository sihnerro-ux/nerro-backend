# ============================================================
# NERRO - Weather Service (services/weather_service.py)
# Purpose        : Fetches real weather data (Open-Meteo API), forecast and
#                  logistics impact for NE states.
# Consumed by    : /api/weather/*
# TEAM NOTE      : *** REAL-TIME DATA INTEGRATION POINT ***
#                  Already wired to the free Open-Meteo API. If you use another
#                  provider (IMD, VisualCrossing, etc.), replace OPEN_METEO_BASE
#                  and the request/parse logic but keep the return shapes.
# ============================================================
from typing import Optional

import httpx

OPEN_METEO_BASE = "https://api.open-meteo.com/v1"


class WeatherService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        await self.client.aclose()

    async def get_current_weather(self, lat: float, lon: float) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "weather_code",
                "cloud_cover",
                "surface_pressure",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
            ]),
            "timezone": "Asia/Kolkata",
        }
        try:
            resp = await self.client.get(f"{OPEN_METEO_BASE}/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})

            wind_speed = current.get("wind_speed_10m", 0) or 0
            precipitation = current.get("precipitation", 0) or 0
            snowfall = current.get("snowfall", 0) or 0

            return {
                "latitude": lat,
                "longitude": lon,
                "temperature_c": current.get("temperature_2m"),
                "feels_like_c": current.get("apparent_temperature"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "precipitation_mm": precipitation,
                "rain_mm": current.get("rain", 0),
                "snowfall_cm": snowfall,
                "wind_speed_kmh": wind_speed,
                "wind_direction_deg": current.get("wind_direction_10m"),
                "wind_gusts_kmh": current.get("wind_gusts_10m"),
                "cloud_cover_percent": current.get("cloud_cover"),
                "surface_pressure_hpa": current.get("surface_pressure"),
                "weather_code": current.get("weather_code"),
                "condition": self._decode_weather_code(current.get("weather_code")),
                "source": "open-meteo",
            }
        except Exception as e:
            return {
                "latitude": lat,
                "longitude": lon,
                "error": str(e),
                "source": "open-meteo",
            }

    async def get_forecast(self, lat: float, lon: float, days: int = 7) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "weather_code",
            ]),
            "timezone": "Asia/Kolkata",
            "forecast_days": min(days, 16),
        }
        try:
            resp = await self.client.get(f"{OPEN_METEO_BASE}/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            time_dates = daily.get("time", [])

            forecast_days = []
            for i, date in enumerate(time_dates):
                forecast_days.append({
                    "date": date,
                    "temp_max_c": daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                    "temp_min_c": daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                    "precipitation_mm": daily.get("precipitation_sum", [])[i] if i < len(daily.get("precipitation_sum", [])) else None,
                    "precipitation_probability": daily.get("precipitation_probability_max", [])[i] if i < len(daily.get("precipitation_probability_max", [])) else None,
                    "wind_speed_kmh": daily.get("wind_speed_10m_max", [])[i] if i < len(daily.get("wind_speed_10m_max", [])) else None,
                    "wind_gusts_kmh": daily.get("wind_gusts_10m_max", [])[i] if i < len(daily.get("wind_gusts_10m_max", [])) else None,
                    "weather_code": daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else None,
                    "condition": self._decode_weather_code(
                        daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else None
                    ),
                })

            return {
                "latitude": lat,
                "longitude": lon,
                "days": len(forecast_days),
                "forecast": forecast_days,
                "source": "open-meteo",
            }
        except Exception as e:
            return {
                "latitude": lat,
                "longitude": lon,
                "error": str(e),
                "source": "open-meteo",
            }

    async def get_logistics_impact(self, lat: float, lon: float) -> dict:
        weather = await self.get_current_weather(lat, lon)
        if "error" in weather:
            return {
                "latitude": lat,
                "longitude": lon,
                "impact_level": "unknown",
                "factors": [],
                "recommendations": ["Unable to fetch weather data. Exercise normal caution."],
                "source": "open-meteo",
            }

        factors: list[dict] = []
        recommendations: list[str] = []
        risk_score = 0

        rain = weather.get("rain_mm", 0) or 0
        snow = weather.get("snowfall_cm", 0) or 0
        wind = weather.get("wind_speed_kmh", 0) or 0
        gusts = weather.get("wind_gusts_kmh", 0) or 0
        humidity = weather.get("humidity_percent", 0) or 0

        if rain > 50:
            factors.append({"factor": "heavy_rainfall", "severity": "critical", "value_mm": rain})
            risk_score += 35
            recommendations.append("Avoid low-lying roads. High flooding risk.")
        elif rain > 20:
            factors.append({"factor": "moderate_rainfall", "severity": "high", "value_mm": rain})
            risk_score += 20
            recommendations.append("Reduce speed. Watch for waterlogging on urban roads.")
        elif rain > 5:
            factors.append({"factor": "light_rainfall", "severity": "moderate", "value_mm": rain})
            risk_score += 8
            recommendations.append("Wet roads - maintain safe following distance.")

        if snow > 10:
            factors.append({"factor": "heavy_snowfall", "severity": "critical", "value_cm": snow})
            risk_score += 40
            recommendations.append("CRITICAL: Heavy snow. Avoid mountain passes. Carry chains.")
        elif snow > 2:
            factors.append({"factor": "snowfall", "severity": "high", "value_cm": snow})
            risk_score += 25
            recommendations.append("Snow on road. Use tire chains. Reduce speed significantly.")

        if wind > 60 or gusts > 80:
            factors.append({"factor": "extreme_wind", "severity": "critical", "wind_kmh": wind, "gusts_kmh": gusts})
            risk_score += 30
            recommendations.append("DANGER: Extreme winds. High-profile vehicles should halt.")
        elif wind > 40:
            factors.append({"factor": "strong_wind", "severity": "high", "wind_kmh": wind})
            risk_score += 15
            recommendations.append("Strong crosswinds on exposed stretches. Drive cautiously.")

        if humidity > 95 and rain == 0:
            factors.append({"factor": "fog_risk", "severity": "moderate", "humidity": humidity})
            risk_score += 10
            recommendations.append("High humidity with no rain - fog possible. Use fog lights.")

        impact_level = "low"
        if risk_score >= 60:
            impact_level = "severe"
        elif risk_score >= 35:
            impact_level = "high"
        elif risk_score >= 15:
            impact_level = "moderate"

        if not recommendations:
            recommendations.append("Weather conditions are favorable. Normal operations can proceed.")

        return {
            "latitude": lat,
            "longitude": lon,
            "impact_level": impact_level,
            "risk_score": min(risk_score, 100),
            "weather_summary": {
                "temperature_c": weather.get("temperature_c"),
                "condition": weather.get("condition"),
                "precipitation_mm": rain,
                "wind_speed_kmh": wind,
            },
            "factors": factors,
            "recommendations": recommendations,
            "source": "open-meteo",
        }

    @staticmethod
    def _decode_weather_code(code: Optional[int]) -> str:
        if code is None:
            return "Unknown"
        mapping = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Freezing drizzle",
            57: "Heavy freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snowfall",
            73: "Moderate snowfall",
            75: "Heavy snowfall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return mapping.get(code, f"Code {code}")


weather_service = WeatherService()
