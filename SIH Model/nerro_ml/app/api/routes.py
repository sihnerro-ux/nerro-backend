"""
NERRO ML — Route Optimization API Endpoints
POST /route/optimize    — find safest route between two towns
GET  /route/network     — full network status for GIS overlay
GET  /route/blocked     — list blocked segments
"""

from fastapi import APIRouter, HTTPException

from app.routing.graph_builder import get_network_status
from app.routing.optimizer import (
    find_alternate_route,
    find_safest_route,
    get_blocked_segments,
)
from app.schemas.api_models import (
    NetworkStatusResponse,
    RouteOptimizeRequest,
    RouteOptimizeResponse,
)

router = APIRouter(prefix="/route", tags=["Route Optimization"])

# Will be injected by main.py
road_graph = None


def set_graph(G):
    global road_graph
    road_graph = G


# ── POST /route/optimize ──────────────────────────────────────────

@router.post("/optimize", response_model=RouteOptimizeResponse)
def optimize_route(req: RouteOptimizeRequest):
    """Find the safest and most efficient route between two towns."""
    if road_graph is None:
        raise HTTPException(503, "Road network not initialized")

    result = find_safest_route(
        road_graph, req.origin, req.destination, req.algorithm,
    )
    if result is None:
        raise HTTPException(
            404,
            f"No route found from '{req.origin}' to '{req.destination}'",
        )

    # Optionally find alternate
    alt = None
    if req.find_alternate:
        alt = find_alternate_route(
            road_graph, req.origin, req.destination, result["path"],
        )

    result["alternate_route"] = alt
    return result


# ── GET /route/network ────────────────────────────────────────────

@router.get("/network", response_model=NetworkStatusResponse)
def network_status():
    """Return full road network with current risk colors for GIS map overlay."""
    if road_graph is None:
        raise HTTPException(503, "Road network not initialized")

    segments = get_network_status(road_graph)
    blocked = [s for s in segments if s["is_blocked"]]
    high_risk = [s for s in segments if s["risk_color"] in ("RED", "BLACK")]

    return {
        "total_segments": len(segments),
        "blocked_count": len(blocked),
        "high_risk_count": len(high_risk),
        "segments": segments,
    }


# ── GET /route/blocked ────────────────────────────────────────────

@router.get("/blocked")
def blocked_segments():
    """List all currently blocked road segments."""
    if road_graph is None:
        raise HTTPException(503, "Road network not initialized")

    blocked = get_blocked_segments(road_graph)
    return {"blocked_count": len(blocked), "segments": blocked}
