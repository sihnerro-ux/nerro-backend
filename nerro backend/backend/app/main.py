# ============================================================
# NERRO - FastAPI Application Entry (app/main.py)
# Purpose        : Creates the FastAPI app, registers ALL routers, CORS,
#                  health check and the realtime WebSocket (ws://host/ws).
#             Run with:  uvicorn app.main:app --reload
#                      (Swagger UI at /docs)
# TEAM NOTE      : To add a new API module:
#                  1) create app/routes/myfeature.py (prefix="/api/...")
#                  2) import the router here
#                  3) app.include_router(my_router)
#                  WebSocket broadcast() helper is reused by services to push
#                  real-time updates to the frontend.
# ============================================================
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import Base, engine
from app.routes.auth import router as auth_router
from app.routes.roads import router as roads_router
from app.routes.incidents import router as incidents_router
from app.routes.vehicles import router as vehicles_router
from app.routes.routes_engine import router as routes_router
from app.routes.predictions import router as predictions_router
from app.routes.alerts import router as alerts_router
from app.routes.emergency import router as emergency_router
from app.routes.analytics import router as analytics_router
from app.routes.weather import router as weather_router
from app.routes.states import router as states_router

settings = get_settings()

connected_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
    for ws in connected_clients:
        await ws.close(code=1000)


app = FastAPI(
    title="NERRO API",
    version="1.0.0",
    description="North East Route Risk Optimisation - Logistics Intelligence Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(roads_router)
app.include_router(incidents_router)
app.include_router(vehicles_router)
app.include_router(routes_router)
app.include_router(predictions_router)
app.include_router(alerts_router)
app.include_router(emergency_router)
app.include_router(analytics_router)
app.include_router(weather_router)
app.include_router(states_router)


@app.get("/", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "NERRO API",
        "version": "1.0.0",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            msg_type = payload.get("type", "ping")

            if msg_type == "subscribe":
                await websocket.send_json({
                    "type": "subscribed",
                    "channels": payload.get("channels", []),
                })
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({
                    "type": "ack",
                    "received": msg_type,
                })
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


async def broadcast(message: dict):
    dead: list[WebSocket] = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)
