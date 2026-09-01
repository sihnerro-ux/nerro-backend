"""
NERRO ML — Road Network Graph Builder
Builds a NetworkX graph of the NER road network.
Nodes are towns, edges are road segments with dynamic ML-informed costs.
"""

import math
from typing import Optional

import networkx as nx

from app.config import NER_TOWNS, ROUTE_COST_WEIGHTS
from app.data.synthetic import NER_ROAD_SEGMENTS, TOWN_ELEVATIONS


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_graph() -> nx.Graph:
    """Create an undirected weighted graph of the NER road network.

    Node attributes:
        lat, lon, elevation_m

    Edge attributes:
        distance_km, road_type, base_travel_minutes,
        risk_score (default 0.1), predicted_delay (default 0),
        cost (computed dynamically)
    """
    G = nx.Graph()

    # ── Add nodes ─────────────────────────────────────────────────
    for name, (lat, lon) in NER_TOWNS.items():
        G.add_node(name, lat=lat, lon=lon,
                   elevation_m=TOWN_ELEVATIONS.get(name, 100))

    # ── Add edges ─────────────────────────────────────────────────
    for town_a, town_b, dist_km, road_type in NER_ROAD_SEGMENTS:
        if town_a not in G or town_b not in G:
            continue

        # Base speed depends on road type
        speed_map = {1: 50, 2: 35, 3: 25}  # km/h
        base_speed = speed_map.get(road_type, 30)
        base_minutes = (dist_km / base_speed) * 60

        G.add_edge(
            town_a, town_b,
            distance_km=dist_km,
            road_type=road_type,
            base_travel_minutes=round(base_minutes, 1),
            risk_score=0.1,          # default low risk
            predicted_delay=0.0,     # default no delay
            is_blocked=False,
            cost=dist_km,            # initial cost = distance
        )

    return G


def update_edge_risk(G: nx.Graph, town_a: str, town_b: str,
                     risk_score: float, predicted_delay: float = 0.0):
    """Update an edge's risk score and recompute its cost."""
    if not G.has_edge(town_a, town_b):
        return

    w = ROUTE_COST_WEIGHTS
    is_blocked = risk_score > 0.80

    edge = G[town_a][town_b]
    edge["risk_score"] = risk_score
    edge["predicted_delay"] = predicted_delay
    edge["is_blocked"] = is_blocked

    if is_blocked:
        edge["cost"] = w["blockage_penalty"]
    else:
        edge["cost"] = (
            w["distance"] * edge["distance_km"]
            + w["delay"] * predicted_delay
            + w["risk"] * risk_score * 100  # scale risk to be comparable
        )


def update_all_edges(G: nx.Graph, risk_data: dict[tuple, dict]):
    """Batch-update edges with ML predictions.

    risk_data: {(town_a, town_b): {"risk_score": ..., "predicted_delay": ...}}
    """
    for (a, b), data in risk_data.items():
        update_edge_risk(
            G, a, b,
            risk_score=data.get("risk_score", 0.1),
            predicted_delay=data.get("predicted_delay", 0.0),
        )


def get_network_status(G: nx.Graph) -> list[dict]:
    """Return the full network status for GIS visualization.

    Each edge → {from, to, distance_km, risk_score, risk_color, ...}
    """
    segments = []
    for u, v, data in G.edges(data=True):
        risk = data.get("risk_score", 0)
        if data.get("is_blocked"):
            color = "BLACK"
        elif risk > 0.55:
            color = "RED"
        elif risk > 0.25:
            color = "YELLOW"
        else:
            color = "GREEN"

        segments.append({
            "from": u,
            "to": v,
            "from_lat": G.nodes[u]["lat"],
            "from_lon": G.nodes[u]["lon"],
            "to_lat": G.nodes[v]["lat"],
            "to_lon": G.nodes[v]["lon"],
            "distance_km": data["distance_km"],
            "road_type": data.get("road_type", 2),
            "risk_score": round(risk, 4),
            "risk_color": color,
            "predicted_delay": round(data.get("predicted_delay", 0), 1),
            "is_blocked": data.get("is_blocked", False),
            "cost": round(data.get("cost", 0), 2),
        })
    return segments
