"""
NERRO ML Intelligence Engine — FastAPI Application
Main entry point that wires up models, graph, and API routes.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health as health_api
from app.api import predict as predict_api
from app.api import routes as routes_api
from app.models.risk_classifier import RiskClassifier
from app.models.delay_regressor import DelayRegressor
from app.routing.graph_builder import build_graph


# ── Lifespan: load models & graph once at startup ─────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load trained models and build road network graph."""
    print("🚀 NERRO ML Engine starting up…")

    # Load models (they auto-load from disk if .pkl exists)
    risk_model = RiskClassifier()
    delay_model = DelayRegressor()

    if risk_model.model is None:
        print("⚠️  Risk model not found. Run `python -m scripts.train` first.")
    if delay_model.model is None:
        print("⚠️  Delay model not found. Run `python -m scripts.train` first.")

    # Build road network graph
    graph = build_graph()
    print(f"🗺️  Road graph built: {graph.number_of_nodes()} towns, "
          f"{graph.number_of_edges()} segments")

    # Inject into API modules
    predict_api.set_models(risk_model, delay_model)
    routes_api.set_graph(graph)
    health_api.set_dependencies(risk_model, delay_model, graph)

    print("✅ NERRO ML Engine ready!")
    yield
    print("🛑 NERRO ML Engine shutting down.")


# ── FastAPI app ───────────────────────────────────────────────────

app = FastAPI(
    title="NERRO ML Intelligence Engine",
    description=(
        "AI/ML engine for North-East Region road logistics: "
        "predicts route disruptions, estimates travel delays, "
        "recommends actions, and finds optimal safe routes."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow GIS dashboard to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────
app.include_router(predict_api.router)
app.include_router(routes_api.router)
app.include_router(health_api.router)


@app.get("/", tags=["Root"])
def root():
    return {
        "service": "NERRO ML Intelligence Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "predict_risk": "POST /predict/risk",
            "predict_delay": "POST /predict/delay",
            "predict_batch": "POST /predict/batch",
            "predict_town": "GET /predict/town/{town_name}",
            "optimize_route": "POST /route/optimize",
            "network_status": "GET /route/network",
            "blocked_segments": "GET /route/blocked",
            "health": "GET /health",
            "model_health": "GET /health/models",
        },
    }
