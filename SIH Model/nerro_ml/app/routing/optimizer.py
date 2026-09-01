"""
NERRO ML — Route Optimizer (Model C)
Risk-aware shortest path using Dijkstra and A* over the NER road graph.
"""

import math
from typing import Optional

import networkx as nx

from app.config import NER_TOWNS


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Haversine great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _heuristic(G: nx.Graph, u: str, v: str) -> float:
    """A* heuristic: straight-line haversine distance between two nodes."""
    u_data = G.nodes[u]
    v_data = G.nodes[v]
    return _haversine_km(
        u_data["lat"], u_data["lon"],
        v_data["lat"], v_data["lon"],
    )


def find_safest_route(
    G: nx.Graph,
    origin: str,
    destination: str,
    algorithm: str = "astar",
) -> Optional[dict]:
    """Find the optimal route between two towns considering risk and delay.

    Uses the pre-computed 'cost' edge attribute which factors in:
        distance + delay + risk + blockage penalty.

    Args:
        G: The NER road network graph with updated edge costs.
        origin: Starting town name.
        destination: Target town name.
        algorithm: "dijkstra" or "astar".

    Returns:
        dict with path details, or None if no path exists.
    """
    if origin not in G or destination not in G:
        return None

    try:
        if algorithm == "astar":
            path = nx.astar_path(
                G, origin, destination,
                heuristic=lambda u, v: _heuristic(G, u, v),
                weight="cost",
            )
        else:
            path = nx.dijkstra_path(G, origin, destination, weight="cost")
    except nx.NetworkXNoPath:
        return None

    # Build segment details
    segments = []
    total_distance = 0.0
    total_delay = 0.0
    total_cost = 0.0
    max_risk = 0.0
    has_blocked = False

    for i in range(len(path) - 1):
        edge = G[path[i]][path[i + 1]]
        seg = {
            "from": path[i],
            "to": path[i + 1],
            "distance_km": edge["distance_km"],
            "risk_score": round(edge.get("risk_score", 0), 4),
            "predicted_delay": round(edge.get("predicted_delay", 0), 1),
            "is_blocked": edge.get("is_blocked", False),
            "cost": round(edge.get("cost", 0), 2),
        }
        segments.append(seg)
        total_distance += edge["distance_km"]
        total_delay += edge.get("predicted_delay", 0)
        total_cost += edge.get("cost", 0)
        max_risk = max(max_risk, edge.get("risk_score", 0))
        if edge.get("is_blocked"):
            has_blocked = True

    # Estimate base travel time (no delays)
    base_minutes = sum(
        G[path[i]][path[i + 1]].get("base_travel_minutes", 0)
        for i in range(len(path) - 1)
    )

    return {
        "origin": origin,
        "destination": destination,
        "algorithm": algorithm,
        "path": path,
        "segments": segments,
        "total_distance_km": round(total_distance, 1),
        "total_delay_minutes": round(total_delay, 1),
        "estimated_travel_minutes": round(base_minutes + total_delay, 1),
        "total_cost": round(total_cost, 2),
        "max_risk_score": round(max_risk, 4),
        "has_blocked_segments": has_blocked,
        "num_stops": len(path),
    }


def find_alternate_route(
    G: nx.Graph,
    origin: str,
    destination: str,
    primary_path: list[str],
) -> Optional[dict]:
    """Find an alternate route that avoids the primary path's edges.

    Creates a copy of the graph, removes edges from the primary path,
    then finds a new shortest path.
    """
    G_alt = G.copy()

    # Remove edges of the primary path
    for i in range(len(primary_path) - 1):
        a, b = primary_path[i], primary_path[i + 1]
        if G_alt.has_edge(a, b):
            G_alt.remove_edge(a, b)

    result = find_safest_route(G_alt, origin, destination, algorithm="dijkstra")
    if result:
        result["is_alternate"] = True
    return result


def get_blocked_segments(G: nx.Graph) -> list[dict]:
    """Return all currently blocked road segments."""
    blocked = []
    for u, v, data in G.edges(data=True):
        if data.get("is_blocked", False):
            blocked.append({
                "from": u,
                "to": v,
                "risk_score": round(data.get("risk_score", 0), 4),
                "predicted_delay": round(data.get("predicted_delay", 0), 1),
            })
    return blocked
